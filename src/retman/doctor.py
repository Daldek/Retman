"""``retman doctor check``: what works, what does not, how to fix it.

See ARCHITECTURE 7.2.
"""

import importlib.metadata
import json
import os
import tomllib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import httpx

from retman import __version__
from retman.backends import build_decision_backend
from retman.backends.base import DecisionBackend
from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.catalog.envelope import Item, Notice, status_of
from retman.config import Config, Settings, load_config, load_settings
from retman.environment import OptionValue, environment
from retman.exceptions import (
    BackendConnectionError,
    BackendError,
    ConfigError,
    ErrorCode,
    ManifestError,
    TranslationError,
)
from retman.i18n.loader import Texts, load_core_texts, load_texts
from retman.outcomes import EXIT_FAILED, EXIT_OK, EXIT_PARTIAL
from retman.registry.loader import discover_manifests, version_matches
from retman.registry.manifest import ManifestSpec, validate_manifest
from retman.stores import (
    IMGW_MARKER,
    IMGW_REFERENCE_FILE,
    ToolOutcome,
    hardlink_error,
    imgw_store_state,
    nearest_existing,
    probe_imgw_write,
    symlink_component,
)

if TYPE_CHECKING:
    from retman.devtools.light import LightCheck
Status = Literal["ok", "warning", "error", "off"]

# The fallback language only renders the report when the config cannot be read
REPORT_LANGUAGE = "pl"


@dataclass(frozen=True)
class Check:
    """One line of the report; ``blocking`` problems make the outcome partial or failed.

    A blocking check names the registry ``code`` of its failure and, where the code
    is coarser than the cause, the ``reason`` (ERR-1): it is a failed unit of the
    result (AGI-4.2).
    """

    status: Status
    text: str
    hint: str | None = None
    blocking: bool = False
    code: ErrorCode | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Require the registry code of a blocking check."""
        if self.blocking and self.code is None:
            raise ValueError("A blocking check names the registry code of its failure")


@dataclass
class Section:
    """A titled group of checks (configuration, model, tools, ...)."""

    key: str
    title: str
    checks: list[Check] = field(default_factory=list)


@dataclass
class DoctorReport:
    """Result of all checks: ``sections`` of checks, the units of ``items()``."""

    version: str
    sections: list[Section]

    def _numbered(self) -> Iterable[tuple[str, Check]]:
        for section in self.sections:
            for number, check in enumerate(section.checks, 1):
                yield f"{section.key}.{number}", check

    def items(self) -> list[Item]:
        """Return the units of the result: each passed check and each blocking one.

        A passed check (status ``ok``) is an ``ok`` unit, a blocking one a ``failed``
        unit with its registry code; warnings and problems that do not block work are
        :meth:`notices`.
        """
        items: list[Item] = []
        for ident, check in self._numbered():
            if check.blocking:
                items.append(
                    Item(ident, "failed", check.code, check.reason, check.text)
                )
            elif check.status == "ok":
                items.append(Item(ident, "ok", message=check.text))
        return items

    def notices(self) -> list[Notice]:
        """Return the warnings and the non-blocking problems as notices."""
        return [
            Notice(
                "warning",
                f"check_{check.status}",
                f"{check.text} {check.hint}" if check.hint else check.text,
            )
            for _, check in self._numbered()
            if check.status in ("warning", "error") and not check.blocking
        ]

    @property
    def exit_code(self) -> int:
        """``0`` when nothing blocks work, else ``10`` (``partial``).

        ``11`` (``failed``) when no check passed at all.
        """
        return {"ok": EXIT_OK, "partial": EXIT_PARTIAL, "failed": EXIT_FAILED}[
            status_of(self.items())
        ]

    def to_text(self, texts: Texts) -> str:
        """Terminal report as in ARCHITECTURE 7.2."""
        lines = [texts.get("doctor.title", version=self.version)]
        for section in self.sections:
            lines.extend(["", section.title])
            for check in section.checks:
                line = texts.get(
                    "doctor.line",
                    marker=texts.get(f"doctor.marker_{check.status}"),
                    text=check.text,
                )
                if check.hint:
                    line = texts.get("doctor.with_hint", line=line, hint=check.hint)
                lines.append(line)
        return "\n".join(lines) + "\n"

    def document(self) -> dict[str, Any]:
        """Return the document ``retman-doctor/1`` (without its ``schema``)."""
        ids = {id(check): ident for ident, check in self._numbered()}
        return {
            "sections": [
                {
                    "key": section.key,
                    "title": section.title,
                    "checks": [
                        {
                            "id": ids[id(check)],
                            "status": check.status,
                            "text": check.text,
                            "hint": check.hint,
                            "blocking": check.blocking,
                            **({"code": check.code} if check.code else {}),
                            **({"reason": check.reason} if check.reason else {}),
                        }
                        for check in section.checks
                    ],
                }
                for section in self.sections
            ]
        }


def _plural(texts: Texts, key: str, count: int) -> str:
    """Polish plural forms: 1 wynik, 2 wyniki, 5 wyników."""
    if count == 1:
        form = "one"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        form = "few"
    else:
        form = "many"
    return texts.get(f"doctor.{key}_{form}", count=count)


def _config_problems(texts: Texts, error: ConfigError) -> list[Check]:
    checks: list[Check] = []
    for problem in error.problems:
        code, reason = ConfigError.classify(problem)
        checks.append(
            Check(
                "error",
                texts.get(
                    f"config.{problem}",
                    path=error.path,
                    keys=error.problem_details.get(problem, ""),
                    error=error.problem_details.get("error", ""),
                    backend=error.problem_details.get("backend", ""),
                ),
                blocking=True,
                code=code,
                reason=reason,
            )
        )
    return checks


def _project_checks(config: Settings, project_dir: Path, texts: Texts) -> list[Check]:
    project = project_dir.resolve()
    root = project / config.results_dir
    checks: list[Check] = []
    folders = (
        sorted(
            folder
            for folder in root.iterdir()
            if folder.is_dir() and folder.name.split("_", 1)[0].isdigit()
        )
        if root.is_dir()
        else []
    )
    # Results are created later, so writability is checked on the nearest
    # existing folder without creating anything in the project
    writable = os.access(nearest_existing(root), os.W_OK)
    checks.append(
        Check(
            "ok" if writable else "error",
            texts.get(
                "doctor.project",
                project=project,
                results_dir=config.results_dir,
                results=_plural(texts, "results", len(folders)),
                writable=texts.get(
                    "doctor.writable" if writable else "doctor.not_writable"
                ),
            ),
            None if writable else texts.get("doctor.hint_not_writable"),
            blocking=not writable,
            code=None if writable else "io_error",
            reason=None if writable else "project_not_writable",
        )
    )
    unreadable = []
    for folder in folders:
        try:
            with (folder / "result.json").open(encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, ValueError):
            unreadable.append(folder.name)
    if unreadable:
        checks.append(
            Check(
                "warning",
                texts.get("doctor.unreadable_results", folders=", ".join(unreadable)),
                texts.get("doctor.hint_unreadable_results"),
            )
        )
    return checks


def _models_on_server(
    config: Config, client: httpx.Client
) -> tuple[list[str] | None, int | None]:
    """Model ids from ``GET /models``; ``(None, status)`` if the list is unavailable."""
    headers: dict[str, str] = {}
    if config.decision.api_key_env:
        api_key = os.environ.get(config.decision.api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    response = client.get(
        f"{config.decision.url.rstrip('/')}/models",
        headers=headers,
        timeout=config.decision.timeout_s,
    )
    if response.status_code != 200:
        return None, response.status_code
    try:
        return [str(item["id"]) for item in response.json()["data"]], None
    except (ValueError, KeyError, TypeError):
        return None, response.status_code


def _decision_checks(
    config: Config,
    texts: Texts,
    backend: DecisionBackend | None,
    client: httpx.Client,
) -> list[Check]:
    decision = config.decision
    address = Check(
        "ok",
        texts.get("doctor.address", backend=decision.backend, url=decision.url),
    )
    if backend is None:
        try:
            backend = (
                OpenAICompatibleBackend(decision, texts, client)
                if decision.backend == "openai_compatible"
                else build_decision_backend(config, texts)
            )
        except ConfigError as err:
            return [address, *_config_problems(texts, err)]
    checks = [address]
    try:
        models, status = _models_on_server(config, client)
    except httpx.RequestError:
        return [
            Check(
                "error",
                texts.get("doctor.no_response", url=decision.url),
                texts.get("doctor.hint_no_response", path=config.path),
                blocking=True,
                code="source_unavailable",
                reason="backend_connection",
            )
        ]
    if models is None:
        checks.append(
            Check("warning", texts.get("doctor.no_model_list", status=status or ""))
        )
    elif decision.model in models:
        checks.append(
            Check("ok", texts.get("doctor.model_listed", model=decision.model))
        )
    else:
        checks.append(
            Check(
                "warning",
                texts.get(
                    "doctor.model_not_listed",
                    model=decision.model,
                    models=", ".join(models) or texts.get("doctor.none"),
                ),
                texts.get("doctor.hint_model", path=config.path),
            )
        )
    options = {
        "terrain": texts.get("doctor.test_terrain"),
        "weather": texts.get("doctor.test_weather"),
    }
    try:
        answer = backend.choose(
            texts.get("doctor.test_command"), texts.get("doctor.test_question"), options
        )
    except BackendConnectionError:
        checks.append(
            Check(
                "error",
                texts.get("doctor.no_response", url=decision.url),
                texts.get("doctor.hint_no_response", path=config.path),
                blocking=True,
                code="source_unavailable",
                reason="backend_connection",
            )
        )
        return checks
    except BackendError as err:
        checks.append(
            Check(
                "error",
                texts.get("doctor.test_failed", error=err),
                texts.get("doctor.hint_model", path=config.path),
                blocking=True,
                code="source_unavailable",
                reason="backend_error",
            )
        )
        return checks
    details = (
        texts.get(
            "doctor.confidence_value",
            value=f"{answer.confidence:.2f}".replace(".", ","),
            method=texts.get(f"doctor.method_{answer.confidence_method}"),
        )
        if answer.confidence is not None
        else texts.get("doctor.confidence_missing")
    )
    if answer.key == "terrain":
        checks.append(Check("ok", texts.get("doctor.test_ok", details=details)))
    else:
        checks.append(
            Check(
                "warning",
                texts.get("doctor.test_wrong", details=details),
                texts.get("doctor.hint_test_wrong"),
            )
        )
    thresholds = decision.thresholds
    if decision.confidence == "none":
        checks.append(
            Check(
                "warning",
                texts.get("doctor.confidence_none"),
                texts.get("doctor.hint_confidence_none", path=config.path),
            )
        )
    elif "auto" in (thresholds.operation, thresholds.parameter):
        checks.append(Check("warning", texts.get("doctor.thresholds_auto")))
    else:
        checks.append(
            Check(
                "ok",
                texts.get(
                    "doctor.thresholds",
                    operation=thresholds.operation,
                    parameter=thresholds.parameter,
                ),
            )
        )
    return checks


def _tool_checks(
    config: Settings | None,
    texts: Texts,
    manifests: list[tuple[ManifestSpec, Path]],
    version_lookup: Callable[[str], str],
) -> tuple[list[Check], dict[str, tuple[ManifestSpec, str]]]:
    """Per-tool lines and the tools in use: their manifest and installed version."""
    checks: list[Check] = []
    active: dict[str, tuple[ManifestSpec, str]] = {}
    available = 0
    for manifest, _ in manifests:
        tool = manifest["tool"]
        supported = manifest["supported_versions"]
        try:
            version = version_lookup(manifest["distribution"])
        except importlib.metadata.PackageNotFoundError:
            checks.append(
                Check(
                    "error",
                    texts.get("doctor.tool_missing", tool=tool),
                    texts.get("doctor.hint_tool_missing", source=manifest["source"]),
                )
            )
            continue
        if not version_matches(version, supported):
            checks.append(
                Check(
                    "warning",
                    texts.get(
                        "doctor.tool_unsupported",
                        tool=tool,
                        version=version,
                        supported=supported,
                    ),
                    texts.get(
                        "doctor.hint_tool_unsupported",
                        supported=supported,
                        source=manifest["source"],
                    ),
                )
            )
            continue
        if config is not None and (
            config.enabled_tools is not None and tool not in config.enabled_tools
        ):
            checks.append(
                Check(
                    "off",
                    texts.get(
                        "doctor.tool_disabled",
                        tool=tool,
                        version=version,
                        path=config.path,
                    ),
                )
            )
            continue
        count = len(manifest["operations"])
        available += count
        active[tool] = (manifest, version)
        checks.append(
            Check(
                "ok",
                texts.get(
                    "doctor.tool_ok",
                    tool=tool,
                    version=version,
                    supported=supported,
                    operations=_plural(texts, "operations", count),
                ),
            )
        )
    if not available:
        checks.append(
            Check(
                "error",
                texts.get("doctor.no_operations"),
                texts.get("doctor.hint_no_operations"),
                blocking=True,
                code="missing_dependency",
                reason="no_operations",
            )
        )
    return checks, active


def _store_folder(
    tool: str, store: Path, texts: Texts, config_path: Path, *, symlinks_refused: bool
) -> tuple[list[Check], Literal["ok", "missing", "broken"]]:
    """Check a store folder: no symbolic links, it exists or can be created, writable.

    Returns the problems found and the state of the folder: ``missing`` is a folder
    that does not exist yet but can be created, ``broken`` one that cannot be used.
    """
    checks: list[Check] = []
    link = symlink_component(store)
    if link is not None:
        resolved = store.resolve()
        key = "symlink_refused" if symlinks_refused else "symlink"
        checks.append(
            Check(
                "error" if symlinks_refused else "warning",
                texts.get(f"doctor.stores.{key}", tool=tool, link=link),
                texts.get(
                    "doctor.stores.hint_symlink",
                    tool=tool,
                    resolved=resolved,
                    config=config_path,
                ),
                blocking=symlinks_refused,
                code="store_unavailable" if symlinks_refused else None,
                reason="symlink_refused" if symlinks_refused else None,
            )
        )
    hint = texts.get("doctor.stores.hint_store_dir", tool=tool, config=config_path)
    if not store.exists():
        parent = nearest_existing(store)
        if parent.is_dir() and os.access(parent, os.W_OK | os.X_OK):
            return checks, "missing"
        text = texts.get("doctor.stores.cannot_create", tool=tool, path=store)
        checks.append(
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason="cannot_create",
            )
        )
        return checks, "broken"
    if not store.is_dir():
        text = texts.get("doctor.stores.not_a_directory", tool=tool, path=store)
        checks.append(
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason="not_a_directory",
            )
        )
        return checks, "broken"
    if not os.access(store, os.W_OK | os.X_OK):
        text = texts.get("doctor.stores.not_writable", tool=tool, path=store)
        checks.append(
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason="not_writable",
            )
        )
        return checks, "broken"
    return checks, "ok"


def _cache_checks(cache_file: Path, texts: Texts, config_path: Path) -> list[Check]:
    """Kartograf works without its metadata cache, only slower: warnings only."""
    folder = cache_file.parent
    if cache_file.is_dir():
        problem = texts.get("doctor.stores.cache_is_folder", path=cache_file)
    elif not folder.is_dir():
        problem = texts.get("doctor.stores.cache_dir_missing", path=folder)
    elif not os.access(folder, os.W_OK | os.X_OK) or (
        cache_file.exists() and not os.access(cache_file, os.W_OK)
    ):
        problem = texts.get("doctor.stores.cache_not_writable", path=cache_file)
    else:
        return [Check("ok", texts.get("doctor.stores.cache_ok", path=cache_file))]
    hint = texts.get("doctor.stores.hint_cache", folder=folder, config=config_path)
    return [Check("warning", problem, hint)]


def _hardlink_checks(
    tool: str, folder: Path, texts: Texts, config_path: Path
) -> list[Check]:
    """Check that the store folder takes hard links.

    Both tool stores publish every version with hard links; FAT/exFAT and some
    network shares have none. Tried in the store, or in the closest existing folder
    when the store is not created yet (the same file system).
    """
    try:
        failure = hardlink_error(folder)
    except OSError:
        text = texts.get("doctor.stores.not_writable", tool=tool, path=folder)
        hint = texts.get("doctor.stores.hint_store_dir", tool=tool, config=config_path)
        return [
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason="not_writable",
            )
        ]
    if failure is None:
        return []
    reason = failure.strerror or str(failure)
    text = texts.get(
        "doctor.stores.no_hardlinks", tool=tool, path=folder, reason=reason
    )
    hint = texts.get("doctor.stores.hint_no_hardlinks", tool=tool, config=config_path)
    return [
        Check(
            "error",
            text,
            hint,
            blocking=True,
            code="store_unavailable",
            reason="no_hardlinks",
        )
    ]


def _kartograf_checks(
    settings: dict[str, Any], texts: Texts, config_path: Path
) -> list[Check]:
    """Kartograf's store keeps every version of a file as a hard link target."""
    store = Path(settings["store_dir"])
    checks, state = _store_folder(
        "kartograf", store, texts, config_path, symlinks_refused=False
    )
    where: Path | None = None
    if state == "missing":
        checks.append(
            Check(
                "warning",
                texts.get("doctor.stores.missing", tool="kartograf", path=store),
                texts.get("doctor.stores.hint_missing_kartograf"),
            )
        )
        # The file system is the one of the closest existing folder
        where = nearest_existing(store)
    elif state == "ok":
        where = store
    if where is not None:
        checks.extend(_hardlink_checks("kartograf", where, texts, config_path))
    if state == "ok" and not checks:
        checks.append(Check("ok", texts.get("doctor.stores.kartograf_ok", path=store)))
    checks.extend(_cache_checks(Path(settings["cache_file"]), texts, config_path))
    return checks


def _imgw_store_checks(store: Path, texts: Texts, config_path: Path) -> list[Check]:
    """IMGWTools creates a store in an empty folder and marks it with a file."""
    checks, state = _store_folder(
        "imgwtools", store, texts, config_path, symlinks_refused=True
    )
    if state == "broken":
        return checks
    found = imgw_store_state(store)
    args = {"path": store, "marker": IMGW_MARKER, "schema": found.detail}
    config = {"config": config_path}
    if found.state in ("missing", "empty"):
        checks.append(
            Check(
                "warning",
                texts.get("doctor.stores.imgw_not_initialised", **args),
                texts.get("doctor.stores.hint_imgw_init"),
            )
        )
    elif found.state == "foreign":
        text = texts.get("doctor.stores.imgw_foreign", **args)
        hint = texts.get("doctor.stores.hint_imgw_foreign", **config)
        checks.append(
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason="foreign_folder",
            )
        )
    elif found.state in ("unreadable", "unsupported"):
        text = texts.get(f"doctor.stores.imgw_{found.state}", **args)
        hint = texts.get("doctor.stores.hint_imgw_marker", **config)
        checks.append(
            Check(
                "error",
                text,
                hint,
                blocking=True,
                code="store_unavailable",
                reason=f"marker_{found.state}",
            )
        )
    if found.state in ("missing", "empty", "ready"):
        where = store if state == "ok" else nearest_existing(store)
        checks.extend(_hardlink_checks("imgwtools", where, texts, config_path))
    if found.state == "ready" and not checks:
        checks.append(Check("ok", texts.get("doctor.stores.imgw_ready", **args)))
    return checks


def _pyarrow_check(texts: Texts, source: str) -> Check:
    """Check ``pyarrow``: IMGWTools series are Parquet files (``imgwtools[store]``)."""
    try:
        pyarrow = importlib.import_module("pyarrow")
    except ImportError:
        return Check(
            "warning",
            texts.get("doctor.stores.pyarrow_missing"),
            texts.get("doctor.stores.hint_pyarrow_missing", source=source),
        )
    return Check(
        "ok", texts.get("doctor.stores.pyarrow_ok", version=pyarrow.__version__)
    )


def _reference_check(folder: Path, texts: Texts, config_path: Path) -> Check:
    if not folder.is_dir():
        return Check(
            "warning",
            texts.get("doctor.stores.reference_missing", path=folder),
            texts.get("doctor.stores.hint_reference", config=config_path),
        )
    present = (folder / IMGW_REFERENCE_FILE).is_file()
    return Check(
        "ok",
        texts.get(
            "doctor.stores.reference_ok",
            path=folder,
            file=IMGW_REFERENCE_FILE,
            state=texts.get(
                "doctor.stores.reference_present"
                if present
                else "doctor.stores.reference_absent"
            ),
        ),
    )


def _probe_check(
    outcome: ToolOutcome, version: str, texts: Texts, source: str, config_path: Path
) -> Check:
    if outcome.status == "ok":
        return Check("ok", texts.get("doctor.stores.probe_ok", version=version))
    return Check(
        "error",
        texts.get("doctor.stores.probe_failed", version=version, detail=outcome.detail),
        texts.get("doctor.stores.hint_probe_failed", source=source, config=config_path),
        blocking=True,
        code="store_unavailable",
        reason="probe_failed",
    )


def _store_checks(
    config: Settings,
    texts: Texts,
    active: dict[str, tuple[ManifestSpec, str]],
    *,
    deep: bool,
    probe: Callable[[], ToolOutcome],
) -> list[Check]:
    """Check the stores of the tools that are in use (installed, supported, enabled)."""
    checks: list[Check] = []
    if "kartograf" in active and "kartograf" in config.tools:
        checks.extend(_kartograf_checks(config.tools["kartograf"], texts, config.path))
    if "imgwtools" in active and "imgwtools" in config.tools:
        manifest, version = active["imgwtools"]
        settings = config.tools["imgwtools"]
        checks.extend(
            _imgw_store_checks(Path(settings["store_dir"]), texts, config.path)
        )
        arrow = _pyarrow_check(texts, manifest["source"])
        checks.append(arrow)
        checks.append(
            _reference_check(Path(settings["reference_data_dir"]), texts, config.path)
        )
        # An end-to-end write in a temporary folder (init, an archive, a series, a
        # catalog): slow, so only on request
        if arrow.status == "ok" and deep:
            checks.append(
                _probe_check(probe(), version, texts, manifest["source"], config.path)
            )
    return checks


def _conformance_checks(
    tool_manifests: list[tuple[ManifestSpec, Path]],
    active: dict[str, tuple[ManifestSpec, str]],
    texts: Texts,
    conformance: "LightCheck | None",
) -> list[Check]:
    """Run the light drift check of the tools in use (X1, X4; ARCHITECTURE 3.2.3).

    Whether the installed catalog still has the commands the manifest names and
    offers no value the manifest neither offers nor excludes. A tool the scaffold
    has nothing to check against gives no line.
    """
    # The scaffold is imported only here: nothing of it is needed to start
    from retman.devtools.light import light_lines

    directories = {manifest["tool"]: folder for manifest, folder in tool_manifests}
    return [
        Check(line.status, line.text, line.hint)
        for tool, (manifest, version) in active.items()
        for line in light_lines(
            manifest, directories[tool], version, texts, conformance
        )
    ]


def _translation_checks(
    language: str, texts: Texts, manifests: list[tuple[ManifestSpec, Path]]
) -> list[Check]:
    problems: list[str] = []
    try:
        load_core_texts(language)
    except TranslationError as err:
        problems.append(str(err))
    for manifest, directory in manifests:
        try:
            if language not in manifest["translations"]:
                raise ManifestError(
                    f"{manifest['tool']}: missing {language} translations"
                )
            translations = {
                lang: load_texts(directory / filename)
                for lang, filename in manifest["translations"].items()
            }
            validate_manifest(manifest, translations)
        except (ManifestError, OSError, tomllib.TOMLDecodeError) as err:
            problems.append(str(err))
    if not problems:
        return [Check("ok", texts.get("doctor.translations_ok"))]
    return [
        Check(
            "error",
            texts.get("doctor.translations_problem", problem=problem),
            texts.get("doctor.hint_translations"),
            blocking=True,
            code="internal_error",
            reason="missing_translation",
        )
        for problem in problems
    ]


def run_doctor(
    config_path: Path | None,
    project_dir: Path,
    *,
    backend: DecisionBackend | None = None,
    client: httpx.Client | None = None,
    manifests: Iterable[tuple[ManifestSpec, Path]] | None = None,
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    deep: bool = False,
    probe: Callable[[], ToolOutcome] = probe_imgw_write,
    conformance: "LightCheck | None" = None,
    options: Mapping[str, OptionValue] | None = None,
) -> tuple[DoctorReport, Texts]:
    """
    Check configuration, models, tools, translations and the project workspace.

    Parameters
    ----------
    config_path : Path | None
        Central config file; the system location by default.
    project_dir : Path
        Current project folder.
    backend, client, manifests, version_lookup
        Injections for offline tests; by default the configured backend,
        a new HTTP client, all tool manifests and installed package versions.
    deep : bool, optional
        Also run the slow checks: whether IMGWTools can write a store here.
    probe : Callable, optional
        The IMGWTools write probe; an injection for offline tests.
    conformance : LightCheck, optional
        The light drift check of the tools in use; by default the one of
        ``retman.devtools`` on the discovered tools. With injected ``manifests``
        it runs only when given, so that a test never meets a real tool.
    options : Mapping[str, OptionValue], optional
        The settings given by command-line options (``--lang``, ``--verbose``).

    Returns
    -------
    tuple[DoctorReport, Texts]
        The report and the texts to render it with.
    """
    texts = load_core_texts(REPORT_LANGUAGE)
    tool_manifests = list(manifests if manifests is not None else discover_manifests())
    file = environment(config_path, options=options).file
    sections: list[Section] = []
    configuration = Section("configuration", texts.get("doctor.section_configuration"))
    sections.append(configuration)
    try:
        settings: Settings | None = load_settings(config_path, options=options)
    except ConfigError as err:
        settings = None
        configuration.checks.extend(_config_problems(texts, err))
    config: Config | None = None
    if settings is not None:
        texts = load_core_texts(settings.language)
        configuration.title = texts.get("doctor.section_configuration")
        state = texts.get(
            "doctor.config_exists" if file.exists else "doctor.config_missing"
        )
        configuration.checks.append(
            Check("ok", texts.get("doctor.config", path=file.path, state=state))
        )
        configuration.checks.extend(_project_checks(settings, project_dir, texts))
        # The model server has no default: without it only planning is blocked
        try:
            config = load_config(config_path, options=options)
        except ConfigError as err:
            configuration.checks.extend(_config_problems(texts, err))
    if config is not None:
        owns_client = client is None
        http = client if client is not None else httpx.Client()
        try:
            sections.append(
                Section(
                    "decision",
                    texts.get("doctor.section_decision"),
                    _decision_checks(config, texts, backend, http),
                )
            )
        finally:
            if owns_client:
                http.close()
    tool_checks, active = _tool_checks(settings, texts, tool_manifests, version_lookup)
    sections.append(Section("tools", texts.get("doctor.section_tools"), tool_checks))
    if settings is not None:
        store_checks = _store_checks(settings, texts, active, deep=deep, probe=probe)
        if store_checks:
            sections.append(
                Section("stores", texts.get("doctor.section_stores"), store_checks)
            )
    if manifests is None or conformance is not None:
        conformance_checks = _conformance_checks(
            tool_manifests, active, texts, conformance
        )
        if conformance_checks:
            sections.append(
                Section(
                    "conformance",
                    texts.get("scaffold.doctor_section"),
                    conformance_checks,
                )
            )
    language = settings.language if settings is not None else REPORT_LANGUAGE
    sections.append(
        Section(
            "translations",
            texts.get("doctor.section_translations", language=language),
            _translation_checks(language, texts, tool_manifests),
        )
    )
    if settings is not None:
        sections.append(
            Section(
                "text",
                texts.get("doctor.section_text"),
                [
                    Check(
                        "off",
                        texts.get("doctor.text_off", backend=settings.text_backend),
                    )
                ],
            )
        )
    return DoctorReport(__version__, sections), texts

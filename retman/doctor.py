"""``retman doctor``: what works, what does not and how to fix it (ARCHITECTURE 7.2)."""

import importlib.metadata
import json
import os
import tomllib
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import httpx

from retman import __version__
from retman.backends import build_decision_backend
from retman.backends.base import DecisionBackend
from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.config import Config, default_config_path, load_config
from retman.exceptions import (
    BackendConnectionError,
    BackendError,
    ConfigError,
    ManifestError,
    TranslationError,
)
from retman.i18n.loader import Texts, load_core_texts, load_texts
from retman.registry.loader import discover_manifests, version_matches
from retman.registry.manifest import ManifestSpec, validate_manifest

Status = Literal["ok", "warning", "error", "off"]

# The fallback language only renders the report when the config cannot be read
REPORT_LANGUAGE = "pl"


@dataclass(frozen=True)
class Check:
    """One line of the report; ``blocking`` problems make the exit code 1."""

    status: Status
    text: str
    hint: str | None = None
    blocking: bool = False


@dataclass
class Section:
    """A titled group of checks (configuration, model, tools, ...)."""

    key: str
    title: str
    checks: list[Check] = field(default_factory=list)


@dataclass
class DoctorReport:
    """Result of all checks; ``exit_code`` is 1 when something blocks work."""

    version: str
    sections: list[Section]

    @property
    def exit_code(self) -> int:
        return int(
            any(check.blocking for section in self.sections for check in section.checks)
        )

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

    def to_json(self) -> str:
        """The same report for bug reports (``retman doctor --json``)."""
        return (
            json.dumps(
                {
                    "retman": self.version,
                    "exit_code": self.exit_code,
                    "sections": [asdict(section) for section in self.sections],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


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
    return [
        Check(
            "error",
            texts.get(
                f"config.{problem}",
                path=error.path,
                keys=error.details.get(problem, ""),
                error=error.details.get("error", ""),
                backend=error.details.get("backend", ""),
            ),
            blocking=True,
        )
        for problem in error.problems
    ]


def _nearest_existing(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _project_checks(config: Config, project_dir: Path, texts: Texts) -> list[Check]:
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
    writable = os.access(_nearest_existing(root), os.W_OK)
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
    config: Config | None,
    texts: Texts,
    manifests: list[tuple[ManifestSpec, Path]],
    version_lookup: Callable[[str], str],
) -> list[Check]:
    checks: list[Check] = []
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
            )
        )
    return checks


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

    Returns
    -------
    tuple[DoctorReport, Texts]
        The report and the texts to render it with.
    """
    texts = load_core_texts(REPORT_LANGUAGE)
    tool_manifests = list(manifests if manifests is not None else discover_manifests())
    path = config_path or default_config_path()
    sections: list[Section] = []
    configuration = Section("configuration", texts.get("doctor.section_configuration"))
    sections.append(configuration)
    try:
        config: Config | None = load_config(config_path)
    except ConfigError as err:
        config = None
        configuration.checks.extend(_config_problems(texts, err))
    if config is not None:
        texts = load_core_texts(config.language)
        configuration.title = texts.get("doctor.section_configuration")
        configuration.checks.append(Check("ok", texts.get("doctor.config", path=path)))
        configuration.checks.extend(_project_checks(config, project_dir, texts))
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
    sections.append(
        Section(
            "tools",
            texts.get("doctor.section_tools"),
            _tool_checks(config, texts, tool_manifests, version_lookup),
        )
    )
    language = config.language if config is not None else REPORT_LANGUAGE
    sections.append(
        Section(
            "translations",
            texts.get("doctor.section_translations", language=language),
            _translation_checks(language, texts, tool_manifests),
        )
    )
    if config is not None:
        sections.append(
            Section(
                "text",
                texts.get("doctor.section_text"),
                [
                    Check(
                        "off", texts.get("doctor.text_off", backend=config.text_backend)
                    )
                ],
            )
        )
    return DoctorReport(__version__, sections), texts

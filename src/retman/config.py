"""Central config file ``retman.toml``: location, loading, ``retman init``."""

import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

from retman.exceptions import ConfigError

CONFIG_FILENAME = "retman.toml"

DecisionBackendName = Literal["basal", "openai_compatible"]
ConfidenceSetting = Literal["auto", "logprobs", "consistency", "none"]
DiagnosticLevel = Literal["debug", "info", "warning"]

_DECISION_BACKENDS: tuple[str, ...] = ("basal", "openai_compatible")
_CONFIDENCE_SETTINGS: tuple[str, ...] = ("auto", "logprobs", "consistency", "none")
_TEXT_BACKENDS: tuple[str, ...] = ("none",)
_DIAGNOSTIC_LEVELS: tuple[str, ...] = ("debug", "info", "warning")
# "local" keeps stored versions and asks no source; the others are Kartograf's
# update modes of a download ("check" never downloads, so it is not a setting)
_KARTOGRAF_UPDATE_MODES: tuple[str, ...] = ("local", "upgrade", "force")

# Folder names of the two tool stores inside the folder chosen in ``retman init``
KARTOGRAF_STORE_NAME = "kartograf"
IMGWTOOLS_STORE_NAME = "imgwtools"


@dataclass(frozen=True)
class Thresholds:
    """Confidence thresholds; ``"auto"`` means basal calibration (ARCH 6.2)."""

    operation: float | Literal["auto"]
    parameter: float | Literal["auto"]


@dataclass(frozen=True)
class DecisionConfig:
    """``[decision]``: the decision model (ARCHITECTURE 3.3.2).

    ``confidence`` and ``consistency_runs`` apply to ``openai_compatible`` only
    and are ``None`` for ``basal``. ``api_key_env`` is the NAME of an
    environment variable, never the key itself (ARCHITECTURE rozdz. 10).
    """

    backend: DecisionBackendName
    url: str
    model: str
    timeout_s: float
    thresholds: Thresholds
    api_key_env: str | None
    confidence: ConfidenceSetting | None
    consistency_runs: int | None


@dataclass(frozen=True)
class Config:
    """Contents of the central config file; every value Retman uses is here.

    ``tools`` holds the validated ``[tools.<tool>]`` tables, the settings a tool
    client needs (ARCHITECTURE 9.1): paths are absolute ``str``, ``workers`` an
    ``int``, ``update`` a ``str``. Tools without settings are absent.
    """

    path: Path
    decision: DecisionConfig
    text_backend: Literal["none"]
    language: str
    results_dir: str
    enabled_tools: tuple[str, ...] | None
    journal_commands: bool
    diagnostic_level: DiagnosticLevel
    collect_commands: bool
    collect_path: Path
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)


def default_config_path() -> Path:
    """
    Location of the central config file for the current system.

    Returns
    -------
    Path
        Linux: ``$XDG_CONFIG_HOME/retman/retman.toml`` (default ``~/.config``);
        macOS: ``~/Library/Application Support/retman/retman.toml``;
        Windows: ``%APPDATA%\\retman\\retman.toml``.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "retman" / CONFIG_FILENAME


def default_log_dir() -> Path:
    """Directory of the technical log for the current system (ARCHITECTURE 5.4)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "retman" / "Logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "retman"
    xdg = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "state"
    return base / "retman"


def default_data_dir() -> Path:
    """Per-user data folder of Retman for the current system.

    Linux: ``$XDG_DATA_HOME/retman`` (default ``~/.local/share/retman``);
    macOS: ``~/Library/Application Support/retman``;
    Windows: ``%LOCALAPPDATA%\\retman``.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "retman"


def default_collect_path() -> Path:
    """Default file of the command collection for the current system (ADR-010)."""
    return default_data_dir() / "collected.jsonl"


def default_stores_dir() -> Path:
    """Folder offered by ``retman init`` for the stores of all tools.

    The tool stores are two folders inside it (``kartograf`` and ``imgwtools``),
    so they share one disk; the user may choose another folder.
    """
    return default_data_dir() / "stores"


def default_cache_file() -> Path:
    """Kartograf's metadata cache; a local disk, never the (possibly shared) stores."""
    return default_data_dir() / "kartograf_cache.db"


def default_reference_data_dir() -> Path:
    """Folder of IMGWTools reference files (``hydro_stations_locations.csv``)."""
    return default_data_dir() / "imgw-reference"


@dataclass(frozen=True)
class ToolPaths:
    """The absolute paths ``retman init`` writes to the ``[tools.*]`` tables."""

    kartograf_store: Path
    kartograf_cache: Path
    imgwtools_store: Path
    imgwtools_reference: Path


def tool_paths(stores_dir: Path | None = None) -> ToolPaths:
    """Paths of the tool stores for the folder chosen in ``retman init``.

    Both stores are folders inside ``stores_dir`` (one disk, two folders); the
    cache and the reference files stay in the per-user data folder, a local
    disk. Paths are resolved: IMGWTools refuses a symbolic link in a store path.

    Parameters
    ----------
    stores_dir : Path, optional
        :func:`default_stores_dir` by default.
    """
    stores = stores_dir if stores_dir is not None else default_stores_dir()
    stores = stores.expanduser().resolve()
    return ToolPaths(
        kartograf_store=stores / KARTOGRAF_STORE_NAME,
        kartograf_cache=default_cache_file().expanduser().resolve(),
        imgwtools_store=stores / IMGWTOOLS_STORE_NAME,
        imgwtools_reference=default_reference_data_dir().expanduser().resolve(),
    )


def _toml_string(value: str) -> str:
    """TOML string of ``value``: a literal one (backslashes of Windows paths stay as
    they are), a basic one only when the text holds a quote or a control character."""
    if "'" in value or any(ord(char) < 32 for char in value):
        return json.dumps(value, ensure_ascii=False)
    return f"'{value}'"


def config_template(
    *, collect_commands: bool = False, stores_dir: Path | None = None
) -> str:
    """Text of the full config file with comments, written by ``retman init``.

    Every path is written out for this system, so the file shows every value
    Retman uses (no hidden defaults, N-11).

    Parameters
    ----------
    collect_commands : bool, optional
        The user's answer about collecting commands (ADR-010).
    stores_dir : Path, optional
        Folder holding both tool stores as ``kartograf`` and ``imgwtools``;
        :func:`default_stores_dir` by default.
    """
    paths = tool_paths(stores_dir)
    values = {
        "@COLLECT_COMMANDS@": "true" if collect_commands else "false",
        "@COLLECT_PATH@": _toml_string(str(default_collect_path())),
        "@KARTOGRAF_STORE_DIR@": _toml_string(str(paths.kartograf_store)),
        "@KARTOGRAF_CACHE_FILE@": _toml_string(str(paths.kartograf_cache)),
        "@IMGWTOOLS_STORE_DIR@": _toml_string(str(paths.imgwtools_store)),
        "@IMGWTOOLS_REFERENCE_DIR@": _toml_string(str(paths.imgwtools_reference)),
    }
    text = (
        resources.files("retman")
        .joinpath("config_template.toml")
        .read_text(encoding="utf-8")
    )
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    return text


def init_config(
    path: Path | None = None,
    *,
    collect_commands: bool = False,
    stores_dir: Path | None = None,
) -> Path:
    """
    Write the full config file from the template (``retman init``).

    Only the file is written: the store folders are created by the caller
    (``retman init``), never as a side effect of writing the settings.

    Parameters
    ----------
    path : Path, optional
        Target file; the system location by default.
    collect_commands : bool, optional
        The user's explicit answer about collecting commands (ADR-010);
        disabled unless the user agreed.
    stores_dir : Path, optional
        Folder for the stores of the tools (``kartograf`` and ``imgwtools`` are
        created inside it); :func:`default_stores_dir` by default.

    Returns
    -------
    Path
        The written file.

    Raises
    ------
    ConfigError
        The file already exists (problem ``"already_exists"``); it is never
        overwritten.
    """
    target = path or default_config_path()
    if target.exists():
        raise ConfigError(target, ["already_exists"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        config_template(collect_commands=collect_commands, stores_dir=stores_dir),
        encoding="utf-8",
        newline="\n",
    )
    return target


def load_config(path: Path | None = None) -> Config:
    """
    Read and validate the central config file.

    Parameters
    ----------
    path : Path, optional
        Config file; the system location by default.

    Returns
    -------
    Config
        Validated settings.

    Raises
    ------
    ConfigError
        The file is missing (``"missing_file"``), is not valid TOML
        (``"invalid_toml"``) or has missing or invalid values; all problems
        found are reported at once.
    """
    target = path or default_config_path()
    if not target.exists():
        raise ConfigError(target, ["missing_file"])
    try:
        with target.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(target, ["invalid_toml"], {"error": str(err)}) from err
    return _parse(target, data)


class _Reader:
    """Collects all problems of a config file instead of stopping at the first."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self._keys: dict[str, list[str]] = {}

    @property
    def problems(self) -> list[str]:
        return sorted(self._keys)

    @property
    def details(self) -> dict[str, str]:
        return {kind: ", ".join(keys) for kind, keys in self._keys.items()}

    def _problem(self, kind: str, key: str) -> None:
        keys = self._keys.setdefault(kind, [])
        if key not in keys:
            keys.append(key)

    def get(self, key: str, *, optional: bool = False) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                if not optional:
                    self._problem("missing_key", key)
                return None
            node = node[part]
        return node

    def string(self, key: str, *, optional: bool = False) -> str | None:
        value = self.get(key, optional=optional)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            self._problem("invalid_value", key)
            return None
        return value

    def choice(self, key: str, allowed: tuple[str, ...]) -> str | None:
        value = self.get(key)
        if value is None:
            return None
        if value not in allowed:
            self._problem("invalid_value", key)
            return None
        return cast(str, value)

    def boolean(self, key: str) -> bool | None:
        value = self.get(key)
        if value is None:
            return None
        if not isinstance(value, bool):
            self._problem("invalid_value", key)
            return None
        return value

    def positive_number(self, key: str) -> float | None:
        value = self.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            self._problem("invalid_value", key)
            return None
        return float(value)

    def positive_int(self, key: str) -> int | None:
        value = self.get(key)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            self._problem("invalid_value", key)
            return None
        return value

    def absolute_path(self, key: str) -> str | None:
        """Absolute path without ``..``; a relative one would depend on the folder
        Retman is started in. Returned normalised, as text."""
        value = self.string(key)
        if value is None:
            return None
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts:
            self._problem("invalid_value", key)
            return None
        return str(path)

    def threshold(self, key: str) -> float | Literal["auto"] | None:
        value = self.get(key)
        if value is None:
            return None
        if value == "auto":
            return "auto"
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 < value <= 1
        ):
            self._problem("invalid_value", key)
            return None
        return float(value)

    def fail(self, kind: str, key: str) -> None:
        self._problem(kind, key)


def _inside(path: Path, folder: Path) -> bool:
    """Whether ``path`` is ``folder`` or lies below it (text comparison only)."""
    return path == folder or folder in path.parents


def _parse_tools(read: _Reader) -> dict[str, dict[str, Any]]:
    """``[tools.kartograf]`` and ``[tools.imgwtools]``: stores, cache, workers.

    Every value is required (no hidden defaults, N-11). Paths are checked as text
    only; whether they exist and work is the business of ``retman doctor``.
    """
    kartograf_store = cache_file = imgw_store = reference_dir = None
    workers = update = None
    if read.get("tools.kartograf", optional=True) is None:
        read.fail("missing_tools", "tools.kartograf")
    else:
        kartograf_store = read.absolute_path("tools.kartograf.store_dir")
        cache_file = read.absolute_path("tools.kartograf.cache_file")
        workers = read.positive_int("tools.kartograf.workers")
        update = read.choice("tools.kartograf.update", _KARTOGRAF_UPDATE_MODES)
    if read.get("tools.imgwtools", optional=True) is None:
        read.fail("missing_tools", "tools.imgwtools")
    else:
        imgw_store = read.absolute_path("tools.imgwtools.store_dir")
        reference_dir = read.absolute_path("tools.imgwtools.reference_data_dir")

    # The stores are siblings: neither may contain the other (IMGWTools refuses a
    # store inside or around a Kartograf store), and the cache and the reference
    # files are not store content (a store scan reports foreign files)
    stores = {
        "tools.kartograf.store_dir": kartograf_store,
        "tools.imgwtools.store_dir": imgw_store,
    }
    folders = {key: Path(value) for key, value in stores.items() if value is not None}
    if len(folders) == len(stores):
        left, right = folders.values()
        if _inside(left, right) or _inside(right, left):
            read.fail("paths_overlap", " / ".join(folders))
    for key, value in (
        ("tools.kartograf.cache_file", cache_file),
        ("tools.imgwtools.reference_data_dir", reference_dir),
    ):
        for store_key, folder in folders.items():
            if value is not None and _inside(Path(value), folder):
                read.fail("paths_overlap", f"{key} / {store_key}")
    return {
        "kartograf": {
            "store_dir": kartograf_store,
            "cache_file": cache_file,
            "workers": workers,
            "update": update,
        },
        "imgwtools": {"store_dir": imgw_store, "reference_data_dir": reference_dir},
    }


def _parse(path: Path, data: dict[str, Any]) -> Config:
    read = _Reader(data)
    backend = read.choice("decision.backend", _DECISION_BACKENDS)
    url = read.string("decision.url")
    model = read.string("decision.model")
    timeout_s = read.positive_number("decision.timeout_s")
    api_key_env = read.string("decision.api_key_env", optional=True)
    operation = read.threshold("decision.thresholds.operation")
    parameter = read.threshold("decision.thresholds.parameter")

    confidence: str | None = None
    consistency_runs: int | None = None
    if backend == "openai_compatible":
        confidence = read.choice("decision.confidence", _CONFIDENCE_SETTINGS)
        consistency_runs = read.positive_int("decision.consistency_runs")
        # "auto" thresholds mean basal calibration; with confidence = "none"
        # thresholds are ignored (ARCHITECTURE 6.2)
        if confidence != "none":
            for key, value in (
                ("decision.thresholds.operation", operation),
                ("decision.thresholds.parameter", parameter),
            ):
                if value == "auto":
                    read.fail("auto_threshold_without_basal", key)

    text_backend = read.choice("text.backend", _TEXT_BACKENDS)
    language = read.string("ui.language")
    results_dir = read.string("output.results_dir")
    # Results belong to the project folder (ARCHITECTURE 5.1): no absolute
    # paths and no way out of the folder
    if results_dir is not None and (
        Path(results_dir).is_absolute()
        or Path(results_dir).drive
        or ".." in Path(results_dir).parts
    ):
        read.fail("invalid_value", "output.results_dir")
        results_dir = None
    enabled = read.get("adapters.enabled", optional=True)
    if enabled is not None and (
        not isinstance(enabled, list)
        or not all(isinstance(name, str) and name for name in enabled)
    ):
        read.fail("invalid_value", "adapters.enabled")
        enabled = None
    journal_commands = read.boolean("log.journal_commands")
    diagnostic_level = read.choice("log.diagnostic_level", _DIAGNOSTIC_LEVELS)
    collect_commands = read.boolean("privacy.collect_commands")
    collect_path = read.string("privacy.collect_path")
    if collect_path is not None and not Path(collect_path).is_absolute():
        read.fail("invalid_value", "privacy.collect_path")
        collect_path = None
    tools = _parse_tools(read)

    if read.problems:
        raise ConfigError(path, read.problems, read.details)
    # All values are present and valid here; casts narrow the reader's Optionals
    return Config(
        path=path,
        decision=DecisionConfig(
            backend=cast(DecisionBackendName, backend),
            url=cast(str, url),
            model=cast(str, model),
            timeout_s=cast(float, timeout_s),
            thresholds=Thresholds(
                operation=cast(float | Literal["auto"], operation),
                parameter=cast(float | Literal["auto"], parameter),
            ),
            api_key_env=api_key_env,
            confidence=cast(ConfidenceSetting | None, confidence),
            consistency_runs=consistency_runs,
        ),
        text_backend=cast(Literal["none"], text_backend),
        language=cast(str, language),
        results_dir=cast(str, results_dir),
        enabled_tools=tuple(enabled) if enabled is not None else None,
        journal_commands=cast(bool, journal_commands),
        diagnostic_level=cast(DiagnosticLevel, diagnostic_level),
        collect_commands=cast(bool, collect_commands),
        collect_path=Path(cast(str, collect_path)),
        tools=tools,
    )

"""Central config file ``retman.toml``: location, loading, ``retman init``."""

import os
import sys
import tomllib
from dataclasses import dataclass
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
    """Contents of the central config file; every value Retman uses is here."""

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


def default_collect_path() -> Path:
    """Default file of the command collection for the current system (ADR-010).

    Linux: ``$XDG_DATA_HOME/retman/collected.jsonl`` (default ``~/.local/share``);
    macOS: ``~/Library/Application Support/retman/collected.jsonl``;
    Windows: ``%LOCALAPPDATA%\\retman\\collected.jsonl``.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "retman" / "collected.jsonl"


def config_template(*, collect_commands: bool = False) -> str:
    """Text of the full config file with comments, written by ``retman init``.

    The collection path is written out for this system, so the file shows every
    value Retman uses (no hidden defaults, N-11).
    """
    return (
        resources.files("retman")
        .joinpath("config_template.toml")
        .read_text(encoding="utf-8")
        .replace("@COLLECT_COMMANDS@", "true" if collect_commands else "false")
        .replace("@COLLECT_PATH@", str(default_collect_path()))
    )


def init_config(path: Path | None = None, *, collect_commands: bool = False) -> Path:
    """
    Write the full config file from the template (``retman init``).

    Parameters
    ----------
    path : Path, optional
        Target file; the system location by default.
    collect_commands : bool, optional
        The user's explicit answer about collecting commands (ADR-010);
        disabled unless the user agreed.

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
        config_template(collect_commands=collect_commands),
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
    )

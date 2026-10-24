"""The settings of Retman: ``[retman]`` of ``nogat.toml``, checked, and written out.

:mod:`retman.environment` finds each value (option, variable, file, default,
DEV-18.1); this module checks them and builds what the program uses. Every setting
has a default except the model server (``[retman.decision]``), which has no
meaningful one: :func:`load_config` reports what is missing, while
:func:`load_settings`, and with it every command that needs no model, works from
the defaults (N-11 read as "no hidden default": ``retman config show`` lists each
value with its source and ``retman config init`` writes the tables out).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Final, Literal, cast

from retman.environment import (
    COLLECT_PATH,
    IMGWTOOLS_REFERENCE,
    IMGWTOOLS_STORE_NAME,
    KARTOGRAF_CACHE,
    KARTOGRAF_STORE_NAME,
    KEYS,
    TOOL,
    ConfigFile,
    Environment,
    OptionValue,
    environment,
)
from retman.exceptions import ConfigError
from retman.i18n.loader import text_language

DecisionBackendName = Literal["basal", "openai_compatible"]
ConfidenceSetting = Literal["auto", "logprobs", "consistency", "none"]
LogLevel = Literal["debug", "info", "warning", "error"]

# The model server has no default: a command that needs no model works without it
_MODEL_REQUIRED: Final[tuple[str, ...]] = (
    "decision.backend",
    "decision.url",
    "decision.model",
    "decision.timeout_s",
    "decision.thresholds.operation",
    "decision.thresholds.parameter",
)
_THRESHOLDS: Final[tuple[str, ...]] = _MODEL_REQUIRED[-2:]
_OPENAI_REQUIRED: Final[tuple[str, ...]] = (
    "decision.confidence",
    "decision.consistency_runs",
)
_STORE_KEYS: Final[tuple[str, ...]] = (
    "tools.kartograf.store_dir",
    "tools.imgwtools.store_dir",
)
_SIDE_KEYS: Final[tuple[str, ...]] = (
    "tools.kartograf.cache_file",
    "tools.imgwtools.reference_data_dir",
)


@dataclass(frozen=True)
class Thresholds:
    """Confidence thresholds; ``"auto"`` means basal calibration (ARCH 6.2)."""

    operation: float | Literal["auto"]
    parameter: float | Literal["auto"]


@dataclass(frozen=True)
class DecisionConfig:
    """``[retman.decision]``: the decision model (ARCHITECTURE 3.3.2).

    ``confidence`` and ``consistency_runs`` apply to ``openai_compatible`` only
    and are ``None`` for ``basal``. ``api_key_env`` is the NAME of an
    environment variable, never the key itself (ARCHITECTURE chapter 10).
    """

    backend: DecisionBackendName
    url: str
    model: str
    timeout_s: float
    thresholds: Thresholds
    api_key_env: str | None
    confidence: ConfidenceSetting | None
    consistency_runs: int | None


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Every setting but the model server: what a command without a model uses.

    ``language`` is the language of the texts: ``lang``, or Polish while ``lang``
    has no translation (the English texts are not written yet). ``tools`` holds the
    ``[retman.tools.<tool>]`` tables, the settings a tool client needs
    (ARCHITECTURE 9.1): paths are absolute ``str``, ``workers`` an ``int``,
    ``update`` a ``str``. Tools without settings are absent.
    """

    path: Path
    language: str
    log_level: LogLevel
    text_backend: Literal["none"]
    results_dir: str
    enabled_tools: tuple[str, ...] | None
    journal_commands: bool
    collect_commands: bool
    collect_path: Path
    tools: dict[str, dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class Config(Settings):
    """All settings, the model server included: what planning needs."""

    decision: DecisionConfig


class _Problems:
    """Collects all problems of the settings instead of stopping at the first."""

    def __init__(self) -> None:
        self._keys: dict[str, list[str]] = {}

    def __bool__(self) -> bool:
        return bool(self._keys)

    def add(self, kind: str, key: str) -> None:
        keys = self._keys.setdefault(kind, [])
        if key not in keys:
            keys.append(key)

    def raise_for(self, path: Path) -> None:
        if self._keys:
            details = {kind: ", ".join(keys) for kind, keys in self._keys.items()}
            raise ConfigError(path, sorted(self._keys), details)


def _inside(path: Path, folder: Path) -> bool:
    """Whether ``path`` is ``folder`` or lies below it (text comparison only)."""
    return path == folder or folder in path.parents


def _check_values(env: Environment, problems: _Problems, *, model: bool) -> None:
    """Report the given values that cannot be used (``invalid_value``)."""
    for key in KEYS:
        if key.name.startswith("decision.") and not model:
            continue
        setting = env.setting(key.name)
        if setting.error is not None:
            given = setting.given
            origin = f" ({given.name})" if given and given.source == "env" else ""
            problems.add("invalid_value", key.name + origin)


def _check_paths(env: Environment, problems: _Problems) -> None:
    """Check that the stores are siblings and the side files lie outside them.

    IMGWTools refuses a store inside or around a Kartograf store, and a store scan
    reports foreign files.
    """
    stores = {name: Path(env.setting(name).value) for name in _STORE_KEYS}
    left, right = stores.values()
    if _inside(left, right) or _inside(right, left):
        problems.add("paths_overlap", " / ".join(stores))
    for key in _SIDE_KEYS:
        for store_key, folder in stores.items():
            if _inside(Path(env.setting(key).value), folder):
                problems.add("paths_overlap", f"{key} / {store_key}")


def _missing(env: Environment, problems: _Problems, names: tuple[str, ...]) -> None:
    for name in names:
        setting = env.setting(name)
        if setting.value is None and setting.error is None:
            problems.add("missing_key", name)


def _decision(env: Environment, problems: _Problems) -> DecisionConfig | None:
    """Build the model settings; ``None`` when they are not complete and valid."""
    _missing(env, problems, _MODEL_REQUIRED)
    backend = env.setting("decision.backend").value
    confidence = consistency_runs = None
    if backend == "openai_compatible":
        _missing(env, problems, _OPENAI_REQUIRED)
        confidence = env.setting("decision.confidence").value
        consistency_runs = env.setting("decision.consistency_runs").value
        # "auto" thresholds mean basal calibration; with confidence = "none"
        # thresholds are ignored (ARCHITECTURE 6.2)
        if confidence != "none":
            for name in _THRESHOLDS:
                if env.setting(name).value == "auto":
                    problems.add("auto_threshold_without_basal", name)
    values = {name: env.setting(name).value for name in _MODEL_REQUIRED}
    if problems or any(value is None for value in values.values()):
        return None
    return DecisionConfig(
        backend=cast(DecisionBackendName, backend),
        url=values["decision.url"],
        model=values["decision.model"],
        timeout_s=values["decision.timeout_s"],
        thresholds=Thresholds(
            operation=values["decision.thresholds.operation"],
            parameter=values["decision.thresholds.parameter"],
        ),
        api_key_env=env.setting("decision.api_key_env").value,
        confidence=cast(ConfidenceSetting | None, confidence),
        consistency_runs=consistency_runs,
    )


def _settings(env: Environment) -> Settings:
    """Build the settings from values that are known to be valid."""

    def value(name: str) -> Any:
        return env.setting(name).value

    def text(name: str) -> str:
        return str(value(name))

    return Settings(
        path=env.file.path,
        language=text_language(value("lang")),
        log_level=cast(LogLevel, value("log_level")),
        text_backend=cast(Literal["none"], value("text.backend")),
        results_dir=value("output.results_dir"),
        enabled_tools=value("adapters.enabled"),
        journal_commands=value("log.journal_commands"),
        collect_commands=value("privacy.collect_commands"),
        collect_path=value("privacy.collect_path"),
        tools={
            "kartograf": {
                "store_dir": text("tools.kartograf.store_dir"),
                "cache_file": text("tools.kartograf.cache_file"),
                "workers": value("tools.kartograf.workers"),
                "update": value("tools.kartograf.update"),
            },
            "imgwtools": {
                "store_dir": text("tools.imgwtools.store_dir"),
                "reference_data_dir": text("tools.imgwtools.reference_data_dir"),
            },
        },
    )


def _raise_file_problem(file: ConfigFile) -> None:
    if file.problem is not None:
        raise ConfigError(file.path, [file.problem], {"error": file.error or ""})


def load_settings(
    path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    options: Mapping[str, OptionValue] | None = None,
) -> Settings:
    """Read and validate every setting but the model server.

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.
    options : Mapping[str, OptionValue], optional
        The settings given by command-line options (``--lang``, ``--verbose``,
        ``--quiet``; :func:`retman.environment.cli_options`).

    Returns
    -------
    Settings
        Validated settings; the file may be missing, the defaults then apply.

    Raises
    ------
    ConfigError
        The file named by ``--config`` or ``NOGAT_CONFIG`` is missing
        (``"missing_file"``), cannot be read (``"unreadable_file"``), is not
        valid TOML (``"invalid_toml"``) or has a section that is not a table
        (``"invalid_section"``), or a value is not valid; all problems of the
        values are reported at once.
    """
    env = environment(path, environ, options)
    _raise_file_problem(env.file)
    problems = _Problems()
    _check_values(env, problems, model=False)
    if not problems:
        _check_paths(env, problems)
    problems.raise_for(env.file.path)
    return _settings(env)


def load_config(
    path: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    options: Mapping[str, OptionValue] | None = None,
) -> Config:
    """Read and validate every setting, the model server included.

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.
    options : Mapping[str, OptionValue], optional
        As for :func:`load_settings`.

    Returns
    -------
    Config
        Validated settings.

    Raises
    ------
    ConfigError
        As :func:`load_settings`, and ``"missing_key"`` for a model setting that
        nothing sets: the model server has no default.
    """
    env = environment(path, environ, options)
    _raise_file_problem(env.file)
    problems = _Problems()
    _check_values(env, problems, model=True)
    if not problems:
        _check_paths(env, problems)
    decision = _decision(env, problems)
    problems.raise_for(env.file.path)
    assert decision is not None  # no problem was found, so the model is complete
    return Config(**vars(_settings(env)), decision=decision)


@dataclass(frozen=True)
class ToolPaths:
    """The absolute paths ``config init`` writes to the ``[retman.tools.*]`` tables."""

    kartograf_store: Path
    kartograf_cache: Path
    imgwtools_store: Path
    imgwtools_reference: Path


def default_stores_dir(env: Environment) -> Path:
    """Folder offered by ``retman config init`` for the stores of all tools.

    The tool stores are two folders inside it (``kartograf`` and ``imgw``), so
    they share one disk; the user may choose another folder.
    """
    return env.data_dir


def default_collect_path(env: Environment) -> Path:
    """Return the default file of the command collection (ADR-010)."""
    return COLLECT_PATH(env)


def tool_paths(env: Environment, stores_dir: Path | None = None) -> ToolPaths:
    """Paths of the tool stores for the folder chosen in ``retman config init``.

    Both stores are folders inside ``stores_dir`` (one disk, two folders); the
    cache and the reference files stay in the cache folder, a local disk. Paths
    are resolved: IMGWTools refuses a symbolic link in a store path.

    Parameters
    ----------
    env : Environment
        Gives ``data_dir`` and ``cache_dir``.
    stores_dir : Path, optional
        :func:`default_stores_dir` by default.
    """
    stores = stores_dir if stores_dir is not None else default_stores_dir(env)
    stores = stores.expanduser().resolve()
    return ToolPaths(
        kartograf_store=stores / KARTOGRAF_STORE_NAME,
        kartograf_cache=KARTOGRAF_CACHE(env).expanduser().resolve(),
        imgwtools_store=stores / IMGWTOOLS_STORE_NAME,
        imgwtools_reference=IMGWTOOLS_REFERENCE(env).expanduser().resolve(),
    )


def _toml_string(value: str) -> str:
    """Return the TOML string of ``value``.

    A literal one (backslashes of Windows paths stay as they are), a basic one only
    when the text holds a quote or a control character.
    """
    if "'" in value or any(ord(char) < 32 for char in value):
        return json.dumps(value, ensure_ascii=False)
    return f"'{value}'"


def config_template(
    *,
    collect_commands: bool = False,
    stores_dir: Path | None = None,
    env: Environment | None = None,
) -> str:
    """Text of the ``[retman]`` tables with comments, written by ``config init``.

    Every path is written out for this system, so the file shows every value
    Retman uses (no hidden defaults, N-11). The shared keys (``lang``,
    ``log_level``, ``data_dir``, ``cache_dir``) are left as comments: a value here
    would override the ``[nogat]`` table the other tools share.

    Parameters
    ----------
    collect_commands : bool, optional
        The user's answer about collecting commands (ADR-010).
    stores_dir : Path, optional
        Folder holding both tool stores as ``kartograf`` and ``imgw``;
        :func:`default_stores_dir` by default.
    env : Environment, optional
        The sources of ``data_dir`` and ``cache_dir``; the process environment by
        default.
    """
    env = env if env is not None else environment()
    paths = tool_paths(env, stores_dir)
    values = {
        "@COLLECT_COMMANDS@": "true" if collect_commands else "false",
        "@COLLECT_PATH@": _toml_string(str(default_collect_path(env))),
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


def init_target(env: Environment) -> Path:
    """Return the file ``retman config init`` writes, or raise why it cannot.

    The checks come before any question of ``retman config init``: the answers would
    be thrown away.

    Raises
    ------
    ConfigError
        The file has a ``[retman]`` table (problem ``"already_exists"``; it is never
        overwritten), or cannot be read or is not valid TOML, so that the tables
        cannot be appended safely.
    """
    if env.file.problem not in (None, "missing_file"):
        _raise_file_problem(env.file)
    if TOOL in env.file.sections:
        raise ConfigError(env.file.path, ["already_exists"])
    return env.file.path


def init_config(
    path: Path | None = None,
    *,
    collect_commands: bool = False,
    stores_dir: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Write the ``[retman]`` tables into ``nogat.toml`` (``retman config init``).

    A missing file is created; an existing one gets the tables appended and its
    other tables stay as they are. Only the file is written: the store folders are
    created by the caller (``retman config init``), never as a side effect of
    writing the settings.

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    collect_commands : bool, optional
        The user's explicit answer about collecting commands (ADR-010);
        disabled unless the user agreed.
    stores_dir : Path, optional
        Folder for the stores of the tools (``kartograf`` and ``imgw`` are
        created inside it); :func:`default_stores_dir` by default.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.

    Returns
    -------
    Path
        The written file.

    Raises
    ------
    ConfigError
        The file has a ``[retman]`` table (problem ``"already_exists"``; it is never
        overwritten), or cannot be read or is not valid TOML, so that the tables
        cannot be appended safely.
    """
    env = environment(path, environ)
    target = init_target(env)
    text = config_template(
        collect_commands=collect_commands, stores_dir=stores_dir, env=env
    )
    if env.file.exists:
        existing = target.read_text(encoding="utf-8")
        if existing.strip():
            text = existing + ("\n" if existing.endswith("\n") else "\n\n") + text
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target

"""The sources of the settings of Retman: ``nogat.toml``, variables, user directories.

A setting comes from the first of: the command-line option (``--lang``, ``--verbose``
and ``--quiet`` are the only ones, :func:`cli_options`), the variable
``RETMAN_<KEY>``, the shared variable ``NOGAT_<KEY>`` (shared keys only), the table
``[retman]`` of ``nogat.toml``, the table ``[nogat]`` of it (shared keys only) and the
built-in default (DEV-18.1, ECO-028). ``<KEY>`` is the
dotted key in capitals with ``_`` for ``.``: ``decision.url`` is
``RETMAN_DECISION_URL``. An empty variable counts as unset. The shared keys are
``lang``, ``log_level``, ``data_dir`` and ``cache_dir``.

The file is ``nogat.toml`` in ``platformdirs.user_config_path("nogat")``, at the
path in ``NOGAT_CONFIG`` or at the path of ``--config``; it is read with
``tomllib``, a missing default file is no error, and Retman needs neither the
``nogat`` package nor a ``.env`` file. A value that cannot be used is dropped and
reported (``Setting.error``); :mod:`retman.config` turns that into an error for the
commands that need the setting, and ``retman config show`` reports it.

Credentials never come from the file or from a variable of Retman (DEV-18.4): the
key of an external model provider is read from the variable that
``decision.api_key_env`` names.
"""

import logging
import math
import os
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

import platformdirs

from retman.exceptions import UsageError

logger = logging.getLogger(__name__)

APP: Final = "nogat"
TOOL: Final = "retman"
PREFIX: Final = "RETMAN_"
SHARED_PREFIX: Final = "NOGAT_"
CONFIG_ENV: Final = "NOGAT_CONFIG"
CONFIG_FILENAME: Final = "nogat.toml"

SettingSource = Literal["default", "env", "file", "option"]
FileSource = Literal["default", "NOGAT_CONFIG", "option"]
Kind = Literal[
    "choice",
    "text",
    "path",
    "folder",
    "number",
    "integer",
    "flag",
    "threshold",
    "names",
]

LANGUAGES: Final[tuple[str, ...]] = ("pl", "en")
LOG_LEVELS: Final[tuple[str, ...]] = ("debug", "info", "warning", "error")
DECISION_BACKENDS: Final[tuple[str, ...]] = ("basal", "openai_compatible")
CONFIDENCE_SETTINGS: Final[tuple[str, ...]] = (
    "auto",
    "logprobs",
    "consistency",
    "none",
)
TEXT_BACKENDS: Final[tuple[str, ...]] = ("none",)
# "local" keeps stored versions and asks no source; the others are Kartograf's
# update modes of a download ("check" never downloads, so it is not a setting)
KARTOGRAF_UPDATE_MODES: Final[tuple[str, ...]] = ("local", "upgrade", "force")

# Folder names of the two tool stores inside the folder chosen in ``config init``
KARTOGRAF_STORE_NAME: Final = "kartograf"
IMGWTOOLS_STORE_NAME: Final = "imgw"

_TRUE_WORDS: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_WORDS: Final = frozenset({"0", "false", "no", "off"})
_THRESHOLD_WANTS: Final = "must be a number in (0, 1] or auto"


def default_data_dir() -> Path:
    """Return the user data folder of ``nogat`` for this system (``platformdirs``)."""
    return Path(platformdirs.user_data_path(APP))


def default_cache_dir() -> Path:
    """Return the user cache folder of ``nogat`` for this system (``platformdirs``)."""
    return Path(platformdirs.user_cache_path(APP))


@dataclass(frozen=True)
class Key:
    """One setting: its dotted name, the kind of value and its default.

    ``default`` is ``None`` for a setting without a default (the model server and
    the optional keys); it gets the environment for the settings that follow a
    directory (``data_dir``, ``cache_dir``).
    """

    name: str
    kind: Kind
    allowed: tuple[str, ...] = ()
    shared: bool = False
    default: Callable[["Environment"], object] | None = None

    @property
    def variable(self) -> str:
        """The variable of the tool: ``RETMAN_`` and the key in capitals."""
        return PREFIX + self.name.upper().replace(".", "_")


def _in_data(*parts: str) -> Callable[["Environment"], Path]:
    return lambda env: env.data_dir.joinpath(*parts)


def _in_cache(*parts: str) -> Callable[["Environment"], Path]:
    return lambda env: env.cache_dir.joinpath(*parts)


# Where the files of Retman and of the tools go when no setting says otherwise
KARTOGRAF_STORE = _in_data(KARTOGRAF_STORE_NAME)
KARTOGRAF_CACHE = _in_cache(KARTOGRAF_STORE_NAME, "metadata.db")
IMGWTOOLS_STORE = _in_data(IMGWTOOLS_STORE_NAME)
IMGWTOOLS_REFERENCE = _in_cache(IMGWTOOLS_STORE_NAME, "reference")
COLLECT_PATH = _in_data(TOOL, "collected.jsonl")

KEYS: Final[tuple[Key, ...]] = (
    Key("lang", "choice", LANGUAGES, shared=True, default=lambda _: "pl"),
    Key("log_level", "choice", LOG_LEVELS, shared=True, default=lambda _: "warning"),
    Key("data_dir", "path", shared=True, default=lambda _: default_data_dir()),
    Key("cache_dir", "path", shared=True, default=lambda _: default_cache_dir()),
    Key("decision.backend", "choice", DECISION_BACKENDS),
    Key("decision.url", "text"),
    Key("decision.model", "text"),
    Key("decision.timeout_s", "number"),
    Key("decision.api_key_env", "text"),
    Key("decision.confidence", "choice", CONFIDENCE_SETTINGS),
    Key("decision.consistency_runs", "integer"),
    Key("decision.thresholds.operation", "threshold"),
    Key("decision.thresholds.parameter", "threshold"),
    Key("text.backend", "choice", TEXT_BACKENDS, default=lambda _: "none"),
    Key("output.results_dir", "folder", default=lambda _: "retman-output"),
    Key("adapters.enabled", "names"),
    Key("tools.kartograf.store_dir", "path", default=KARTOGRAF_STORE),
    Key("tools.kartograf.cache_file", "path", default=KARTOGRAF_CACHE),
    Key("tools.kartograf.workers", "integer", default=lambda _: 4),
    Key(
        "tools.kartograf.update",
        "choice",
        KARTOGRAF_UPDATE_MODES,
        default=lambda _: "local",
    ),
    Key("tools.imgwtools.store_dir", "path", default=IMGWTOOLS_STORE),
    Key("tools.imgwtools.reference_data_dir", "path", default=IMGWTOOLS_REFERENCE),
    Key("log.journal_commands", "flag", default=lambda _: True),
    Key("privacy.collect_commands", "flag", default=lambda _: False),
    Key("privacy.collect_path", "path", default=COLLECT_PATH),
)
"""Every setting of Retman, in the order of ``config show``."""

BY_NAME: Final = {key.name: key for key in KEYS}


@dataclass(frozen=True)
class ConfigFile:
    """The user's ``nogat.toml``, read once.

    ``sections`` holds the tables ``nogat`` and ``retman`` that the file has (the
    tables of other tools are not read); ``problem`` names why the file cannot be
    used (``missing_file`` for a file named by ``--config`` or ``NOGAT_CONFIG``
    that does not exist, ``unreadable_file``, ``invalid_toml``, ``invalid_section``)
    and ``error`` says it in words. A missing default file is no problem.
    """

    path: Path
    source: FileSource
    exists: bool
    sections: Mapping[str, Mapping[str, Any]]
    problem: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class Found:
    """A setting found outside the built-in default.

    ``value`` is the raw value (the text of a variable, the TOML value of a file, the
    value of an option), ``name`` the option (``--lang``), the variable
    (``RETMAN_DECISION_URL``) or the table (``[retman.decision]``).
    """

    value: Any
    source: Literal["env", "file", "option"]
    name: str


@dataclass(frozen=True)
class Setting:
    """One setting with the layer that gave its value.

    ``value`` is typed by the kind of the key (``Path``, ``str``, ``bool``, ``int``,
    ``float``, ``"auto"`` for a threshold, a tuple of names) and ``None`` when
    nothing sets a key that has no default. A given value that cannot be used is
    dropped: the setting has the default, ``error`` says why and ``given`` is what
    was dropped.
    """

    value: Any
    source: SettingSource
    name: str | None
    error: str | None = None
    given: Found | None = None


@dataclass(frozen=True)
class OptionValue:
    """The value of a setting given by a command-line option, and the option's name."""

    value: Any
    flag: str


def read_config_file(
    path: Path | None = None, environ: Mapping[str, str] | None = None
) -> ConfigFile:
    """Read ``nogat.toml`` of ``--config``, of ``NOGAT_CONFIG`` or the default one.

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.

    Returns
    -------
    ConfigFile
        The file and its tables; when it cannot be used the tables are empty and
        ``problem`` says why.
    """
    variables = os.environ if environ is None else environ
    source: FileSource
    if path is not None:
        target, source = path.expanduser(), "option"
    elif variables.get(CONFIG_ENV):
        target, source = Path(variables[CONFIG_ENV]).expanduser(), "NOGAT_CONFIG"
    else:
        target = Path(platformdirs.user_config_path(APP)) / CONFIG_FILENAME
        source = "default"

    def unusable(problem: str, error: str, *, exists: bool) -> ConfigFile:
        return ConfigFile(target, source, exists, {}, problem, error)

    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        # A missing default file is the normal case; a named one is a mistake
        if source == "default":
            return ConfigFile(target, source, False, {})
        return unusable("missing_file", "the file does not exist", exists=False)
    except UnicodeDecodeError:
        return unusable("unreadable_file", "the file is not UTF-8 text", exists=True)
    except OSError as error:
        reason = f"the file cannot be read: {error.strerror or error}"
        return unusable("unreadable_file", reason, exists=True)
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        reason = f"the file is not valid TOML: {error}"
        return unusable("invalid_toml", reason, exists=True)
    sections: dict[str, Mapping[str, Any]] = {}
    for name in (APP, TOOL):
        if name not in document:
            continue
        table = document[name]
        if not isinstance(table, dict):
            return unusable("invalid_section", f"[{name}] is not a table", exists=True)
        sections[name] = table
    logger.debug("Read the settings file %s", target)
    return ConfigFile(target, source, True, sections)


class _Invalid(ValueError):
    """A given value cannot be used; the text says what the setting wants."""


def _text(raw: object) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise _Invalid("must be a text")
    return raw.strip()


def _positive(
    raw: object, kind: type[int] | type[float], wants: str, *, parse: bool
) -> float:
    """Return ``raw`` as a positive finite number (a whole one for ``int``)."""
    if isinstance(raw, bool):
        raise _Invalid(wants)
    if parse and isinstance(raw, str):
        try:
            raw = kind(raw.strip())
        except ValueError:
            raise _Invalid(wants) from None
    if not isinstance(raw, int | float) or (kind is int and not isinstance(raw, int)):
        raise _Invalid(wants)
    if not math.isfinite(raw) or raw <= 0:
        raise _Invalid(wants)
    return raw


def _coerce(key: Key, raw: object, *, parse: bool) -> object:
    """Return ``raw`` as the value of ``key``.

    ``parse`` is true for the text of a variable, which is parsed to the kind of the
    key; a value of the file must already have it.

    Raises
    ------
    _Invalid
        ``raw`` is not valid for the key.
    """
    match key.kind:
        case "choice":
            choice = _text(raw).lower()
            if choice not in key.allowed:
                raise _Invalid(f"must be one of {', '.join(key.allowed)}")
            return choice
        case "text":
            return _text(raw)
        case "path":
            path = Path(_text(raw)).expanduser()
            if not path.is_absolute() or ".." in path.parts:
                # A relative one would depend on the folder Retman is started in
                raise _Invalid("must be an absolute path without ..")
            return path
        case "folder":
            folder = Path(_text(raw))
            if folder.is_absolute() or folder.drive or ".." in folder.parts:
                # Results belong to the project folder (ARCHITECTURE 5.1)
                raise _Invalid("must be a relative folder name inside the project")
            return str(folder)
        case "number":
            return float(
                _positive(raw, float, "must be a positive number", parse=parse)
            )
        case "integer":
            return int(
                _positive(raw, int, "must be a positive whole number", parse=parse)
            )
        case "flag":
            if parse and isinstance(raw, str):
                word = raw.strip().lower()
                if word in _TRUE_WORDS | _FALSE_WORDS:
                    return word in _TRUE_WORDS
            elif isinstance(raw, bool):
                return raw
            raise _Invalid("must be true or false")
        case "threshold":
            if isinstance(raw, str) and raw.strip().lower() == "auto":
                return "auto"
            try:
                fraction = float(_positive(raw, float, _THRESHOLD_WANTS, parse=parse))
            except _Invalid:
                raise _Invalid(_THRESHOLD_WANTS) from None
            if fraction > 1:
                raise _Invalid(_THRESHOLD_WANTS)
            return fraction
        case "names":
            names = raw
            if parse and isinstance(raw, str):
                names = [part.strip() for part in raw.split(",")]
            if not isinstance(names, list) or not all(
                isinstance(name, str) and name for name in names
            ):
                raise _Invalid("must be a list of names")
            return tuple(names)
    raise AssertionError(key.kind)  # pragma: no cover


class Environment:
    """The sources of the settings: options, ``nogat.toml`` and the environment.

    :meth:`setting` resolves one key by the order of DEV-18.1 and remembers it.
    ``options`` maps a key to the value of the command-line option that sets it
    (:func:`cli_options`).
    """

    def __init__(
        self,
        file: ConfigFile,
        environ: Mapping[str, str],
        options: Mapping[str, OptionValue] | None = None,
    ) -> None:
        self.file = file
        self._environ = environ
        self._options = options or {}
        self._settings: dict[str, Setting] = {}

    @property
    def environ(self) -> Mapping[str, str]:
        """The process environment the settings are read from."""
        return self._environ

    @property
    def data_dir(self) -> Path:
        """The parent of the data stores (``data_dir``)."""
        return cast(Path, self.setting("data_dir").value)

    @property
    def cache_dir(self) -> Path:
        """The parent of the caches (``cache_dir``)."""
        return cast(Path, self.setting("cache_dir").value)

    def lookup(self, key: Key) -> Found | None:
        """Find ``key`` in the options, variables and file, in the order of DEV-18.1.

        Returns
        -------
        Found or None
            The first layer that holds a non-empty value, or ``None`` for the
            built-in default.
        """
        if (option := self._options.get(key.name)) is not None:
            return Found(option.value, "option", option.flag)
        variables = [key.variable]
        if key.shared:
            variables.append(SHARED_PREFIX + key.name.upper())
        for variable in variables:
            if value := self._environ.get(variable, "").strip():
                return Found(value, "env", variable)
        parent = key.name.rpartition(".")[0]
        for table in (TOOL, APP) if key.shared else (TOOL,):
            node: Any = self.file.sections.get(table)
            for part in key.name.split("."):
                node = node.get(part) if isinstance(node, Mapping) else None
            if node is not None and node != "":
                where = f"{table}.{parent}" if parent else table
                return Found(node, "file", f"[{where}]")
        return None

    def setting(self, name: str) -> Setting:
        """Resolve one setting.

        Parameters
        ----------
        name : str
            A dotted key of :data:`KEYS`.

        Raises
        ------
        KeyError
            ``name`` is no setting of Retman.
        """
        known = self._settings.get(name)
        if known is not None:
            return known
        key = BY_NAME[name]
        default = key.default(self) if key.default is not None else None
        found = self.lookup(key)
        if found is None:
            result = Setting(default, "default", None)
        else:
            try:
                value = _coerce(key, found.value, parse=found.source == "env")
                result = Setting(value, found.source, found.name)
            except _Invalid as why:
                short = name.rpartition(".")[2]
                label = (
                    found.name if found.source != "file" else f"{found.name} {short}"
                )
                result = Setting(default, "default", None, f"{label}: {why}", found)
        self._settings[name] = result
        return result


def cli_options(
    *, lang: str | None = None, verbose: bool = False, quiet: bool = False
) -> dict[str, OptionValue]:
    """Return the settings that the options of a command line give (DEV-18.1).

    Parameters
    ----------
    lang : str, optional
        ``--lang``: the language of the human-readable output (``pl`` or ``en``).
    verbose, quiet : bool, optional
        ``--verbose`` sets ``log_level`` to ``debug``, ``--quiet`` to ``error``;
        they exclude each other.

    Returns
    -------
    dict
        ``lang`` and ``log_level`` by the options that were given.

    Raises
    ------
    UsageError
        Both ``verbose`` and ``quiet`` are given.
    """
    if verbose and quiet:
        raise UsageError(
            "--verbose and --quiet exclude each other",
            details={"reason": "exclusive_options", "options": ["verbose", "quiet"]},
            hint="Give --verbose or --quiet, not both.",
        )
    options: dict[str, OptionValue] = {}
    if lang is not None:
        options["lang"] = OptionValue(lang, "--lang")
    if verbose:
        options["log_level"] = OptionValue("debug", "--verbose")
    if quiet:
        options["log_level"] = OptionValue("error", "--quiet")
    return options


def environment(
    path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    options: Mapping[str, OptionValue] | None = None,
) -> Environment:
    """Read the file and the environment once; see :class:`Environment`.

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.
    options : Mapping[str, OptionValue], optional
        The settings given by command-line options (:func:`cli_options`).
    """
    variables = os.environ if environ is None else environ
    return Environment(read_config_file(path, variables), variables, options)

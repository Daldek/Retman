"""``retman config show``: the settings in force and where each comes from (DEV-18.6).

The report works with a settings file that cannot be used: it says so
(``config_file.error``) instead of raising, so that it can be used to repair the
file. It shows what the environment and ``nogat.toml`` give; the command-line options
of a call apply to that call only. Credentials are reported as ``present`` or
``missing``, never by value (DEV-18.4).
"""

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from retman import __version__
from retman.environment import (
    BY_NAME,
    KEYS,
    TOOL,
    Environment,
    FileSource,
    Setting,
    SettingSource,
    environment,
)
from retman.i18n.loader import Texts
from retman.stores import tree_size

SCHEMA: Final = "retman-config/1"
# A key of the file that no setting uses and whose name asks for a secret is said
# to be a credential: those come from the environment only
_CREDENTIAL_WORDS: Final = ("key", "token", "secret", "password", "credential")
_STORES: Final = {
    "kartograf": "tools.kartograf.store_dir",
    "imgwtools": "tools.imgwtools.store_dir",
}


@dataclass(frozen=True)
class IgnoredKey:
    """A key of ``[retman]`` that no setting uses (``config_file.ignored``)."""

    key: str
    reason: Literal["credential", "unknown"]


@dataclass(frozen=True)
class FileInfo:
    """The settings file as ``config show`` reports it."""

    path: Path
    source: FileSource
    exists: bool
    error: str | None
    ignored: tuple[IgnoredKey, ...]


@dataclass(frozen=True)
class StoreInfo:
    """A store root with its source and size (DEV-18.6).

    ``root`` is ``None`` for Retman's own store: it keeps none (the tools keep
    theirs, :attr:`ConfigReport.stores`). ``size_bytes`` counts the files below the
    root, a hard-linked file once, and is ``None`` while the folder does not exist.
    """

    root: Path | None
    source: SettingSource | None
    name: str | None
    exists: bool
    size_bytes: int | None


@dataclass(frozen=True)
class ConfigReport:
    """The settings in force (``retman-config/1``).

    ``keys`` maps each dotted key to its :class:`~retman.environment.Setting`;
    ``credentials`` the variable that holds the key of an external model provider
    (named by ``decision.api_key_env``) to ``present`` or ``missing``; ``store`` is
    Retman's own store (none), ``stores`` the stores of the tools it drives.
    """

    version: str
    config_file: FileInfo
    keys: Mapping[str, Setting]
    credentials: Mapping[str, Literal["present", "missing"]]
    store: StoreInfo
    stores: Mapping[str, StoreInfo]

    def to_dict(self) -> dict[str, Any]:
        """Return the document of ``retman-config/1`` as plain JSON values."""
        file = self.config_file
        return {
            "schema": SCHEMA,
            "tool": TOOL,
            "version": self.version,
            "config_file": {
                "path": str(file.path),
                "source": file.source,
                "exists": file.exists,
                "error": file.error,
                "ignored": [
                    {"key": item.key, "reason": item.reason} for item in file.ignored
                ],
            },
            "keys": {
                name: {
                    "value": _jsonable(setting.value),
                    "source": setting.source,
                    "name": setting.name,
                    "error": setting.error,
                }
                for name, setting in self.keys.items()
            },
            "credentials": dict(self.credentials),
            "store": _store_dict(self.store),
            "stores": {tool: _store_dict(info) for tool, info in self.stores.items()},
        }

    def to_json(self) -> str:
        """Return the document as indented JSON text."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


def _jsonable(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _store_dict(info: StoreInfo) -> dict[str, Any]:
    return {
        "root": None if info.root is None else str(info.root),
        "source": info.source,
        "name": info.name,
        "exists": info.exists,
        "size_bytes": info.size_bytes,
    }


def _leaves(table: Mapping[str, Any], prefix: str = "") -> Iterator[str]:
    """Yield the dotted names of the keys of a table, descending into sub-tables."""
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping) and name not in BY_NAME:
            yield from _leaves(value, f"{name}.")
        else:
            yield name


def _ignored(env: Environment) -> tuple[IgnoredKey, ...]:
    ignored: list[IgnoredKey] = []
    for name in _leaves(env.file.sections.get(TOOL, {})):
        if name in BY_NAME:
            continue
        secret = any(
            word in name.rpartition(".")[2].lower() for word in _CREDENTIAL_WORDS
        )
        ignored.append(IgnoredKey(name, "credential" if secret else "unknown"))
    return tuple(ignored)


def _store(env: Environment, key: str) -> StoreInfo:
    setting = env.setting(key)
    root = Path(setting.value)
    exists = root.is_dir()
    return StoreInfo(
        root=root,
        source=setting.source,
        name=setting.name,
        exists=exists,
        size_bytes=tree_size(root) if exists else None,
    )


def get_config(
    path: Path | None = None, *, environ: Mapping[str, str] | None = None
) -> ConfigReport:
    """Report the settings in force and where each comes from (DEV-18.6).

    Parameters
    ----------
    path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    environ : Mapping[str, str], optional
        The process environment; ``os.environ`` by default.

    Returns
    -------
    ConfigReport
        ``config_file``, every key with its value and source, ``credentials``
        and the roots of the stores with their sizes. A file that cannot be used,
        or a value that cannot be used, is reported, not raised.
    """
    env = environment(path, environ)
    file = env.file
    key_name = env.setting("decision.api_key_env").value
    credentials: dict[str, Literal["present", "missing"]] = {}
    if key_name is not None:
        credentials[key_name] = "present" if env.environ.get(key_name) else "missing"
    return ConfigReport(
        version=__version__,
        config_file=FileInfo(
            file.path, file.source, file.exists, file.error, _ignored(env)
        ),
        keys={key.name: env.setting(key.name) for key in KEYS},
        credentials=credentials,
        store=StoreInfo(None, None, None, False, None),
        stores={tool: _store(env, key) for tool, key in _STORES.items()},
    )


def _size_text(size: int) -> str:
    amount = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024:
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TiB"


def _value_text(value: object, texts: Texts) -> str:
    if value is None:
        return texts.get("config_show.unset")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return ", ".join(value)
    return str(value)


def _source_text(setting: Setting, texts: Texts) -> str:
    if setting.source == "default" or setting.name is None:
        return texts.get("config_show.source_default")
    return texts.get(f"config_show.source_{setting.source}", name=setting.name)


def render_config(report: ConfigReport, texts: Texts) -> str:
    """Render the report for the terminal in the language of ``texts``."""
    file = report.config_file
    state = "file_exists" if file.exists else "file_missing"
    lines = [
        texts.get("config_show.title", version=report.version),
        texts.get(
            "config_show.file",
            path=file.path,
            source=texts.get(f"config_show.file_source_{file.source}"),
            state=texts.get(f"config_show.{state}"),
        ),
    ]
    if file.error:
        lines.append(texts.get("config_show.file_error", error=file.error))
    for item in file.ignored:
        lines.append(
            texts.get(
                f"config_show.ignored_{item.reason}", name=item.key, path=file.path
            )
        )
    lines += ["", texts.get("config_show.settings")]
    for name, setting in report.keys.items():
        line = texts.get(
            "config_show.setting",
            name=name,
            value=_value_text(setting.value, texts),
            source=_source_text(setting, texts),
        )
        lines.append(line)
        if setting.error:
            lines.append(texts.get("config_show.setting_error", error=setting.error))
    lines += ["", texts.get("config_show.credentials")]
    if report.credentials:
        for name, state in report.credentials.items():
            lines.append(
                texts.get(
                    "config_show.credential",
                    name=name,
                    state=texts.get(f"config_show.credential_{state}"),
                )
            )
    else:
        lines.append(texts.get("config_show.no_credentials"))
    lines += ["", texts.get("config_show.stores")]
    for tool, info in report.stores.items():
        assert info.root is not None
        if info.exists and info.size_bytes is not None:
            state_text = texts.get(
                "config_show.store_exists", size=_size_text(info.size_bytes)
            )
        else:
            state_text = texts.get("config_show.store_missing")
        lines.append(
            texts.get("config_show.store", tool=tool, root=info.root, state=state_text)
        )
    return "\n".join(lines) + "\n"

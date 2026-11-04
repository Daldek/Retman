"""Reader of Hydrolog's command catalog (``list_commands``, ``command_schema``)."""

import importlib
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

from retman.devtools.model import (
    CommandInfo,
    OptionInfo,
    Reader,
    ToolCatalog,
    Verdict,
)

# Document schemas the Hydrolog client of Retman understands: the domain documents of
# the commands its operations run, which ``run_command`` wraps in the
# ``hydrolog-result/1`` envelope
KNOWN_SCHEMAS = (
    "hydrolog-result/1",
    "hydrolog-tc-watershed/1",
    "hydrolog-scs-effective/1",
    "hydrolog-precip-hietogram/1",
    "hydrolog-hydrograph-generate/1",
    "hydrolog-stats-flood-frequency/1",
    "hydrolog-morphometry-watershed/1",
)

# Groups of commands about Hydrolog itself, not computations an operation is expected
# to offer: the catalog, the settings and the web interface
_META_GROUPS = frozenset({"commands", "config", "gui"})
# The plan option of a writing command, which the client owns (``check_command``)
_CHECK = "check"


def _enum(prop: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return the allowed values of an option as text, or ``None`` for free form."""
    values = prop.get("enum")
    return tuple(str(item["value"]) for item in values) if values else None


def _kind(prop: Mapping[str, Any]) -> str:
    """Return the type label of an option: ``path`` for a path, else the JSON type."""
    return "path" if prop.get("path_role") else str(prop["type"])


def _minimum(prop: Mapping[str, Any]) -> float | None:
    value = prop.get("min", prop.get("exclusive_minimum"))
    return None if value is None else float(value)


def _maximum(prop: Mapping[str, Any]) -> float | None:
    value = prop.get("max", prop.get("exclusive_maximum"))
    return None if value is None else float(value)


def _example_options(hydrolog: ModuleType, call: str) -> Mapping[str, object] | None:
    """Return the options of an example command line; ``None`` if it does not parse."""
    try:
        options: Mapping[str, object] = hydrolog.parse_command(call).options
    except hydrolog.HydrologError:
        return None
    return options


def read_catalog() -> ToolCatalog:
    """Hydrolog's catalog: every command with its options and effects.

    The command layer (``validate_command``, ``run_command``) takes every command of
    the catalog, so every command is ``runnable``; a command is ``data`` unless it is
    about Hydrolog itself (``commands``, ``config``, ``gui``): a computation is what an
    operation offers even though it reads and writes nothing.
    """
    hydrolog = importlib.import_module("hydrolog")
    listed = hydrolog.list_commands().to_dict()
    entries = {
        row["name"]: hydrolog.command_schema(row["name"]).to_dict()["commands"][0]
        for row in listed["commands"]
    }
    commands: dict[str, CommandInfo] = {}
    for name, entry in entries.items():
        effects = entry["effects"]
        group = name.split()[0]
        commands[name] = CommandInfo(
            id=name,
            group=group,
            summary=str(entry["summary"]),
            options=tuple(
                OptionInfo(
                    name=prop["name"],
                    required=bool(prop["required"]),
                    allowed=_enum(prop),
                    kind=_kind(prop),
                    default=prop.get("default"),
                    minimum=_minimum(prop),
                    maximum=_maximum(prop),
                    description=str(prop["description"]),
                )
                for prop in entry["options"]
                if prop["name"] != _CHECK
            ),
            network=bool(effects["network"]),
            writes=effects["writes"] != "none",
            data=group not in _META_GROUPS,
            result_schema=str(entry["result"]["schema"]),
            check_schema="hydrolog-result/1" if entry["check"] else "",
            examples=tuple(
                options
                for example in entry["examples"]
                if (options := _example_options(hydrolog, example["call"])) is not None
            ),
        )
    return ToolCatalog(
        tool="hydrolog",
        version=str(hydrolog.__version__),
        commands=commands,
        error_codes=tuple(
            sorted({code for entry in entries.values() for code in entry["errors"]})
        ),
        known_schemas=KNOWN_SCHEMAS,
    )


def validate(command: str, options: Mapping[str, object]) -> Verdict:
    """Hydrolog's own offline validation (``validate_command``)."""
    hydrolog = importlib.import_module("hydrolog")
    try:
        hydrolog.validate_command(command, **options)
    except hydrolog.HydrologError as error:
        details = dict(error.details)
        allowed = details.get("allowed")
        option = details.get("option")
        return Verdict(
            ok=False,
            option=option if isinstance(option, str) else None,
            allowed=tuple(str(value) for value in allowed) if allowed else None,
            detail=str(error),
        )
    return Verdict(ok=True)


def scratch_settings(root: Path) -> dict[str, Any]:
    """``[retman.tools.hydrolog]``: Hydrolog has no settings in Retman."""
    return {}


READER = Reader(read_catalog, validate, scratch_settings)

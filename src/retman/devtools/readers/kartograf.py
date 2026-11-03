"""Reader of Kartograf's command catalog (``list_commands``, ``command_schema``)."""

import importlib
import inspect
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

# Document schemas the Kartograf client of Retman understands: the domain documents of
# the commands its operations run, which ``run_command`` wraps in the
# ``kartograf-result/1`` envelope (a download and the marker ``store init`` writes),
# and the plan ``check_command`` puts into it
KNOWN_SCHEMAS = ("kartograf-download/1", "kartograf-store-init/1", "kartograf-plan/1")

# Error codes of the registry that a library client never meets
UNREACHABLE_ERRORS = {
    "forbidden": "only the MCP server raises it (a path outside --allow-dir, a write "
    "on a server that does not write)",
}

# The plan option of a command that has a plan, which is no argument of a function
_CHECK = "check"


def _run_options(kartograf: ModuleType) -> frozenset[str]:
    """Return the names a run takes besides the data options: store, plan, workers...

    The catalog lists every argument of the library function of a command; the
    arguments of ``run_command`` and ``check_command`` other than the command and its
    options (``root``, ``output_dir``, ``update``, ``plan``, ``workers``, ``summary``,
    ``force``, ``cache``...) are the environment of a call, which Retman's client owns,
    and the plan option ``check``.
    """
    names: set[str] = {_CHECK}
    for function in (kartograf.run_command, kartograf.check_command):
        names.update(inspect.signature(function).parameters)
    return frozenset(names - {"command", "options"})


def _enum(prop: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return the allowed values of an option as text, or ``None`` for free form."""
    values = prop.get("enum")
    return tuple(str(item["value"]) for item in values) if values else None


def _kind(prop: Mapping[str, Any]) -> str:
    """Return the type label of an option: ``path`` for a path, else the JSON type."""
    return "path" if prop.get("path_role") else str(prop["type"])


def _example_options(kartograf: ModuleType, call: str) -> Mapping[str, object] | None:
    """Return the options of an example command line; ``None`` if it does not parse."""
    try:
        options: Mapping[str, object] = kartograf.parse_command(call).options
    except kartograf.KartografError:
        return None
    return options


def read_catalog() -> ToolCatalog:
    """Kartograf's catalog: every command with its data options and effects.

    The command layer (``validate_command``, ``run_command``, ``check_command``) takes
    every command of the catalog; a command is ``data`` for the scaffold when its run
    has effects (``effects.read_only`` is false in ``command_schema``), so the source
    listings, the store reads, ``sheet`` and ``config show`` are not unused data
    commands. The check of a command is a plan.
    """
    kartograf = importlib.import_module("kartograf")
    listed = kartograf.list_commands().to_dict()
    entries = {
        row["name"]: kartograf.command_schema(row["name"]).to_dict()["commands"][0]
        for row in listed["commands"]
    }
    run_options = _run_options(kartograf)
    commands: dict[str, CommandInfo] = {}
    for name, entry in entries.items():
        effects = entry["effects"]
        has_plan = bool(entry["check"])
        commands[name] = CommandInfo(
            id=name,
            group=name.split()[0],
            summary=str(entry["summary"]),
            options=tuple(
                OptionInfo(
                    name=prop["name"],
                    required=bool(prop["required"]),
                    allowed=_enum(prop),
                    kind=_kind(prop),
                    default=prop.get("default"),
                    minimum=prop.get("min"),
                    maximum=prop.get("max"),
                    description=str(prop["description"]),
                )
                for prop in entry["options"]
                if prop["name"] not in run_options
            ),
            network=bool(effects["network"]),
            writes=effects["writes"] != "none",
            data=not effects["read_only"],
            result_schema=str(entry["result"]["schema"]),
            check_schema="kartograf-plan/1" if has_plan else "",
            examples=tuple(
                options
                for example in entry["examples"]
                if (options := _example_options(kartograf, example["call"])) is not None
            ),
        )
    return ToolCatalog(
        tool="kartograf",
        version=str(kartograf.__version__),
        commands=commands,
        error_codes=tuple(
            sorted({code for entry in entries.values() for code in entry["errors"]})
        ),
        unreachable_errors=UNREACHABLE_ERRORS,
        known_schemas=KNOWN_SCHEMAS,
    )


def validate(command: str, options: Mapping[str, object]) -> Verdict:
    """Kartograf's own offline validation (``validate_command``)."""
    kartograf = importlib.import_module("kartograf")
    try:
        kartograf.validate_command(command, options)
    except kartograf.KartografError as error:
        allowed = getattr(error, "allowed", None)
        return Verdict(
            ok=False,
            option=getattr(error, "option", None),
            options=tuple(getattr(error, "options", None) or ()),
            allowed=tuple(allowed) if allowed else None,
            detail=str(error),
        )
    return Verdict(ok=True)


def scratch_settings(root: Path) -> dict[str, Any]:
    """``[retman.tools.kartograf]`` in a scratch folder: nothing outside it is used."""
    return {
        "store_dir": str(root / "kartograf"),
        "cache_file": str(root / "kartograf-cache.db"),
        "workers": 1,
        "update": "local",
    }


READER = Reader(read_catalog, validate, scratch_settings)

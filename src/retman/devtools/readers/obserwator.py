"""Reader of Obserwator's command catalog (``command_schema``, Nogat commands-1)."""

import importlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retman.devtools.model import (
    CommandInfo,
    OptionInfo,
    Reader,
    ToolCatalog,
    Verdict,
)

# Document schemas the Obserwator client of Retman understands: the result
# envelope of ``run_command`` and the plan of ``check_command``
KNOWN_SCHEMAS = ("obserwator-result/1", "obserwator-plan/1")


def _enum(prop: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return the allowed values of an option or of its list items, as text.

    An option's ``enum`` is a list of ``{value, meaning}``; the items of a list
    option name their values in ``items.enum``.
    """
    values = prop.get("enum")
    if values is None and isinstance(prop.get("items"), dict):
        values = prop["items"].get("enum")
    if not values:
        return None
    return tuple(
        str(value["value"] if isinstance(value, dict) else value) for value in values
    )


def _kind(prop: Mapping[str, Any]) -> str:
    """Return the type label of an option: ``path``, ``date`` or the JSON type."""
    if prop.get("path_role"):
        return "path"
    if prop.get("format") == "date":
        return "date"
    return str(prop["type"])


def read_catalog() -> ToolCatalog:
    """Obserwator's catalog: every command with its options and effects."""
    obserwator = importlib.import_module("obserwator")
    document = obserwator.command_schema(lang="en")
    commands: dict[str, CommandInfo] = {}
    for entry in document["commands"]:
        effects = entry["effects"]
        options = tuple(
            OptionInfo(
                name=prop["name"],
                required=bool(prop["required"]),
                allowed=_enum(prop),
                kind=_kind(prop),
                default=prop.get("default"),
                minimum=prop.get("min"),
                maximum=prop.get("max"),
                description=str(prop.get("description", "")),
            )
            for prop in entry["options"]
        )
        commands[entry["name"]] = CommandInfo(
            id=entry["name"],
            group=str(entry.get("group") or entry["name"].split()[0]),
            summary=str(entry["summary"]),
            options=options,
            network=bool(effects["network"]),
            writes=effects["writes"] != "none",
            data=True,
            result_schema=str(entry["result"]["schema"]),
            check_schema="obserwator-plan/1" if entry["check"] else "",
        )
    registry = obserwator.ERROR_CODES
    return ToolCatalog(
        tool="obserwator",
        version=str(obserwator.__version__),
        commands=commands,
        error_codes=tuple(registry),
        # A code without an exit code belongs to the REST API only
        unreachable_errors={
            code: "only the REST API raises it (no command-line exit code)"
            for code, spec in registry.items()
            if spec.exit_code is None
        },
        known_schemas=KNOWN_SCHEMAS,
    )


def validate(command: str, options: Mapping[str, object]) -> Verdict:
    """Obserwator's own offline validation (``validate_command``)."""
    obserwator = importlib.import_module("obserwator")
    try:
        obserwator.validate_command(command, options=options)
    except obserwator.ObserwatorError as error:
        details = getattr(error, "details", None) or {}
        allowed = details.get("allowed")
        return Verdict(
            ok=False,
            option=details.get("option"),
            options=tuple(details.get("options") or ()),
            allowed=tuple(str(value) for value in allowed) if allowed else None,
            detail=str(error),
        )
    return Verdict(ok=True)


def scratch_settings(root: Path) -> dict[str, Any]:
    """``[retman.tools.obserwator]`` in a scratch folder: nothing outside it is used."""
    return {
        "store_dir": str(root / "obserwator"),
        "raw_store_dir": str(root / "obserwator-raw"),
        "reference_data_dir": str(root / "obserwator-reference"),
    }


READER = Reader(read_catalog, validate, scratch_settings)

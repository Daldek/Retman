"""Reader of IMGWTools' command catalog (``imgwtools.command_schema``, 3.x)."""

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

# Document schemas the IMGWTools client of Retman understands: the result
# envelope of ``run_command`` and the plan of ``check_command``
KNOWN_SCHEMAS = ("imgw-result/1", "imgw-plan/1")


def _enum(prop: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return the enumerated values of a JSON-Schema property or its array items."""
    values = prop.get("enum")
    if values is None and isinstance(prop.get("items"), dict):
        values = prop["items"].get("enum")
    return tuple(str(value) for value in values) if values else None


def _kind(prop: Mapping[str, Any]) -> str:
    """Return the tool's type label: ``path`` for ``x-imgw-type``, else the type."""
    if "x-imgw-type" in prop:
        return str(prop["x-imgw-type"])
    if prop.get("format") == "date":
        return "date"
    return str(prop.get("type", "enum" if "enum" in prop else ""))


def read_catalog() -> ToolCatalog:
    """IMGWTools' catalog: every command with its JSON-Schema options and effects."""
    imgwtools = importlib.import_module("imgwtools")
    document = imgwtools.command_schema(lang="en")
    commands: dict[str, CommandInfo] = {}
    for item in document["commands"]:
        meta = item["x-imgw"]
        required = set(item.get("required", ()))
        options = tuple(
            OptionInfo(
                name=name,
                required=name in required,
                allowed=_enum(prop),
                kind=_kind(prop),
                default=prop.get("default"),
                minimum=prop.get("minimum"),
                maximum=prop.get("maximum"),
                description=str(prop.get("description", "")),
            )
            for name, prop in item.get("properties", {}).items()
        )
        commands[meta["command"]] = CommandInfo(
            id=meta["command"],
            group=str(meta.get("group", "")),
            summary=str(item.get("description", "")),
            options=options,
            network=bool(meta.get("network")),
            writes=meta.get("writes", "none") != "none",
            data=True,
            result_schema=str(document["result_schema"]),
            check_schema="imgw-plan/1" if meta.get("check") else "",
        )
    registry = imgwtools.ERROR_CODES
    return ToolCatalog(
        tool="imgwtools",
        version=str(imgwtools.__version__),
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
    """IMGWTools' own offline validation (``validate_command``)."""
    imgwtools = importlib.import_module("imgwtools")
    try:
        imgwtools.validate_command(command, options=options)
    except imgwtools.IMGWError as error:
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
    """``[tools.imgwtools]`` below a scratch folder: nothing outside it is touched."""
    return {
        "store_dir": str(root / "imgwtools"),
        "reference_data_dir": str(root / "imgwtools-reference"),
    }


READER = Reader(read_catalog, validate, scratch_settings)

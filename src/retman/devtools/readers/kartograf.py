"""Reader of Kartograf's command catalog (``kartograf.get_catalog``, 0.8)."""

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

# Document schemas the Kartograf client of Retman understands: the data
# documents of the download commands and the plan of ``check_command``
KNOWN_SCHEMAS = ("kartograf-download/1", "kartograf-plan/1")

# Error codes of the registry that a library client never meets
UNREACHABLE_ERRORS = {
    "usage_error": "only the command-line parser raises it (parse_command)",
    "interrupted": "Ctrl-C reaches Retman as KeyboardInterrupt, not as an error",
    "terminated": "the SIGTERM of the command-line process",
}

# Effects of the catalog that change something on disk
_WRITING_EFFECTS = frozenset({"store_write", "project_write", "cache_delete"})


def read_catalog() -> ToolCatalog:
    """Kartograf's catalog: every command with its task options and effects."""
    kartograf = importlib.import_module("kartograf")
    catalog = kartograf.get_catalog(params=True, tables=True)
    data = {item.id for item in kartograf.data_commands()}
    commands: dict[str, CommandInfo] = {}
    for info in catalog.commands:
        options = tuple(
            OptionInfo(
                name=param.name,
                required=bool(param.required),
                allowed=tuple(param.allowed) if param.allowed else None,
                kind=str(param.kind),
                default=param.default,
                description=param.description or "",
            )
            # Environment arguments (store, workers, update...) are the client's
            for param in info.params
            if param.task
        )
        effects = set(info.effects)
        commands[info.id] = CommandInfo(
            id=info.id,
            group=info.group or "",
            summary=info.summary or "",
            options=options,
            network="network" in effects,
            writes=bool(effects & _WRITING_EFFECTS),
            data=info.id in data,
            result_schema=info.result_schema or "",
            check_schema=info.check_result_schema or "",
            examples=tuple(dict(example.options) for example in info.examples),
        )
    return ToolCatalog(
        tool="kartograf",
        version=str(kartograf.__version__),
        commands=commands,
        error_codes=tuple(item.code for item in catalog.errors),
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

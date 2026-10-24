"""Serialization of the command catalog: ``retman-commands/1`` and the command list.

``retman-commands/1`` is the catalog of Nogat's ``commands-1`` schema (AGI-2.4): the
documents returned by ``retman commands schema`` (one command, or all of them
page by page). ``retman-command-list/1`` is its short form, one line per command, for
discovery (AGI-1.5: catalog summary, then command schema, then the full guide).
"""

import base64
import binascii
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from retman import __version__
from retman._json import to_jsonable
from retman.catalog.spec import TOOL, Command, Option
from retman.exceptions import InvalidValueError
from retman.i18n.loader import Texts, load_core_texts

COMMANDS_SCHEMA: Final = "retman-commands/1"
"""Value of the ``schema`` key of the catalog document."""
COMMAND_LIST_SCHEMA: Final = "retman-command-list/1"
"""Value of the ``schema`` key of the command list."""

_STANDARD_TYPES: Final[Mapping[str, str]] = {
    "number": "number",
    "integer": "integer",
    "string": "string",
    "boolean": "boolean",
    "choice": "string",
    "string_list": "array",
    "path": "string",
}
_EXAMPLE_VALUES: Final = 3


@dataclass(frozen=True)
class Document:
    """A JSON document of the catalog with ``to_dict()`` and ``to_json()`` (AGI-4.4).

    Parameters
    ----------
    data : Mapping
        The document; it is JSON-compatible and has a ``schema`` key.
    """

    data: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of the document as a dictionary."""
        copied: dict[str, Any] = json.loads(json.dumps(self.data, allow_nan=False))
        return copied

    def to_json(self, indent: int | None = None) -> str:
        """Return the document as JSON text (UTF-8 characters are not escaped)."""
        return json.dumps(self.data, ensure_ascii=False, allow_nan=False, indent=indent)


# --- pagination -----------------------------------------------------------------------


def _decode_cursor(cursor: str | None, total: int) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, binascii.Error, UnicodeError):
        offset = -1
    if not 0 <= offset <= total:
        raise InvalidValueError(
            f"Option 'cursor': {cursor!r} is not a cursor of this collection",
            details={"reason": "invalid_cursor", "option": "cursor", "value": cursor},
            hint="Pass the next_cursor of the previous page unchanged.",
        )
    return offset


def paginate[T](
    items: Sequence[T], limit: int | None, cursor: str | None
) -> tuple[Sequence[T], dict[str, Any] | None]:
    """Return one page of ``items`` and its ``page`` document (AGI-4.2).

    Parameters
    ----------
    items : sequence
        The whole collection.
    limit : int or None
        Items per page (at least 1); ``None`` returns everything and no ``page``
        unless a ``cursor`` is given.
    cursor : str or None
        ``next_cursor`` of the previous page; ``None`` starts at the beginning.

    Returns
    -------
    tuple
        The page and ``{"total", "next_cursor", "truncated"}``, or ``None`` when the
        collection is not paginated.

    Raises
    ------
    InvalidValueError
        ``limit`` is below 1 or ``cursor`` is not one that a page returned.
    """
    if limit is None and cursor is None:
        return items, None
    if limit is not None and limit < 1:
        raise InvalidValueError(
            f"Option 'limit': must be >= 1, got {limit}",
            details={"reason": "minimum", "option": "limit", "minimum": 1},
        )
    total = len(items)
    start = _decode_cursor(cursor, total)
    end = total if limit is None else min(start + limit, total)
    truncated = end < total
    next_cursor = (
        base64.urlsafe_b64encode(str(end).encode("ascii")).decode("ascii")
        if truncated
        else None
    )
    page: dict[str, Any] = {"total": total, "truncated": truncated}
    if truncated:
        page["next_cursor"] = next_cursor
    return items[start:end], page


# --- catalog documents ----------------------------------------------------------------


def _example_values(command: Command, option: Option) -> list[Any]:
    values: list[Any] = []
    for example in command.examples:
        value = example.get(option.name)
        if value is None:
            continue
        converted = to_jsonable(value)
        if converted not in values:
            values.append(converted)
    return values[:_EXAMPLE_VALUES]


def _option_entry(command: Command, option: Option, polish: Texts) -> dict[str, Any]:
    """One entry of ``options`` (AGI-2.3)."""
    base = f"catalog.{command.operation_id}.options.{option.name}"
    entry: dict[str, Any] = {
        "name": option.name,
        "type": _STANDARD_TYPES[option.type],
    }
    if option.type == "string_list":
        entry["items"] = "string"
    if option.unit is not None:
        entry["unit"] = option.unit
    entry["required"] = option.required
    if option.default is not None:
        entry["default"] = to_jsonable(option.normalize(option.default))
    if option.type == "choice":
        entry["enum"] = [
            {"value": value, "meaning": option.meanings[value]}
            for value in option.choices
        ]
    if option.minimum is not None:
        entry["min"] = option.minimum
    if option.maximum is not None:
        entry["max"] = option.maximum
    if option.exclusive_minimum is not None:
        entry["exclusive_minimum"] = option.exclusive_minimum
    examples = _example_values(command, option)
    if examples:
        entry["examples"] = examples
    entry["description"] = option.description
    if option.one_of is not None:
        entry["one_of"] = option.one_of
    if option.path_role is not None:
        entry["path_role"] = option.path_role
    translated: dict[str, Any] = {"description": polish.get(f"{base}.description")}
    if option.type == "choice":
        translated["enum"] = {
            value: polish.get(f"{base}.meanings.{value}") for value in option.choices
        }
    entry["i18n"] = {"pl": translated}
    return entry


def command_entry(command: Command) -> dict[str, Any]:
    """Return the catalog entry of one command (Nogat ``commands-1`` ``command``).

    Parameters
    ----------
    command : Command
        The declaration.

    Returns
    -------
    dict
        ``name``, ``operation_id``, ``function``, ``summary``, ``description``,
        ``options``, ``result``, ``effects``, ``check``, ``rules``, ``examples``
        (``call`` and a ``result`` excerpt), ``errors`` and ``i18n`` (the Polish
        texts of the command and of its options).
    """
    polish = load_core_texts("pl")
    base = f"catalog.{command.operation_id}"
    effects = command.effects
    return {
        "name": command.name,
        "operation_id": command.operation_id,
        "function": command.function,
        "summary": command.summary,
        "description": command.description,
        "options": [_option_entry(command, item, polish) for item in command.options],
        "result": {
            "schema": command.result_schema,
            "cardinality": command.cardinality,
        },
        "effects": {
            "read_only": effects.read_only,
            "writes": effects.writes,
            "idempotent": effects.idempotent,
            "network": effects.network,
            "destructive": effects.destructive,
        },
        "check": command.check_command,
        "rules": list(command.rules),
        "examples": [
            {
                "call": command.command_line(example),
                "result": to_jsonable(dict(command.example_results[number])),
            }
            for number, example in enumerate(command.examples)
        ],
        "errors": list(command.errors),
        "i18n": {
            "pl": {
                "summary": polish.get(f"{base}.summary"),
                "description": polish.get(f"{base}.description"),
                "rules": polish.lines(f"{base}.rules") if command.rules else [],
            }
        },
    }


def catalog_document(commands: Iterable[Command]) -> dict[str, Any]:
    """Return the ``retman-commands/1`` document of ``commands``.

    Parameters
    ----------
    commands : iterable of Command
        The commands to describe, in catalog order.

    Returns
    -------
    dict
        ``{"schema", "tool", "version", "commands"}``.
    """
    return {
        "schema": COMMANDS_SCHEMA,
        "tool": TOOL,
        "version": __version__,
        "commands": [command_entry(command) for command in commands],
    }


def command_list(commands: Iterable[Command]) -> dict[str, Any]:
    """Return the ``retman-command-list/1`` document of ``commands``.

    Parameters
    ----------
    commands : iterable of Command
        The commands to list, in catalog order.

    Returns
    -------
    dict
        ``{"schema", "tool", "version", "commands"}`` with, per command, ``name``,
        ``operation_id``, ``summary`` and ``read_only``.
    """
    return {
        "schema": COMMAND_LIST_SCHEMA,
        "tool": TOOL,
        "version": __version__,
        "commands": [
            {
                "name": command.name,
                "operation_id": command.operation_id,
                "summary": command.summary,
                "read_only": command.effects.read_only,
            }
            for command in commands
        ],
    }

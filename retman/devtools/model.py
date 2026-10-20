"""The tool catalogs as the scaffold sees them: one neutral model, read per tool.

A *reader* (``retman/devtools/readers/<tool>.py``) turns a tool's own machine
catalog into a ``ToolCatalog``; everything else in ``retman.devtools`` is generic
and knows nothing about a particular tool.
"""

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retman.exceptions import RetmanError


class ScaffoldError(RetmanError):
    """A scaffold command cannot be carried out (unknown tool or command...)."""


@dataclass(frozen=True)
class OptionInfo:
    """One option of a catalog command, as the tool's own API takes it.

    ``allowed`` lists the enumerated values in the tool's form (``None``: free
    form); ``kind`` is the tool's own type label (``str``, ``int``, ``path``,
    ``bbox``, ``flag``...). ``minimum``/``maximum`` are numeric bounds the
    catalog states.
    """

    name: str
    required: bool = False
    allowed: tuple[str, ...] | None = None
    kind: str = ""
    default: object = None
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""


@dataclass(frozen=True)
class CommandInfo:
    """A catalog command: its options and what running it does.

    ``network`` and ``writes`` are the effects of a run; ``data`` tells whether
    ``validate_command``/``run_command`` take it (a command of the catalog such
    as a source listing is not a data command). ``examples`` are option sets the
    tool itself documents (seeds for ``retman-scaffold draft``).
    """

    id: str
    group: str = ""
    summary: str = ""
    options: tuple[OptionInfo, ...] = ()
    network: bool = False
    writes: bool = False
    data: bool = True
    result_schema: str = ""
    check_schema: str = ""
    examples: tuple[Mapping[str, object], ...] = ()

    def option(self, name: str) -> OptionInfo | None:
        """The option of that name, or ``None``."""
        return next((item for item in self.options if item.name == name), None)

    @property
    def effects(self) -> tuple[str, ...]:
        """The effects of a run (``network``, ``writes``); empty for a read."""
        return tuple(
            name
            for name, present in (("network", self.network), ("writes", self.writes))
            if present
        )


@dataclass(frozen=True)
class ToolCatalog:
    """What an installed tool's catalog offers, in one neutral shape.

    ``error_codes`` are the codes of the tool's error registry;
    ``unreachable_errors`` maps those a library client never meets (CLI usage,
    signals, REST-only) to the reason, so that they need no Retman text.
    ``known_schemas`` are the document schemas Retman's client understands.
    """

    tool: str
    version: str
    commands: Mapping[str, CommandInfo]
    error_codes: tuple[str, ...] = ()
    unreachable_errors: Mapping[str, str] = field(default_factory=dict)
    known_schemas: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    """The tool's offline verdict on a command, for ``retman-scaffold draft``.

    ``option``/``options`` name the options at fault, ``allowed`` what the tool
    would accept there (as in ``ToolError``).
    """

    ok: bool
    option: str | None = None
    options: tuple[str, ...] = ()
    allowed: tuple[str, ...] | None = None
    detail: str = ""


@dataclass(frozen=True)
class Reader:
    """The three things the scaffold needs from one tool, read lazily.

    ``read_catalog`` imports the tool and returns its catalog; ``validate`` is the
    tool's own offline validation (used by ``draft`` before any manifest exists);
    ``scratch_settings`` builds a ``[tools.<tool>]`` table below a scratch folder
    for the tool's client factory.
    """

    read_catalog: Callable[[], ToolCatalog]
    validate: Callable[[str, Mapping[str, object]], Verdict]
    scratch_settings: Callable[[Path], dict[str, Any]]


def load_reader(tool: str) -> Reader | None:
    """The reader of a tool (``retman.devtools.readers.<tool>``), if there is one.

    Nothing is imported from the tool itself here: the reader module imports it
    only when ``read_catalog`` or ``validate`` is called.
    """
    try:
        module = importlib.import_module(f"retman.devtools.readers.{tool}")
    except ModuleNotFoundError as error:
        if error.name == f"retman.devtools.readers.{tool}":
            return None
        raise
    reader: Reader = module.READER
    return reader

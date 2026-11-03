"""Common types of extractors: values read from text by code, never by a model."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from retman.adapters.catalog import CatalogCall, ToolDocument


@dataclass(frozen=True)
class Reading:
    """
    One possible interpretation of a fragment of the command.

    Parameters
    ----------
    value : Any
        Normalized, JSON-serializable value (str, int, float, list, dict).
    label_key : str
        Translation key in ``src/retman/i18n/pl.toml`` (section ``extractors``)
        describing this reading, used when Retman has to ask which one is meant.
    label_args : dict[str, str]
        Values used to format the label text.
    """

    value: Any
    label_key: str
    label_args: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Match:
    """
    A fragment of the text recognised by an extractor.

    One reading means the fragment is unambiguous; several readings mean Retman
    must ask which one is meant (ARCHITECTURE 6.1) — never pick silently.

    Parameters
    ----------
    start, end : int
        Position of the fragment in the text (``text[start:end]``).
    readings : tuple[Reading, ...]
        Possible interpretations, at least one.
    confirm : bool, optional
        The only reading is a fuzzy recognition (an inflected station name):
        Retman asks the user to confirm it instead of accepting it silently.
    """

    start: int
    end: int
    readings: tuple[Reading, ...]
    confirm: bool = False

    @property
    def ambiguous(self) -> bool:
        """Whether Retman must ask: several readings or one that needs confirming."""
        return len(self.readings) > 1 or self.confirm


class TextSource(Protocol):
    """Translated texts by dotted key; ``retman.i18n.loader.Texts`` fits."""

    def get(self, key: str, **args: object) -> str:
        """Text under ``key`` with ``{placeholders}`` filled from ``args``."""
        ...


@dataclass(frozen=True)
class Hint:
    """
    Why a required parameter got no usable reading, for the question about it.

    Parameters
    ----------
    key : str
        Translation key under ``extractors.hints`` in ``src/retman/i18n/pl.toml``.
    args : dict[str, str]
        Values used to format the text.
    """

    key: str
    args: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ExtractionContext:
    """
    Read-only facts that context-aware extractors may use; built by the pipeline.

    Extractors read only offline data: the tool is reached through ``lookup``
    (the tool client's offline catalog lookup), never over the network.

    Parameters
    ----------
    tool : str
        Tool of the operation being planned (manifest ``tool``).
    settings : Mapping[str, Any]
        The validated ``[retman.tools.<tool>]`` table of ``nogat.toml``.
    project_dir : Path
        Project folder.
    scope : Mapping[str, Any]
        Merged ``option_meta`` of the chosen options of the operation's choice
        parameters resolved so far (e.g. dataset provider, kind and variables).
    lookup : Callable[[CatalogCall], ToolDocument]
        Offline catalog lookup of the tool; raises ``RetmanError`` subclasses
        carrying the tool's error ``code``.
    today : date
        The current date, fixed per Retman instance so planning is reproducible.
    memo : dict[str, Any], optional
        Cache shared by the contexts of one planning pass (not part of equality).
    """

    tool: str
    settings: Mapping[str, Any]
    project_dir: Path
    scope: Mapping[str, Any]
    lookup: "Callable[[CatalogCall], ToolDocument]"
    today: date
    memo: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

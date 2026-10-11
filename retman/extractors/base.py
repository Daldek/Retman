"""Common types of extractors: values read from text by code, never by a model."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Reading:
    """
    One possible interpretation of a fragment of the command.

    Parameters
    ----------
    value : Any
        Normalized, JSON-serializable value (str, int, float, list, dict).
    label_key : str
        Translation key in ``retman/i18n/pl.toml`` (section ``extractors``)
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
    """

    start: int
    end: int
    readings: tuple[Reading, ...]

    @property
    def ambiguous(self) -> bool:
        """Whether the fragment has more than one reading."""
        return len(self.readings) > 1

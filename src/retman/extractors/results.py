"""Recognise numbered project result references in a user's command."""

import re
from typing import Any

from retman.extractors.base import Match, Reading

_RESULT_RE = re.compile(
    r"(?<![\w#])(?:\#(?P<hash>[1-9][0-9]*)|"
    r"wynik(?:u|iem|owi|i)?\s+(?:nr\s*)?\#?(?P<word>[1-9][0-9]*))\b",
    re.IGNORECASE,
)


def extract_result_refs(text: str) -> list[Match]:
    """
    Read ``#N``, ``wynik N`` and ``wyniku nr N`` references.

    Parameters
    ----------
    text : str
        User command or answer.

    Returns
    -------
    list[Match]
        Positive result numbers in order of appearance.
    """
    matches = []
    for found in _RESULT_RE.finditer(text):
        number = int(found.group("hash") or found.group("word"))
        matches.append(
            Match(
                found.start(),
                found.end(),
                (
                    Reading(
                        number,
                        "extractors.result.number",
                        {"number": str(number)},
                    ),
                ),
            )
        )
    return matches


def validate_result(value: Any) -> str | None:
    """Reject non-positive or non-integer project result numbers."""
    return (
        None if type(value) is int and value > 0 else "extractors.errors.invalid_result"
    )

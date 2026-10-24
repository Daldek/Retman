"""Names the user gives to things in a project, e.g. an IMGW project task.

The tool accepts only a strict spelling (``^[a-z0-9][a-z0-9_-]{0,63}$``), and a
name is not silently "fixed": the user's spelling is read as written and the
validator rejects what the tool would reject, with the rule in the message.
Ordinary words after "zadanie" are prose ("dodaj zadanie pobierania opadów"), so
a name is read only when it is quoted, follows an explicit cue ("o nazwie",
"nazwij") or looks like an identifier (``opady_poznan``).
"""

import re
from typing import Any

from retman.extractors.base import Match, Reading
from retman.extractors.text import fold

IDENTIFIER_PATTERN = r"[a-z0-9][a-z0-9_-]{0,63}"
_IDENTIFIER_RE = re.compile(IDENTIFIER_PATTERN)
_QUOTED_RE = re.compile(r"[\"„“«'](?P<name>[^\"”“»'\s]{1,80})[\"”“»']")
_NAME = r"[\"„“«']?(?P<name>[^\s\"”“»',;:!?]+)"
# On folded text, so the cues match without Polish letters ("nazwą")
_EXPLICIT_RE = re.compile(
    r"(?<!\w)(?:(?:o|pod)\s+nazw\w*|nazwa\s+zadani\w*|nazwij(?:\s+(?:je|to|zadanie))?"
    rf"|nazwac(?:\s+(?:je|to|zadanie))?)\s+{_NAME}"
)
_TASK_RE = re.compile(rf"(?<!\w)zadani\w*\s+(?:(?:o|pod)\s+nazw\w*\s+)?{_NAME}")


def extract_identifiers(text: str) -> list[Match]:
    """
    Names of project tasks: quoted, after "o nazwie"/"nazwij", or identifier-like.

    A quoted word with the shape of an identifier counts without a cue (it
    cannot be a station name or a path). After an explicit cue the word is read as
    written even when it breaks the rules, so ``validate_identifier`` can say why.
    After "zadanie" only a word that contains ``_``, ``-`` or a digit is a name.

    Parameters
    ----------
    text : str
        Command or answer.

    Returns
    -------
    list[Match]
        Values are the names (str); a name written twice is reported once.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_identifiers(
    ...     'Dodaj zadanie "opady" do projektu')]
    ['opady']
    >>> [m.readings[0].value for m in extract_identifiers(
    ...     "usuń zadanie przeplywy-warta")]
    ['przeplywy-warta']
    >>> extract_identifiers("dodaj zadanie pobierania opadów")
    []
    """
    found: dict[str, Match] = {}
    for hit in _QUOTED_RE.finditer(text):
        name = hit.group("name")
        if _IDENTIFIER_RE.fullmatch(name):
            found.setdefault(name, _match(hit.start(), hit.end(), name))
    folded = fold(text)
    for pattern, identifier_like in ((_EXPLICIT_RE, False), (_TASK_RE, True)):
        for hit in pattern.finditer(folded):
            # Cues were matched on folded text; the name is read as typed
            start, end = hit.span("name")
            name = text[start:end].rstrip(".")
            if not name:
                continue
            if identifier_like and not re.search(r"[0-9_-]", name):
                continue
            found.setdefault(name, _match(start, start + len(name), name))
    return sorted(found.values(), key=lambda match: match.start)


def read_identifier_answer(text: str) -> list[Match]:
    """Answer about the name: a single word, trimmed of quotes, is the name."""
    name = text.strip().strip("\"'„”“«»").strip()
    if not name or re.search(r"\s", name):
        return extract_identifiers(text)
    return [_match(0, len(text), name)]


def _match(start: int, end: int, name: str) -> Match:
    return Match(
        start,
        end,
        (Reading(name, "extractors.identifier.name", {"name": name}),),
    )


def validate_identifier(value: Any) -> str | None:
    """Return the translation key of the problem with a task name, or None."""
    if isinstance(value, str) and _IDENTIFIER_RE.fullmatch(value):
        return None
    return "extractors.errors.invalid_identifier"

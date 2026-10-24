"""Place names that become search fragments for the tool's station search.

IMGWTools searches station names by a case- and diacritics-insensitive fragment,
so a Polish inflected form ("na Wiśle", "w Poznaniu") must be reduced to a stem
that is still a part of the nominative. The synoptic ``station_name`` option is
a plain case-insensitive fragment: it keeps the user's letters, only the ending
is cut. Both readers take the word after a cue ("na", "w", "ze stacji", "na
rzece") or a quoted phrase; a lowercase word counts only after a cue that is
followed by names ("rzece", "miejscowości", "nazwie"), because "stacje
hydrologiczne" or "w magazynie" are not places.
"""

import re
from collections.abc import Mapping
from typing import Any

from retman.extractors.base import Match, Reading, TextSource
from retman.extractors.text import fold, words

# Cues that introduce a place; the place must then be capitalised
_WEAK_CUES = frozenset(
    {"na", "w", "we", "z", "ze", "dla", "przy", "nad", "pod"}
    | {"stacji", "stacja", "stacje"}
)
# Cues that are followed by a name even when it is typed in lowercase
_STRONG_CUES = frozenset(
    {"rzece", "rzeka", "rzeki", "rzeke", "nazwie", "nazwa"}
    | {"miejscowosci", "miejscowosc"}
)
# Words that follow a cue but are not places
_NOT_PLACES = frozenset(
    {
        "polsce", "polska", "polski", "polskie", "polskich", "czechach", "czechy",
        "czeskie", "czeskich", "imgw", "pib", "chmi", "chmu", "gugik", "europie",
        "swiecie",
    }
)  # fmt: skip
_QUOTED_RE = re.compile(r"[\"„“«](?P<phrase>[^\"”“»\n]{2,80})[\"”“»]")
_ENDINGS = ("iem", "owi", "ach", "ie", "iu", "ia", "a", "e", "y", "i", "u", "o")
# Locative alternations to undo: "Odrze" -> "Odr", "Rabce" -> "Rab"
_ALTERNATIONS = ("rz", "dz", "sz", "c")
_MIN_STEM = 3
_SYNOP_CODE_RE = re.compile(
    r"(?<![\w.,])(?:kod\w*|id|identyfikator\w*|numer\w*|nr)\s*[:=#]?\s*"
    r"(?:stacji\s+)?(?P<code>[0-9]{5})(?!\d)(?![.,]\d)"
)


def _cut(folded: str) -> int:
    """Letters of the ending of an inflected (folded) place name to cut off."""
    for ending in _ENDINGS:
        if folded.endswith(ending) and len(folded) - len(ending) >= _MIN_STEM:
            stem = folded[: -len(ending)]
            for alternation in _ALTERNATIONS:
                # "rz" is "r" in the nominative ("Odrze" - "Odra"): keep that letter
                keep = 1 if alternation == "rz" else 0
                if (
                    stem.endswith(alternation)
                    and len(stem) - len(alternation) + keep >= _MIN_STEM
                ):
                    return len(ending) + len(alternation) - keep
            return len(ending)
    return 0


def _names(text: str) -> list[tuple[int, int, str, bool]]:
    """Candidate place names: (start, end, written text, quoted) in the text."""
    found: list[tuple[int, int, str, bool]] = []
    for hit in _QUOTED_RE.finditer(text):
        phrase = hit.group("phrase").strip()
        if phrase:
            found.append((hit.start(), hit.end(), phrase, True))
    text_words = words(fold(text))
    quoted_spans = [(start, end) for start, end, _, _ in found]
    for position, cue in enumerate(text_words):
        weak = cue.text in _WEAK_CUES
        if not weak and cue.text not in _STRONG_CUES:
            continue
        strong = cue.text in _STRONG_CUES
        following = position + 1
        # "na rzece Wiśle": a cue followed by a strong cue
        while following < len(text_words) and text_words[following].text in (
            _STRONG_CUES
        ):
            strong = True
            following += 1
        if following >= len(text_words):
            continue
        word = text_words[following]
        written = text[word.start : word.end]
        if (
            len(word.text) < _MIN_STEM
            or word.text.isdigit()
            or word.text in _NOT_PLACES
            or word.text in _WEAK_CUES
            or not (strong or written[:1].isupper())
            or any(start <= word.start < end for start, end in quoted_spans)
        ):
            continue
        end = word.end
        # A hyphenated name stays whole: "Poznań-Ławica"
        while (
            end < len(text)
            and text[end] == "-"
            and end + 1 < len(text)
            and text[end + 1].isalpha()
        ):
            end += 1
            while end < len(text) and text[end].isalpha():
                end += 1
        found.append((word.start, end, text[word.start : end], False))
    return sorted(found)


def extract_place_query(text: str) -> list[Match]:
    """
    Search fragments for the station search: places named in the command.

    The value's ``text`` is folded and, for one inflected word, reduced to its
    stem so the tool's substring search finds the nominative ("Poznaniu" gives
    ``poznan``, "Wiśle" gives ``wisl``, "Odrze" gives ``odr``); ``raw`` is what the
    user wrote. A quoted phrase and a hyphenated name are kept whole.

    Parameters
    ----------
    text : str
        Command or answer.

    Returns
    -------
    list[Match]
        One match per place, value ``{"type": "query", "text": ..., "raw": ...}``.

    Examples
    --------
    >>> [m.readings[0].value["text"] for m in extract_place_query(
    ...     "Znajdź stacje hydrologiczne na Wiśle")]
    ['wisl']
    >>> extract_place_query("Znajdź stacje hydrologiczne")
    []
    """
    matches = []
    seen: set[str] = set()
    for start, end, written, quoted in _names(text):
        folded = fold(written)
        stem = folded
        if not quoted and "-" not in written:
            stem = folded[: len(folded) - _cut(folded)]
        if stem in seen:
            continue
        seen.add(stem)
        matches.append(
            Match(
                start,
                end,
                (
                    Reading(
                        {"type": "query", "text": stem, "raw": written},
                        "extractors.query.fragment",
                        {"text": stem, "raw": written},
                    ),
                ),
            )
        )
    return matches


def read_place_query_answer(text: str) -> list[Match]:
    """Answer to the question about the place: the cues are optional.

    A command-like answer ("na Wiśle") is read as in a command; any other short
    answer is the fragment itself ("Poznań", "Bogdanka"), folded and whole.
    """
    matches = extract_place_query(text)
    if matches:
        return matches
    phrase = " ".join(text.split())
    if not 2 <= len(phrase) <= 80:
        return []
    return [
        Match(
            0,
            len(text),
            (
                Reading(
                    {"type": "query", "text": fold(phrase), "raw": phrase},
                    "extractors.query.fragment",
                    {"text": fold(phrase), "raw": phrase},
                ),
            ),
        )
    ]


def validate_place_query(value: Any) -> str | None:
    """Translation key of the problem with a place query, or None."""
    if (
        not isinstance(value, dict)
        or value.get("type") != "query"
        or not isinstance(value.get("text"), str)
        or not value["text"].strip()
        or not isinstance(value.get("raw"), str)
    ):
        return "extractors.errors.invalid_query"
    return None


def describe_place_query(value: Mapping[str, Any], texts: TextSource) -> str:
    """Plan text of a place query: the fragment, and the word it came from."""
    text, raw = str(value.get("text")), str(value.get("raw"))
    if fold(raw) == text:
        return texts.get("extractors.display.query_same", text=text)
    return texts.get("extractors.display.query", text=text, raw=raw)


def extract_synop_station(text: str) -> list[Match]:
    """
    Synoptic station: a 5-digit id after "kod"/"nr"/"id", or a name fragment.

    The tool matches ``station_name`` as a case-insensitive fragment that keeps
    diacritics, so the name keeps the user's letters and only the inflected
    ending is cut ("Warszawie" gives "Warszaw").

    Returns
    -------
    list[Match]
        Values ``{"type": "synop_station", "code": "12330", "name": None}`` or
        ``{"type": "synop_station", "code": None, "name": "Warszaw"}``.
    """
    matches = []
    folded = fold(text)
    for hit in _SYNOP_CODE_RE.finditer(folded):
        code = hit.group("code")
        matches.append(
            Match(
                hit.start(),
                hit.end(),
                (
                    Reading(
                        {"type": "synop_station", "code": code, "name": None},
                        "extractors.synop_station.code",
                        {"code": code},
                    ),
                ),
            )
        )
    if matches:
        # A code is exact: a name beside it ("Warszawa, kod 12375") adds nothing
        return matches
    for start, end, written, quoted in _names(text):
        name = written
        if not quoted and "-" not in written:
            name = written[: len(written) - _cut(fold(written))]
        matches.append(
            Match(
                start,
                end,
                (
                    Reading(
                        {"type": "synop_station", "code": None, "name": name},
                        "extractors.synop_station.name",
                        {"name": name, "raw": written},
                    ),
                ),
            )
        )
    return sorted(matches, key=lambda match: match.start)


def read_synop_station_answer(text: str) -> list[Match]:
    """Answer about the synoptic station: a bare 5-digit id or a bare name."""
    matches = extract_synop_station(text)
    if matches:
        return matches
    answer = " ".join(text.split())
    if re.fullmatch(r"[0-9]{5}", answer):
        value: dict[str, Any] = {"type": "synop_station", "code": answer, "name": None}
        key = "code"
    elif 2 <= len(answer) <= 80 and not answer.isdigit():
        value = {"type": "synop_station", "code": None, "name": answer}
        key = "name"
    else:
        return []
    return [
        Match(
            0,
            len(text),
            (
                Reading(
                    value,
                    f"extractors.synop_station.{key}",
                    {"code": answer, "name": answer, "raw": answer},
                ),
            ),
        )
    ]


def validate_synop_station(value: Any) -> str | None:
    """Translation key of the problem with a synoptic station value, or None."""
    if not isinstance(value, dict) or value.get("type") != "synop_station":
        return "extractors.errors.invalid_synop_station"
    code, name = value.get("code"), value.get("name")
    if isinstance(code, str) and name is None:
        ok = re.fullmatch(r"[0-9]{5}", code) is not None
    elif isinstance(name, str) and code is None:
        ok = bool(name.strip())
    else:
        ok = False
    return None if ok else "extractors.errors.invalid_synop_station"


def describe_synop_station(value: Mapping[str, Any], texts: TextSource) -> str:
    """Plan text of a synoptic station value."""
    if value.get("code"):
        return texts.get("extractors.display.synop_code", code=str(value["code"]))
    return texts.get("extractors.display.synop_name", name=str(value.get("name")))

"""Coordinate reference systems named in a command and their role (ADR-009).

A command may name the system of the input rectangle and the system of the
result in the same sentence ("x=… w 2180, przelicz do 3045"). The model mixed
them up with high confidence, so code decides which mention is the output:
it returns only the mentions it can attribute to the result and leaves the
rest to a question (never a silent guess, ARCHITECTURE 6.1).
"""

import re
from dataclasses import dataclass

from retman.extractors.areas import extract_area
from retman.extractors.base import Match, Reading
from retman.extractors.text import fold, starts_within_one_edit

# Names of systems that commands mention; any other "EPSG:<code>" is still read
# so Retman can say the system is not supported.
_NAMED: tuple[tuple[str, int], ...] = (
    (r"pl\s*-?\s*1992|puwg\s*-?\s*(?:19)?92|uklad(?:zie|u)?\s+(?:19)?92", 2180),
    (r"s\s*-?\s*jtsk|kro[vw]ak", 5514),
    (
        r"etrs\s*-?\s*89\s*/?\s*(?:etrs\s*-?\s*)?tm\s*-?\s*33|utm\s*-?\s*33\s*n?"
        r"|tm\s*-?\s*33",
        3045,
    ),
    (r"wgs\s*-?\s*84", 4326),
)
# Bare numbers count in commands only next to a word about systems, because
# four digits also mean TERYT codes, years or sheet numbers.
_KNOWN_CODES = (2180, 5514, 3045, 4326)
_EPSG_RE = re.compile(r"(?<!\w)epsg\s*[:\-]?\s*(?P<code>[0-9]{4,5})(?![0-9])")
_NAMED_RE = tuple(
    (re.compile(rf"(?<!\w)(?:{pattern})(?!\w)"), code) for pattern, code in _NAMED
)
_BARE_RE = re.compile(
    rf"(?<![\w.,])(?P<code>{'|'.join(map(str, _KNOWN_CODES))})(?!\w|[.,][0-9])"
)
_WORD_RE = re.compile(r"[a-z0-9]+")

# Words before a mention that make it the result system. Stems of at least five
# letters tolerate one typo (missing, extra, changed or swapped letter); short
# words must match exactly, because one letter changes their meaning ("do"/"od").
_OUTPUT_STEMS = (
    "wynik",
    "przelicz",
    "zapisz",
    "zapisa",
    "docelow",
    "eksport",
    "reprojek",
    "transform",
    "wyjsciow",
)
_OUTPUT_WORDS = frozenset({"do"})
_INPUT_STEMS = ("prostok", "wspolrzedn", "wejsciow")
# Words allowed between the rectangle and the system that describes it
# ("530000 … 382100 w układzie PL-1992").
_GAP_WORDS = frozenset({"w", "we", "uklad", "ukladzie", "ukladu", "crs"})
_BARE_CUES = frozenset({"epsg", "uklad", "ukladzie", "ukladu", "kod", "crs"})
_WINDOW = 3  # words before a mention searched for cues


@dataclass(frozen=True)
class _Mention:
    start: int
    end: int
    code: int


def _word_role(word: str) -> str | None:
    """Role one word suggests; exact stems win over typo tolerance.

    Without that order "wejściowy" (input) would also be one typo away from
    "wyjściowy" (output).
    """
    if word in _OUTPUT_WORDS or any(word.startswith(s) for s in _OUTPUT_STEMS):
        return "output"
    if any(word.startswith(s) for s in _INPUT_STEMS):
        return "input"
    output = any(starts_within_one_edit(word, s) for s in _OUTPUT_STEMS)
    source = any(starts_within_one_edit(word, s) for s in _INPUT_STEMS)
    if output == source:
        return None
    return "output" if output else "input"


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _cue(words: list[str]) -> str | None:
    """Role suggested by words before a mention; None for none or conflicting."""
    roles = {role for word in words if (role := _word_role(word)) is not None}
    return roles.pop() if len(roles) == 1 else None


def _mentions(folded: str, *, bare_needs_cue: bool) -> list[_Mention]:
    found: list[_Mention] = []

    def free(start: int, end: int) -> bool:
        return not any(start < m.end and end > m.start for m in found)

    for match in _EPSG_RE.finditer(folded):
        found.append(_Mention(match.start(), match.end(), int(match.group("code"))))
    for pattern, code in _NAMED_RE:
        for match in pattern.finditer(folded):
            if free(match.start(), match.end()):
                found.append(_Mention(match.start(), match.end(), code))
    for match in _BARE_RE.finditer(folded):
        if not free(match.start(), match.end()):
            continue
        before = _words(folded[: match.start()])[-_WINDOW:]
        if bare_needs_cue and not any(
            word in _BARE_CUES or _word_role(word) == "output" for word in before
        ):
            continue
        found.append(_Mention(match.start(), match.end(), int(match.group("code"))))
    return sorted(found, key=lambda mention: mention.start)


def _reading(code: int) -> Reading:
    return Reading(f"EPSG:{code}", "extractors.crs.code", {"code": str(code)})


def extract_crs(text: str) -> list[Match]:
    """
    Systems a command names for the result; empty when no mention clearly is one.

    Mentions separated only by punctuation (``PL-1992 EPSG:2180``) form a group
    with one role, decided in this order:

    1. directly after the rectangle, with at most ``w``/``w układzie`` between
       (``… 382100 w PL-1992``): input;
    2. words before the group: ``wynik``, ``do``, ``przelicz``, ``zapisz``,
       ``docelowy`` … give output, ``prostokąt``, ``współrzędne`` give input;
    3. no such words, but the code differs from the system of the rectangle's
       numbers (WGS84 or PL-1992 by their range): output — it cannot describe
       the rectangle;
    4. otherwise unknown.

    Only output mentions are returned; input and unknown ones lead to a question.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        One reading per output mention, value ``"EPSG:<code>"`` (supported by
        the operation or not — the caller checks).

    Examples
    --------
    >>> [m.readings[0].value for m in extract_crs(
    ...     "x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045")]
    ['EPSG:3045']
    >>> extract_crs("Wycinek NMT 530000 382000 530100 382100 PL-1992.")
    []
    """
    folded = fold(text)
    rectangles = [
        (match, match.readings[0].value["crs"])
        for match in extract_area(text)
        if all(
            isinstance(r.value, dict) and r.value.get("type") == "bbox"
            for r in match.readings
        )
    ]
    rectangle_codes = {int(crs.split(":")[1]) for _, crs in rectangles}
    groups: list[list[_Mention]] = []
    for mention in _mentions(folded, bare_needs_cue=True):
        if groups and not _words(folded[groups[-1][-1].end : mention.start]):
            groups[-1].append(mention)
        else:
            groups.append([mention])
    results: list[Match] = []
    for index, group in enumerate(groups):
        start = group[0].start
        previous = max(
            [0]
            + [m.end for m, _ in rectangles if m.end <= start]
            + [g[-1].end for g in groups[:index]]
        )
        right_after_rectangle = any(
            m.end <= start
            and all(w in _GAP_WORDS for w in _words(folded[m.end : start]))
            for m, _ in rectangles
        )
        role = (
            "input"
            if right_after_rectangle
            else _cue(_words(folded[previous:start])[-_WINDOW:])
        )
        if (
            role is None
            and rectangle_codes
            and not {m.code for m in group} & (rectangle_codes)
        ):
            role = "output"
        if role == "output":
            results.extend(
                Match(mention.start, mention.end, (_reading(mention.code),))
                for mention in group
            )
    return results


def read_crs_answer(text: str) -> list[Match]:
    """Systems named in an answer to the question about the result system.

    The answer is about the result only, so every mention counts and bare codes
    need no surrounding words (``2180``, ``s-jtsk``).
    """
    return [
        Match(mention.start, mention.end, (_reading(mention.code),))
        for mention in _mentions(fold(text), bare_needs_cue=False)
    ]


def validate_crs(value: object) -> str | None:
    """Translation key of the problem, or None for an ``EPSG:<code>`` value."""
    if isinstance(value, str) and re.fullmatch(r"EPSG:[0-9]{4,5}", value):
        return None
    return "extractors.errors.invalid_crs"

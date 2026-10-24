"""Years, periods and the kind of year named in a command (ADR-009 pattern).

Three parameters of the IMGW operations are read here, all by code:

* ``years`` — archive years in the tool's own numbering (``2000–2020``,
  ``2010, 2012 i 2015``, ``z 2015 roku``);
* ``period`` — a stretch of time: years or dates (``od 1 stycznia 2000 do
  31 grudnia 2020``, ``maj–wrzesień 2010``, ``01.01.2000 – 31.12.2020``);
* ``year_type`` — hydrological (1 November – 31 October) or calendar year.

Nothing is guessed (ARCHITECTURE 1.1, 6.1). A bare four-digit number is not a
year (it may be a TERYT code, a sheet or an EPSG code), a range written backwards
is returned as written for the validator to reject, relative and open periods
(``ostatnie 10 lat``, ``od 2010``) give no value, only a hint why, and the word
"hydrologiczne" counts as the year type only when it describes the year noun —
not when it describes the data (``dane hydrologiczne z lat 2000–2020``).

Text is compared folded (no diacritics, any letter case); cue words of five
letters or more tolerate one typo, shorter ones are matched exactly.
"""

import calendar
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, TypeGuard

from retman.extractors.base import ExtractionContext, Hint, Match, Reading, TextSource
from retman.extractors.text import (
    equals_within_one_edit,
    fold,
    starts_within_one_edit,
)

# The oldest data of the supported datasets: ČHMÚ daily water levels from 1887.
_FIRST_YEAR = 1887
_FIRST_DAY = date(_FIRST_YEAR, 1, 1)
_NUMBERINGS = ("hydrological", "calendar")

_INVALID_YEARS = "extractors.errors.invalid_years"
_YEARS_OUT_OF_RANGE = "extractors.errors.years_out_of_range"
_YEARS_ORDER = "extractors.errors.years_order"
_INVALID_PERIOD = "extractors.errors.invalid_period"
_PERIOD_ORDER = "extractors.errors.period_order"
_PERIOD_OUT_OF_RANGE = "extractors.errors.period_out_of_range"

# --- Words -------------------------------------------------------------------

# Month names with their cases, folded. Typos are tolerated only in the longer
# forms; the shorter ones ("maja"/"marca") are two edits apart, so a word that is
# one typo away from a long form never reaches two months.
_MONTH_FORMS: dict[int, tuple[str, ...]] = {
    1: ("styczen", "stycznia", "styczniowi", "styczniem", "styczniu"),
    2: ("luty", "lutego", "lutemu", "lutym"),
    3: ("marzec", "marca", "marcowi", "marcem", "marcu"),
    4: ("kwiecien", "kwietnia", "kwietniowi", "kwietniem", "kwietniu"),
    5: ("maj", "maja", "majowi", "majem", "maju"),
    6: ("czerwiec", "czerwca", "czerwcowi", "czerwcem", "czerwcu"),
    7: ("lipiec", "lipca", "lipcowi", "lipcem", "lipcu"),
    8: ("sierpien", "sierpnia", "sierpniowi", "sierpniem", "sierpniu"),
    9: ("wrzesien", "wrzesnia", "wrzesniowi", "wrzesniem", "wrzesniu"),
    10: (
        "pazdziernik",
        "pazdziernika",
        "pazdziernikowi",
        "pazdziernikiem",
        "pazdzierniku",
    ),
    11: ("listopad", "listopada", "listopadowi", "listopadem", "listopadzie"),
    12: ("grudzien", "grudnia", "grudniowi", "grudniem", "grudniu"),
}
_MONTH_BY_FORM = {
    form: month for month, forms in _MONTH_FORMS.items() for form in forms
}
_MONTH_TYPO_MIN_LENGTH = 6
# Three-letter abbreviations ("maj" has none). "sie" is also the folded "się".
_ABBREVIATIONS = {
    "sty": 1,
    "lut": 2,
    "mar": 3,
    "kwi": 4,
    "cze": 6,
    "lip": 7,
    "sie": 8,
    "wrz": 9,
    "paz": 10,
    "lis": 11,
    "gru": 12,
}
# Roman numerals count only in capitals: "i" is the conjunction "and".
_ROMAN_MONTHS = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
}

# Prepositions that make a single four-digit number a year ("z 2015", "w 2015").
_PREPOSITIONS = frozenset({"z", "ze", "w", "we", "za", "dla"})
# Words after a year that say it is one ("2015 r.", "2015 roku").
_YEAR_SUFFIXES = frozenset({"r", "rok", "roku"})
# Year nouns with the endings of the adjective that agrees with them. The
# abbreviations "r." and "l." agree with anything.
_NOUN_ENDINGS: dict[str, frozenset[str]] = {
    "rok": frozenset({"y"}),
    "roku": frozenset({"ego", "ym"}),
    "rokiem": frozenset({"ym"}),
    "rokowi": frozenset({"emu"}),
    "lata": frozenset({"e"}),
    "lat": frozenset({"ych"}),
    "latach": frozenset({"ych"}),
    "latom": frozenset({"ym"}),
    "latami": frozenset({"ymi"}),
    "rocznik": frozenset({"y"}),
    "rocznika": frozenset({"ego"}),
    "roczniku": frozenset({"ym"}),
    "rocznikiem": frozenset({"ym"}),
    "roczniki": frozenset({"e"}),
    "rocznikow": frozenset({"ych"}),
    "rocznikach": frozenset({"ych"}),
}
_ENDINGS = ("ymi", "ych", "ego", "emu", "ym", "ej", "y", "e", "a")
# Words that tie a year or date to a second one that Retman reads neither as a
# list nor as a range ("z 2010 lub 2012", "z lat 2000–2020 bez 2015").
_ALTERNATIVES = frozenset({"lub", "albo", "czy", "badz", "bez", "oprocz"})
# Ends of an open period that depend on today's date ("od 2010 do dziś").
_RELATIVE_ENDS = frozenset(
    {"dzis", "dzisiaj", "dzisiejszego", "dzisiejszej", "teraz", "obecnie", "konca"}
)
_RELATIVE_UNITS = frozenset(
    {
        "rok",
        "roku",
        "lat",
        "lata",
        "latach",
        "miesiecy",
        "miesiace",
        "miesiac",
        "dni",
        "dzien",
        "tygodni",
        "tygodnie",
        "dekad",
        "dekade",
        "dekady",
        "dziesiecioleci",
        "dziesiecioleciu",
    }
)
_RELATIVE_YEAR_WORDS = ("ubieg", "zeszl", "biez", "obecn", "poprzedn", "aktualn")

# --- Tokens ------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"(?P<iso>[0-9]{4}-[0-9]{1,2}-[0-9]{1,2})(?![0-9])"
    r"|(?P<blob>[0-9]+(?:[.,/:][0-9]+)+)"
    r"|(?P<num>[0-9]+)"
    r"|(?P<word>[a-z]+)"
    r"|(?P<dash>[-\u2010-\u2015\u2212])"
    r"|(?P<sep>[,;])"
    r"|(?P<other>\S)"
)
_COMMA_YEARS_RE = re.compile(r"[0-9]{4}(?:,[0-9]{4})+")
_DOTTED_RE = re.compile(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}")
_NUMERIC = ("num", "iso", "dotted", "junk")


@dataclass(frozen=True, slots=True)
class _Tok:
    """One token of folded text; ``raw`` is the original spelling (for case)."""

    kind: str  # iso dotted junk num word dash sep other
    text: str
    raw: str
    start: int
    end: int


def _tokenize(text: str) -> list[_Tok]:
    """Split text into tokens, keeping glued numbers (``1.01.2000``) whole.

    Numbers joined by ``. , / :`` are one token: a date in the form
    ``d.m.yyyy`` or, if it is not one, junk (``52.2297``, ``01/02/2000``,
    ``10:30``) — never years. Only years separated by commas without spaces
    (``2010,2012``) are split again.
    """
    folded = fold(text)
    tokens: list[_Tok] = []
    for found in _TOKEN_RE.finditer(folded):
        kind = found.lastgroup or "other"
        start, end = found.span()
        if kind == "blob":
            blob = found.group()
            if _COMMA_YEARS_RE.fullmatch(blob):
                position = start
                for part in blob.split(","):
                    stop = position + len(part)
                    raw = text[position:stop]
                    tokens.append(_Tok("num", part, raw, position, stop))
                    if stop < end:
                        tokens.append(_Tok("sep", ",", ",", stop, stop + 1))
                    position = stop + 1
                continue
            kind = "dotted" if _DOTTED_RE.fullmatch(blob) else "junk"
        tokens.append(_Tok(kind, found.group(), text[start:end], start, end))
    return tokens


def _token(tokens: list[_Tok], k: int) -> _Tok | None:
    return tokens[k] if 0 <= k < len(tokens) else None


def _glued_dot(tokens: list[_Tok], k: int) -> bool:
    """Whether a dot follows token ``k`` directly (an abbreviation's dot)."""
    token, after = _token(tokens, k), _token(tokens, k + 1)
    return (
        token is not None
        and after is not None
        and after.kind == "other"
        and after.text == "."
        and after.start == token.end
    )


@lru_cache(maxsize=4096)
def _month_of(word: str) -> int | None:
    """Month a folded word names (one typo allowed in the long forms), else None."""
    month = _MONTH_BY_FORM.get(word)
    if month is not None or len(word) < _MONTH_TYPO_MIN_LENGTH - 1:
        return month
    near = {
        month
        for form, month in _MONTH_BY_FORM.items()
        if abs(len(form) - len(word)) <= 1
        and equals_within_one_edit(word, form, min_length=_MONTH_TYPO_MIN_LENGTH)
    }
    return near.pop() if len(near) == 1 else None


def _is_date(year: int, month: int, day: int) -> bool:
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


# --- Year nouns and the year type adjectives ----------------------------------


@dataclass(frozen=True, slots=True)
class _Noun:
    end: int  # token index after the noun (and the dot of "r.")
    form: str | None  # key of _NOUN_ENDINGS; None for the abbreviations "r." "l."


@dataclass(frozen=True, slots=True)
class _Adjective:
    value: str  # "hydrological" or "calendar"
    end: int  # token index after the adjective (and the dot of "hydrol.")
    ending: str | None  # inflection ending; None for an abbreviation


@lru_cache(maxsize=4096)
def _noun_form(word: str) -> str | None:
    """Key of ``_NOUN_ENDINGS`` that a folded word is (one typo in long forms)."""
    if word in _NOUN_ENDINGS:
        return word
    for form in _NOUN_ENDINGS:
        if abs(len(form) - len(word)) <= 1 and equals_within_one_edit(word, form):
            return form
    return None


def _noun(tokens: list[_Tok], k: int) -> _Noun | None:
    """Year noun starting at token ``k`` (rok, lata, latach, rocznik, r., l.)."""
    token = _token(tokens, k)
    if token is None or token.kind != "word":
        return None
    word = token.text
    if word == "r":
        return _Noun(k + 2 if _glued_dot(tokens, k) else k + 1, None)
    if word == "l":
        return _Noun(k + 2, None) if _glued_dot(tokens, k) else None
    form = _noun_form(word)
    return None if form is None else _Noun(k + 1, form)


@lru_cache(maxsize=4096)
def _adjective_kind(word: str, lax: bool) -> tuple[str, bool] | None:
    """Year type a folded word stands for and whether it is an abbreviation."""
    if starts_within_one_edit(word, "hydrolog"):
        return "hydrological", False
    if starts_within_one_edit(word, "kalendarzow"):
        return "calendar", False
    if word == "hydrol" or (lax and word == "hydro"):
        return "hydrological", True
    if word == "kalend" or (lax and word.startswith("kalendarz")):
        return "calendar", True
    return None


def _adjective(tokens: list[_Tok], k: int, *, lax: bool) -> _Adjective | None:
    """Year type adjective at token ``k``.

    ``hydro`` and ``kalendarz`` stand for the types only in answers (``lax``):
    in a command they would also begin other words.
    """
    token = _token(tokens, k)
    if token is None or token.kind != "word":
        return None
    kind = _adjective_kind(token.text, lax)
    if kind is None:
        return None
    value, abbreviation = kind
    if abbreviation:
        return _Adjective(value, k + 2 if _glued_dot(tokens, k) else k + 1, None)
    return _Adjective(value, k + 1, _ending(token.text))


def _ending(word: str) -> str | None:
    """Inflection ending of an adjective (``ych``, ``ego``, ``y`` …)."""
    return next((ending for ending in _ENDINGS if word.endswith(ending)), None)


def _agrees(noun: _Noun, adjective: _Adjective) -> bool:
    if noun.form is None or adjective.ending is None:
        return True
    return adjective.ending in _NOUN_ENDINGS[noun.form]


# --- Reading dates and years ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Problem:
    """Why a form was not read, for ``explain_period``."""

    key: str
    args: dict[str, str]
    position: int


@dataclass(frozen=True, slots=True)
class _Month:
    value: int
    end: int  # token index after the month word (and the dot of an abbreviation)
    uncertain: bool  # an abbreviation that is also an ordinary word
    named: bool  # spelled out, not an abbreviation or a Roman numeral


@dataclass(frozen=True, slots=True)
class _Point:
    """A date, a whole month or a part of a date (``year`` is None: "1 maja")."""

    first: int
    end: int
    year: int | None
    month: int | None
    day: int | None
    valid: bool = True
    uncertain: bool = False


@dataclass(frozen=True, slots=True)
class _Atom:
    year: int
    end: int
    marked: bool  # a preposition, a year noun or "r." says the number is a year


@dataclass(frozen=True, slots=True)
class _Item:
    """One range of years or one year of a list of years."""

    end: int
    first: int
    last: int
    is_range: bool
    marked: bool
    open_end: bool  # "od 2010" without an end


def _single(point: _Point) -> tuple[date, date] | None:
    """First and last day of a date or of a whole month; None if impossible."""
    if not point.valid or point.year is None or point.month is None:
        return None
    if point.day is not None:
        day = date(point.year, point.month, point.day)
        return day, day
    last = calendar.monthrange(point.year, point.month)[1]
    return date(point.year, point.month, 1), date(point.year, point.month, last)


def _resolve(first: _Point, last: _Point) -> tuple[date, date] | None:
    """Both ends of a range; ``first`` may borrow its year and month from ``last``.

    ``maj–wrzesień 2010`` takes the year from the end, ``od 1 do 15 maja 2010``
    the year and month. ``None`` for an impossible date or a day without a month.
    """
    end = _single(last)
    if end is None or not first.valid:
        return None
    if first.month is None and last.day is None:
        return None  # "od 1 do maja 2010": the day has no month to belong to
    year = first.year if first.year is not None else last.year
    month = first.month if first.month is not None else last.month
    if year is None or month is None:
        return None
    try:
        start = date(year, month, first.day or 1)
    except ValueError:
        return None
    return start, end[1]


def _reading_years(first: int, last: int) -> Reading:
    value = {"type": "years", "first": first, "last": last}
    # The text of a single year gets the arguments of the range text too
    args = {"first": str(first), "last": str(last)}
    key = "extractors.period.year" if first == last else "extractors.period.years"
    return Reading(value, key, args)


def _reading_year_list(years: list[int]) -> Reading:
    value = {"type": "year_list", "years": years}
    shown = ", ".join(str(year) for year in years)
    return Reading(value, "extractors.period.year_list", {"years": shown})


def _reading_dates(start: date, end: date) -> Reading:
    value = {"type": "dates", "start": start.isoformat(), "end": end.isoformat()}
    args = {"start": start.isoformat(), "end": end.isoformat()}
    key = "extractors.period.date" if start == end else "extractors.period.dates"
    return Reading(value, key, args)


class _Reader:
    """Everything one text says about dates and years.

    Dates are read first and their tokens are used up, so the year of
    ``15 maja 2010`` is never read again as a year. A form that is recognised but
    not usable (an impossible date, ``od 2010`` without an end, ``2010–12``) uses
    up its tokens too and gives no reading.

    Parameters
    ----------
    text : str
        Command or answer.
    lax : bool
        Reading an answer: a bare four-digit number is a year.
    """

    def __init__(self, text: str, *, lax: bool) -> None:
        self.text = text
        self.lax = lax
        self.tokens = _tokenize(text)
        self.used = [False] * len(self.tokens)
        self.dates: list[Match] = []
        self.years: list[Match] = []
        self.problems: list[_Problem] = []
        j = 0
        while j < len(self.tokens):
            end = self._date_group(j)
            j = j + 1 if end is None else end
        j = 0
        while j < len(self.tokens):
            end = None if self.used[j] else self._year_group(j)
            j = j + 1 if end is None else end

    # -- token helpers -------------------------------------------------------

    def tok(self, k: int) -> _Tok | None:
        return _token(self.tokens, k)

    def word(self, k: int) -> str | None:
        token = self.tok(k)
        return token.text if token is not None and token.kind == "word" else None

    def _mark(self, first: int, end: int) -> None:
        for k in range(first, end):
            self.used[k] = True

    def _match(self, first: int, end: int, reading: Reading, *, confirm: bool) -> Match:
        start, stop = self.tokens[first].start, self.tokens[end - 1].end
        return Match(start, stop, (reading,), confirm)

    def _is_year(self, k: int) -> bool:
        """Tell whether a four-digit number stands alone (not in ``q2010``)."""
        token = self.tok(k)
        if token is None or token.kind != "num" or len(token.text) != 4:
            return False
        if self.used[k]:
            return False
        before, after = self.tok(k - 1), self.tok(k + 1)
        if before is not None and before.kind == "word" and before.end == token.start:
            return False
        return not (
            after is not None
            and after.kind == "word"
            and after.start == token.end
            and after.text not in _YEAR_SUFFIXES
        )

    def _suffix(self, k: int) -> int:
        """Index after "r.", "r", "rok" or "roku" that follows a year."""
        word = self.word(k)
        if word in ("rok", "roku"):
            return k + 1
        if word == "r":
            return k + 2 if _glued_dot(self.tokens, k) else k + 1
        return k

    def _range_separator(self, k: int) -> int | None:
        """Index after a dash, "do" or "aż do" (a comma may precede the words)."""
        token = self.tok(k)
        if token is not None and token.kind == "dash":
            return k + 1
        if token is not None and token.kind == "sep" and token.text == ",":
            k += 1  # "od 2010, do 2020"
        if self.word(k) == "az" and self.word(k + 1) == "do":
            return k + 2
        return k + 1 if self.word(k) == "do" else None

    def _list_separator(self, k: int) -> int | None:
        """Index after the separator of a list of years (``,`` ``i`` ``oraz``)."""
        start = k
        token = self.tok(k)
        if token is not None and token.kind == "sep":
            k += 1
        word = self.word(k)
        if word in ("i", "oraz", "plus"):
            k += 1
        elif word == "a" and self.word(k + 1) in ("takze", "tez"):
            k += 2
        else:
            token = self.tok(k)
            if token is not None and token.kind == "other" and token.text in ("+", "&"):
                k += 1
        return k if k > start else None

    # -- forms that are part of something longer -------------------------------

    def _month_word(self, k: int) -> bool:
        token = self.tok(k)
        return (
            token is not None
            and token.kind == "word"
            and (_month_of(token.text) is not None or token.text in _ABBREVIATIONS)
        )

    def _ties(self, k: int) -> bool:
        """Whether token ``k`` is a number or a month: part of another date."""
        token = self.tok(k)
        return token is not None and (token.kind in _NUMERIC or self._month_word(k))

    def _relative_end(self, k: int) -> bool:
        return self.word(k) in _RELATIVE_ENDS

    def _tied(self, first: int, end: int) -> bool:
        """Whether tokens ``first:end`` belong to a longer form Retman does not read.

        ``2010-12``, ``2010/11``, ``z 2010 lub 2012``, ``z lat 2000–2020 bez 2015``,
        ``maj 2010 do września``, ``od 2010 do dziś``: reading the part would
        silently drop the rest. A dash with spaces around it is punctuation
        (``stacja 150160180 - z 2010 roku``), not a range, unless a month or a
        relative end stands next to it.
        """
        return self._tied_after(end) or self._tied_before(first)

    def _tied_after(self, end: int) -> bool:
        after = self.tok(end)
        if after is None:
            return False
        if after.kind == "dash":
            number, last = self.tok(end + 1), self.tok(end - 1)
            glued = (
                last is not None
                and number is not None
                and last.end == after.start
                and after.end == number.start
            )
            return (
                (glued and self._ties(end + 1))
                or self._month_word(end + 1)
                or self._relative_end(end + 1)
            )
        if after.kind == "other" and after.text == "/":
            return self._ties(end + 1)
        k = end + 1 if after.kind == "sep" else end  # "z 2010, do dziś"
        if self.word(k) == "az" and self.word(k + 1) == "do":
            return self._follows_number(k + 2) or self._relative_end(k + 2)
        if self.word(k) in ("do", *_ALTERNATIVES):
            return self._follows_number(k + 1) or self._relative_end(k + 1)
        return False

    def _tied_before(self, first: int) -> bool:
        before = self.tok(first - 1)
        if before is None or not self._ties(first - 2):
            return False
        if before.kind == "dash":
            if self._month_word(first - 2):
                return True  # "sty - gru 2010": a month needs no glue
            number, link = self.tok(first - 2), self.tok(first)
            return (
                number is not None
                and link is not None
                and number.end == before.start
                and before.end == link.start
            )
        if before.kind == "other":
            return before.text == "/"
        return before.text in _ALTERNATIVES

    def _follows_number(self, k: int) -> bool:
        """Whether a number, a month or a year with its marker starts at ``k``."""
        return self._ties(k) or self._atom(k, allow_preposition=True) is not None

    # -- dates -----------------------------------------------------------------

    def _month(self, k: int, *, after_day: bool) -> _Month | None:
        """Month named by the word at ``k``.

        Names always count. Abbreviations count only after a day or directly
        before a year, Roman numerals (capitals) only after a day.
        """
        token = self.tok(k)
        if token is None or token.kind != "word" or self.used[k]:
            return None
        word = token.text
        month = _month_of(word)
        if month is not None:
            return _Month(month, k + 1, False, True)
        end = k + 2 if _glued_dot(self.tokens, k) else k + 1
        if after_day and token.raw in _ROMAN_MONTHS:
            return _Month(_ROMAN_MONTHS[token.raw], end, False, False)
        month = _ABBREVIATIONS.get(word)
        if month is None or not (after_day or self._is_year(end)):
            return None
        if word == "sie" and "ę" in token.raw.lower():
            return None  # spelled "się", the ordinary word
        # Without a day or a dot, "sie 2010" may be the folded "się" before a year
        doubtful = word == "sie" and not after_day and end == k + 1
        return _Month(month, end, doubtful, False)

    def _point(self, j: int, *, partial: bool) -> _Point | None:
        """Date, whole month or (``partial``) a part of a date starting at ``j``."""
        token = self.tok(j)
        if token is None or self.used[j]:
            return None
        if token.kind in ("iso", "dotted"):
            first, second, third = (int(p) for p in re.split(r"[-.]", token.text))
            year, month, day = (
                (first, second, third)
                if token.kind == "iso"
                else (third, second, first)
            )
            end = self._suffix(j + 1)
            return _Point(j, end, year, month, day, valid=_is_date(year, month, day))
        if token.kind == "num" and len(token.text) <= 2:
            return self._day_point(j, int(token.text), partial=partial)
        if token.kind == "word":
            return self._month_point(j, partial=partial)
        return None

    def _day_point(self, j: int, day: int, *, partial: bool) -> _Point | None:
        """``15 maja 2010``; partial: ``15 maja`` or a bare day before a range."""
        named = self._month(
            j + 2 if _glued_dot(self.tokens, j) else j + 1, after_day=True
        )
        if named is None:
            if not partial:
                return None
            return _Point(j, j + 1, None, None, day, valid=1 <= day <= 31)
        if self._is_year(named.end):
            year = int(self.tokens[named.end].text)
            return _Point(
                j,
                self._suffix(named.end + 1),
                year,
                named.value,
                day,
                valid=_is_date(year, named.value, day),
                uncertain=named.uncertain,
            )
        if not partial:
            return None
        return _Point(
            j,
            named.end,
            None,
            named.value,
            day,
            valid=1 <= day <= 31,
            uncertain=named.uncertain,
        )

    def _month_point(self, j: int, *, partial: bool) -> _Point | None:
        """``maj 2010`` (the whole month); partial: ``maj`` before a range."""
        named = self._month(j, after_day=False)
        if named is None:
            return None
        if self._is_year(named.end):
            year = int(self.tokens[named.end].text)
            return _Point(
                j,
                self._suffix(named.end + 1),
                year,
                named.value,
                None,
                valid=year >= 1,
                uncertain=named.uncertain,
            )
        if partial and named.named:
            return _Point(j, named.end, None, named.value, None)
        return None

    def _date_group(self, j: int) -> int | None:
        """Read a date or a range of dates at token ``j``; the end index or None."""
        od = self.word(j) == "od"
        first = self._point(j + 1 if od else j, partial=True)
        if first is None:
            return None
        separator = self._range_separator(first.end)
        last = self._point(separator, partial=False) if separator is not None else None
        if last is None:
            if first.year is None:
                return None  # no year: "15 maja" alone says nothing
            end = first.end
            span = _single(first)
            opened = od or self.word(j - 1) == "do"
        else:
            end = last.end
            span = _resolve(first, last)
            opened = False
        self._mark(j, end)
        if opened:
            if span is not None:
                key = "extractors.hints.period_open_" + ("end" if od else "start")
                shown = span[0] if od else span[1]
                self.problems.append(
                    _Problem(key, {"date": shown.isoformat()}, self.tokens[j].start)
                )
            return end
        if span is None or self._tied(j, end):
            return end
        uncertain = first.uncertain or (last is not None and last.uncertain)
        reading = _reading_dates(*span)
        self.dates.append(self._match(j, end, reading, confirm=uncertain))
        return end

    # -- years -----------------------------------------------------------------

    def _lead(self, k: int) -> int | None:
        """Index after "[adjective] year noun [adjective]" at ``k``, else None."""
        adjective = _adjective(self.tokens, k, lax=False)
        if adjective is not None:
            k = adjective.end
        noun = _noun(self.tokens, k)
        if noun is None:
            return None
        adjective = _adjective(self.tokens, noun.end, lax=False)
        return noun.end if adjective is None else adjective.end

    def _atom(self, j: int | None, *, allow_preposition: bool) -> _Atom | None:
        """Read a year with the words that mark it (``w latach 2015 r.``)."""
        if j is None:
            return None
        k = j
        marked = False
        if allow_preposition and self.word(k) in _PREPOSITIONS:
            marked = True
            k += 1
        lead = self._lead(k)
        if lead is not None:
            marked = True
            k = lead
        if not self._is_year(k):
            return None
        end = self._suffix(k + 1)
        return _Atom(int(self.tokens[k].text), end, marked or end > k + 1)

    def _item(self, j: int) -> _Item | None:
        od = self.word(j) == "od"
        first = self._atom(j + 1 if od else j, allow_preposition=not od)
        if first is None:
            return None
        separator = self._range_separator(first.end)
        last = self._atom(separator, allow_preposition=False)
        if last is not None:
            return _Item(last.end, first.year, last.year, True, True, False)
        return _Item(first.end, first.year, first.year, False, first.marked, od)

    def _year_group(self, j: int) -> int | None:
        """Read years at token ``j``: a year, a range or a list; end index or None."""
        if self.word(j) == "do":
            atom = self._atom(j + 1, allow_preposition=False)
            if atom is None:
                return None
            self._mark(j, atom.end)
            args = {"year": str(atom.year)}
            problem = _Problem(
                "extractors.hints.years_open_start", args, self.tokens[j].start
            )
            self.problems.append(problem)
            return atom.end
        first = self._item(j)
        if first is None:
            return None
        items = [first]
        while (k := self._list_separator(items[-1].end)) is not None:
            following = self._item(k)
            if following is None:
                break
            items.append(following)
        end = items[-1].end
        opened = next((item for item in items if item.open_end), None)
        bare = len(items) == 1 and not (first.is_range or first.marked or self.lax)
        if bare and opened is None:
            return None  # a bare number: may be a TERYT code, a sheet or a system
        self._mark(j, end)
        if opened is not None:
            args = {"year": str(opened.first)}
            problem = _Problem(
                "extractors.hints.years_open_end", args, self.tokens[j].start
            )
            self.problems.append(problem)
            return end
        if self._tied(j, end):
            return end
        reading = self._years_reading(items)
        if reading is not None:
            self.years.append(self._match(j, end, reading, confirm=False))
        return end

    @staticmethod
    def _years_reading(items: list[_Item]) -> Reading | None:
        if len(items) == 1:
            return _reading_years(items[0].first, items[0].last)
        years: list[int] = []
        for item in items:
            if item.first > item.last:
                return None  # a backwards range inside a list cannot be listed
            years.extend(range(item.first, item.last + 1))
        return _reading_year_list(years)

    # -- relative periods --------------------------------------------------------

    def relative_phrase(self) -> str | None:
        """First relative period in the text (``ostatnie 10 lat``, ``od 5 lat``)."""
        spans: list[tuple[int, int]] = []
        for k, token in enumerate(self.tokens):
            if token.kind != "word":
                continue
            span = self._relative_span(k, token.text)
            if span is not None:
                spans.append(span)
        if not spans:
            return None
        first, end = min(spans)
        return self.text[self.tokens[first].start : self.tokens[end - 1].end]

    def _relative_span(self, k: int, word: str) -> tuple[int, int] | None:
        if word.startswith("ostatn"):
            for m in range(k + 1, min(k + 4, len(self.tokens))):
                follower = self.tokens[m]
                if follower.kind == "word" and follower.text in _RELATIVE_UNITS:
                    previous = self.tok(k - 1)
                    counted = previous is not None and previous.kind == "num"
                    return (k - 1 if counted else k), m + 1
                if follower.kind not in ("num", "word"):
                    break
        elif word == "od":
            number = self.tok(k + 1)
            if (
                number is not None
                and number.kind == "num"
                and len(number.text) <= 3
                and self.word(k + 2) in _RELATIVE_UNITS
            ):
                return k, k + 3
            if self.word(k + 1) == "poczatku":
                return k, k + 2
        elif word.startswith(_RELATIVE_YEAR_WORDS):
            if self.word(k + 1) in ("rok", "roku", "lata", "lat"):
                return k, k + 2
        elif word in ("tym", "tego"):
            if self.word(k + 1) == "roku":
                return k, k + 2
        elif word == "do" and self._relative_end(k + 1):
            return self._with_start(k), k + 2
        return None

    def _with_start(self, k: int) -> int:
        """Start of the ``od … do dziś`` phrase whose "do" is at ``k``."""
        j = k - 1
        while j >= 0 and (
            self._ties(j)
            or self.word(j) in _YEAR_SUFFIXES
            or self.tokens[j].text == "."
        ):
            j -= 1
        return j if self.word(j) == "od" else k


# --- Public: years and period ----------------------------------------------------


def _by_position(*groups: list[Match]) -> list[Match]:
    return sorted((match for group in groups for match in group), key=lambda m: m.start)


def extract_years(text: str) -> list[Match]:
    """
    Archive years in a command: a range, a list or a single year.

    A single year needs a word that says it is one: ``z``, ``ze``, ``w``, ``we``,
    ``za``, ``dla`` before it, ``rok``, ``roku``, ``lat``, ``lata``, ``latach``,
    ``l.`` or ``r.`` before or ``rok``, ``roku``, ``r.`` after. Ranges
    (``2000–2020``, ``od 2000 do 2020``) and lists (``2010, 2012 i 2015``) need
    no word. A bare four-digit number is not a year, nor is a number inside
    another number or a date. Open (``od 2010``) and relative (``ostatnie 10
    lat``) forms give nothing; :func:`explain_period` says why.

    A range written backwards is returned as written; the validator rejects it.
    A list that mixes ranges and years (``2000–2002, 2005``) is expanded.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        In order of appearance. Values ``{"type": "years", "first", "last"}``
        (a single year has ``first == last``) or ``{"type": "year_list",
        "years": [...]}``.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_years("Dane z lat 2000–2020")]
    [{'type': 'years', 'first': 2000, 'last': 2020}]
    >>> extract_years("powiat 1465")
    []
    """
    return _Reader(text, lax=False).years


def read_years_answer(text: str) -> list[Match]:
    """Years in an answer to the question about them: a bare ``2015`` is enough."""
    return _Reader(text, lax=True).years


def extract_period(text: str) -> list[Match]:
    """
    Read a period in a command: years (as in :func:`extract_years`) or dates.

    Dates: ``2000-01-01``, ``1.01.2000``, ``15 maja 2010``, ``1 XI 2019``
    (capital Roman numerals), whole months (``w maju 2010``, ``styczeń 2000``)
    and ranges of them with ``od … do …`` or a dash (``maj–wrzesień 2010``,
    ``od maja do września 2010``). The first month of a range starts on its
    first day, the last ends on its last day. A range borrows the year (and
    month) it lacks from its end. Impossible dates, ``od 15.05.2010`` without an
    end and relative forms give nothing. Slash dates are not read.

    Dates win over years: the year of a date is not read again as a year. An
    abbreviation that is also an ordinary word (``sie 2010``, which could be
    "się") is returned with ``confirm`` set.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        In order of appearance. Besides the values of :func:`extract_years`:
        ``{"type": "dates", "start": "2000-01-01", "end": "2020-12-31"}``
        (a single day has ``start == end``). A year list is returned too; the
        manifest's ``accepts`` drops it for a continuous period.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_period("maj–wrzesień 2010")]
    [{'type': 'dates', 'start': '2010-05-01', 'end': '2010-09-30'}]
    """
    reader = _Reader(text, lax=False)
    return _by_position(reader.dates, reader.years)


def read_period_answer(text: str) -> list[Match]:
    """Read a period in an answer: like :func:`extract_period`, a bare year suffices."""
    reader = _Reader(text, lax=True)
    return _by_position(reader.dates, reader.years)


def explain_period(text: str) -> Hint | None:
    """
    Why a required period or years got no usable reading, for the question.

    Relative periods come first (``ostatnie 10 lat``, ``od 5 lat``, ``od 2010 do
    dziś``): Retman never turns them into years. Then the first open form:
    ``od 2010`` or ``od 15.05.2010`` without an end, ``do 2020`` without a start.

    Parameters
    ----------
    text : str
        The command or answer that gave nothing usable.

    Returns
    -------
    Hint or None
        ``extractors.hints.period_relative`` (``phrase``),
        ``years_open_end`` / ``years_open_start`` (``year``),
        ``period_open_end`` / ``period_open_start`` (``date``); None when the
        text has no such form.

    Examples
    --------
    >>> explain_period("dane od 2010").key
    'extractors.hints.years_open_end'
    """
    reader = _Reader(text, lax=True)
    phrase = reader.relative_phrase()
    if phrase is not None:
        return Hint("extractors.hints.period_relative", {"phrase": phrase})
    if reader.problems:
        problem = min(reader.problems, key=lambda found: found.position)
        return Hint(problem.key, dict(problem.args))
    return None


# --- Public: validators and display ------------------------------------------------


def _is_int(value: object) -> TypeGuard[int]:
    return type(value) is int


def _years_error(value: Mapping[str, Any], ctx: ExtractionContext) -> str | None:
    kind = value.get("type")
    if kind == "years":
        first, last = value.get("first"), value.get("last")
        if not (_is_int(first) and _is_int(last)):
            return _INVALID_YEARS
        if not all(_FIRST_YEAR <= year <= ctx.today.year for year in (first, last)):
            return _YEARS_OUT_OF_RANGE
        return _YEARS_ORDER if first > last else None
    if kind == "year_list":
        years = value.get("years")
        if not isinstance(years, list | tuple) or len(years) < 2:
            return _INVALID_YEARS
        if not all(_is_int(year) for year in years):
            return _INVALID_YEARS
        if not all(_FIRST_YEAR <= year <= ctx.today.year for year in years):
            return _YEARS_OUT_OF_RANGE
        if any(a >= b for a, b in zip(years, years[1:], strict=False)):
            return _INVALID_YEARS
        return None
    return _INVALID_YEARS


def validate_years(value: Any, ctx: ExtractionContext) -> str | None:
    """
    Return the translation key of the problem with a years value, or None if valid.

    A range needs integer years from 1887 to the current year with
    ``first <= last``; a year list needs at least two such years in strictly
    increasing order. Values that went through JSON are valid as well.
    """
    if not isinstance(value, Mapping):
        return _INVALID_YEARS
    return _years_error(value, ctx)


def _parse_iso(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_period(value: Any, ctx: ExtractionContext) -> str | None:
    """
    Return the translation key of the problem with a period value, or None if valid.

    Years are checked as in :func:`validate_years` (a list of years is not a
    continuous period). Dates must be ISO strings of real days with
    ``start <= end``, from 1887-01-01 to today.
    """
    if not isinstance(value, Mapping):
        return _INVALID_PERIOD
    kind = value.get("type")
    if kind == "years":
        return _years_error(value, ctx)
    if kind != "dates":
        return _INVALID_PERIOD
    start, end = _parse_iso(value.get("start")), _parse_iso(value.get("end"))
    if start is None or end is None:
        return _INVALID_PERIOD
    if start > end:
        return _PERIOD_ORDER
    if start < _FIRST_DAY or end > ctx.today:
        return _PERIOD_OUT_OF_RANGE
    return None


def describe_period(value: Mapping[str, Any], texts: TextSource) -> str:
    """
    Plan text of a years, year list or dates value.

    Raises
    ------
    ValueError
        For any other value.
    """
    kind = value.get("type")
    if kind == "years":
        args = {"first": str(value["first"]), "last": str(value["last"])}
        single = value["first"] == value["last"]
        return texts.get(f"extractors.display.{'year' if single else 'years'}", **args)
    if kind == "year_list":
        shown = ", ".join(str(year) for year in value["years"])
        return texts.get("extractors.display.year_list", years=shown)
    if kind == "dates":
        args = {"start": str(value["start"]), "end": str(value["end"])}
        single = value["start"] == value["end"]
        return texts.get(f"extractors.display.{'date' if single else 'dates'}", **args)
    raise ValueError(f"not a period value: {value!r}")


# --- Public: conversions ------------------------------------------------------------


def period_dates(period: Mapping[str, Any], year_type: str) -> tuple[date, date]:
    """
    First and last day of a period.

    Years become whole calendar years (``first-01-01 … last-12-31``) or whole
    hydrological years (``(first-1)-11-01 … last-10-31``); a hydrological year
    is named after the calendar year it ends in. Dates are returned as they are,
    whatever the year type.

    Parameters
    ----------
    period : Mapping[str, Any]
        A ``years`` or ``dates`` value.
    year_type : str
        ``"hydrological"`` or ``"calendar"`` (only years need it).

    Returns
    -------
    tuple[date, date]
        First and last day, both included.

    Raises
    ------
    ValueError
        For a year list (not continuous), an unknown value or year type,
        unreal dates or a period that ends before it starts.

    Examples
    --------
    >>> period_dates({"type": "years", "first": 2000, "last": 2020}, "hydrological")
    (datetime.date(1999, 11, 1), datetime.date(2020, 10, 31))
    """
    kind = period.get("type")
    if kind == "dates":
        start, end = _parse_iso(period.get("start")), _parse_iso(period.get("end"))
        if start is None or end is None or start > end:
            raise ValueError(f"not a period of dates: {period!r}")
        return start, end
    if kind != "years":
        raise ValueError(f"not a continuous period: {period!r}")
    first, last = period.get("first"), period.get("last")
    if not (_is_int(first) and _is_int(last)) or first > last:
        raise ValueError(f"not a range of years: {period!r}")
    if year_type == "calendar":
        return date(first, 1, 1), date(last, 12, 31)
    if year_type == "hydrological":
        return date(first - 1, 11, 1), date(last, 10, 31)
    raise ValueError(f"unknown year type {year_type!r}")


def _numbering_year(day: date, numbering: str) -> int:
    if numbering == "hydrological" and day.month >= 11:
        return day.year + 1
    return day.year


def archive_years(start: date, end: date, numbering: str) -> list[int]:
    """
    Archive years that cover every day from ``start`` to ``end``.

    A hydrological archive year ``Y`` holds 1 November ``Y-1`` – 31 October
    ``Y``; a calendar one holds the calendar year. The first and last years are
    the smallest that still contain ``start`` and ``end``.

    Parameters
    ----------
    start, end : date
        First and last day of the period.
    numbering : str
        ``"hydrological"`` or ``"calendar"``: the dataset's archive numbering.

    Returns
    -------
    list[int]
        Consecutive years.

    Raises
    ------
    ValueError
        For an unknown numbering or ``end`` before ``start``.

    Examples
    --------
    >>> archive_years(date(2000, 1, 1), date(2020, 12, 31), "hydrological")[-3:]
    [2019, 2020, 2021]
    """
    if numbering not in _NUMBERINGS:
        raise ValueError(f"unknown archive numbering {numbering!r}")
    if end < start:
        raise ValueError(f"period ends before it starts: {start} – {end}")
    first, last = _numbering_year(start, numbering), _numbering_year(end, numbering)
    return list(range(first, last + 1))


# --- Public: year type -------------------------------------------------------------


def _between(token: _Tok) -> bool:
    """Tokens that may stand between a year noun and its adjective: the years."""
    if token.kind in ("num", "dash", "sep"):
        return True
    if token.kind == "other":
        return token.text == "."
    return token.text in ("do", "od", "i", "oraz", "az", "r", "rok", "roku")


def _partner(
    tokens: list[_Tok], k: int, adjective: _Adjective
) -> tuple[int, int] | None:
    """Token span of the year noun the adjective at ``k`` describes, or None.

    The noun directly before the adjective always counts. A noun before the
    years (``z lat 2000–2020 hydrologicznych``) or directly after the adjective
    (``hydrologiczne lata``) counts only if the adjective agrees with it:
    otherwise it describes a noun on its other side (``dane hydrologiczne lat
    2000–2020``).
    """
    for start in (k - 1, k - 2):
        noun = _noun(tokens, start) if start >= 0 else None
        if noun is not None and noun.end == k:
            return start, adjective.end
    j = k - 1
    while j >= 0:
        for start in (j, j - 1):
            noun = _noun(tokens, start) if start >= 0 else None
            if noun is not None and noun.end == j + 1 and _agrees(noun, adjective):
                return start, adjective.end
        if not _between(tokens[j]):
            break
        j -= 1
    noun = _noun(tokens, adjective.end)
    if noun is not None and _agrees(noun, adjective):
        return k, noun.end
    return None


def _coordinated(tokens: list[_Tok], first: int, k: int) -> bool:
    """Whether only a conjunction stands between tokens ``first`` and ``k``.

    ``rok hydrologiczny i kalendarzowy``: the second adjective describes the
    same noun as the first.
    """
    return first < k and all(
        token.kind == "sep"
        or token.text in ("i", "oraz", "lub", "albo", "czy")
        or (token.kind == "other" and token.text == ".")
        for token in tokens[first:k]
    )


def _year_types(text: str, *, lax: bool) -> list[Match]:
    """Year type adjectives that describe a year noun (any, in an answer)."""
    tokens = _tokenize(text)
    found = [
        (k, adjective)
        for k in range(len(tokens))
        if (adjective := _adjective(tokens, k, lax=lax)) is not None
    ]
    partners = [_partner(tokens, k, adjective) for k, adjective in found]
    attached = [partner is not None for partner in partners]
    # "rok hydrologiczny i kalendarzowy": the noun is shared with the neighbour
    for i in range(1, len(found)):
        if attached[i - 1] and _coordinated(tokens, found[i - 1][1].end, found[i][0]):
            attached[i] = True
    # "hydrologiczne i kalendarzowe lata": likewise, if the noun agrees with it
    for i in range(len(found) - 2, -1, -1):
        (k, adjective), (next_k, next_adjective) = found[i], found[i + 1]
        noun = _noun(tokens, next_adjective.end)
        partner = partners[i + 1]
        if (
            noun is not None
            and partner is not None
            and partner[0] == next_k
            and _coordinated(tokens, adjective.end, next_k)
            and _agrees(noun, adjective)
        ):
            attached[i] = True
    matches: list[Match] = []
    for i, (k, adjective) in enumerate(found):
        if not (attached[i] or lax):
            continue
        first, end = k, adjective.end
        if (partner := partners[i]) is not None:
            first, end = min(first, partner[0]), max(end, partner[1])
        reading = Reading(adjective.value, f"extractors.year_type.{adjective.value}")
        matches.append(Match(tokens[first].start, tokens[end - 1].end, (reading,)))
    return matches


def extract_year_type(text: str) -> list[Match]:
    """
    Year type named in a command: ``"hydrological"`` or ``"calendar"``.

    The adjective counts only when it describes a year noun (``rok``, ``lata``,
    ``rocznik``, ``r.`` …): directly after it (``lata hydrologiczne``, ``rok
    hydrol.``), after the years that follow it (``z lat 2000–2020
    hydrologicznych``) or directly before it (``hydrologicznego roku``). In the
    last two cases the adjective must agree with the noun in case and number.
    ``dane hydrologiczne z lat 2000–2020`` says nothing about the year type.
    ``rok hydrologiczny i kalendarzowy`` gives two matches.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        One match per mention, one reading each with the plain string value
        ``"hydrological"`` or ``"calendar"``.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_year_type("rok hydrologiczny 2015")]
    ['hydrological']
    >>> extract_year_type("dobowe dane hydrologiczne z lat 2000–2020")
    []
    """
    return _year_types(text, lax=False)


def read_year_type_answer(text: str) -> list[Match]:
    """Year type in an answer: a bare ``hydrologiczne``, ``kalendarzowy``, ``hydro``."""
    return _year_types(text, lax=True)


def validate_year_type(value: Any) -> str | None:
    """Return the translation key of the problem with a year type, or None."""
    if isinstance(value, str) and value in _NUMBERINGS:
        return None
    return "extractors.errors.invalid_year_type"

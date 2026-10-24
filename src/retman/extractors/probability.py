"""Exceedance probability and return period from a Polish command (ARCHITECTURE 4.4).

The value is always a fraction ``p`` (``0.01`` for 1 %), read by code and never by
a model. Forms with a percent sign, ``Q1%``, ``T = 50``, ``raz na 50 lat``,
``50-letnia``, ``woda stuletnia`` and ``prawdopodobieństwo 0,01`` are unambiguous;
a number written without any of those markers can mean a percent, a return period
or a fraction, so every such reading is returned and Retman asks (ARCHITECTURE
6.1). A bare number is read only after ``dla``, ``prawdopodobieństwo`` or
``p =``, or inside a list started by one of them, never as part of a point, date,
year, sheet code or other number.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from retman.extractors.base import Match, Reading, TextSource
from retman.extractors.numbers import (
    DASHES,
    LETNI,
    PROCENTOWY,
    Token,
    attached,
    compound_adjective,
    is_dash,
    prefix_matches,
    read_number,
    split_lists,
    tokenize,
)
from retman.extractors.text import equals_within_one_edit, fold

_PERCENT = "percent"
_PERIOD = "return_period"
_FRACTION = "fraction"

# Return periods above this are not read from a bare ``Q`` number or a loose cue:
# they would also swallow codes and years.
_MAX_PERIOD_YEARS = 10_000
# "1 rok" would be p = 1 and "2020 roku" is a year, so only "lat"/"lata" count.
_YEAR_WORDS = ("lat", "lata")
# Point in Poland (ARCHITECTURE 6.1): a latitude and a longitude are never read
# as probabilities.
_LATITUDE = (49.0, 55.0)
_LONGITUDE = (14.0, 24.5)
_COORDINATE_GLUE_SYMBOLS = ",;°'\""
_COORDINATE_GLUE_WORDS = frozenset({"n", "e"})
_COORDINATE_GLUE_LENGTH = 3
# Units that make ``Q 12,5 m3/s`` a flow instead of a probability.
_FLOW_UNITS = frozenset({"m", "l", "dm", "cm", "mm", "km", "ha", "ls"})
_TEMPERATURE_UNITS = frozenset({"c", "k", "st", "stopni"})
_Q_WORDS = ("q", "qp")
# Symbols that glue a number to its neighbour (ranges, dates, times, versions).
_BINDING = DASHES + "/:."
# Words allowed between a cue and its number: ``prawdopodobieństwo przewyższenia 1%``.
_FILLER_STEMS = ("przewyzsz", "przekrocz", "wystap", "wynosz")
_HALVES = {
    "pol": Decimal("0.5"),
    "poltora": Decimal("1.5"),
    "poltorej": Decimal("1.5"),
}
# What may follow a bare number that is read as a probability. Anything else
# (``2 godziny``, ``3 z 4 arkuszy``, ``9 do 12``) makes it a quantity of
# something else.
_FOLLOWER_WORDS = frozenset(
    {
        *("i", "oraz", "lub", "albo", "a", "ale", "czyli", "tj", "np"),
        *("w", "we", "na", "przy", "dla", "przez", "wg", "wedlug"),
        *("bo", "gdy", "jesli", "aby", "zeby", "prosze", "dziekuje"),
    }
)
_FOLLOWER_SYMBOLS = ".,;:!?"


@dataclass(frozen=True)
class _Candidate:
    """One way to read a number: its value as a fraction and what it was written as."""

    value: float
    kind: str


@dataclass
class _Item:
    """A probability mention found in the command.

    ``number`` is set while a number still waits for its reading (``Q50``,
    ``dla 5``): the reading depends on the list the number belongs to. ``plain``
    names the marker (``%`` or ``lat``) of a bare ``N %`` / ``N lat``; it also
    applies to the bare numbers before it in a list. A ``loose`` item (``N lat``
    without a cue) is read only inside a list or in an answer.
    """

    first: int  # token range [first, last)
    last: int
    start: int  # character span
    end: int
    candidates: list[_Candidate] = field(default_factory=list)
    number: Decimal | None = None
    q: bool = False  # written with the ``Q`` prefix
    bare: bool = False  # a number with no marker at all
    cue: str | None = None  # "dla" or "probability" before a bare number
    plain: str | None = None
    loose: bool = False


def _from_percent(percent: Decimal) -> float:
    return float(percent / 100)


def _from_period(years: Decimal) -> float:
    return float(1 / years)


def _q_candidates(number: Decimal) -> list[_Candidate]:
    """Return the readings of ``Q<number>`` without a percent sign (ARCHITECTURE 4.4).

    ``Q50`` is 50 % or a 50-year period, so both are returned, percent first. Only
    one is possible for ``Q1`` (a one-year period gives p = 1, impossible: 1 %)
    and for ``Q100`` (100 % is impossible: T = 100) and both agree for ``Q10``.
    A period is a whole number of years; ``Q1,5`` can only be a percent.
    """
    candidates: list[_Candidate] = []
    if 0 < number < 100:  # Q100 would be 100 %: impossible, so only a period is left
        candidates.append(_Candidate(_from_percent(number), _PERCENT))
    # Q1 as a period would be T = 1 year, p = 1: impossible, so Q1 stays 1 % and is
    # accepted silently. A period is a whole number of years.
    if number == number.to_integral_value() and 2 <= number <= _MAX_PERIOD_YEARS:
        period = _Candidate(_from_period(number), _PERIOD)
        # Q10: both readings are 10 %, nothing to ask
        if not candidates or candidates[0].value != period.value:
            candidates.append(period)
    return candidates


def _bare_candidates(number: Decimal, cue: str | None) -> list[_Candidate]:
    """Return the readings of a bare number: always asked, even if one is impossible.

    After ``prawdopodobieństwo`` or ``p =`` a number strictly between 0 and 1 is a
    fraction and needs no question.
    """
    if cue == "probability" and 0 < number < 1:
        return [_Candidate(float(number), _FRACTION)]
    return [
        _Candidate(_from_percent(number), _PERCENT),
        _Candidate(float(number), _FRACTION),
    ]


def _convert(number: Decimal, marker: str) -> _Candidate:
    """Return the reading of a bare number whose list ends with ``%`` or ``lat``."""
    if marker == _PERCENT:
        return _Candidate(_from_percent(number), _PERCENT)
    return _Candidate(_from_period(number), _PERIOD)


def _format_number(value: float) -> str:
    """Format a number without exponent or trailing zeros: ``0.5``, ``1``, ``12.5``."""
    return f"{value:.9f}".rstrip("0").rstrip(".") or "0"


def probability_percent(probability: float) -> float:
    """
    Probability as a percent, without floating point noise.

    Examples
    --------
    >>> probability_percent(0.01), probability_percent(0.07)
    (1.0, 7.0)
    """
    return round(probability * 100, 9)


def _years_text(probability: float) -> str:
    """Return period in years of a probability, at most one decimal."""
    return _format_number(round(1 / probability, 1)) if probability > 0 else "-"


def _label_args(values: list[float], kind: str) -> dict[str, str]:
    """Texts for the label of a reading; the values of a list are joined by commas.

    The label texts end a percent with ``%``, so percents are joined by ``%, ``:
    ``p = 50%, 20%``.
    """
    if kind == _FRACTION:
        return {"value": ", ".join(_format_number(v) for v in values)}
    percent = "%, ".join(_format_number(probability_percent(v)) for v in values)
    if kind == _PERCENT:
        return {"percent": percent}
    return {"years": ", ".join(_years_text(v) for v in values), "percent": percent}


def _reading(candidate: _Candidate) -> Reading:
    return Reading(
        candidate.value,
        f"extractors.probability.{candidate.kind}",
        _label_args([candidate.value], candidate.kind),
    )


def _has_fraction(token: Token) -> bool:
    return "." in token.text or "," in token.text


def _in_poland(latitude: float, longitude: float) -> bool:
    return (
        _LATITUDE[0] <= latitude <= _LATITUDE[1]
        and _LONGITUDE[0] <= longitude <= _LONGITUDE[1]
    )


def _is_glue(token: Token) -> bool:
    """Whether a token may stand between latitude and longitude: ``, ° N``."""
    if token.kind == "sym":
        return token.text in _COORDINATE_GLUE_SYMBOLS
    return token.kind == "word" and token.text in _COORDINATE_GLUE_WORDS


def _coordinate_numbers(tokens: list[Token]) -> set[int]:
    """Return the indices of decimals that form a point in Poland (``52.23, 21.01``)."""
    found: set[int] = set()
    for index, token in enumerate(tokens):
        if token.kind != "num" or not _has_fraction(token):
            continue
        position = index + 1
        while (
            position <= index + _COORDINATE_GLUE_LENGTH
            and position < len(tokens)
            and _is_glue(tokens[position])
        ):
            position += 1
        if (
            position >= len(tokens)
            or tokens[position].kind != "num"
            or not _has_fraction(tokens[position])
        ):
            continue
        first, second = float(token.number), float(tokens[position].number)
        if _in_poland(first, second) or _in_poland(second, first):
            found.update((index, position))
    return found


def _ending_matches(word: str, endings: tuple[str, ...]) -> bool:
    """Whether ``word`` is one of the adjective forms, allowing one typo."""
    return word in endings or any(equals_within_one_edit(word, e) for e in endings)


def _is_percent_word(word: str) -> bool:
    return word == "proc" or prefix_matches(word, "procent")


class _Reader:
    """Finds the probability mentions of one text, left to right, never overlapping."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        # Numbers of a point are never probabilities
        self.coordinates = _coordinate_numbers(tokens)

    def items(self) -> list[_Item]:
        items: list[_Item] = []
        index = 0
        while index < len(self.tokens):
            item = self._item_at(index)
            if item is None:
                index += 1
            else:
                items.append(item)
                index = item.last
        return items

    def _item_at(self, index: int) -> _Item | None:
        for parse in (
            self._period_phrase,
            self._adjective,
            self._probability_cue,
            self._p_cue,
            self._q_item,
            self._percent_item,
            self._year_item,
            self._dla_item,
            self._plain_number,
        ):
            item = parse(index)
            if item is not None:
                return item
        return None

    # -- token helpers ---------------------------------------------------------

    def _is(self, index: int, kind: str, *texts: str) -> bool:
        return (
            0 <= index < len(self.tokens)
            and self.tokens[index].kind == kind
            and (not texts or self.tokens[index].text in texts)
        )

    def _make(self, first: int, last: int, **fields: Any) -> _Item:
        return _Item(
            first, last, self.tokens[first].start, self.tokens[last - 1].end, **fields
        )

    def _free_before(self, index: int) -> bool:
        """Whether the number is not glued to a word, dash or date part before it."""
        tokens = self.tokens
        if index == 0 or not attached(tokens[index - 1], tokens[index]):
            return True
        before = tokens[index - 1]
        return not (
            before.kind == "word" or (before.kind == "sym" and before.text in _BINDING)
        )

    def _glued_by_symbol(self, index: int) -> bool:
        """Whether a dash, slash or colon touches the token after ``index``."""
        tokens = self.tokens
        return (
            index + 1 < len(tokens)
            and attached(tokens[index], tokens[index + 1])
            and tokens[index + 1].kind == "sym"
            and tokens[index + 1].text in DASHES + "/:"
        )

    def _free_after(self, index: int) -> bool:
        """Whether the number is not glued to a word, dash or range part after it."""
        tokens = self.tokens
        if index + 1 >= len(tokens) or not attached(tokens[index], tokens[index + 1]):
            return True
        return tokens[index + 1].kind != "word" and not self._glued_by_symbol(index)

    def _isolated(self, index: int) -> bool:
        """Whether a number stands alone: not glued to a word, range or date."""
        return self._free_before(index) and self._free_after(index)

    def _skip_fillers(self, position: int) -> int:
        """Skip up to two words that may stand between a cue and its number."""
        for _ in range(2):
            if not self._is(position, "word"):
                break
            word = self.tokens[position].text
            if (
                word in ("p", "t")
                or word.startswith("rown")
                or any(prefix_matches(word, stem) for stem in _FILLER_STEMS)
            ):
                position += 1
            else:
                break
        return position

    def _percent_marker(self, index: int) -> int | None:
        """Token index after ``%``, ``procent`` or ``-procentowy`` at ``index``."""
        tokens = self.tokens
        if self._is(index, "sym", "%"):
            return index + 1
        if self._is(index, "word") and _is_percent_word(tokens[index].text):
            return index + 1
        if (
            index + 1 < len(tokens)
            and is_dash(tokens[index])
            and attached(tokens[index - 1], tokens[index])
            and attached(tokens[index], tokens[index + 1])
            and self._is(index + 1, "word")
            and _is_percent_word(tokens[index + 1].text)
        ):
            return index + 2
        return None

    def _bare(self, first: int, index: int, cue: str | None) -> _Item | None:
        """Read a number with no marker (``dla 5``), if it can be a probability."""
        number = self.tokens[index].number
        if (
            not 0 < number <= 100
            or index in self.coordinates
            or not self._isolated(index)
        ):
            return None
        return self._make(first, index + 1, number=number, bare=True, cue=cue)

    # -- forms -----------------------------------------------------------------

    def _period_phrase(self, index: int) -> _Item | None:
        """Cue phrases: ``okres powtarzalności``, ``T =``, ``raz na``, ``co``."""
        tokens = self.tokens
        if tokens[index].kind != "word":
            return None
        word = tokens[index].text
        if (
            prefix_matches(word, "okres")
            and self._is(index + 1, "word")
            and prefix_matches(tokens[index + 1].text, "powtarzalnosc")
        ):
            return self._period_after(index, index + 2, loose=False)
        if prefix_matches(word, "powtarzalnosc"):
            return self._period_after(index, index + 1, loose=False)
        if word == "t" and self._is(index + 1, "sym", "=", ":"):
            return self._period_after(index, index + 2, loose=False, temperature=True)
        if word == "raz" and self._is(index + 1, "word", "na"):
            return self._period_after(index, index + 2, loose=True)
        if word in ("co", "dla"):
            return self._period_after(index, index + 1, loose=True)
        return None

    def _period_after(
        self, first: int, position: int, *, loose: bool, temperature: bool = False
    ) -> _Item | None:
        """Read the number of years after a cue.

        A loose cue (``raz na``, ``co``, ``dla``) needs the unit ``lat`` and a whole
        number of years above one: ``dla 1 roku`` is not a probability.
        """
        tokens = self.tokens
        if not loose:
            position = self._skip_fillers(position)
            if self._is(position, "sym", "=", ":"):
                position += 1
        number = read_number(tokens, position)
        if number is None:
            return None
        years, after = number
        unit = self._is(after, "word", *_YEAR_WORDS)
        if years <= 0 or (loose and not unit):
            return None
        if self._is(after - 1, "num") and self._glued_by_symbol(after - 1):
            return None  # "T = 1/p" is a formula
        if loose and (
            years != years.to_integral_value() or not 1 < years <= _MAX_PERIOD_YEARS
        ):
            return None
        if temperature and (
            self._is(after, "sym", "°") or self._is(after, "word", *_TEMPERATURE_UNITS)
        ):
            return None
        return self._make(
            first,
            after + 1 if unit else after,
            candidates=[_Candidate(_from_period(years), _PERIOD)],
        )

    def _adjective(self, index: int) -> _Item | None:
        """Numeral adjectives: ``stuletnia``, ``50-letnia``, ``1-procentowy``."""
        tokens = self.tokens
        token = tokens[index]
        if token.kind == "word":
            years = compound_adjective(token.text, LETNI)
            if years is not None:
                candidate = _Candidate(_from_period(Decimal(years)), _PERIOD)
                return self._make(index, index + 1, candidates=[candidate])
            percent = compound_adjective(token.text, PROCENTOWY)
            if percent is not None:
                candidate = _Candidate(_from_percent(Decimal(percent)), _PERCENT)
                return self._make(index, index + 1, candidates=[candidate])
            return None
        if token.kind != "num" or (
            index > 0
            and tokens[index - 1].kind == "word"
            and attached(tokens[index - 1], token)
        ):
            return None
        position = index + 1
        if (
            position + 1 < len(tokens)
            and is_dash(tokens[position])
            and attached(token, tokens[position])
            and attached(tokens[position], tokens[position + 1])
        ):
            position += 1
        if not self._is(position, "word"):
            return None
        word = tokens[position].text
        if _ending_matches(word, LETNI) and token.number > 0:
            candidate = _Candidate(_from_period(token.number), _PERIOD)
        elif _ending_matches(word, PROCENTOWY):
            candidate = _Candidate(_from_percent(token.number), _PERCENT)
        else:
            return None
        return self._make(index, position + 1, candidates=[candidate])

    def _probability_cue(self, index: int) -> _Item | None:
        """``prawdopodobieństwo 0,01``, ``prawdopodobieństwem 2 %``."""
        tokens = self.tokens
        if tokens[index].kind != "word" or not prefix_matches(
            tokens[index].text, "prawdopodobienstw"
        ):
            return None
        position = self._skip_fillers(index + 1)
        if self._is(position, "sym", "=", ":"):
            position += 1
        return self._number_after_cue(index, position, "probability")

    def _p_cue(self, index: int) -> _Item | None:
        """``p = 1%``, ``p=0,01``."""
        if self._is(index, "word", "p") and self._is(index + 1, "sym", "=", ":"):
            return self._number_after_cue(index, index + 2, "probability")
        return None

    def _number_after_cue(self, first: int, position: int, cue: str) -> _Item | None:
        """Read a number after a cue: a percent at once, a bare number keeps the cue."""
        if not self._is(position, "num"):
            return None
        end = self._percent_marker(position + 1)
        if end is not None:
            candidate = _Candidate(
                _from_percent(self.tokens[position].number), _PERCENT
            )
            return self._make(first, end, candidates=[candidate])
        return self._bare(first, position, cue)

    def _q_item(self, index: int) -> _Item | None:
        """``Q1%``, ``Q 1 %``, ``Q=1,5%`` and ``Q50`` (no percent sign: ambiguous)."""
        tokens = self.tokens
        if not self._is(index, "word", *_Q_WORDS):
            return None
        position = index + 1
        if self._is(position, "sym", "=", ":", "_"):
            position += 1
        if not self._is(position, "num"):
            return None
        number = tokens[position].number
        end = self._percent_marker(position + 1)
        if end is not None:
            candidate = _Candidate(_from_percent(number), _PERCENT)
            return self._make(index, end, candidates=[candidate], q=True)
        after = position + 1
        if self._is(after, "word", *_FLOW_UNITS) or not self._free_after(position):
            return None
        return self._make(index, after, number=number, q=True)

    def _percent_item(self, index: int) -> _Item | None:
        """``1%``, ``0,5 %``, ``2 procent``, ``pięć procent``."""
        token = self.tokens[index]
        if token.kind == "word" and token.text in _HALVES:
            # "pół procenta", "półtora procenta"
            value, after = _HALVES[token.text], index + 1
        else:
            number = read_number(self.tokens, index)
            if number is None:
                return None
            value, after = number
        end = self._percent_marker(after)
        if end is None:
            return None
        candidate = _Candidate(_from_percent(value), _PERCENT)
        return self._make(index, end, candidates=[candidate], plain=_PERCENT)

    def _year_item(self, index: int) -> _Item | None:
        """``100 lat`` or ``sto lat`` without a cue: read in a list or an answer."""
        number = read_number(self.tokens, index)
        if number is None:
            return None
        years, after = number
        if (
            not self._is(after, "word", *_YEAR_WORDS)
            or years != years.to_integral_value()
            or not 1 < years <= _MAX_PERIOD_YEARS
        ):
            return None
        candidate = _Candidate(_from_period(years), _PERIOD)
        return self._make(
            index, after + 1, candidates=[candidate], plain=_PERIOD, loose=True
        )

    def _dla_item(self, index: int) -> _Item | None:
        """``dla 1``: a number after ``dla`` without any marker."""
        if not (self._is(index, "word", "dla") and self._is(index + 1, "num")):
            return None
        if any(
            parse(index + 1) is not None
            for parse in (self._percent_item, self._year_item, self._adjective)
        ):
            return None
        return self._bare(index, index + 1, "dla")

    def _plain_number(self, index: int) -> _Item | None:
        """Read a number with no cue as the continuation of a list or an answer."""
        if not self._is(index, "num"):
            return None
        return self._bare(index, index, None)


def _good_follower(tokens: list[Token], index: int) -> bool:
    """Whether what follows a bare number allows reading it as a probability."""
    if index >= len(tokens):
        return True
    token = tokens[index]
    if token.kind == "sym":
        return token.text in _FOLLOWER_SYMBOLS
    return (
        token.kind == "word"
        and token.text in _FOLLOWER_WORDS
        and not attached(tokens[index - 1], token)
    )


def _groups(tokens: list[Token], items: list[_Item]) -> Iterator[list[_Item]]:
    """Group the items into lists; a ``Q`` among bare numbers opens its own list."""
    for group in split_lists(tokens, items):
        current = [group[0]]
        for item in group[1:]:
            if item.q and not current[0].q:
                yield current
                current = []
            current.append(item)
        yield current


def _apply_markers(group: list[_Item]) -> None:
    """Let ``%`` or ``lat`` after bare numbers set their reading: ``dla 1, 2 i 10%``."""
    run: list[tuple[_Item, Decimal]] = []
    for item in group:
        if item.bare and item.number is not None:
            run.append((item, item.number))
            continue
        if item.plain is not None:
            for bare, number in run:
                bare.candidates = [_convert(number, item.plain)]
                bare.number = None
        run = []


def _licensed(group: list[_Item], index: int) -> bool:
    """Whether an item may open a list when the command has no cue before it.

    A bare number or ``N lat`` without a cue is not about probability, unless a
    ``%`` ends the run of bare numbers: ``1, 2, 5 i 10%`` is a list of percents.
    """
    item = group[index]
    if item.loose:
        return False
    if not (item.bare and item.cue is None):
        return True
    end = index
    while end < len(group) and group[end].bare:
        end += 1
    return end < len(group) and group[end].plain == _PERCENT


def _group_matches(
    tokens: list[Token], group: list[_Item], *, answer: bool
) -> list[Match]:
    """Return the matches of one list: separate, or whole-list readings if unsure."""
    if not answer:
        while group and not _licensed(group, 0):
            group = group[1:]
    if not group:
        return []
    cue, q_list = group[0].cue, group[0].q
    _apply_markers(group)
    if (
        group[-1].bare
        and group[-1].number is not None
        and not _good_follower(tokens, group[-1].last)
    ):
        while group and group[-1].bare and group[-1].number is not None:
            group = group[:-1]
    for item in group:
        if item.number is not None:
            item.candidates = (
                _q_candidates(item.number)
                if item.q or q_list
                else _bare_candidates(item.number, cue)
            )
            item.number = None
    group = [item for item in group if item.candidates]
    if not group:
        return []
    if len(group) == 1:
        item = group[0]
        return [
            Match(item.start, item.end, tuple(_reading(c) for c in item.candidates))
        ]
    if all(len(item.candidates) == 1 for item in group):
        return [
            Match(item.start, item.end, (_reading(item.candidates[0]),))
            for item in group
        ]
    # Some item is unclear: the whole list gets one reading per interpretation, so
    # Retman asks once and keeps the clear items (they have the same value in each).
    readings = []
    for index in range(2):
        values = [
            item.candidates[min(index, len(item.candidates) - 1)].value
            for item in group
        ]
        kind = next(
            item.candidates[index].kind
            for item in group
            if len(item.candidates) > index
        )
        readings.append(
            Reading(values, f"extractors.probability.{kind}", _label_args(values, kind))
        )
    return [Match(group[0].start, group[-1].end, tuple(readings))]


def _restated(text: str, first: Match, second: Match) -> Match | None:
    """Merge ``A (B)`` when B restates A, e.g. Retman's own ``1% (T = 100 lat)``."""
    if any(isinstance(r.value, list) for m in (first, second) for r in m.readings):
        return None
    if text[first.end : second.start].strip() != "(":
        return None
    rest = text[second.end :]
    if not rest.lstrip().startswith(")"):
        return None
    close = second.end + len(rest) - len(rest.lstrip()) + 1
    common = tuple(
        r
        for r in first.readings
        if any(math.isclose(r.value, o.value, rel_tol=1e-9) for o in second.readings)
    )
    return Match(first.start, close, common) if common else None


def _merge_restatements(text: str, matches: list[Match]) -> list[Match]:
    merged: list[Match] = []
    index = 0
    while index < len(matches):
        joined = (
            _restated(text, matches[index], matches[index + 1])
            if index + 1 < len(matches)
            else None
        )
        merged.append(joined or matches[index])
        index += 2 if joined else 1
    return merged


def _extract(text: str, *, answer: bool) -> list[Match]:
    tokens = tokenize(fold(text))
    matches: list[Match] = []
    for group in _groups(tokens, _Reader(tokens).items()):
        matches.extend(_group_matches(tokens, group, answer=answer))
    return _merge_restatements(text, matches)


def extract_probability(text: str) -> list[Match]:
    """
    Extract probabilities (as fractions) and return periods from a command.

    Unambiguous forms give one reading: ``1%``, ``p = 1%``, ``Q1,5%``,
    ``prawdopodobieństwo 0,01``, ``woda stuletnia``, ``50-letnia``,
    ``okres powtarzalności 50 lat``, ``T = 50``, ``raz na 50 lat``, ``co 100 lat``.
    ``Q50`` (no ``%``) can be 50 % or a 50-year period: two readings, percent
    first; ``Q10`` and ``Q1`` have only one possible meaning and ``Q100`` is read
    as a period. A number after ``dla``, ``prawdopodobieństwo`` or ``p =`` with no
    marker (``dla 1``, ``dla 0,5``) always has two readings: a percent and a
    fraction (the fraction is offered even when it is impossible).

    In a list (``Q1% i Q10%``, ``dla 1, 2 i 10%``) every item is a separate match.
    Items are joined by ``,``, ``;`` and one kind of conjunction (``i``, ``oraz``,
    ``lub``, ``a także``); a ``%`` or ``lat`` ending the list applies to the bare
    numbers before it. When some item of a list is unclear (``dla 1, 2 i 10``,
    ``Q50, Q20``) the list is ONE match whose readings are lists (all items as
    percents, all as periods or fractions; clear items keep their value), so that
    one question settles the whole list. For a ``multiple`` parameter the pipeline
    wraps a scalar reading the user picks into a list and stores a whole-list
    reading as it is.

    A bare number followed by another quantity (``dla 2 godzin``, ``dla 3 z 4
    arkuszy``) or taken by a point, date, year or code is not read.

    Parameters
    ----------
    text : str
        User command.

    Returns
    -------
    list[Match]
        Matches in order of appearance. Values are floats (fractions, ``0.01`` for
        1 %) or, for the whole-list readings, lists of floats. A value outside
        ``0 < p < 1`` (``150%``, ``dla 5`` read as a fraction) is returned as it
        is: :func:`validate_probability` rejects it, so it is never dropped
        silently.

    Examples
    --------
    >>> extract_probability("Q1%")[0].readings[0].value
    0.01
    >>> [m.readings[0].value for m in extract_probability("dla 1, 2 i 10%")]
    [0.01, 0.02, 0.1]
    >>> [r.value for r in extract_probability("Q50")[0].readings]
    [0.5, 0.02]
    """
    return _extract(text, answer=False)


def read_probability_answer(text: str) -> list[Match]:
    """
    Read an answer to the question about the probability.

    The rules are those of :func:`extract_probability`, except that the answer is
    about the probability only: a bare number needs no cue (``1`` still has two
    readings, because it can be a percent or a fraction) and ``100 lat`` or
    ``sto lat`` needs no cue either.
    """
    return _extract(text, answer=True)


def validate_probability(value: Any) -> str | None:
    """Return the translation key of the problem, or None for a float ``0 < p < 1``."""
    if isinstance(value, float) and math.isfinite(value) and 0 < value < 1:
        return None
    return "extractors.errors.invalid_probability"


def describe_probability(value: Any, texts: TextSource) -> str:
    """
    Plan text of a probability: percent and return period, ``1% (T = 100 lat)``.

    Parameters
    ----------
    value : Any
        Probability as a fraction (a valid value of the ``probability`` extractor).
    texts : TextSource
        Translations with ``extractors.display.probability`` (``percent`` and
        ``years``).
    """
    if validate_probability(value) is not None:
        return str(value)
    return texts.get(
        "extractors.display.probability",
        percent=_format_number(probability_percent(value)),
        years=_years_text(value),
    )

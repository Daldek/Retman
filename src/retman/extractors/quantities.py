"""Numbers with units read from Polish text: curve number, rainfall, area, durations.

The hydrological operations (Hydrolog) take quantities that a command states as a
number with its unit or after the word that names it: ``CN 72``, ``opad 50 mm``,
``powierzchnia 45,3 km²``, ``krok 5 min``, ``czas koncentracji 1,5 h``. Each extractor
reads one quantity in the unit of the tool (mm, km², minutes), by code and never by the
model (ARCHITECTURE 1.1, 4.3). A number is read only with its unit or its cue word,
never as part of a date, a code or another quantity, and several values of one
quantity are several matches, so Retman asks which one is meant (ARCHITECTURE 6.1).

Durations are those of :func:`retman.extractors.numbers.extract_duration`, told apart
by the word before them: ``krok``, ``co`` or ``interwał`` mark the time step,
``czas koncentracji`` or ``tc`` the time of concentration, and any other duration is
the duration of the rain. An answer to a question about one of these quantities may be
a bare number for the curve number, the depth and the area (the question names the
unit), but a duration needs its unit, as everywhere else.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from retman.extractors.base import Match, Reading, TextSource
from retman.extractors.numbers import (
    Token,
    attached,
    extract_duration,
    prefix_matches,
    read_number,
    split_lists,
    tokenize,
)
from retman.extractors.text import fold

# A unit after a number: the factor to the unit of the quantity and the index after it
Unit = tuple[Decimal, int]
UnitReader = Callable[[Sequence[Token], int], Unit | None]

# Bounds of the values (the tool's own limits, or the largest sensible value)
_CN_RANGE = (Decimal(1), Decimal(100))
# The largest daily rainfall ever measured is about 1,800 mm
_MAX_DEPTH_MM = 2000

_SQUARE = "2"
_HECTARE = Decimal("0.01")
# Words between a cue and its number that say nothing: "CN wynosi 72", "krok czasowy
# 5 min", "czas koncentracji równy 90 min"
_FILLERS = frozenset(
    {
        "o",
        "w",
        "z",
        "ze",
        "przy",
        "ok",
        "okolo",
        "rzedu",
        "jest",
        "to",
        "wynosi",
        "wynoszacy",
        "wynoszacym",
        "wynoszacej",
        "wynoszace",
        "rowny",
        "rowna",
        "rowne",
        "rownym",
        "rownej",
        "wartosc",
        "wartosci",
        "czas",
        "czasu",
        "czasie",
        "czasem",
        "czasowy",
        "czasowym",
        "czasowego",
        "czasowej",
        "czasowe",
        "obliczeniowy",
        "obliczeniowym",
        "obliczeniowego",
        "hietogramu",
        "hydrogramu",
    }
)
# Symbols between a cue and its number: "CN = 72", "tc: 90 min", "CN-72"
_GLUE = frozenset("=:-(")
# Words a list of values is joined by (``split_lists`` uses the same)
_LIST_WORDS = frozenset({"i", "oraz", "lub", "albo"})
# The longest run of fillers looked through between a cue and its number
_CUE_DISTANCE = 4

_CURVE_NUMBER = "cn"
_STEP = "step"
_CONCENTRATION = "concentration"
_STEP_WORDS = frozenset({"co", "dt"})
_STEP_STEMS = ("krok", "interwal", "rozdzielczosc", "odstep")
_CONCENTRATION_WORDS = frozenset({"tc"})
_CONCENTRATION_STEMS = ("koncentracj",)
# Time words after "na" that make a depth a rate: "50 mm na godzinę"
_TIME_STEMS = ("godzin", "minut", "dob", "dzien", "sekund")
# Units that end a list of curve numbers: "CN 72 i 50 mm", "CN 72 i 60 min"
_UNIT_WORDS = frozenset(
    {"min", "h", "godz", "s", "m", "km", "cm", "mm", "ha", "lat", "lata", "dni"}
)
_UNIT_STEMS = ("minut", "godzin", "sekund", "metr", "kilometr")
# Antecedent moisture conditions written between "CN" and its number
_AMC_WORDS = frozenset({"amc", "ii", "iii"})


def number_value(value: Decimal) -> int | float:
    """Return a JSON number: an ``int`` for a whole number, else a ``float``.

    Examples
    --------
    >>> number_value(Decimal("72")), number_value(Decimal("45.3"))
    (72, 45.3)
    """
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def format_quantity(value: float) -> str:
    """Format a number without exponent or trailing zeros: ``45.3``, ``72``, ``0.5``.

    Examples
    --------
    >>> format_quantity(45.30), format_quantity(72.0), format_quantity(0.025)
    ('45.3', '72', '0.025')
    """
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _word(tokens: Sequence[Token], index: int) -> str | None:
    """Return the text of a word token at ``index``, ``None`` for anything else."""
    if 0 <= index < len(tokens) and tokens[index].kind == "word":
        return tokens[index].text
    return None


def _code_number(tokens: Sequence[Token], index: int) -> bool:
    """Whether a number touches a word before it (``q10``, ``v2``: a code)."""
    return (
        tokens[index].kind == "num"
        and index > 0
        and tokens[index - 1].kind == "word"
        and attached(tokens[index - 1], tokens[index])
    )


# --- Cues --------------------------------------------------------------------


def _cue_of(word: str) -> str | None:
    if word == _CURVE_NUMBER:
        return _CURVE_NUMBER
    if word in _STEP_WORDS or any(word.startswith(stem) for stem in _STEP_STEMS):
        return _STEP
    if word in _CONCENTRATION_WORDS or any(
        prefix_matches(word, stem) for stem in _CONCENTRATION_STEMS
    ):
        return _CONCENTRATION
    return None


def cue_before(tokens: Sequence[Token], index: int) -> str | None:
    """Return the quantity the words before token ``index`` name, if any.

    The words are read backwards through fillers and ``=``/``:``: ``krok czasowy``
    names the time step, ``czas koncentracji`` or ``tc`` the time of concentration and
    ``CN`` the curve number; any other word ends the search.

    Examples
    --------
    >>> tokens = tokenize("krok czasowy 5 min")
    >>> cue_before(tokens, 2)
    'step'
    >>> cue_before(tokenize("opad 60 min"), 1) is None
    True
    """
    position = index - 1
    looked = 0
    while position >= 0 and looked <= _CUE_DISTANCE:
        token = tokens[position]
        position -= 1
        if token.kind == "sym" and token.text in _GLUE:
            continue
        if token.kind != "word":
            return None
        cue = _cue_of(token.text)
        if cue is not None:
            return cue
        if token.text not in _FILLERS:
            return None
        looked += 1
    return None


# --- Numbers with units ------------------------------------------------------


@dataclass
class _Item:
    """A number of a command: its tokens, value and, once known, its unit factor."""

    first: int
    last: int
    number: Decimal
    factor: Decimal | None = None


def _is_rate(tokens: Sequence[Token], index: int) -> bool:
    """Whether a unit is followed by ``/h`` or ``na godzinę``: a rate, not a depth."""
    if index < len(tokens) and tokens[index].text == "/":
        return True
    after = _word(tokens, index + 1)
    return (
        _word(tokens, index) == "na"
        and after is not None
        and (after == "h" or any(after.startswith(stem) for stem in _TIME_STEMS))
    )


def depth_unit(tokens: Sequence[Token], index: int) -> Unit | None:
    """Millimetres at ``index``: ``mm``, ``milimetrów``; never a rate (``mm/h``)."""
    word = _word(tokens, index)
    if word is None:
        return None
    if word != "mm" and not (
        len(word) >= len("milimetr") - 1 and prefix_matches(word, "milimetr")
    ):
        return None
    if _is_rate(tokens, index + 1):
        return None
    return Decimal(1), index + 1


def area_unit(tokens: Sequence[Token], index: int) -> Unit | None:
    """Square kilometres at ``index`` (``km²``, ``km2``, ``km kw.``) or hectares."""
    word = _word(tokens, index)
    if word is None:
        return None
    if word in ("ha", "hektar") or (len(word) >= 6 and prefix_matches(word, "hektar")):
        return _HECTARE, index + 1
    after = index + 1
    if word == "km":
        if (
            after < len(tokens)
            and tokens[after].text == _SQUARE
            and attached(tokens[index], tokens[after])
        ):
            return Decimal(1), after + 1
        if (
            after + 1 < len(tokens)
            and tokens[after].text == "^"
            and tokens[after + 1].text == _SQUARE
        ):
            return Decimal(1), after + 2
    elif not (len(word) >= len("kilometr") and prefix_matches(word, "kilometr")):
        return None
    square = _word(tokens, after)
    if square == "kw":
        end = after + 1
        if end < len(tokens) and tokens[end].text == ".":
            end += 1
        return Decimal(1), end
    if square is not None and prefix_matches(square, "kwadrat"):
        return Decimal(1), after + 1
    return None


def _items(tokens: Sequence[Token], unit_at: UnitReader) -> list[_Item]:
    """Numbers of the command, with the unit that follows each, if any.

    A code (``q10``) and a number another quantity names (``CN 72``, ``krok 5``) are
    not items, so that they never take the unit of a list next to them.
    """
    items: list[_Item] = []
    index = 0
    while index < len(tokens):
        number = read_number(tokens, index)
        if number is None:
            index += 1
            continue
        value, after = number
        if _code_number(tokens, index) or cue_before(tokens, index) is not None:
            index = after
            continue
        unit = unit_at(tokens, after)
        if unit is None:
            items.append(_Item(index, after, value))
            index = after
            continue
        factor, end = unit
        items.append(_Item(index, end, value, factor))
        index = end
    return items


def _with_units(tokens: Sequence[Token], items: list[_Item]) -> list[_Item]:
    """Items that have a unit; a list's last unit applies to it all (``50 i 70 mm``)."""
    found: list[_Item] = []
    for group in split_lists(tokens, items):
        factor: Decimal | None = None
        for item in reversed(group):
            if item.factor is not None:
                factor = item.factor
            elif factor is not None:
                item.factor = factor
        found.extend(item for item in group if item.factor is not None)
    return found


def _unit_matches(
    text: str, unit_at: UnitReader, label_key: str, *, bare: bool = False
) -> list[Match]:
    """Return the matches of a quantity with a unit, in the unit of the quantity.

    ``bare`` also reads numbers without a unit (an answer to the question about the
    quantity, which names the unit), but only when nothing has a unit.
    """
    tokens = tokenize(fold(text))
    items = _items(tokens, unit_at)
    chosen = _with_units(tokens, items)
    if not chosen and bare:
        chosen = [item for item in items if item.factor is None]
        for item in chosen:
            item.factor = Decimal(1)
    matches = []
    for item in chosen:
        assert item.factor is not None
        value = number_value(item.number * item.factor)
        matches.append(
            Match(
                tokens[item.first].start,
                tokens[item.last - 1].end,
                (Reading(value, label_key, {"value": format_quantity(value)}),),
            )
        )
    return matches


# --- Curve number ------------------------------------------------------------


def _unit_follows(tokens: Sequence[Token], index: int) -> bool:
    """Whether a unit stands at ``index``: millimetres, an area, a length or a time."""
    if index >= len(tokens):
        return False
    if tokens[index].text in ("%", "\u2030"):
        return True
    word = _word(tokens, index)
    return word is not None and (
        word in _UNIT_WORDS
        or any(prefix_matches(word, stem) for stem in _UNIT_STEMS)
        or depth_unit(tokens, index) is not None
        or area_unit(tokens, index) is not None
    )


def _curve_numbers(
    tokens: Sequence[Token], index: int
) -> list[tuple[int, int, Decimal]]:
    """Numbers after the cue ``CN`` at ``index``: ``(first, last, value)`` each.

    ``CN 72``, ``CN=72``, ``CN72``, ``CN wynosi 72``; a list (``CN 72 lub 75``) gives
    each value, but a number with a unit of its own (``CN 72 i 50 mm``) ends it.
    """
    position = index + 1
    while position < len(tokens) and (
        (tokens[position].kind == "sym" and tokens[position].text in _GLUE)
        or tokens[position].text == ")"
        or _word(tokens, position) in _FILLERS
        # The moisture condition the number is for: "CN II = 72", "CN(III) 85"
        or _word(tokens, position) in _AMC_WORDS
    ):
        position += 1
    number = read_number(tokens, position)
    if number is None or _unit_follows(tokens, number[1]):
        return []
    found = [(position, number[1], number[0])]
    position = number[1]
    while position + 1 < len(tokens):
        joiner = tokens[position]
        if not (joiner.text == "," or _word(tokens, position) in _LIST_WORDS):
            break
        following = read_number(tokens, position + 1)
        if following is None or _unit_follows(tokens, following[1]):
            break
        value, after = following
        found.append((position + 1, after, value))
        position = after
    return found


def extract_curve_number(text: str) -> list[Match]:
    """
    Extract SCS-CN curve numbers: ``CN 72``, ``CN=72,5``, ``CN wynosi 80``.

    A number is a curve number only after the word ``CN`` (with ``=``, ``:`` or a
    filler such as ``wynosi`` between); a list after it gives one match per value.

    Parameters
    ----------
    text : str
        User command.

    Returns
    -------
    list[Match]
        One match per value, one reading each: the number (``int`` when whole).

    Examples
    --------
    >>> [m.readings[0].value for m in extract_curve_number("dla CN=72 i opadu 50 mm")]
    [72]
    >>> [m.readings[0].value for m in extract_curve_number("CN 72 lub 75,5")]
    [72, 75.5]
    """
    tokens = tokenize(fold(text))
    matches: list[Match] = []
    for index, token in enumerate(tokens):
        if token.kind != "word" or token.text != _CURVE_NUMBER:
            continue
        for first, last, number in _curve_numbers(tokens, index):
            value = number_value(number)
            matches.append(
                Match(
                    tokens[first].start,
                    tokens[last - 1].end,
                    (
                        Reading(
                            value,
                            "extractors.curve_number.value",
                            {"value": format_quantity(value)},
                        ),
                    ),
                )
            )
    return matches


def read_curve_number_answer(text: str) -> list[Match]:
    """Read an answer to the question about the curve number: ``72`` is enough."""
    found = extract_curve_number(text)
    if found:
        return found
    return _unit_matches(
        text, lambda tokens, index: None, "extractors.curve_number.value", bare=True
    )


def validate_curve_number(value: Any) -> str | None:
    """Return the translation key of the problem, or ``None`` for 1 ≤ CN ≤ 100."""
    if _is_number(value) and _CN_RANGE[0] <= Decimal(str(value)) <= _CN_RANGE[1]:
        return None
    return "extractors.errors.invalid_curve_number"


def describe_curve_number(value: Any, texts: TextSource) -> str:
    """Plan text of a curve number."""
    if validate_curve_number(value) is not None:
        return str(value)
    return texts.get("extractors.display.curve_number", value=format_quantity(value))


# --- Rainfall depth ----------------------------------------------------------


def extract_rainfall_depth(text: str) -> list[Match]:
    """
    Extract rainfall depths in millimetres: ``50 mm``, ``38,4 mm``, ``50 milimetrów``.

    A number needs the unit (a list shares its last one: ``50 i 70 mm``); an
    intensity (``mm/h``, ``mm na godzinę``) and a range (``40-50 mm``) are no depth.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_rainfall_depth("opad 38,4 mm w 2 h")]
    [38.4]
    >>> extract_rainfall_depth("natężenie 50 mm/h")
    []
    """
    return _unit_matches(text, depth_unit, "extractors.rainfall_depth.value")


def read_rainfall_depth_answer(text: str) -> list[Match]:
    """Read an answer to the question about the depth: ``50`` is ``50 mm``."""
    return _unit_matches(text, depth_unit, "extractors.rainfall_depth.value", bare=True)


def validate_rainfall_depth(value: Any) -> str | None:
    """Return the translation key of the problem, or ``None`` for 0 < depth ≤ 2000."""
    if _is_number(value) and 0 < value <= _MAX_DEPTH_MM:
        return None
    return "extractors.errors.invalid_rainfall_depth"


def describe_rainfall_depth(value: Any, texts: TextSource) -> str:
    """Plan text of a rainfall depth."""
    if validate_rainfall_depth(value) is not None:
        return str(value)
    return texts.get("extractors.display.rainfall_depth", value=format_quantity(value))


# --- Catchment area ----------------------------------------------------------


def extract_catchment_area(text: str) -> list[Match]:
    """
    Extract an area in square kilometres: ``45,3 km²``, ``45 km2``, ``4530 ha``.

    Square kilometres are written ``km²``, ``km2``, ``km^2``, ``km kw.`` or in words;
    hectares are converted (100 ha = 1 km²). A length in kilometres is no area.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_catchment_area("zlewnia 45,3 km²")]
    [45.3]
    >>> [m.readings[0].value for m in extract_catchment_area("o powierzchni 250 ha")]
    [2.5]
    >>> extract_catchment_area("ciek długości 12 km")
    []
    """
    return _unit_matches(text, area_unit, "extractors.catchment_area.value")


def read_catchment_area_answer(text: str) -> list[Match]:
    """Read an answer to the question about the area: ``45,3`` is ``45,3 km²``."""
    return _unit_matches(text, area_unit, "extractors.catchment_area.value", bare=True)


def validate_catchment_area(value: Any) -> str | None:
    """Return the translation key of the problem, or ``None`` for an area > 0."""
    if _is_number(value) and value > 0:
        return None
    return "extractors.errors.invalid_catchment_area"


def describe_catchment_area(value: Any, texts: TextSource) -> str:
    """Plan text of an area."""
    if validate_catchment_area(value) is not None:
        return str(value)
    return texts.get("extractors.display.catchment_area", value=format_quantity(value))


# --- Durations by role -------------------------------------------------------


def _durations(text: str, role: str | None, label_key: str) -> list[Match]:
    """Durations whose cue is ``role`` (``None``: no cue), relabelled."""
    tokens = tokenize(fold(text))
    starts = {token.start: index for index, token in enumerate(tokens)}
    found: list[Match] = []
    for match in extract_duration(text):
        if cue_before(tokens, starts[match.start]) != role:
            continue
        reading = match.readings[0]
        found.append(
            Match(
                match.start,
                match.end,
                (Reading(reading.value, label_key, dict(reading.label_args)),),
            )
        )
    return found


def extract_rain_duration(text: str) -> list[Match]:
    """
    Extract the duration of a rain: a duration that no cue marks as something else.

    Examples
    --------
    >>> text = "opad 50 mm trwający 2 godziny, krok 10 min"
    >>> [m.readings[0].value for m in extract_rain_duration(text)]
    [120]
    """
    return _durations(text, None, "extractors.duration.minutes")


def extract_time_step(text: str) -> list[Match]:
    """
    Extract a time step: a duration after ``krok``, ``co``, ``interwał`` or ``dt``.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_time_step("opad 60 min z krokiem 5 min")]
    [5]
    >>> [m.readings[0].value for m in extract_time_step("co 10 minut")]
    [10]
    """
    return _durations(text, _STEP, "extractors.duration.step")


def extract_concentration_time(text: str) -> list[Match]:
    """
    Extract a time of concentration: a duration after ``czas koncentracji`` or ``tc``.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_concentration_time("tc = 1,5 h")]
    [90]
    """
    return _durations(text, _CONCENTRATION, "extractors.duration.concentration")

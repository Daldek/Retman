"""Numbers read from Polish text: spoken cardinals, number tokens and durations.

Extractors read values from a command by code, never by a model (ARCHITECTURE
1.1). This module holds what several of them share (a tokenizer for folded text,
the Polish numerals ``dwadzieścia``, ``pięćdziesięcioletni``,
``piętnastominutowy``) and the duration extractor (``15 min``, ``2 godziny``,
``półgodzinny``, ``1,5 godziny``). Text is compared folded (lowercase, no
diacritics) and words of five or more letters tolerate one typo (ADR-009).
"""

import re
from collections.abc import Callable, Hashable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Any, Protocol

from retman.extractors.base import Match, Reading, TextSource
from retman.extractors.text import fold, starts_within_one_edit

# --- Tokens ------------------------------------------------------------------

DASHES = "-\u2013\u2014\u2212"  # hyphen, en dash, em dash, minus sign
_JOINERS = r".,:/\-\u2013\u2014\u2212"
_DASH_JOINERS = r":/\-\u2013\u2014\u2212"
_TOKEN_RE = re.compile(
    # Digit groups joined by ".,:/-" (dates, versions, ranges, times) are never
    # read as one number: they are something else or ambiguous.
    rf"(?P<junk>[0-9]+(?:[{_JOINERS}][0-9]+){{2,}}|[0-9]+[{_DASH_JOINERS}][0-9]+)"
    r"|(?P<num>[0-9]+(?:[.,][0-9]+)?)"
    r"|(?P<word>[a-z]+)"
    r"|(?P<sym>\S)"
)
_COMMA_LIST_RE = re.compile(r"[0-9]+(?:,[0-9]+){2,}")
_MAX_DIGITS = 9


@dataclass(frozen=True)
class Token:
    """
    A piece of folded text with its position.

    Parameters
    ----------
    kind : str
        ``"num"`` (digits with an optional decimal part), ``"word"`` (letters),
        ``"sym"`` (any other single character) or ``"junk"`` (digit groups
        joined by ``.,:/-``, or a number too long to be one).
    text : str
        The folded text of the token.
    start, end : int
        Position in the text the token was taken from (``text[start:end]``).
    """

    kind: str
    text: str
    start: int
    end: int

    @property
    def number(self) -> Decimal:
        """Value of a ``"num"`` token (decimal comma accepted)."""
        return Decimal(self.text.replace(",", "."))


def tokenize(folded: str) -> list[Token]:
    """
    Split folded text into numbers, words, symbols and junk; spaces are dropped.

    Parameters
    ----------
    folded : str
        Text already passed through :func:`retman.extractors.text.fold`.

    Examples
    --------
    >>> [(t.kind, t.text) for t in tokenize("q1,5 % 2.01.2020")]
    [('word', 'q'), ('num', '1,5'), ('sym', '%'), ('junk', '2.01.2020')]
    """
    tokens = []
    for found in _TOKEN_RE.finditer(folded):
        kind = found.lastgroup or "sym"
        text = found.group()
        if kind == "junk" and _COMMA_LIST_RE.fullmatch(text):
            # Two or more commas cannot be one decimal number: "1,2,5" is a list
            # typed without spaces.
            for part in re.finditer(r"[0-9]+|,", text):
                start = found.start() + part.start()
                tokens.append(
                    Token(
                        "sym" if part.group() == "," else "num",
                        part.group(),
                        start,
                        start + len(part.group()),
                    )
                )
            continue
        if kind == "num" and any(
            len(part) > _MAX_DIGITS for part in re.split(r"[.,]", text)
        ):
            kind = "junk"
        tokens.append(Token(kind, text, found.start(), found.end()))
    return tokens


def attached(left: Token, right: Token) -> bool:
    """Whether two tokens touch, without a space between them."""
    return left.end == right.start


def is_dash(token: Token) -> bool:
    """Whether the token is a hyphen or a dash."""
    return token.kind == "sym" and token.text in DASHES


# Words that join the items of a list ("15, 30 i 60 min", "1 oraz 2", "a także").
_LIST_WORDS = frozenset({"i", "oraz", "lub", "albo"})
_MAX_SEPARATORS = 3


class Spanned(Protocol):
    """An item that covers the tokens from ``first`` up to, not including, ``last``."""

    first: int
    last: int


def _conjunction(tokens: Sequence[Token], start: int, stop: int) -> str | None:
    """What joins two items: the conjunction in ``tokens[start:stop]``.

    Returns ``""`` when only commas or semicolons join them and ``None`` when
    anything else lies between (so the items are not one list).
    """
    run = tokens[start:stop]
    if not run or len(run) > _MAX_SEPARATORS:
        return None
    words: list[str] = []
    position = 0
    while position < len(run):
        token = run[position]
        position += 1
        if token.kind == "sym" and token.text in ",;":
            continue
        if token.kind != "word":
            return None
        if token.text in _LIST_WORDS:
            words.append(token.text)
        elif (
            token.text == "a" and position < len(run) and run[position].text == "takze"
        ):
            words.append("a takze")
            position += 1
        else:
            return None
    return " ".join(words)


def split_lists[S: Spanned](
    tokens: Sequence[Token], items: Iterable[S]
) -> Iterator[list[S]]:
    """
    Group items into lists: items joined only by commas, semicolons and the words
    ``i``, ``oraz``, ``lub``, ``albo`` and ``a także``.

    A list has one kind of conjunction (``1, 2 i 5``, ``1 i 2 i 3``); a different one
    starts a new list, so ``dla 1, 2 i 5 oraz 15 min`` is two lists.
    """
    group: list[S] = []
    conjunction = ""
    for item in items:
        if group:
            joiner = _conjunction(tokens, group[-1].last, item.first)
            if joiner is not None and (
                not joiner or not conjunction or joiner == conjunction
            ):
                group.append(item)
                conjunction = conjunction or joiner
                continue
            yield group
            group = []
            conjunction = ""
        group.append(item)
    if group:
        yield group


# --- Typo tolerance ----------------------------------------------------------

_ALPHABET = "abcdefghijklmnopqrstuvwxyz"


@lru_cache(maxsize=16384)
def prefix_matches(word: str, stem: str) -> bool:
    """
    Whether ``word`` starts with ``stem``, tolerating one typo in long stems.

    Stems shorter than five letters match exactly: one letter changes the
    meaning of short words (``do``/``od``).

    Examples
    --------
    >>> prefix_matches("minutach", "minut"), prefix_matches("mniuty", "minut")
    (True, True)
    >>> prefix_matches("minimum", "minut"), prefix_matches("odpowiedz", "do")
    (False, False)
    """
    if word.startswith(stem):
        return True
    return len(word) >= len(stem) - 1 and starts_within_one_edit(word, stem)


def _neighbours(word: str) -> Iterator[str]:
    """Words one typo away: a missing, extra, changed or swapped letter."""
    for index in range(len(word) + 1):
        head, tail = word[:index], word[index:]
        if tail:
            yield head + tail[1:]
            if len(tail) > 1:
                yield head + tail[1] + tail[0] + tail[2:]
            for letter in _ALPHABET:
                if letter != tail[0]:
                    yield head + letter + tail[1:]
        for letter in _ALPHABET:
            yield head + letter + tail


def fuzzy_value[V: Hashable](
    word: str, lookup: Callable[[str], V | None], *, min_length: int = 5
) -> V | None:
    """
    Value of the only word within one typo of ``word`` that ``lookup`` knows.

    A typo that could mean two different values is not guessed (ARCHITECTURE
    6.1): the result is then ``None``, like for words shorter than ``min_length``.
    """
    if len(word) < min_length:
        return None
    values = {
        value for near in _neighbours(word) if (value := lookup(near)) is not None
    }
    return values.pop() if len(values) == 1 else None


# --- Spoken cardinals --------------------------------------------------------

# Nominative/accusative and genitive ("dla dwóch godzin", "okres stu lat").
_CARDINAL_FORMS: dict[int, tuple[str, ...]] = {
    0: ("zero",),
    1: ("jeden", "jedna", "jedno", "jednego", "jednej"),
    2: ("dwa", "dwie", "dwoch", "dwu"),
    3: ("trzy", "trzech"),
    4: ("cztery", "czterech"),
    5: ("piec", "pieciu"),
    6: ("szesc", "szesciu"),
    7: ("siedem", "siedmiu"),
    8: ("osiem", "osmiu"),
    9: ("dziewiec", "dziewieciu"),
    10: ("dziesiec", "dziesieciu"),
    11: ("jedenascie", "jedenastu"),
    12: ("dwanascie", "dwunastu"),
    13: ("trzynascie", "trzynastu"),
    14: ("czternascie", "czternastu"),
    15: ("pietnascie", "pietnastu"),
    16: ("szesnascie", "szesnastu"),
    17: ("siedemnascie", "siedemnastu"),
    18: ("osiemnascie", "osiemnastu"),
    19: ("dziewietnascie", "dziewietnastu"),
    20: ("dwadziescia", "dwudziestu"),
    30: ("trzydziesci", "trzydziestu"),
    40: ("czterdziesci", "czterdziestu"),
    50: ("piecdziesiat", "piecdziesieciu"),
    60: ("szescdziesiat", "szescdziesieciu"),
    70: ("siedemdziesiat", "siedemdziesieciu"),
    80: ("osiemdziesiat", "osiemdziesieciu"),
    90: ("dziewiecdziesiat", "dziewiecdziesieciu"),
    100: ("sto", "stu"),
    200: ("dwiescie", "dwustu"),
    300: ("trzysta", "trzystu"),
    400: ("czterysta", "czterystu"),
    500: ("piecset", "pieciuset"),
    600: ("szescset", "szesciuset"),
    700: ("siedemset", "siedmiuset"),
    800: ("osiemset", "osmiuset"),
    900: ("dziewiecset", "dziewieciuset"),
    1000: ("tysiac", "tysiaca"),
}
_CARDINALS = {form: value for value, forms in _CARDINAL_FORMS.items() for form in forms}


def polish_integer(word: str) -> int | None:
    """
    Value of a single Polish cardinal word, ``None`` for anything else.

    Words are folded first, so ``Pięć`` and ``piec`` are the same. Both the
    nominative and the genitive forms are known (``pięć``, ``pięciu``), but only
    whole numbers written as one word: ``dwadzieścia pięć`` is two words.

    Parameters
    ----------
    word : str
        One word, with or without Polish letters.

    Returns
    -------
    int or None
        0–1000 for ``zero`` … ``tysiąc``.

    Examples
    --------
    >>> polish_integer("piec"), polish_integer("dwadziescia"), polish_integer("sto")
    (5, 20, 100)
    >>> polish_integer("dwadziescia piec") is None
    True
    """
    return _CARDINALS.get(fold(word))


def _cardinal_class(value: int) -> tuple[int, bool]:
    """Place of a cardinal in a spoken number and whether nothing may follow it.

    Classes: thousand 0, hundreds 1, tens and teens 2, units 3. Spoken numbers go
    from the highest class down (``sto dwadzieścia pięć``) and a teen or a unit
    closes the number.
    """
    if value in (0, 1000):
        return 0, value == 0
    if value >= 100:
        return 1, False
    if value >= 20:
        return 2, False
    if value >= 10:
        return 2, True
    return 3, True


def read_spoken_number(tokens: Sequence[Token], index: int) -> tuple[int, int] | None:
    """
    Read Polish cardinal words from ``index``: ``(value, index after the words)``.

    The longest valid run is taken, so ``czterdzieści pięć`` is 45, not 5.

    Examples
    --------
    >>> read_spoken_number(tokenize("sto dwadziescia minut"), 0)
    (120, 2)
    """
    total = 0
    position = index
    next_class = 0
    while position < len(tokens) and tokens[position].kind == "word":
        value = _CARDINALS.get(tokens[position].text)
        if value is None:
            break
        place, closes = _cardinal_class(value)
        if place < next_class:
            break
        total += value
        next_class = 4 if closes else place + 1
        position += 1
    return (total, position) if position > index else None


def read_number(tokens: Sequence[Token], index: int) -> tuple[Decimal, int] | None:
    """
    Read a number written with digits or Polish words: ``(value, next index)``.

    Examples
    --------
    >>> read_number(tokenize("1,5 godziny"), 0)
    (Decimal('1.5'), 1)
    >>> read_number(tokenize("piec minut"), 0)
    (Decimal('5'), 1)
    """
    if index >= len(tokens):
        return None
    if tokens[index].kind == "num":
        return tokens[index].number, index + 1
    spoken = read_spoken_number(tokens, index)
    return None if spoken is None else (Decimal(spoken[0]), spoken[1])


# --- Compound numeral adjectives ---------------------------------------------

# Combining forms of numerals as they stand before an adjective ending:
# "dwu-godzinny", "dziesięcio-letni", "stu-letni", "pięciuset-letni", "tysiąc-letni".
_STEM_UNITS = {
    1: "jedno",
    2: "dwu",
    3: "trzy",
    4: "cztero",
    5: "piecio",
    6: "szescio",
    7: "siedmio",
    8: "osmio",
    9: "dziewiecio",
}
_STEM_TEENS = {
    10: "dziesiecio",
    11: "jedenasto",
    12: "dwunasto",
    13: "trzynasto",
    14: "czternasto",
    15: "pietnasto",
    16: "szesnasto",
    17: "siedemnasto",
    18: "osiemnasto",
    19: "dziewietnasto",
}
_STEM_TENS = {
    20: "dwudziesto",
    30: "trzydziesto",
    40: "czterdziesto",
    50: "piecdziesiecio",
    60: "szescdziesiecio",
    70: "siedemdziesiecio",
    80: "osiemdziesiecio",
    90: "dziewiecdziesiecio",
}
_STEM_HUNDREDS = {
    100: ("stu", "sto"),
    200: ("dwustu",),
    300: ("trzystu",),
    400: ("czterystu",),
    500: ("pieciuset", "piecset"),
    600: ("szesciuset", "szescset"),
    700: ("siedmiuset", "siedemset"),
    800: ("osmiuset", "osiemset"),
    900: ("dziewieciuset", "dziewiecset"),
}


def _stem_forms() -> list[tuple[str, int, int, bool]]:
    """Every combining form as ``(form, value, class, closes)``, longest first."""
    forms: list[tuple[str, int, int, bool]] = []
    forms.extend((form, value, 3, True) for value, form in _STEM_UNITS.items())
    forms.extend((form, value, 2, True) for value, form in _STEM_TEENS.items())
    forms.extend((form, value, 2, False) for value, form in _STEM_TENS.items())
    for value, variants in _STEM_HUNDREDS.items():
        forms.extend((form, value, 1, False) for form in variants)
    forms.append(("tysiac", 1000, 0, False))
    for table in (_STEM_UNITS, _STEM_TEENS, _STEM_TENS):
        forms.extend(
            (form + "tysiac", value * 1000, 0, False) for value, form in table.items()
        )
    return sorted(forms, key=lambda form: -len(form[0]))


_STEM_FORMS = _stem_forms()


def _parse_stem(stem: str, next_class: int) -> int | None:
    for form, value, place, closes in _STEM_FORMS:
        if place >= next_class and stem.startswith(form):
            rest = stem[len(form) :]
            if not rest:
                return value
            tail = _parse_stem(rest, 4 if closes else place + 1)
            if tail is not None:
                return value + tail
    return None


@lru_cache(maxsize=4096)
def combining_value(stem: str) -> int | None:
    """
    Value of a compound numeral prefix, ``None`` when ``stem`` is not one.

    Examples
    --------
    >>> combining_value("dwudziestopiecio"), combining_value("stupiecdziesiecio")
    (25, 150)
    >>> combining_value("pieciuset"), combining_value("tysiac")
    (500, 1000)
    >>> combining_value("wielo") is None
    True
    """
    return _parse_stem(stem, 0) if stem else None


def _endings(stem: str, tails: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(stem + tail for tail in tails)


# Adjective endings after the stem: "letni, letnia, letnie, letniego …" and
# "godzinny, godzinna, godzinne, godzinnego …".
_SOFT_TAILS = ("", "a", "e", "ego", "ej", "emu", "m", "ch", "mi")
_HARD_TAILS = ("y", "a", "e", "ego", "ej", "emu", "ym", "ych", "ymi")
LETNI = _endings("letni", _SOFT_TAILS)
PROCENTOWY = _endings("procentow", _HARD_TAILS)
MINUTOWY = _endings("minutow", _HARD_TAILS)
GODZINNY = _endings("godzinn", _HARD_TAILS) + _endings("godzinow", _HARD_TAILS)
# The shortest numeral adjective is "dwuletni" (8 letters); a typo may drop one.
_FUZZY_ADJECTIVE_LENGTH = 7


def _exact_compound(word: str, endings: tuple[str, ...]) -> int | None:
    if not word.endswith(endings):
        return None
    for ending in endings:
        if word.endswith(ending):
            return combining_value(word[: -len(ending)])
    return None


@lru_cache(maxsize=4096)
def compound_adjective(word: str, endings: tuple[str, ...]) -> int | None:
    """
    Number named by a compound adjective such as ``pięćdziesięcioletnia``.

    The word is the numeral's combining form and one of ``endings``; one typo is
    tolerated. A bare ending without a numeral (``letni`` = summer) never counts.

    Parameters
    ----------
    word : str
        Folded word.
    endings : tuple[str, ...]
        Folded adjective forms such as :data:`LETNI` or :data:`MINUTOWY`.

    Examples
    --------
    >>> compound_adjective("piecdziesiecioletnia", LETNI)
    50
    >>> compound_adjective("pietnastominutowych", MINUTOWY)
    15
    >>> compound_adjective("letnia", LETNI) is None
    True
    """
    value = _exact_compound(word, endings)
    if value is None:
        value = fuzzy_value(
            word,
            lambda near: _exact_compound(near, endings),
            min_length=_FUZZY_ADJECTIVE_LENGTH,
        )
    return value


# --- Durations ---------------------------------------------------------------

_HOUR = 60
_QUARTER_HOUR = 15
_QUARTERS = frozenset({"kwadrans", "kwadransa", "kwadransu", "kwadransie"})
_HALF_WORDS = {
    "pol": Decimal("0.5"),
    "poltora": Decimal("1.5"),
    "poltorej": Decimal("1.5"),
}


# Common words one typo away from a unit: "rodzin(a)" is not "godzin(a)".
_NOT_UNITS = ("rodzin",)


@lru_cache(maxsize=4096)
def _unit_minutes(word: str) -> int | None:
    """Minutes in the unit a word names: ``min``, ``h``, ``godzin…``, ``kwadrans…``."""
    if word == "min":
        return 1
    if word in ("h", "godz"):
        return _HOUR
    if word.startswith(_NOT_UNITS) or word == "minus":
        return None
    if prefix_matches(word, "minut"):
        return 1
    if prefix_matches(word, "godzin"):
        return _HOUR
    if prefix_matches(word, "kwadrans"):
        return _QUARTER_HOUR
    return None


def _exact_fused(word: str, *, allow_bare: bool) -> Decimal | None:
    """Minutes of a one-word duration: ``dwugodzinny``, ``półgodzinny``, ``godzinny``.

    ``allow_bare`` accepts words without a numeral (``godzinny`` = 1 h,
    ``kwadrans``); typo-corrected words must not, because ``godziny`` is one typo
    away from ``godzinny`` and means just hours.
    """
    if word in _QUARTERS:
        return Decimal(_QUARTER_HOUR) if allow_bare else None
    for endings, factor in ((GODZINNY, _HOUR), (MINUTOWY, 1)):
        if not word.endswith(endings):
            continue
        ending = next(e for e in endings if word.endswith(e))
        stem = word[: -len(ending)]
        if not stem:
            return Decimal(_HOUR) if allow_bare and factor == _HOUR else None
        if factor == _HOUR and stem in _HALF_WORDS:
            return _HALF_WORDS[stem] * factor
        number = combining_value(stem)
        return None if number is None else Decimal(number * factor)
    return None


@lru_cache(maxsize=4096)
def _fused_minutes(word: str) -> Decimal | None:
    value = _exact_fused(word, allow_bare=True)
    if value is None:
        value = fuzzy_value(
            word,
            lambda near: _exact_fused(near, allow_bare=False),
            min_length=_FUZZY_ADJECTIVE_LENGTH,
        )
    return value


@dataclass
class _Item:
    """One number of a command with what is known about its unit.

    ``minutes`` is set for items with a unit (or a one-word duration), ``number``
    for numbers still waiting for the unit of the list they belong to; ``unit``
    (minutes per unit) is what a list's trailing unit hands to its other numbers.
    """

    first: int
    last: int
    minutes: Decimal | None = None
    number: Decimal | None = None
    unit: int | None = None


def _word_at(tokens: Sequence[Token], index: int, *texts: str) -> bool:
    return (
        0 <= index < len(tokens)
        and tokens[index].kind == "word"
        and tokens[index].text in texts
    )


def _after_word(tokens: Sequence[Token], index: int) -> bool:
    """Whether a number token touches a word before it (``q10``, ``v2``: a code)."""
    return (
        index > 0
        and tokens[index - 1].kind == "word"
        and attached(tokens[index - 1], tokens[index])
    )


def _unit_at(
    tokens: Sequence[Token], index: int, previous: Token
) -> tuple[int, int] | None:
    """Duration unit at ``index``: ``(minutes per unit, next index)``.

    A hyphen touching both neighbours is skipped (``15-minutowy``).
    """
    position = index
    if (
        position + 1 < len(tokens)
        and is_dash(tokens[position])
        and attached(previous, tokens[position])
        and attached(tokens[position], tokens[position + 1])
    ):
        position += 1
    if position >= len(tokens) or tokens[position].kind != "word":
        return None
    minutes = _unit_minutes(tokens[position].text)
    return None if minutes is None else (minutes, position + 1)


def _extend_with_minutes(
    tokens: Sequence[Token], end: int, hours: Decimal
) -> tuple[Decimal, int] | None:
    """Total minutes when hours are followed by minutes: ``1 h 30 min``, ``1h30``."""
    position = end
    if (
        position < len(tokens)
        and tokens[position].text == "."
        and attached(tokens[position - 1], tokens[position])
    ):
        position += 1
    if _word_at(tokens, position, "i"):
        position += 1
    number = read_number(tokens, position)
    if number is None:
        return None
    minutes, after = number
    if minutes != minutes.to_integral_value() or not 0 < minutes < _HOUR:
        return None
    unit = _unit_at(tokens, after, tokens[after - 1])
    if unit is not None and unit[0] == 1:
        return hours * _HOUR + minutes, unit[1]
    if (
        unit is None
        and position == end
        and tokens[end - 1].text == "h"
        and tokens[position].kind == "num"
        and attached(tokens[end - 1], tokens[position])
    ):
        return hours * _HOUR + minutes, after
    return None


def _number_with_unit(tokens: Sequence[Token], index: int) -> _Item | None:
    number = read_number(tokens, index)
    if number is None or (tokens[index].kind == "num" and _after_word(tokens, index)):
        return None
    value, after = number
    if _word_at(tokens, after, "i") and _word_at(tokens, after + 1, "pol"):
        # "dwie i pół godziny"
        half = _unit_at(tokens, after + 2, tokens[after + 1])
        if half is not None and half[0] == _HOUR:
            return _Item(index, half[1], (value + Decimal("0.5")) * _HOUR)
    unit = _unit_at(tokens, after, tokens[after - 1])
    if unit is None:
        return None
    factor, end = unit
    if factor == _HOUR and value == value.to_integral_value():
        longer = _extend_with_minutes(tokens, end, value)
        if longer is not None:
            return _Item(index, longer[1], longer[0], unit=1)
    return _Item(index, end, value * factor, unit=factor)


def _word_duration(tokens: Sequence[Token], index: int) -> _Item | None:
    """Durations that need no number: ``godzinny``, ``półgodzinny``, ``kwadrans`` …"""
    word = tokens[index].text
    fused = _fused_minutes(word)
    if fused is not None:
        return _Item(index, index + 1, fused)
    if word in _HALF_WORDS or word == "cwierc":
        # "pół godziny", "półtorej godziny", "ćwierć godziny"
        unit = _unit_at(tokens, index + 1, tokens[index])
        if unit is not None and unit[0] == _HOUR:
            fraction = _HALF_WORDS.get(word, Decimal("0.25"))
            return _Item(index, unit[1], fraction * _HOUR)
    if word in ("godzina", "godzine"):
        # "godzina i 30 minut"; a lone "godzina" can be the time of day
        longer = _extend_with_minutes(tokens, index + 1, Decimal(1))
        if longer is not None:
            return _Item(index, longer[1], longer[0], unit=1)
    return None


def _duration_items(tokens: Sequence[Token]) -> list[_Item]:
    items: list[_Item] = []
    index = 0
    while index < len(tokens):
        item = _word_duration(tokens, index) if tokens[index].kind == "word" else None
        item = item or _number_with_unit(tokens, index)
        if item is None:
            number = read_number(tokens, index)
            if number is not None and not (
                tokens[index].kind == "num" and _after_word(tokens, index)
            ):
                item = _Item(index, number[1], number=number[0])
        if item is None:
            index += 1
        else:
            items.append(item)
            index = item.last
    return items


def _apply_trailing_units(group: list[_Item]) -> None:
    """Give numbers without a unit the unit ending their list (``15, 30 i 60 min``)."""
    unit: int | None = None
    for item in reversed(group):
        if item.unit is not None:
            unit = item.unit
        elif item.minutes is None and item.number is not None and unit is not None:
            item.minutes = item.number * unit


def _durations(tokens: Sequence[Token]) -> list[tuple[_Item, Decimal]]:
    """Items that are durations, with their minutes, in order of appearance."""
    found: list[tuple[_Item, Decimal]] = []
    for group in split_lists(tokens, _duration_items(tokens)):
        _apply_trailing_units(group)
        found.extend((item, item.minutes) for item in group if item.minutes is not None)
    return found


def extract_duration(text: str) -> list[Match]:
    """
    Extract durations (whole minutes) from a command.

    Forms: ``15 min``, ``15 minut``, ``15-minutowy``, ``1 h``, ``2 godziny``,
    ``3 godz.``, ``1,5 godziny``, ``dwie godziny``, ``pięć minut``,
    ``dwugodzinny``, ``godzinny``, ``półgodzinny``, ``pół godziny``,
    ``półtorej godziny``, ``kwadrans``, ``1 h 30 min``. In a list the trailing
    unit applies to every number before it (``15, 30 i 60 min``); a number
    without any unit is never a duration. Durations that are not a whole number
    of minutes (``1,3 min``) give no reading, and neither does a range
    (``5-10 min``). A list uses one conjunction (:func:`split_lists`), so in
    ``dla 1, 2 i 5 oraz 15 min`` only the last number gets the unit.

    Parameters
    ----------
    text : str
        User command.

    Returns
    -------
    list[Match]
        One match per duration in order of appearance, one reading each: an
        ``int`` number of minutes.

    Examples
    --------
    >>> [m.readings[0].value for m in extract_duration("dla 15, 30 i 60 min")]
    [15, 30, 60]
    >>> extract_duration("2 godziny")[0].readings[0].value
    120
    """
    tokens = tokenize(fold(text))
    matches = []
    for item, exact in _durations(tokens):
        if exact != exact.to_integral_value():
            continue
        minutes = int(exact)
        matches.append(
            Match(
                tokens[item.first].start,
                tokens[item.last - 1].end,
                (
                    Reading(
                        minutes,
                        "extractors.duration.minutes",
                        {"minutes": str(minutes)},
                    ),
                ),
            )
        )
    return matches


def read_duration_answer(text: str) -> list[Match]:
    """
    Read an answer to the question about a duration.

    The rules are those of :func:`extract_duration`. A bare number is not read
    as minutes, so Retman asks again and shows an example with a unit.
    """
    return extract_duration(text)


def validate_duration(value: Any) -> str | None:
    """Translation key of the problem, or ``None`` for a whole number of minutes ≥ 1."""
    if type(value) is int and value >= 1:
        return None
    return "extractors.errors.invalid_duration"


def describe_duration(value: Any, texts: TextSource) -> str:
    """
    Plan text of a duration: whole hours as ``2 h``, anything else in minutes.

    Parameters
    ----------
    value : Any
        Minutes (a valid value of the ``duration`` extractor).
    texts : TextSource
        Translations with ``extractors.display.duration`` (``minutes``) and
        ``extractors.display.duration_hours`` (``hours``).
    """
    if validate_duration(value) is not None:
        return str(value)
    if value % _HOUR == 0:
        return texts.get("extractors.display.duration_hours", hours=str(value // _HOUR))
    return texts.get("extractors.display.duration", minutes=str(value))

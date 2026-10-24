"""Polish numerals and durations read from a command, without a model or a tool."""

import json
from decimal import Decimal
from typing import Any

import pytest

from retman.extractors.numbers import (
    GODZINNY,
    LETNI,
    MINUTOWY,
    PROCENTOWY,
    combining_value,
    compound_adjective,
    describe_duration,
    extract_duration,
    fuzzy_value,
    polish_integer,
    read_duration_answer,
    read_number,
    read_spoken_number,
    tokenize,
    validate_duration,
)


class _Texts:
    """Translations stand-in: shows which key and arguments the code asked for."""

    def get(self, key: str, **args: object) -> str:
        return key + "|" + ",".join(f"{name}={value}" for name, value in args.items())


def _minutes(command: str) -> list[int]:
    return [match.readings[0].value for match in extract_duration(command)]


@pytest.mark.parametrize(
    ("word", "value"),
    [
        ("zero", 0),
        ("jeden", 1),
        ("jedna", 1),
        ("jedno", 1),
        ("dwa", 2),
        ("dwie", 2),
        ("trzy", 3),
        ("cztery", 4),
        ("piec", 5),
        ("Pięć", 5),
        ("szesc", 6),
        ("siedem", 7),
        ("osiem", 8),
        ("dziewiec", 9),
        ("dziesiec", 10),
        ("jedenascie", 11),
        ("dwanascie", 12),
        ("trzynascie", 13),
        ("czternascie", 14),
        ("pietnascie", 15),
        ("szesnascie", 16),
        ("siedemnascie", 17),
        ("osiemnascie", 18),
        ("dziewietnascie", 19),
        ("dwadziescia", 20),
        ("trzydziesci", 30),
        ("czterdziesci", 40),
        ("piecdziesiat", 50),
        ("szescdziesiat", 60),
        ("siedemdziesiat", 70),
        ("osiemdziesiat", 80),
        ("dziewiecdziesiat", 90),
        ("sto", 100),
        ("dwiescie", 200),
        ("trzysta", 300),
        ("czterysta", 400),
        ("piecset", 500),
        ("szescset", 600),
        ("siedemset", 700),
        ("osiemset", 800),
        ("dziewiecset", 900),
        ("tysiac", 1000),
        # genitive, as after "dla": "dla dwóch godzin", "okres stu lat"
        ("dwoch", 2),
        ("pieciu", 5),
        ("pietnastu", 15),
        ("dwudziestu", 20),
        ("stu", 100),
        ("dwustu", 200),
        ("pieciuset", 500),
    ],
)
def test_polish_integer_reads_cardinal_words(word: str, value: int) -> None:
    assert polish_integer(word) == value


@pytest.mark.parametrize(
    "word", ["", "dwadziescia piec", "minut", "tysiace", "sto1", "piecc", "5"]
)
def test_polish_integer_knows_only_single_cardinal_words(word: str) -> None:
    assert polish_integer(word) is None


@pytest.mark.parametrize(
    ("text", "value", "words"),
    [
        ("czterdziesci piec minut", 45, 2),
        ("sto dwadziescia minut", 120, 2),
        ("dwiescie piecdziesiat lat", 250, 2),
        ("dwie godziny", 2, 1),
        ("piec piec minut", 5, 1),
        ("pietnascie piec", 15, 1),
    ],
)
def test_read_spoken_number_takes_the_whole_number(
    text: str, value: int, words: int
) -> None:
    assert read_spoken_number(tokenize(text), 0) == (value, words)


def test_read_number_reads_digits_with_decimal_comma_or_words() -> None:
    assert read_number(tokenize("1,5 h"), 0) == (Decimal("1.5"), 1)
    assert read_number(tokenize("piec min"), 0) == (Decimal(5), 1)
    assert read_number(tokenize("min"), 0) is None


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("2.01.2020", ["junk"]),
        ("0.7.2", ["junk"]),
        ("5-10", ["junk"]),
        ("10:30", ["junk"]),
        ("1,5", ["num"]),
        ("1,2,5", ["num", "sym", "num", "sym", "num"]),
        ("12345678901", ["junk"]),
    ],
)
def test_tokenize_never_reads_joined_digit_groups_as_one_number(
    text: str, kinds: list[str]
) -> None:
    assert [token.kind for token in tokenize(text)] == kinds


@pytest.mark.parametrize(
    ("word", "value"),
    [
        ("dwuletnia", 2),
        ("trzyletnia", 3),
        ("czteroletnia", 4),
        ("piecioletnia", 5),
        ("szescioletnia", 6),
        ("siedmioletnia", 7),
        ("osmioletnia", 8),
        ("dziewiecioletnia", 9),
        ("dziesiecioletnia", 10),
        ("jedenastoletnia", 11),
        ("dwunastoletnia", 12),
        ("trzynastoletnia", 13),
        ("czternastoletnia", 14),
        ("pietnastoletnia", 15),
        ("szesnastoletnia", 16),
        ("siedemnastoletnia", 17),
        ("osiemnastoletnia", 18),
        ("dziewietnastoletnia", 19),
        ("dwudziestoletnia", 20),
        ("dwudziestopiecioletnia", 25),
        ("trzydziestoletnia", 30),
        ("czterdziestoletnia", 40),
        ("piecdziesiecioletnia", 50),
        ("szescdziesiecioletnia", 60),
        ("siedemdziesiecioletnia", 70),
        ("osiemdziesiecioletnia", 80),
        ("dziewiecdziesiecioletnia", 90),
        ("stuletnia", 100),
        ("stoletnia", 100),
        ("stupiecdziesiecioletnia", 150),
        ("dwustuletnia", 200),
        ("dwustupiecdziesiecioletnia", 250),
        ("trzystuletnia", 300),
        ("czterystuletnia", 400),
        ("piecsetletnia", 500),
        ("pieciusetletnia", 500),
        ("szescsetletnia", 600),
        ("szesciusetletnia", 600),
        ("siedemsetletnia", 700),
        ("siedmiusetletnia", 700),
        ("osiemsetletnia", 800),
        ("osmiusetletnia", 800),
        ("dziewiecsetletnia", 900),
        ("dziewieciusetletnia", 900),
        ("tysiacletnia", 1000),
        ("dwutysiacletnia", 2000),
        ("pieciotysiacletnia", 5000),
        ("dziesieciotysiacletnia", 10000),
    ],
)
def test_compound_adjective_reads_numeral_adjectives_with_letni(
    word: str, value: int
) -> None:
    assert compound_adjective(word, LETNI) == value


@pytest.mark.parametrize("ending", LETNI)
def test_compound_adjective_knows_every_gender_and_case_of_letni(ending: str) -> None:
    assert compound_adjective("piecdziesiecio" + ending, LETNI) == 50


@pytest.mark.parametrize(
    ("word", "endings", "value"),
    [
        ("pietnastominutowych", MINUTOWY, 15),
        ("dwugodzinny", GODZINNY, 2),
        ("jednoprocentowa", PROCENTOWY, 1),
        ("dziesieciominutowy", MINUTOWY, 10),
    ],
)
def test_compound_adjective_works_for_minutes_hours_and_percents(
    word: str, endings: tuple[str, ...], value: int
) -> None:
    assert compound_adjective(word, endings) == value


@pytest.mark.parametrize(
    "word", ["letni", "letnia", "wieloletni", "kilkuletni", "stulecie", "godzinny"]
)
def test_compound_adjective_needs_a_numeral_before_the_ending(word: str) -> None:
    assert compound_adjective(word, LETNI) is None


@pytest.mark.parametrize(
    "word", ["piecdziesieciolenia", "piecdziesiecioletnai", "piecdziesieciooletnia"]
)
def test_compound_adjective_tolerates_one_typo(word: str) -> None:
    assert compound_adjective(word, LETNI) == 50


def test_combining_value_is_none_for_text_that_is_no_numeral() -> None:
    assert combining_value("") is None
    assert combining_value("wielo") is None
    assert combining_value("dwudziestopiecio") == 25


def test_fuzzy_value_does_not_guess_between_two_values() -> None:
    values = {"dziesiec": 10, "dziewiec": 9}

    assert fuzzy_value("dziesiac", values.get) == 10
    assert fuzzy_value("dziexiec", values.get) is None
    assert fuzzy_value("dzie", values.get) is None


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("15 min", 15),
        ("15 minut", 15),
        ("15 minuty", 15),
        ("15 min.", 15),
        ("15min", 15),
        ("15-minutowy", 15),
        ("15-minutowa", 15),
        ("15-minutowe", 15),
        ("15-minutowych", 15),
        ("15 minutowy", 15),
        ("godzinny", 60),
        ("godzinna", 60),
        ("opad godzinny", 60),
        ("1 h", 60),
        ("1 godz.", 60),
        ("1 godzina", 60),
        ("60 min", 60),
        ("2 godziny", 120),
        ("2 godzin", 120),
        ("2h", 120),
        ("3 godz", 180),
        ("dwugodzinny", 120),
        ("trzygodzinna", 180),
        ("polgodzinny", 30),
        ("pol godziny", 30),
        ("kwadrans", 15),
        ("cwierc godziny", 15),
        ("trzy kwadranse", 45),
        ("1,5 godziny", 90),
        ("0,3 h", 18),
        ("poltorej godziny", 90),
        ("dwie godziny", 120),
        ("piec minut", 5),
        ("pietnascie minut", 15),
        ("pietnastominutowy", 15),
        ("trzydziestominutowa", 30),
        ("dla dwoch godzin", 120),
        ("dla pieciu minut", 5),
        ("12 h", 720),
    ],
)
def test_extract_duration_reads_one_duration(command: str, expected: int) -> None:
    assert _minutes(command) == [expected]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("15, 30 i 60 min", [15, 30, 60]),
        ("1 i 2 godziny", [60, 120]),
        ("15 min, 1 h, 2 h", [15, 60, 120]),
        ("15; 30 oraz 45 minut", [15, 30, 45]),
        ("5 lub 10 min", [5, 10]),
        ("5 a także 10 min", [5, 10]),
        ("15,30,60 min", [15, 30, 60]),
        ("dwie i trzy godziny", [120, 180]),
        ("15 i 30 min oraz 1 i 2 h", [15, 30, 60, 120]),
        ("1 i 2 i 3 godziny", [60, 120, 180]),
        # a different conjunction starts a new list: it gets no trailing unit
        ("dla 1, 2 i 5 oraz 15 min", [15]),
        ("dla 1, 2 i 5 oraz 15, 30 i 60 min", [15, 30, 60]),
        ("15 min, 30, 60 min", [15, 30, 60]),
        # a number without any unit is never a duration
        ("15 min i 30", [15]),
        ("dla 15, 30", []),
    ],
)
def test_extract_duration_lists_share_the_trailing_unit(
    command: str, expected: list[int]
) -> None:
    assert _minutes(command) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("czterdziesci piec minut", 45),
        ("sto dwadziescia minut", 120),
        ("1 h 30 min", 90),
        ("1h30", 90),
        ("2 godz. 15 min", 135),
        ("godzina i 30 minut", 90),
        ("2 godziny i 30 minut", 150),
        ("dwie godziny i trzydziesci minut", 150),
        ("dwie i pol godziny", 150),
    ],
)
def test_extract_duration_reads_several_words_as_one_duration(
    command: str, expected: int
) -> None:
    assert _minutes(command) == [expected]


def test_extract_duration_separated_hours_and_minutes_are_two_durations() -> None:
    assert _minutes("1 h, 30 min") == [60, 30]
    assert _minutes("30 min 1 h") == [30, 60]


@pytest.mark.parametrize(
    "command",
    [
        "15",
        "dla 15",
        "H 150",
        "Q10",
        "Q5H",
        "x2h",
        "dla 50 lat",
        "dla 2020 roku",
        "minimum 5",
        "5 minimum",
        "5 minus",
        "1,3 min",
        "5-10 min",
        "godziny pracy",
        "o godzinie 14",
        "godzina 14",
        "przez godzine",
        "dwoch rodzin",
        "stacja 0-123-45-H1",
        "dla 1, 2 i 10%",
        "N-34-130-D",
    ],
)
def test_extract_duration_does_not_read_non_durations(command: str) -> None:
    assert extract_duration(command) == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("15 MINUT", 15),
        ("15 minutt", 15),
        ("15 mniut", 15),
        ("2 godizny", 120),
        ("DWIE GODZINY", 120),
        ("Pietnascie minut", 15),
        ("dwugodzinyn", 120),
        ("polgodzinnny", 30),
    ],
)
def test_extract_duration_ignores_case_diacritics_and_one_typo(
    command: str, expected: int
) -> None:
    assert _minutes(command) == [expected]


def test_extract_duration_does_not_correct_short_unit_words() -> None:
    assert extract_duration("15 mi") == []
    assert extract_duration("15 hh") == []


def test_extract_duration_spans_cover_the_number_and_its_unit() -> None:
    text = "Dla 15 minut i 2 godzin oraz 1,5 h"

    matches = extract_duration(text)

    assert [text[m.start : m.end] for m in matches] == ["15 minut", "2 godzin", "1,5 h"]
    assert [m.start for m in matches] == sorted(m.start for m in matches)
    assert not any(match.ambiguous for match in matches)


def test_extract_duration_values_are_json_safe_whole_minutes() -> None:
    matches = extract_duration("15 min, 1 h i dwie godziny")

    for match in matches:
        assert type(match.readings[0].value) is int
        assert (
            json.loads(json.dumps(match.readings[0].value)) == match.readings[0].value
        )
        assert validate_duration(match.readings[0].value) is None


def test_read_duration_answer_reads_units_but_not_bare_numbers() -> None:
    assert [m.readings[0].value for m in read_duration_answer("15 min")] == [15]
    assert [m.readings[0].value for m in read_duration_answer("2 godziny")] == [120]
    assert read_duration_answer("15") == []
    assert read_duration_answer("") == []


@pytest.mark.parametrize("value", [1, 15, 90, 1440])
def test_validate_duration_accepts_whole_minutes(value: int) -> None:
    assert validate_duration(value) is None
    assert validate_duration(json.loads(json.dumps(value))) is None


@pytest.mark.parametrize(
    "value", [0, -5, 1.5, 15.0, True, "15", None, [15], float("nan")]
)
def test_validate_duration_rejects_everything_else(value: Any) -> None:
    assert validate_duration(value) == "extractors.errors.invalid_duration"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (60, "extractors.display.duration_hours|hours=1"),
        (120, "extractors.display.duration_hours|hours=2"),
        (1440, "extractors.display.duration_hours|hours=24"),
        (90, "extractors.display.duration|minutes=90"),
        (15, "extractors.display.duration|minutes=15"),
    ],
)
def test_describe_duration_shows_whole_hours_as_hours(
    value: int, expected: str
) -> None:
    assert describe_duration(value, _Texts()) == expected

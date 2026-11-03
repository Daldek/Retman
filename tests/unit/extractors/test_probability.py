"""Probability and return period read from a command (ARCHITECTURE 4.4)."""

import json
from typing import Any

import pytest

from retman.extractors.base import Match
from retman.extractors.probability import (
    describe_probability,
    extract_probability,
    probability_percent,
    read_probability_answer,
    validate_probability,
)

PERCENT = "extractors.probability.percent"
PERIOD = "extractors.probability.return_period"
FRACTION = "extractors.probability.fraction"


class _Texts:
    """Translations stand-in: shows which key and arguments the code asked for."""

    def get(self, key: str, **args: object) -> str:
        return key + "|" + ",".join(f"{name}={value}" for name, value in args.items())


class _PlanTexts:
    """The plan text of ARCHITECTURE 4.4, as Retman prints it."""

    def get(self, key: str, **args: object) -> str:
        assert key == "extractors.display.probability"
        return "{percent}% (T = {years} lat)".format(**args)


def _single(command: str) -> Match:
    matches = extract_probability(command)
    assert len(matches) == 1, matches
    return matches[0]


def _first_values(command: str) -> list[Any]:
    return [match.readings[0].value for match in extract_probability(command)]


def _all_values(command: str) -> list[list[Any]]:
    return [[r.value for r in m.readings] for m in extract_probability(command)]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # percent
        ("1%", 0.01),
        ("p = 1%", 0.01),
        ("p=1%", 0.01),
        ("Q1%", 0.01),
        ("Q 1 %", 0.01),
        ("Q=1%", 0.01),
        ("Q = 1 %", 0.01),
        ("q1%", 0.01),
        ("Q1,5%", 0.015),
        ("Q 0,5 %", 0.005),
        ("0.7%", 0.007),
        ("12,5%", 0.125),
        ("H1%", 0.01),
        ("1 procent", 0.01),
        ("1 proc.", 0.01),
        ("2 procenty", 0.02),
        ("jeden procent", 0.01),
        ("dla jednego procenta", 0.01),
        ("pół procenta", 0.005),
        ("1-procentowy", 0.01),
        ("jednoprocentowa woda", 0.01),
        ("prawdopodobieństwo 1%", 0.01),
        ("prawdopodobieństwem 2 %", 0.02),
        ("o prawdopodobieństwie 1%", 0.01),
        ("prawdopodobieństwo przewyższenia 1%", 0.01),
        ("prawdopodobieństwo wynosi 1%", 0.01),
        # a number strictly between 0 and 1 after a probability cue is a fraction
        ("prawdopodobieństwo 0,01", 0.01),
        ("prawdopodobieństwo przewyższenia 0,01", 0.01),
        ("prawdopodobieństwo 0.5", 0.5),
        ("p = 0,01", 0.01),
        ("p: 0,005", 0.005),
        # return period
        ("woda stuletnia", 0.01),
        ("przepływ stuletni", 0.01),
        ("stuletnie", 0.01),
        ("pięćdziesięcioletnia", 0.02),
        ("okres powtarzalności 50 lat", 0.02),
        ("okresem powtarzalności 100 lat", 0.01),
        ("okres powtarzalności: 20 lat", 0.05),
        ("okres powtarzalności T = 50", 0.02),
        ("okres powtarzalności wynoszący 100 lat", 0.01),
        ("T = 50", 0.02),
        ("T=100 lat", 0.01),
        ("T=100lat", 0.01),
        ("raz na 50 lat", 0.02),
        ("raz na sto lat", 0.01),
        ("raz na pięćdziesiąt lat", 0.02),
        ("co 100 lat", 0.01),
        ("co dwadzieścia lat", 0.05),
        ("co 2 lata", 0.5),
        ("dla 50 lat", 0.02),
        ("dla stu lat", 0.01),
        ("50-letni", 0.02),
        ("50-letnia", 0.02),
        ("50-letnie", 0.02),
        ("50-letniej", 0.02),
        ("50 letnia", 0.02),
        ("100-letnich", 0.01),
        # Q with an unambiguous meaning (see the ambiguous ones below)
        ("Q10", 0.1),
        ("Q100", 0.01),
        ("Q500", 0.002),
        ("Q1", 0.01),
    ],
)
def test_extract_probability_reads_one_unambiguous_value(
    command: str, expected: float
) -> None:
    match = _single(command)

    assert [r.value for r in match.readings] == [expected]
    assert not match.ambiguous


@pytest.mark.parametrize(
    ("command", "label_key", "label_args"),
    [
        ("Q1%", PERCENT, {"percent": "1"}),
        ("Q1,5%", PERCENT, {"percent": "1.5"}),
        ("prawdopodobieństwo 0,01", FRACTION, {"value": "0.01"}),
        ("woda stuletnia", PERIOD, {"years": "100", "percent": "1"}),
        ("T = 200", PERIOD, {"years": "200", "percent": "0.5"}),
        ("Q10", PERCENT, {"percent": "10"}),
        ("Q100", PERIOD, {"years": "100", "percent": "1"}),
        ("Q500", PERIOD, {"years": "500", "percent": "0.2"}),
        ("Q1", PERCENT, {"percent": "1"}),
    ],
)
def test_extract_probability_labels_say_how_the_value_was_read(
    command: str, label_key: str, label_args: dict[str, str]
) -> None:
    reading = _single(command).readings[0]

    assert reading.label_key == label_key
    assert reading.label_args == label_args


@pytest.mark.parametrize(
    ("command", "covered"),
    [
        ("Pobierz dane dla Q1% i inne", "Q1%"),
        ("dla Q 1 % teraz", "Q 1 %"),
        ("dla p = 1%.", "p = 1%"),
        ("z prawdopodobieństwem 2 % w punkcie", "prawdopodobieństwem 2 %"),
        ("policz raz na 50 lat dla punktu", "raz na 50 lat"),
        ("woda stuletnia dla punktu", "stuletnia"),
        ("okres powtarzalności 100 lat dla", "okres powtarzalności 100 lat"),
        ("dla T = 50", "T = 50"),
        ("policz dla 1 w punkcie", "dla 1"),
    ],
)
def test_extract_probability_span_covers_the_recognised_phrase(
    command: str, covered: str
) -> None:
    match = _single(command)

    assert command[match.start : match.end] == covered


@pytest.mark.parametrize(
    ("adjective", "years"),
    [
        ("dwuletnia", 2),
        ("trzyletnia", 3),
        ("czteroletnia", 4),
        ("pięcioletnia", 5),
        ("sześcioletnia", 6),
        ("siedmioletnia", 7),
        ("ośmioletnia", 8),
        ("dziewięcioletnia", 9),
        ("dziesięcioletnia", 10),
        ("jedenastoletnia", 11),
        ("dwunastoletnia", 12),
        ("trzynastoletnia", 13),
        ("czternastoletnia", 14),
        ("piętnastoletnia", 15),
        ("szesnastoletnia", 16),
        ("siedemnastoletnia", 17),
        ("osiemnastoletnia", 18),
        ("dziewiętnastoletnia", 19),
        ("dwudziestoletnia", 20),
        ("dwudziestopięcioletnia", 25),
        ("trzydziestoletnia", 30),
        ("czterdziestoletnia", 40),
        ("pięćdziesięcioletnia", 50),
        ("sześćdziesięcioletnia", 60),
        ("siedemdziesięcioletnia", 70),
        ("osiemdziesięcioletnia", 80),
        ("dziewięćdziesięcioletnia", 90),
        ("stuletnia", 100),
        ("stupięćdziesięcioletnia", 150),
        ("dwustuletnia", 200),
        ("dwustupięćdziesięcioletnia", 250),
        ("trzystuletnia", 300),
        ("czterystuletnia", 400),
        ("pięćsetletnia", 500),
        ("pięciusetletnia", 500),
        ("sześćsetletnia", 600),
        ("siedmiusetletnia", 700),
        ("ośmiusetletnia", 800),
        ("dziewięćsetletnia", 900),
        ("tysiącletnia", 1000),
        ("dwutysiącletnia", 2000),
        ("pięciotysiącletnia", 5000),
        ("dziesięciotysiącletnia", 10000),
    ],
)
def test_extract_probability_numeral_adjectives(adjective: str, years: int) -> None:
    match = _single(f"policz {adjective} wodę")

    assert [r.value for r in match.readings] == [1 / years]
    assert match.readings[0].label_key == PERIOD


@pytest.mark.parametrize(
    "form",
    ["stuletni", "stuletnia", "stuletnie", "stuletniego", "stuletniej", "stuletniemu"]
    + ["stuletnim", "stuletnich", "stuletnimi", "stuletnią"],
)
def test_extract_probability_numeral_adjective_in_every_gender_and_case(
    form: str,
) -> None:
    assert _first_values(f"przepływ {form}") == [0.01]


@pytest.mark.parametrize(
    "adjective",
    ["letnia", "wieloletnia", "kilkuletni", "stulecie", "dziesięciokrotnie"],
)
def test_extract_probability_summer_and_other_adjectives_are_not_return_periods(
    adjective: str,
) -> None:
    assert extract_probability(f"opad {adjective}") == []


@pytest.mark.parametrize(
    ("command", "percent", "period"),
    [
        ("Q50", 0.5, 0.02),
        ("Q20", 0.2, 0.05),
        ("Q2", 0.02, 0.5),
        ("Q5", 0.05, 0.2),
        ("Q 50", 0.5, 0.02),
        ("Q = 20", 0.2, 0.05),
        ("q50", 0.5, 0.02),
    ],
)
def test_extract_probability_q_without_percent_asks_percent_or_period(
    command: str, percent: float, period: float
) -> None:
    match = _single(command)

    assert match.ambiguous
    assert [r.value for r in match.readings] == [percent, period]
    assert [r.label_key for r in match.readings] == [PERCENT, PERIOD]


def test_extract_probability_q50_labels_show_both_meanings() -> None:
    percent, period = _single("Q50").readings

    assert percent.label_args == {"percent": "50"}
    assert period.label_args == {"years": "50", "percent": "2"}


@pytest.mark.parametrize(("command", "expected"), [("Q1,5", 0.015), ("Q0,5", 0.005)])
def test_extract_probability_q_with_decimal_is_only_a_percent(
    command: str, expected: float
) -> None:
    # a return period is a whole number of years
    assert [r.value for r in _single(command).readings] == [expected]


@pytest.mark.parametrize(
    ("command", "values"),
    [
        ("dla 1", [0.01, 1.0]),
        ("dla 0,5", [0.005, 0.5]),
        ("dla 5", [0.05, 5.0]),
        ("dla 50", [0.5, 50.0]),
        ("dla 100", [1.0, 100.0]),
        ("prawdopodobieństwo 1", [0.01, 1.0]),
        ("prawdopodobieństwo 5", [0.05, 5.0]),
        ("p = 1", [0.01, 1.0]),
        ("p=5", [0.05, 5.0]),
        ("dla p = 1", [0.01, 1.0]),
    ],
)
def test_extract_probability_bare_number_always_asks_percent_or_fraction(
    command: str, values: list[float]
) -> None:
    match = _single(command)

    assert match.ambiguous
    assert [r.value for r in match.readings] == values
    assert [r.label_key for r in match.readings] == [PERCENT, FRACTION]


def test_extract_probability_bare_number_labels_show_percent_and_fraction() -> None:
    percent, fraction = _single("dla 0,5").readings

    assert percent.label_args == {"percent": "0.5"}
    assert fraction.label_args == {"value": "0.5"}


@pytest.mark.parametrize("value", [1.0, 5.0, 100.0])
def test_validate_probability_rejects_the_impossible_fraction_reading(
    value: float,
) -> None:
    # "dla 1" may be p = 1: it is offered, but choosing it is an error
    assert validate_probability(value) == "extractors.errors.invalid_probability"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("Q1% i Q10%", [0.01, 0.1]),
        ("Q1%, Q2% oraz Q10%", [0.01, 0.02, 0.1]),
        ("Q1% lub Q10%", [0.01, 0.1]),
        ("Q1% a także Q10%", [0.01, 0.1]),
        ("Q1%; Q10%", [0.01, 0.1]),
        ("Q1% i 10%", [0.01, 0.1]),
        ("dla 1%, 2% i 10%", [0.01, 0.02, 0.1]),
        ("dla 1, 2 i 10%", [0.01, 0.02, 0.1]),
        ("dla 1; 2 lub 10%", [0.01, 0.02, 0.1]),
        ("dla 1, 2 a także 10%", [0.01, 0.02, 0.1]),
        ("dla 1, 2 oraz 10 %", [0.01, 0.02, 0.1]),
        ("dla 1,2,5%", [0.01, 0.02, 0.05]),
        ("dla 1 i 2 procent", [0.01, 0.02]),
        ("prawdopodobieństwa 1, 2 i 10%", [0.01, 0.02, 0.1]),
        ("p = 1, 2, 5%", [0.01, 0.02, 0.05]),
        # no cue, but the list ends with a percent sign: all of it is percents
        ("PMAXTP 1, 2, 5, 10, 20 i 50 %", [0.01, 0.02, 0.05, 0.1, 0.2, 0.5]),
        ("1, 2 i 10%", [0.01, 0.02, 0.1]),
        ("dla 10, 20 i 50 lat", [0.1, 0.05, 0.02]),
        ("dla 5, 10 lat", [0.2, 0.1]),
        ("okres powtarzalności 10, 20 i 50 lat", [0.1, 0.05, 0.02]),
        ("prawdopodobieństwo 0,01 i 0,02", [0.01, 0.02]),
        ("T = 10 lat i 1%", [0.1, 0.01]),
        ("Q1% oraz T = 50", [0.01, 0.02]),
        ("Q1, Q10 i Q100", [0.01, 0.1, 0.01]),
    ],
)
def test_extract_probability_list_gives_one_match_per_value(
    command: str, expected: list[float]
) -> None:
    matches = extract_probability(command)

    assert [m.readings[0].value for m in matches] == expected
    assert not any(m.ambiguous for m in matches)


def test_extract_probability_list_items_have_their_own_spans() -> None:
    text = "Q1% i Q10%"

    spans = [text[m.start : m.end] for m in extract_probability(text)]

    assert spans == ["Q1%", "Q10%"]


@pytest.mark.parametrize(
    ("command", "percent", "other", "other_key"),
    [
        ("dla 1, 2 i 10", [0.01, 0.02, 0.1], [1.0, 2.0, 10.0], FRACTION),
        ("dla 1; 2 lub 10", [0.01, 0.02, 0.1], [1.0, 2.0, 10.0], FRACTION),
        ("prawdopodobieństwa 1, 2 i 5", [0.01, 0.02, 0.05], [1.0, 2.0, 5.0], FRACTION),
        ("Q50, Q20", [0.5, 0.2], [0.02, 0.05], PERIOD),
        ("Q50, Q20 i Q2", [0.5, 0.2, 0.02], [0.02, 0.05, 0.5], PERIOD),
        ("Q50 i Q20 i Q2", [0.5, 0.2, 0.02], [0.02, 0.05, 0.5], PERIOD),
        # clear items keep their value in every reading
        ("Q50 i Q10%", [0.5, 0.1], [0.02, 0.1], PERIOD),
        ("Q1% i Q10%, Q50", [0.01, 0.1, 0.5], [0.01, 0.1, 0.02], PERIOD),
        ("Q1, Q2 i Q10", [0.01, 0.02, 0.1], [0.01, 0.5, 0.1], PERIOD),
        ("dla 1%, 2 i 5", [0.01, 0.02, 0.05], [0.01, 2.0, 5.0], FRACTION),
        ("Q1% i 5", [0.01, 0.05], [0.01, 0.2], PERIOD),
    ],
)
def test_extract_probability_unclear_list_is_one_match_with_whole_list_readings(
    command: str, percent: list[float], other: list[float], other_key: str
) -> None:
    match = _single(command)

    assert match.ambiguous
    assert [r.value for r in match.readings] == [percent, other]
    assert [r.label_key for r in match.readings] == [PERCENT, other_key]
    assert match.end == len(command)


def test_extract_probability_whole_list_labels_join_the_values() -> None:
    percent, period = _single("Q50, Q20").readings
    _, fraction = _single("dla 1, 2 i 10").readings

    assert percent.label_args == {"percent": "50%, 20"}
    assert period.label_args == {"years": "50, 20", "percent": "2%, 5"}
    assert fraction.label_args == {"value": "1, 2, 10"}


@pytest.mark.parametrize(
    "command",
    [
        "dla punktu 52.23, 21.01",
        "dla 52.23, 21.01",
        "dla 52,23 21,01",
        "dla 21.01 52.23",
        "dla 52.23N, 21.01E",
        "dla 49.5, 14.5",
        "dla 52°13'46\"N 21°00'44\"E",
        "dla 2020 roku",
        "w roku 2020",
        "dla 2000-2020",
        "od 1.01.2000 do 31.12.2020",
        "z 15.03.2020",
        "dla 12:30",
        "arkusz N-34-130",
        "arkusz N-34-130-D-d-2-4",
        "arkusz 6.179.12",
        "powiat 1465",
        "EPSG:2180",
        "do EPSG:4326",
        "wersja 0.7.2",
        "dla v1.2",
        "dla 486757 637382",
        "dla 150",
        "dla 1000",
        "dla 0",
        "numer 5",
        "5",
        "1,5",
    ],
)
def test_extract_probability_does_not_read_points_dates_codes_or_plain_numbers(
    command: str,
) -> None:
    assert extract_probability(command) == []


@pytest.mark.parametrize(
    "command",
    [
        "dla 2 godzin",
        "dla 15 min",
        "dla 30 minut",
        "dla 15, 30 i 60 min",
        "dla 1 stacji",
        "dla 3 z 4 arkuszy",
        "dla 9 do 12",
        "dla 5-10",
        "dla 5a",
        "dla 10m",
        "dla 1,5 km",
        "dla 1 roku",
        "co 1 rok",
        "Q 12,5 m3/s",
        "Q = 50 m3/s",
        "Q50a",
        "T = 25 °C",
        "gdzie T = 1/p",
        "okres 50 lat",
    ],
)
def test_extract_probability_leaves_numbers_with_another_meaning_alone(
    command: str,
) -> None:
    assert extract_probability(command) == []


def test_extract_probability_a_point_next_to_probabilities_is_not_read() -> None:
    command = (
        "PMAXTP dla punktu 52.23, 21.01 metodą KS dla prawdopodobieństwa 1%, 2% i 5%"
    )

    assert _first_values(command) == [0.01, 0.02, 0.05]


def test_extract_probability_bare_list_after_a_point_still_asks() -> None:
    command = "pobierz pmaxtp dla punktu 52.23 21.01 dla 1, 2 i 10 w punkcie"

    match = _single(command)

    assert [r.value for r in match.readings] == [[0.01, 0.02, 0.1], [1.0, 2.0, 10.0]]
    assert command[match.start : match.end] == "dla 1, 2 i 10"


def test_extract_probability_probabilities_and_durations_in_one_command() -> None:
    command = "dla prawdopodobieństwa 1%, 2% i 5% oraz czasów trwania 15, 30 i 60 min"

    assert _first_values(command) == [0.01, 0.02, 0.05]


def test_extract_probability_a_second_conjunction_starts_a_new_list() -> None:
    command = "dla 1, 2 i 5 oraz 15, 30 i 60 min"

    match = _single(command)

    assert [r.value for r in match.readings] == [[0.01, 0.02, 0.05], [1.0, 2.0, 5.0]]
    assert command[match.start : match.end] == "dla 1, 2 i 5"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("PRAWDOPODOBIEŃSTWO 1%", 0.01),
        ("prawdopodobienstwo 1 %", 0.01),
        ("prawdopodobienstwp 0,01", 0.01),
        ("prawdopodobienswto 1%", 0.01),
        ("prawdopodobieństwie 1%", 0.01),
        ("okers powtarzalnosci 100 lat", 0.01),
        ("okres powtarzlnosci 100 lat", 0.01),
        ("okresem powtarzalnosi 50 lat", 0.02),
        ("OKRES POWTARZALNOŚCI 50 LAT", 0.02),
        ("stuletnai woda", 0.01),
        ("stuleni przepływ", 0.01),
        ("PIĘĆDZIESIĘCIOLETNIA", 0.02),
        ("piecdziesieciolenia", 0.02),
        ("dwudziestopieciolenia", 0.04),
        ("tysiaclentia", 0.001),
        ("jeden procnet", 0.01),
        ("2 procnet", 0.02),
    ],
)
def test_extract_probability_ignores_case_diacritics_and_one_typo(
    command: str, expected: float
) -> None:
    assert _first_values(command) == [expected]


@pytest.mark.parametrize(
    "command",
    [
        "dal 1",
        "ko 100 lat",
        "razna 50 lat",
        "dlaa 50 lat",
        "S = 50",
        "pp = 1",
        "op = 1",
        "a 1",
    ],
)
def test_extract_probability_short_words_are_matched_exactly(command: str) -> None:
    assert extract_probability(command) == []


@pytest.mark.parametrize(
    ("command", "values"),
    [
        ("1", [0.01, 1.0]),
        ("0,5", [0.005, 0.5]),
        ("0,01", [0.0001, 0.01]),
        ("50", [0.5, 50.0]),
        ("dla 1", [0.01, 1.0]),
        (" 1. ", [0.01, 1.0]),
    ],
)
def test_read_probability_answer_a_bare_number_still_asks(
    command: str, values: list[float]
) -> None:
    matches = read_probability_answer(command)

    assert len(matches) == 1
    assert [r.value for r in matches[0].readings] == values
    assert [r.label_key for r in matches[0].readings] == [PERCENT, FRACTION]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("1%", [0.01]),
        ("Q1%", [0.01]),
        ("p=0,01", [0.01]),
        ("T=100", [0.01]),
        ("100 lat", [0.01]),
        ("sto lat", [0.01]),
        ("co 100 lat", [0.01]),
        ("stuletnia", [0.01]),
        ("dwa procent", [0.02]),
        ("1% i 2%", [0.01, 0.02]),
    ],
)
def test_read_probability_answer_reads_the_forms_of_a_command(
    answer: str, expected: list[float]
) -> None:
    matches = read_probability_answer(answer)

    assert [m.readings[0].value for m in matches] == expected
    assert not any(m.ambiguous for m in matches)


def test_read_probability_answer_list_of_bare_numbers_asks_once() -> None:
    match = read_probability_answer("1, 2 i 10")[0]

    assert [r.value for r in match.readings] == [[0.01, 0.02, 0.1], [1.0, 2.0, 10.0]]


@pytest.mark.parametrize(
    "answer", ["", "2 godziny", "52.23 21.01", "tak", "2020", "1 stacja"]
)
def test_read_probability_answer_has_nothing_to_read_in_other_answers(
    answer: str,
) -> None:
    assert read_probability_answer(answer) == []


@pytest.mark.parametrize(
    "command",
    ["1", "0,5", "100 lat", "sto lat", "50", "ostatnie 5, 10 i 15 lat", "arkusze 5, 6"],
)
def test_extract_probability_command_needs_a_cue_for_bare_numbers_and_years(
    command: str,
) -> None:
    assert extract_probability(command) == []


@pytest.mark.parametrize(
    ("command", "covered", "expected"),
    [
        ("dla 1% (T = 100 lat)", "1% (T = 100 lat)", [0.01]),
        ("dla Q100 (1%)", "Q100 (1%)", [0.01]),
        ("Q50 (T = 50 lat)", "Q50 (T = 50 lat)", [0.02]),
        ("Q50 (p = 50%)", "Q50 (p = 50%)", [0.5]),
        ("2% (T = 50 lat)", "2% (T = 50 lat)", [0.02]),
    ],
)
def test_extract_probability_restatement_in_parentheses_is_one_value(
    command: str, covered: str, expected: list[float]
) -> None:
    match = _single(command)

    assert [r.value for r in match.readings] == expected
    assert command[match.start : match.end] == covered
    assert not match.ambiguous


def test_extract_probability_conflicting_restatement_stays_two_values() -> None:
    assert _first_values("dla 1% (T = 50 lat)") == [0.01, 0.02]


@pytest.mark.parametrize("probability", [0.01, 0.02, 0.005, 0.1, 0.002, 0.125, 0.5])
def test_extract_probability_reads_back_the_plan_text(probability: float) -> None:
    shown = describe_probability(probability, _PlanTexts())

    assert _first_values(f"dla {shown}") == [probability]


@pytest.mark.parametrize(
    "command",
    [
        "Q1% i Q10%",
        "dla 1, 2 i 10",
        "dla 1, 2 i 10%",
        "Q50, Q20",
        "dla 150%",
        "raz na 50 lat, Q50 i T = 25",
        "Q100 (T = 100 lat) oraz stuletnia",
        "okres powtarzalności 100 lat; dla 1, 5 i 10",
    ],
)
def test_extract_probability_matches_are_ordered_json_safe_and_labelled(
    command: str,
) -> None:
    matches = extract_probability(command)

    assert matches
    starts_ends = [(m.start, m.end) for m in matches]
    assert starts_ends == sorted(starts_ends)
    assert all(a[1] <= b[0] for a, b in zip(starts_ends, starts_ends[1:], strict=False))
    for match in matches:
        assert match.readings
        for reading in match.readings:
            assert json.loads(json.dumps(reading.value)) == reading.value
            assert reading.label_key in (PERCENT, PERIOD, FRACTION)
            assert all(isinstance(v, str) for v in reading.label_args.values())


@pytest.mark.parametrize(
    ("command", "expected"),
    [("dla 150%", 1.5), ("dla 0%", 0.0), ("100%", 1.0), ("T = 1", 1.0)],
)
def test_extract_probability_impossible_value_is_returned_for_the_validator(
    command: str, expected: float
) -> None:
    # a mention is never dropped silently: validate_probability reports it
    value = _single(command).readings[0].value

    assert value == expected
    assert validate_probability(value) == "extractors.errors.invalid_probability"


def test_extract_probability_empty_and_unrelated_text() -> None:
    assert extract_probability("") == []
    assert extract_probability("Pobierz numeryczny model terenu dla arkusza") == []


@pytest.mark.parametrize("value", [1e-9, 0.01, 0.5, 0.999999])
def test_validate_probability_accepts_floats_strictly_between_zero_and_one(
    value: float,
) -> None:
    assert validate_probability(value) is None
    assert validate_probability(json.loads(json.dumps(value))) is None


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        1.0,
        -0.01,
        1.5,
        0,
        1,
        True,
        False,
        "0.01",
        None,
        [0.01],
        {"p": 0.01},
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_validate_probability_rejects_everything_else(value: Any) -> None:
    assert validate_probability(value) == "extractors.errors.invalid_probability"


@pytest.mark.parametrize(
    ("probability", "percent"),
    [
        (0.01, 1.0),
        (0.07, 7.0),
        (0.57, 57.0),
        (0.29, 29.0),
        (0.005, 0.5),
        (0.125, 12.5),
        (0.0001, 0.01),
    ],
)
def test_probability_percent_has_no_floating_point_noise(
    probability: float, percent: float
) -> None:
    assert probability_percent(probability) == percent


@pytest.mark.parametrize(
    ("probability", "percent", "years"),
    [
        (0.01, "1", "100"),
        (0.02, "2", "50"),
        (0.005, "0.5", "200"),
        (0.125, "12.5", "8"),
        (0.1, "10", "10"),
        (0.002, "0.2", "500"),
        (0.015, "1.5", "66.7"),
        (0.5, "50", "2"),
    ],
)
def test_describe_probability_shows_percent_and_return_period(
    probability: float, percent: str, years: str
) -> None:
    assert describe_probability(probability, _Texts()) == (
        f"extractors.display.probability|percent={percent},years={years}"
    )


def test_describe_probability_plan_text() -> None:
    assert describe_probability(0.01, _PlanTexts()) == "1% (T = 100 lat)"
    assert describe_probability(0.005, _PlanTexts()) == "0.5% (T = 200 lat)"


def test_describe_probability_does_not_hide_an_invalid_value() -> None:
    assert describe_probability(5.0, _Texts()) == "5.0"

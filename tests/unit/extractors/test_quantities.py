"""Numbers with units read from a command (curve number, depth, area, durations)."""

import doctest
import importlib
from collections.abc import Callable
from typing import Any

import pytest

from retman.extractors.base import Match
from retman.extractors.quantities import (
    describe_catchment_area,
    describe_curve_number,
    describe_rainfall_depth,
    extract_catchment_area,
    extract_concentration_time,
    extract_curve_number,
    extract_rain_duration,
    extract_rainfall_depth,
    extract_time_step,
    read_catchment_area_answer,
    read_curve_number_answer,
    read_rainfall_depth_answer,
    validate_catchment_area,
    validate_curve_number,
    validate_rainfall_depth,
)
from retman.i18n.loader import load_core_texts

Reader = Callable[[str], list[Match]]


def values(reader: Reader, text: str) -> list[Any]:
    return [match.readings[0].value for match in reader(text)]


def spans(reader: Reader, text: str) -> list[str]:
    return [text[match.start : match.end] for match in reader(text)]


def test_quantities_doctests_pass() -> None:
    # By import, not by path: extractors/numbers.py would shadow the module numbers
    module = importlib.import_module("retman.extractors.quantities")

    assert doctest.testmod(module).failed == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Opad efektywny dla CN 72", [72]),
        ("CN=80", [80]),
        ("CN = 72,5", [72.5]),
        ("CN: 65", [65]),
        ("CN72 i opad 50 mm", [72]),
        ("liczba CN wynosi 68", [68]),
        ("CN równe 75", [75]),
        ("CN o wartości 70", [70]),
        ("przy CN II = 72", [72]),
        ("CN(III) 85", [85]),
        ("liczba CN siedemdziesiąt dwa", [72]),
        ("cn 90", [90]),
    ],
)
def test_curve_number_follows_its_cue(text: str, expected: list[Any]) -> None:
    assert values(extract_curve_number, text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "opad 72 mm",  # no cue: a depth, not a curve number
        "zlewnia 72 km2",
        "CN zlewni nieznane",  # a cue without a number
        "CN 72 mm",  # the number has a unit of its own
    ],
)
def test_curve_number_needs_the_cue_and_a_bare_number(text: str) -> None:
    assert extract_curve_number(text) == []


def test_several_curve_numbers_are_several_matches_so_retman_asks() -> None:
    assert values(extract_curve_number, "CN 72 lub 75 przy opadzie 40 mm") == [72, 75]
    # The list ends at a number with a unit: it is the depth of the rain
    assert values(extract_curve_number, "dla CN 72 i 50 mm opadu") == [72]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("opad 50 mm", [50]),
        ("suma opadu 38,4 mm", [38.4]),
        ("deszcz 50mm", [50]),
        ("pięćdziesiąt milimetrów deszczu", [50]),
        ("opad 62.5 milimetra", [62.5]),
        ("dla CN 72 i 50 mm opadu", [50]),
        ("opad 40 i 60 mm", [40, 60]),
    ],
)
def test_rainfall_depth_needs_millimetres(text: str, expected: list[Any]) -> None:
    assert values(extract_rainfall_depth, text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "natężenie 50 mm/h",
        "50 mm na godzinę",
        "opad 40-50 mm",  # a range is no single depth
        "opad 50",  # no unit
        "zlewnia 50 km2",
    ],
)
def test_rainfall_depth_is_never_a_rate_a_range_or_a_bare_number(text: str) -> None:
    assert extract_rainfall_depth(text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("zlewnia o powierzchni 45,3 km²", [45.3]),
        ("A = 45 km2", [45]),
        ("45.3 km^2", [45.3]),
        ("12 km kw.", [12]),
        ("120 kilometrów kwadratowych", [120]),
        ("powierzchnia 4530 ha", [45.3]),
        ("250 hektarów", [2.5]),
    ],
)
def test_catchment_area_reads_square_kilometres_and_hectares(
    text: str, expected: list[Any]
) -> None:
    assert values(extract_catchment_area, text) == expected


@pytest.mark.parametrize(
    "text", ["ciek o długości 12,5 km", "45 km 2", "opad 45 mm", "obszar 45"]
)
def test_catchment_area_is_never_a_length(text: str) -> None:
    assert extract_catchment_area(text) == []


def test_durations_are_told_apart_by_their_cue() -> None:
    text = "Hietogram dla 38,4 mm trwającego 2 godziny z krokiem 10 min"

    assert values(extract_rain_duration, text) == [120]
    assert values(extract_time_step, text) == [10]
    assert extract_concentration_time(text) == []


@pytest.mark.parametrize(
    ("text", "rain", "step", "concentration"),
    [
        ("opad 50 mm w 60 min, krok czasowy 5 min", [60], [5], []),
        ("opad 30 mm 60 min co 10 min", [60], [10], []),
        ("czas koncentracji wynosi 90 min, opad 62 mm w 120 min", [120], [], [90]),
        ("tc = 1,5 h", [], [], [90]),
        ("Tc=90min", [], [], [90]),
        ("interwał 15 minut", [], [15], []),
        ("opad 60-minutowy z krokiem 5-minutowym", [60], [5], []),
        ("co najmniej 30 min", [30], [], []),
        ("czas trwania opadu 2 h", [120], [], []),
        ("CN 72 i 60 min", [60], [], []),
    ],
)
def test_each_duration_role_reads_its_own_durations(
    text: str, rain: list[int], step: list[int], concentration: list[int]
) -> None:
    assert values(extract_rain_duration, text) == rain
    assert values(extract_time_step, text) == step
    assert values(extract_concentration_time, text) == concentration


def test_a_duration_of_a_role_is_labelled_by_the_role() -> None:
    (step,) = extract_time_step("krok 5 min")
    (concentration,) = extract_concentration_time("tc 90 min")

    assert step.readings[0].label_key == "extractors.duration.step"
    assert concentration.readings[0].label_key == "extractors.duration.concentration"


def test_answers_may_be_bare_numbers_for_the_unit_the_question_names() -> None:
    assert values(read_curve_number_answer, "72") == [72]
    assert values(read_curve_number_answer, "CN 80") == [80]
    assert values(read_rainfall_depth_answer, "50,5") == [50.5]
    assert values(read_catchment_area_answer, "45,3") == [45.3]
    # A unit still wins over a bare number, and hectares are converted
    assert values(read_catchment_area_answer, "około 300 ha") == [3]
    # Two numbers are two readings: the question is asked again
    assert values(read_rainfall_depth_answer, "50 albo 60") == [50, 60]


@pytest.mark.parametrize(
    ("validate", "valid", "invalid", "key"),
    [
        (validate_curve_number, [1, 72, 72.5, 100], [0, 100.5, -3, True, "72"], "cn"),
        (validate_rainfall_depth, [0.1, 50, 2000], [0, -5, 2000.5, None], "depth"),
        (validate_catchment_area, [0.01, 45.3, 194_000], [0, -1, False], "area"),
    ],
)
def test_validators_take_the_numbers_of_the_tool_range(
    validate: Callable[[Any], str | None],
    valid: list[Any],
    invalid: list[Any],
    key: str,
) -> None:
    assert [validate(value) for value in valid] == [None] * len(valid)
    errors = {validate(value) for value in invalid}
    assert len(errors) == 1
    (error,) = errors
    assert error is not None and error.startswith("extractors.errors.invalid_")


def test_values_are_described_with_their_unit() -> None:
    texts = load_core_texts("pl")

    assert describe_curve_number(72, texts) == "CN 72"
    assert describe_rainfall_depth(38.4, texts) == "38.4 mm"
    assert describe_catchment_area(45.3, texts) == "45.3 km²"


def test_matches_cover_the_number_and_its_unit() -> None:
    text = "zlewnia 45,3 km², CN=72, opad 50 mm"

    assert spans(extract_catchment_area, text) == ["45,3 km²"]
    assert spans(extract_curve_number, text) == ["72"]
    assert spans(extract_rainfall_depth, text) == ["50 mm"]

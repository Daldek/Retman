"""Variables named in commands, read against the variables of the chosen dataset."""

import json
from typing import Any

import pytest
from extractor_context import make_context

from retman.extractors.base import Match
from retman.extractors.variables import (
    KNOWN_VARIABLES,
    describe_variable,
    extract_variables,
    validate_variables,
)
from retman.i18n.loader import load_core_texts

# Variables of the IMGW datasets (imgwtools.datasets())
HYDRO_DAILY = ["H", "Q", "T"]
HYDRO_MONTHLY = [f"{v}_{s}" for v in "HQT" for s in ("min", "mean", "max")]
CLIMATE_DAILY = ["Tmax", "Tmin", "Tmean", "Tground", "P", "snow_cover"]
PRECIPITATION_DAILY = ["P", "snow_cover", "fresh_snow"]
CZECH_METEO = ["P", "Tmean", "Tmax", "Tmin"]


def _codes(matches: list[Match]) -> list[list[str]]:
    return [[reading.value for reading in match.readings] for match in matches]


def _read(command: str, variables: list[str] | None) -> list[list[str]]:
    scope = {"variables": variables} if variables is not None else {}
    return _codes(extract_variables(command, make_context(scope=scope)))


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("przepływy i stany wody", [["Q"], ["H"]]),
        ("tylko stan wody", [["H"]]),
        ("poziom wody i temperatura wody", [["H"], ["T"]]),
        ("H, Q", [["H"], ["Q"]]),
        ("zmienne h i q", []),
        ("przeplyw", [["Q"]]),
        ("Przepływ Q oraz przepływ", [["Q"]]),
        ("temperatura", [["T"]]),
    ],
)
def test_hydrological_daily_names_and_codes(
    command: str, expected: list[list[str]]
) -> None:
    assert _read(command, HYDRO_DAILY) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("minimalny stan wody", [["H_min"]]),
        ("stan wody minimalny", [["H_min"]]),
        ("średni przepływ", [["Q_mean"]]),
        ("maksymalna temperatura wody", [["T_max"]]),
        ("najwyższy stan wody i najniższy przepływ", [["H_max"], ["Q_min"]]),
        # Without a statistic the user must choose among the monthly forms
        ("stan wody", [["H_min", "H_mean", "H_max"]]),
        ("H_mean", [["H_mean"]]),
        ("q_max", [["Q_max"]]),
    ],
)
def test_hydrological_monthly_statistics(
    command: str, expected: list[list[str]]
) -> None:
    assert _read(command, HYDRO_MONTHLY) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("temperatura maksymalna", [["Tmax"]]),
        ("maksymalna temperatura i opady", [["Tmax"], ["P"]]),
        ("temperatura średnia", [["Tmean"]]),
        ("temperatura przygruntowa", [["Tground"]]),
        ("pokrywa śnieżna", [["snow_cover"]]),
        ("śnieg", [["snow_cover"]]),
        ("Tmax i Tmin", [["Tmax"], ["Tmin"]]),
        # A bare "temperatura" fits four variables: Retman asks
        ("temperatura", [["Tmax", "Tmin", "Tmean", "Tground"]]),
    ],
)
def test_climate_stations_names(command: str, expected: list[list[str]]) -> None:
    assert _read(command, CLIMATE_DAILY) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("świeży śnieg", [["fresh_snow"]]),
        ("przyrost śniegu", [["fresh_snow"]]),
        ("pokrywa śnieżna", [["snow_cover"]]),
        ("śnieg", [["snow_cover", "fresh_snow"]]),
        ("opady dobowe", [["P"]]),
        ("opad", [["P"]]),
    ],
)
def test_precipitation_stations_names(command: str, expected: list[list[str]]) -> None:
    assert _read(command, PRECIPITATION_DAILY) == expected


@pytest.mark.parametrize(
    "command",
    ["dane ze stacji opadowych", "stacje opadowe IMGW", "dane opadowe", "przepływowe"],
)
def test_adjectives_naming_a_network_are_not_variables(command: str) -> None:
    assert _read(command, PRECIPITATION_DAILY) == []


def test_czech_meteorological_temperature_offers_the_three_statistics() -> None:
    assert _read("temperatura", CZECH_METEO) == [["Tmax", "Tmin", "Tmean"]]


@pytest.mark.parametrize(
    "command", ["Q1%", "Q 1 %", "T = 50", "T=100 lat", "okres Q10%", "H2O"]
)
def test_single_letters_in_probabilities_and_return_periods_are_not_variables(
    command: str,
) -> None:
    assert _read(command, HYDRO_DAILY) == []


def test_variable_the_dataset_lacks_is_kept_for_the_validator() -> None:
    command = "przepływ i opady"
    context = make_context(scope={"variables": PRECIPITATION_DAILY})

    matches = extract_variables(command, context)

    assert _codes(matches) == [["Q"], ["P"]]
    assert validate_variables("Q", context) == (
        "extractors.errors.variable_not_in_dataset"
    )
    assert validate_variables("P", context) is None


def test_statistic_missing_in_the_dataset_is_reported_not_replaced() -> None:
    context = make_context(scope={"variables": HYDRO_DAILY})

    [match] = extract_variables("minimalny stan wody", context)

    assert [reading.value for reading in match.readings] == ["H_min"]
    assert validate_variables("H_min", context) == (
        "extractors.errors.variable_not_in_dataset"
    )


def test_before_the_dataset_is_known_names_give_plain_variables() -> None:
    assert _read("stan wody", None) == [["H"]]
    assert _read("minimalny stan wody", None) == [["H_min"]]
    # Air or water temperature cannot be told apart yet: Retman asks
    assert _read("temperatura", None) == [["Tmax", "Tmin", "Tmean", "Tground", "T"]]


def test_validator_without_dataset_knows_the_imgw_codes() -> None:
    context = make_context()

    assert all(validate_variables(code, context) is None for code in KNOWN_VARIABLES)
    assert validate_variables("X", context) == "extractors.errors.invalid_variable"
    assert validate_variables(7, context) == "extractors.errors.invalid_variable"
    assert validate_variables("", context) == "extractors.errors.invalid_variable"


def test_validator_trusts_the_dataset_list_over_the_known_codes() -> None:
    context = make_context(scope={"variables": ["wilgotnosc"]})

    assert validate_variables("wilgotnosc", context) is None
    assert validate_variables("H", context) == (
        "extractors.errors.variable_not_in_dataset"
    )


def test_codes_of_a_new_dataset_are_read_case_insensitively() -> None:
    assert _read("chcę WILGOTNOSC", ["wilgotnosc"]) == [["wilgotnosc"]]


def test_extracted_values_survive_a_json_round_trip() -> None:
    context = make_context(scope={"variables": CLIMATE_DAILY})

    for match in extract_variables(
        "temperatura maksymalna, opady, snow_cover", context
    ):
        for reading in match.readings:
            value: Any = json.loads(json.dumps(reading.value))
            assert validate_variables(value, context) is None


def test_every_known_code_has_a_label_and_a_display_text() -> None:
    texts = load_core_texts("pl")

    for code in KNOWN_VARIABLES:
        assert texts.get(f"extractors.variables.names.{code}", code=code).startswith(
            code
        )
        assert describe_variable(code, texts).startswith(code)
    assert describe_variable("wilgotnosc", texts) == "wilgotnosc"

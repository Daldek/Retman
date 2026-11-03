"""Stations named in commands: codes, names against the catalog, inflection, asking."""

import json
from typing import Any

import pytest
from extractor_context import make_context, station_document, station_items

from retman.adapters.catalog import CatalogCall, ToolError
from retman.extractors.base import Match
from retman.extractors.stations import (
    MAX_CANDIDATES,
    StationIndex,
    describe_station,
    explain_station,
    extract_station,
    validate_station,
)
from retman.i18n.loader import load_core_texts


def _codes(match: Match) -> set[str]:
    return {reading.value["code"] for reading in match.readings}


def _only(matches: list[Match]) -> Match:
    assert len(matches) == 1, matches
    return matches[0]


def _error(code: str) -> ToolError:
    return ToolError("imgwtools", code, "test")


# --- loading the catalog -----------------------------------------------------


def test_load_asks_the_tool_for_the_store_catalog_once_per_context() -> None:
    calls: list[CatalogCall] = []

    def lookup(call: CatalogCall) -> dict[str, Any]:
        calls.append(call)
        return station_document()

    context = make_context(lookup=lookup)

    first = StationIndex.load(context)
    second = StationIndex.load(context)

    assert first is second
    assert [(call.command, dict(call.options)) for call in calls] == [
        ("stations find", {"source": "store"})
    ]
    assert len(first) == len(station_items())
    assert first.reason is None


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("not_found", "no_catalog"),
        ("store_unavailable", "no_catalog"),
        ("io_error", "unreadable"),
        ("internal_error", "unreadable"),
    ],
)
def test_load_maps_tool_errors_to_an_empty_index_with_a_reason(
    code: str, reason: str
) -> None:
    def lookup(call: CatalogCall) -> dict[str, Any]:
        raise _error(code)

    index = StationIndex.load(make_context(lookup=lookup))

    assert len(index) == 0
    assert index.reason == reason


@pytest.mark.parametrize(
    ("document", "reason"),
    [
        ({"result": {"items": []}}, "no_catalog"),
        ({"result": {}}, "unreadable"),
        ({"schema": "imgw-result/1"}, "unreadable"),
    ],
)
def test_load_distinguishes_an_empty_catalog_from_an_unexpected_document(
    document: dict[str, Any], reason: str
) -> None:
    index = StationIndex.load(make_context(lookup=lambda call: document))

    assert index.reason == reason


def test_from_entries_skips_items_without_name_or_code() -> None:
    index = StationIndex.from_entries(
        [
            {
                "station_code": "150160170",
                "name": "Mielec",
                "kind": "hydro",
                "provider": "IMGW-PIB",
            },  # fmt: skip
            {
                "station_code": "150160171",
                "name": "",
                "kind": "hydro",
                "provider": "IMGW-PIB",
            },  # fmt: skip
            {"name": "Bez kodu", "kind": "hydro", "provider": "IMGW-PIB"},
            "not a mapping",  # type: ignore[list-item]
        ]
    )

    assert [entry.code for entry in index.entries] == ["150160170"]


# --- codes -------------------------------------------------------------------


def test_code_is_read_without_a_catalog_and_marked_outside_it() -> None:
    def lookup(call: CatalogCall) -> dict[str, Any]:
        raise _error("not_found")

    context = make_context(lookup=lookup)

    match = _only(extract_station("Pobierz opady ze stacji 150160180", context))

    assert match.readings[0].value == {
        "type": "station",
        "provider": "IMGW-PIB",
        "kind": None,
        "code": "150160180",
        "name": None,
        "river": None,
        "in_catalog": False,
    }
    assert not match.ambiguous
    assert validate_station(match.readings[0].value, context) is None


def test_wigos_code_is_upper_cased_and_belongs_to_chmi() -> None:
    match = _only(extract_station("dane stacji 0-203-0-abc12", make_context()))

    value = match.readings[0].value
    assert (value["provider"], value["code"]) == ("CHMI", "0-203-0-ABC12")


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("kod 150160180.", ["150160180"]),
        ("kody 150160180, 150160190", ["150160180", "150160190"]),
        ("punkt 52.150160180", []),
        ("liczba 1501601801", []),
        ("liczba 15016018", []),
        ("0-203-1-001000, następnie 150160180", ["0-203-1-001000", "150160180"]),
    ],
)
def test_code_must_stand_alone(command: str, expected: list[str]) -> None:
    matches = extract_station(command, make_context(index=StationIndex()))

    assert [match.readings[0].value["code"] for match in matches] == expected


def test_catalog_fills_in_a_code_and_a_name_beside_it_is_the_same_station() -> None:
    matches = extract_station(
        "opady ze stacji Poznań-Ławica, kod 352160330", make_context()
    )

    match = _only(matches)
    assert match.readings[0].value["name"] == "POZNAŃ-ŁAWICA"
    assert match.readings[0].value["in_catalog"] is True


# --- names -------------------------------------------------------------------


def test_exact_unique_name_is_accepted_silently() -> None:
    command = "Pobierz opady ze stacji Poznań-Ławica z lat 2000–2020"

    match = _only(extract_station(command, make_context()))

    assert _codes(match) == {"352160330"}
    assert not match.ambiguous
    assert command[match.start : match.end] == "Poznań-Ławica"


def test_longer_name_wins_over_the_station_named_by_its_second_word() -> None:
    items = station_items() + [
        {
            "station_code": "352160999",
            "name": "ŁAWICA",
            "kind": "meteo",
            "provider": "IMGW-PIB",
            "river": None,
        },  # fmt: skip
    ]
    context = make_context(index=StationIndex.from_entries(items))

    match = _only(extract_station("ze stacji Poznań-Ławica", context))

    assert _codes(match) == {"352160330"}


def test_several_stations_of_one_name_are_all_offered() -> None:
    match = _only(extract_station("dane ze stacji Poznań", make_context()))

    assert _codes(match) == {"152160180", "352160330", "352160331"}
    assert match.ambiguous


def test_same_name_of_a_hydro_and_a_meteo_station_is_asked() -> None:
    match = _only(extract_station("dane ze stacji Opole", make_context()))

    assert _codes(match) == {"150170230", "351170375"}


@pytest.mark.parametrize(
    ("command", "code"),
    [
        ("opady w Zatorze", "151160140"),
        ("opady w zatorze", "151160140"),
        ("dane z Dąbia", "150180110"),
        ("dane z Dabia", "150180110"),
        ("dane w Mielcu", "150160170"),
        ("dane w Toruniu", "150180230"),
        ("dane z Kłodzka", "151160270"),
        ("dane z Kamieńca Ząbkowickiego", "151160250"),
        ("w Kamieńcu Ząbkowickim", "151160250"),
        ("dane z Nowego Sącza", "151140111"),
        ("dane w Nowym Targu", "151140112"),
    ],
)
def test_inflected_name_gives_a_single_reading_that_must_be_confirmed(
    command: str, code: str
) -> None:
    match = _only(extract_station(command, make_context()))

    assert _codes(match) == {code}
    assert match.confirm
    assert match.ambiguous


def test_name_in_its_catalog_spelling_needs_no_confirmation_even_in_capitals() -> None:
    match = _only(extract_station("ze stacji KOŁOBRZEG", make_context()))

    assert _codes(match) == {"350180100"}
    assert not match.confirm


def test_without_polish_letters_and_in_lowercase_the_name_is_still_found() -> None:
    match = _only(extract_station("pobierz dane ze stacji kolobrzeg", make_context()))

    assert _codes(match) == {"350180100"}


def test_river_picks_one_of_two_stations_of_the_same_name() -> None:
    both = _only(extract_station("dane stacji Brzeg", make_context()))
    on_river = _only(extract_station("dane stacji Brzeg na Odrze", make_context()))

    assert _codes(both) == {"152170110", "152170111"}
    assert _codes(on_river) == {"152170110"}
    # "Odrze" is inflected, so even the single reading is confirmed
    assert on_river.confirm


def test_river_name_alone_does_not_pick_a_station_of_another_name() -> None:
    matches = extract_station("na Nysie Kłodzkiej", make_context())

    # Words belong to one match only: the river words of "Nysa" are not also
    # the name of "Kłodzko"
    assert [_codes(match) for match in matches] == [{"151160200"}]


def test_typo_in_a_name_is_not_corrected_silently() -> None:
    assert extract_station("ze stacji Poznn", make_context()) == []
    assert extract_station("ze stacji Warszwa", make_context()) == []


# --- noise from ordinary words -------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "Nowe dane ze stacji",  # first word: only exact spelling counts
        "nowe dane ze stacji",
        "Pobierz dane z lat 2000-2020",
        "Opady dobowe z roku 2015",
    ],
)
def test_common_words_do_not_become_stations(command: str) -> None:
    assert extract_station(command, make_context()) == []


def test_lowercase_word_is_not_a_station_in_a_command_that_capitalises_names() -> None:
    match = _only(extract_station("Pobierz nowe dane ze stacji Poznań", make_context()))

    assert "151140111" not in _codes(match)
    assert "152160180" in _codes(match)


def test_acronym_does_not_count_as_capitalisation() -> None:
    match = _only(
        extract_station("pobierz dane IMGW ze stacji poznania", make_context())
    )

    assert _codes(match) == {"152160180", "352160330", "352160331"}
    assert match.confirm


def test_inflected_name_at_the_start_of_the_command_is_not_read() -> None:
    assert extract_station("Zatorze dane", make_context()) == []
    assert _codes(_only(extract_station("Zator dane", make_context()))) == {"151160140"}


# --- scope of the dataset --------------------------------------------------------


def test_dataset_scope_narrows_candidates_to_its_kind_and_provider() -> None:
    meteo = _only(
        extract_station(
            "dane ze stacji Opole",
            make_context(scope={"provider": "IMGW-PIB", "kind": "meteo"}),
        )
    )
    hydro = _only(
        extract_station("dane ze stacji Opole", make_context(scope={"kind": "hydro"}))
    )

    assert _codes(meteo) == {"351170375"}
    assert not meteo.ambiguous
    assert _codes(hydro) == {"150170230"}


def test_czech_station_is_found_by_its_name_in_czech_dataset_scope() -> None:
    context = make_context(scope={"provider": "CHMI", "kind": "hydro"})

    match = _only(extract_station("dane ze stacji Špindlerův Mlýn", context))

    assert _codes(match) == {"0-203-1-001000"}
    assert not match.confirm
    assert extract_station("dane ze stacji Poznań", context) == []


# --- too many candidates ---------------------------------------------------------


def _same_name_stations(count: int) -> StationIndex:
    return StationIndex.from_entries(
        {
            "station_code": f"1501601{number:02d}",
            "name": "Dobra",
            "kind": "hydro",
            "provider": "IMGW-PIB",
            "river": f"Rzeka {number}",
        }
        for number in range(count)
    )


def test_exactly_the_maximum_number_of_candidates_is_listed() -> None:
    context = make_context(index=_same_name_stations(MAX_CANDIDATES))

    match = _only(extract_station("ze stacji Dobra", context))

    assert len(match.readings) == MAX_CANDIDATES


def test_more_candidates_than_a_question_can_list_ask_for_a_better_name() -> None:
    context = make_context(index=_same_name_stations(MAX_CANDIDATES + 1))

    match = _only(extract_station("ze stacji Dobra", context))

    assert len(match.readings) == 1
    assert (
        validate_station(match.readings[0].value, context)
        == "extractors.errors.station_too_many"
    )


# --- validation, hints, display ---------------------------------------------------


def test_validator_accepts_extracted_values_after_a_json_round_trip() -> None:
    context = make_context()
    values = [
        reading.value
        for match in extract_station("Poznań-Ławica i kod 0-203-1-001000", context)
        for reading in match.readings
    ]

    assert len(values) == 2
    for value in values:
        assert validate_station(json.loads(json.dumps(value)), context) is None


@pytest.mark.parametrize(
    ("value", "scope", "error"),
    [
        (None, {}, "invalid_station"),
        ({"type": "area"}, {}, "invalid_station"),
        (
            {"type": "station", "provider": "IMGW-PIB", "code": "12345"},
            {},
            "invalid_station",
        ),
        (
            {"type": "station", "provider": "IMGW-PIB", "code": "0-203-1-001000"},
            {},
            "invalid_station",
        ),
        (
            {"type": "station", "provider": "CHMI", "code": "150160180"},
            {},
            "invalid_station",
        ),
        (
            {"type": "station", "provider": "SMHI", "code": "150160180"},
            {},
            "invalid_station",
        ),
        (
            {"type": "station", "provider": "IMGW-PIB", "code": "150160180"},
            {"provider": "CHMI"},
            "station_wrong_provider",
        ),
        (
            {
                "type": "station",
                "provider": "IMGW-PIB",
                "kind": "hydro",
                "code": "150160180",
            },
            {"kind": "meteo"},
            "station_wrong_kind",
        ),
    ],
)
def test_validator_rejects_malformed_and_out_of_scope_stations(
    value: Any, scope: dict[str, str], error: str
) -> None:
    assert (
        validate_station(value, make_context(scope=scope))
        == f"extractors.errors.{error}"
    )


def test_validator_cannot_check_the_kind_of_a_station_outside_the_catalog() -> None:
    value = {
        "type": "station",
        "provider": "IMGW-PIB",
        "kind": None,
        "code": "150160180",
    }

    assert validate_station(value, make_context(scope={"kind": "meteo"})) is None


@pytest.mark.parametrize(
    ("code", "hint"),
    [
        ("not_found", "station_no_catalog"),
        ("store_unavailable", "station_no_catalog"),
        ("io_error", "station_catalog_unreadable"),
    ],
)
def test_hint_tells_why_names_cannot_be_read(code: str, hint: str) -> None:
    def lookup(call: CatalogCall) -> dict[str, Any]:
        raise _error(code)

    found = explain_station("ze stacji Poznań", make_context(lookup=lookup))

    assert found is not None
    assert found.key == f"extractors.hints.{hint}"


def test_no_hint_when_the_catalog_is_fine() -> None:
    assert explain_station("ze stacji Nigdzie", make_context()) is None


def test_every_label_and_display_text_exists_and_formats() -> None:
    texts = load_core_texts("pl")
    context = make_context()
    values = []
    for item in station_items():
        for match in extract_station(item["name"], context):
            for reading in match.readings:
                texts.get(reading.label_key, **reading.label_args)
                values.append(reading.value)
    outside = {
        "type": "station",
        "provider": "IMGW-PIB",
        "kind": None,
        "code": "150160180",
        "name": None,
        "river": None,
        "in_catalog": False,
    }
    shown = {describe_station(value, texts) for value in [*values, outside]}

    assert "stacja o kodzie 150160180 (IMGW-PIB, poza katalogiem)" in shown
    assert "Poznań (hydro, IMGW-PIB, kod 152160180)" in shown
    assert "POZNAŃ-ŁAWICA (meteo, IMGW-PIB, kod 352160330)" in shown

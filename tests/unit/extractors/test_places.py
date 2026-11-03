"""Search fragments for the station search and synoptic station ids."""

import json
from typing import Any

import pytest

from retman.extractors.base import Match
from retman.extractors.places import (
    describe_place_query,
    describe_synop_station,
    extract_place_query,
    extract_synop_station,
    read_place_query_answer,
    read_synop_station_answer,
    validate_place_query,
    validate_synop_station,
)
from retman.extractors.text import fold
from retman.i18n.loader import load_core_texts


def _values(matches: list[Match]) -> list[dict[str, Any]]:
    return [match.readings[0].value for match in matches]


@pytest.mark.parametrize(
    ("command", "text", "raw"),
    [
        ("Znajdź stacje hydrologiczne na Wiśle", "wisl", "Wiśle"),
        ("Znajdź stacje w Poznaniu", "poznan", "Poznaniu"),
        ("stacje z Opola", "opol", "Opola"),
        ("stacje na Odrze", "odr", "Odrze"),
        ("stacje w Zatorze", "zator", "Zatorze"),
        ("stacje w Łodzi", "lodz", "Łodzi"),
        ("stacje w Krakowie", "krakow", "Krakowie"),
        ("stacje w Warszawie", "warszaw", "Warszawie"),
        ("stacje w Gdyni", "gdyn", "Gdyni"),
        ("stacje dla Poznań", "poznan", "Poznań"),
        ("dla stacji Bogdanka", "bogdank", "Bogdanka"),
    ],
)
def test_place_query_reduces_an_inflected_name_to_a_stem(
    command: str, text: str, raw: str
) -> None:
    assert _values(extract_place_query(command)) == [
        {"type": "query", "text": text, "raw": raw}
    ]


@pytest.mark.parametrize(
    ("nominative", "inflected"),
    [
        ("Wisła", "Wiśle"),
        ("Odra", "Odrze"),
        ("Warta", "Warcie"),
        ("Poznań", "Poznaniu"),
        ("Opole", "Opolu"),
        ("Kraków", "Krakowie"),
        ("Gdynia", "Gdyni"),
        ("Łódź", "Łodzi"),
        ("Kielce", "Kielcach"),
        ("Praga", "Pradze"),
        ("Rabka", "Rabce"),
        ("Skawa", "Skawie"),
        ("Nysa", "Nysie"),
        ("Mielec", "Mielcu"),
        ("Sopot", "Sopocie"),
    ],
)
def test_place_query_stem_is_a_fragment_of_the_nominative(
    nominative: str, inflected: str
) -> None:
    [match] = extract_place_query(f"stacje w {inflected}")

    stem = match.readings[0].value["text"]
    assert len(stem) >= 3
    assert stem in fold(nominative)


@pytest.mark.parametrize(
    "command",
    [
        "Znajdź stacje hydrologiczne",
        "stacje hydrologiczne w Polsce",
        "dane z IMGW",
        "stacje w czechach",
        "stacje hydrologiczne w województwie mazowieckim",
        # A lowercase word after an ordinary cue is not known to be a place
        "stacje na wiśle",
        "stacje w magazynie",
    ],
)
def test_place_query_needs_a_capitalised_name_or_a_cue_followed_by_names(
    command: str,
) -> None:
    assert extract_place_query(command) == []


def test_place_query_accepts_a_lowercase_name_after_a_cue_that_introduces_names() -> (
    None
):
    assert _values(extract_place_query("stacje na rzece wiśle")) == [
        {"type": "query", "text": "wisl", "raw": "wiśle"}
    ]
    assert _values(extract_place_query("w miejscowości zator")) == [
        {"type": "query", "text": "zator", "raw": "zator"}
    ]


def test_place_query_skips_the_cue_of_a_cue() -> None:
    assert _values(extract_place_query("na rzece Nysie Kłodzkiej")) == [
        {"type": "query", "text": "nys", "raw": "Nysie"}
    ]


@pytest.mark.parametrize(
    "command", ['stacje "Poznań-Ławica"', "stacje przy Poznań-Ławica"]
)
def test_place_query_keeps_a_quoted_phrase_and_a_hyphenated_name_whole(
    command: str,
) -> None:
    assert _values(extract_place_query(command)) == [
        {"type": "query", "text": "poznan-lawica", "raw": "Poznań-Ławica"}
    ]


def test_place_query_reads_several_places_once_each() -> None:
    matches = extract_place_query("stacje na Wiśle i w Poznaniu, znowu na Wiśle")

    assert [value["text"] for value in _values(matches)] == ["wisl", "poznan"]


def test_place_query_answer_may_be_the_bare_fragment() -> None:
    assert _values(read_place_query_answer("Poznań")) == [
        {"type": "query", "text": "poznan", "raw": "Poznań"}
    ]
    assert _values(read_place_query_answer("na Wiśle")) == [
        {"type": "query", "text": "wisl", "raw": "Wiśle"}
    ]
    assert read_place_query_answer("  ") == []
    assert read_place_query_answer("x") == []


def test_place_query_validator_and_display() -> None:
    texts = load_core_texts("pl")
    [wisla] = _values(extract_place_query("na Wiśle"))
    [same] = _values(extract_place_query("w Poznań"))

    assert validate_place_query(json.loads(json.dumps(wisla))) is None
    assert validate_place_query({"type": "query", "text": " ", "raw": "x"}) == (
        "extractors.errors.invalid_query"
    )
    assert validate_place_query("wisl") == "extractors.errors.invalid_query"
    assert describe_place_query(wisla, texts) == "„wisl” (z „Wiśle”)"
    assert describe_place_query(same, texts) == "„poznan”"


# --- synoptic stations ------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "aktualne dane ze stacji synoptycznej o kodzie 12330",
        "stacja synoptyczna nr 12330",
        "synop id: 12330",
        "dane stacji kod 12330.",
    ],
)
def test_synop_station_code_follows_a_cue(command: str) -> None:
    assert _values(extract_synop_station(command)) == [
        {"type": "synop_station", "code": "12330", "name": None}
    ]


@pytest.mark.parametrize(
    "command",
    ["synop 12330", "kod 1233", "kod 123300", "kod 12.330", "wartość 12330 mm"],
)
def test_synop_station_number_without_a_cue_or_of_another_shape_is_not_a_code(
    command: str,
) -> None:
    assert extract_synop_station(command) == []


@pytest.mark.parametrize(
    ("command", "name"),
    [
        ("dane synoptyczne dla Gdyni", "Gdyn"),
        ("ze stacji Warszawa", "Warszaw"),
        ("w Warszawie", "Warszaw"),
        ("stacja Białystok", "Białystok"),
    ],
)
def test_synop_station_name_keeps_the_users_letters(command: str, name: str) -> None:
    assert _values(extract_synop_station(command)) == [
        {"type": "synop_station", "code": None, "name": name}
    ]


def test_synop_station_code_wins_over_a_name_beside_it() -> None:
    assert _values(extract_synop_station("stacja Warszawa, kod 12375")) == [
        {"type": "synop_station", "code": "12375", "name": None}
    ]


def test_synop_station_answer_may_be_bare() -> None:
    assert _values(read_synop_station_answer("12330")) == [
        {"type": "synop_station", "code": "12330", "name": None}
    ]
    assert _values(read_synop_station_answer("Warszawa")) == [
        {"type": "synop_station", "code": None, "name": "Warszawa"}
    ]
    assert read_synop_station_answer("1234") == []


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ({"type": "synop_station", "code": "12330", "name": None}, True),
        ({"type": "synop_station", "code": None, "name": "Warszaw"}, True),
        ({"type": "synop_station", "code": "1233", "name": None}, False),
        ({"type": "synop_station", "code": None, "name": " "}, False),
        ({"type": "synop_station", "code": "12330", "name": "Warszaw"}, False),
        ({"type": "synop_station", "code": None, "name": None}, False),
        ("12330", False),
    ],
)
def test_synop_station_validator(value: Any, valid: bool) -> None:
    error = validate_synop_station(json.loads(json.dumps(value)))

    assert (error is None) is valid


def test_synop_station_display() -> None:
    texts = load_core_texts("pl")

    assert describe_synop_station({"code": "12330", "name": None}, texts) == (
        "kod 12330"
    )
    assert describe_synop_station({"code": None, "name": "Warszaw"}, texts) == (
        "fragment nazwy „Warszaw”"
    )

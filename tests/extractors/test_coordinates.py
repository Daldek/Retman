"""Points and PMAXTP grid cells in commands; PL-1992 conversion without pyproj."""

import json
import math
from typing import Any

import pytest

from retman.extractors.base import Match, Reading
from retman.extractors.coordinates import (
    PMAXTP_LATITUDE,
    PMAXTP_LONGITUDE,
    describe_grid_cell,
    describe_point,
    extract_grid_cell,
    extract_point,
    pl1992_to_wgs84,
    read_grid_cell_answer,
    read_point_answer,
    validate_grid_cell,
    validate_point,
    wgs84_to_pl1992,
)

OUTSIDE = "extractors.errors.outside_pmaxtp_frame"
INVALID = "extractors.errors.invalid_point"
# (latitude, longitude, easting, northing); the metres are rounded to a millimetre
REFERENCE_POINTS = [
    (52.2297, 21.0122, 637382.204, 486757.209),
    (50.0647, 19.9450, 567613.619, 244587.531),
    (54.3520, 18.6466, 477037.599, 720936.521),
]


class _Texts:
    """Returns the key and records the arguments the code formats the text with."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, key: str, **args: object) -> str:
        self.calls.append((key, args))
        return key


def _frame_grid() -> list[tuple[float, float]]:
    """Points over the whole PMAXTP frame, its edges and corners included."""
    return [
        (PMAXTP_LATITUDE[0] + 0.25 * row, PMAXTP_LONGITUDE[0] + 0.25 * column)
        for row in range(25)
        for column in range(43)
    ]


def _wgs84(latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "type": "point",
        "latitude": latitude,
        "longitude": longitude,
        "input_crs": "EPSG:4326",
    }


def _readings(text: str, extract: Any = extract_point) -> list[Reading]:
    return [reading for match in extract(text) for reading in match.readings]


def _only(text: str, extract: Any = extract_point) -> Match:
    matches = extract(text)
    assert len(matches) == 1, matches
    return matches[0]


# --- conversion -------------------------------------------------------------


@pytest.mark.parametrize(
    ("latitude", "longitude", "easting", "northing"), REFERENCE_POINTS
)
def test_wgs84_to_pl1992_reference_points(
    latitude: float, longitude: float, easting: float, northing: float
) -> None:
    assert wgs84_to_pl1992(latitude, longitude) == pytest.approx(
        (easting, northing), abs=2e-3
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "easting", "northing"), REFERENCE_POINTS
)
def test_pl1992_to_wgs84_reference_points(
    latitude: float, longitude: float, easting: float, northing: float
) -> None:
    assert pl1992_to_wgs84(easting, northing) == pytest.approx(
        (latitude, longitude), abs=1e-7
    )


def test_pl1992_round_trip_over_the_frame() -> None:
    for latitude, longitude in _frame_grid():
        assert pl1992_to_wgs84(*wgs84_to_pl1992(latitude, longitude)) == pytest.approx(
            (latitude, longitude), abs=1e-9
        )


def test_conversion_agrees_with_pyproj_over_the_frame() -> None:
    pyproj = pytest.importorskip("pyproj")
    forward = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    inverse = pyproj.Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    for latitude, longitude in _frame_grid():
        easting, northing = forward.transform(longitude, latitude)
        assert wgs84_to_pl1992(latitude, longitude) == pytest.approx(
            (easting, northing), abs=1e-3
        )
        expected_longitude, expected_latitude = inverse.transform(easting, northing)
        assert pl1992_to_wgs84(easting, northing) == pytest.approx(
            (expected_latitude, expected_longitude), abs=1e-8
        )


@pytest.mark.parametrize(
    "arguments", [(math.nan, 21.0), (52.0, math.inf), (91.0, 21.0), (52.0, 80.0)]
)
def test_wgs84_to_pl1992_rejects_what_the_series_cannot_convert(
    arguments: tuple[float, float],
) -> None:
    with pytest.raises(ValueError):
        wgs84_to_pl1992(*arguments)


@pytest.mark.parametrize(
    "arguments", [(math.nan, 500_000.0), (500_000.0, -math.inf), (1e7, 500_000.0)]
)
def test_pl1992_to_wgs84_rejects_what_the_series_cannot_convert(
    arguments: tuple[float, float],
) -> None:
    with pytest.raises(ValueError):
        pl1992_to_wgs84(*arguments)


# --- extract_point: WGS84 ---------------------------------------------------

LAT_LON = "extractors.point.wgs84_lat_lon"
LON_LAT = "extractors.point.wgs84_lon_lat"


@pytest.mark.parametrize(
    ("command", "span", "latitude", "longitude", "label_key"),
    [
        (
            "Opady maksymalne PMAXTP dla punktu 52.23, 21.01 metoda POT",
            "52.23, 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        ("Dla punktu 52.23,21.01 pobierz opady", "52.23,21.01", 52.23, 21.01, LAT_LON),
        ("PMAXTP 52,23 21,01 metoda POT", "52,23 21,01", 52.23, 21.01, LAT_LON),
        ("PMAXTP 52,23, 21,01 metoda POT", "52,23, 21,01", 52.23, 21.01, LAT_LON),
        ("punkt 52,2297;21,0122.", "52,2297;21,0122", 52.2297, 21.0122, LAT_LON),
        ("Punkt 52.23/21.01", "52.23/21.01", 52.23, 21.01, LAT_LON),
        ("dla 52.23 i 21.01", "52.23 i 21.01", 52.23, 21.01, LAT_LON),
        ("punkt 52.23\n21.01", "52.23\n21.01", 52.23, 21.01, LAT_LON),
        # The order comes from the disjoint ranges of the frame
        ("punkt 21.01 52.23", "21.01 52.23", 52.23, 21.01, LON_LAT),
        ("punkt 21,01, 52,23", "21,01, 52,23", 52.23, 21.01, LON_LAT),
        # Hemisphere letters, before or after the numbers, in either order
        ("52.23 N 21.01 E", "52.23 N 21.01 E", 52.23, 21.01, LAT_LON),
        ("N 52.23 E 21.01", "N 52.23 E 21.01", 52.23, 21.01, LAT_LON),
        ("punkt 52.23°N, 21.01°E", "52.23°N, 21.01°E", 52.23, 21.01, LAT_LON),
        ("52.23 n 21.01 e", "52.23 n 21.01 e", 52.23, 21.01, LAT_LON),
        ("N=52.23, E=21.01", "N=52.23, E=21.01", 52.23, 21.01, LAT_LON),
        ("21.01 E, 52.23 N", "21.01 E, 52.23 N", 52.23, 21.01, LON_LAT),
        ("E 21.01 N 52.23", "E 21.01 N 52.23", 52.23, 21.01, LON_LAT),
        # A label on one number leaves the other one to the remaining axis
        ("szerokosc 52.23 21.01", "szerokosc 52.23 21.01", 52.23, 21.01, LAT_LON),
        ("dlugosc 21.01 52.23", "dlugosc 21.01 52.23", 52.23, 21.01, LON_LAT),
        # Labels in words, with or without Polish letters and in any case
        (
            "szerokosc 52.23 dlugosc 21.01",
            "szerokosc 52.23 dlugosc 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "SZEROKOŚĆ 52,23 DŁUGOŚĆ 21,01",
            "SZEROKOŚĆ 52,23 DŁUGOŚĆ 21,01",
            52.23,
            21.01,
            LAT_LON,
        ),
        ("szer. 52,23 dl. 21,01", "szer. 52,23 dl. 21,01", 52.23, 21.01, LAT_LON),
        (
            "o szerokości geograficznej 52,23 i długości geograficznej 21,01",
            "szerokości geograficznej 52,23 i długości geograficznej 21,01",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "szerokosc geograficzna: 52.23 N, dlugosc geograficzna: 21.01 E",
            "szerokosc geograficzna: 52.23 N, dlugosc geograficzna: 21.01 E",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "dlugosc 21.01 szerokosc 52.23",
            "dlugosc 21.01 szerokosc 52.23",
            52.23,
            21.01,
            LON_LAT,
        ),
        ("lat 52.23 lon 21.01", "lat 52.23 lon 21.01", 52.23, 21.01, LAT_LON),
        ("lat=52.23, lon=21.01", "lat=52.23, lon=21.01", 52.23, 21.01, LAT_LON),
        (
            "latitude 52.23 longitude 21.01",
            "latitude 52.23 longitude 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "latitude/longitude: 52.23, 21.01",
            "latitude/longitude: 52.23, 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "szerokosc/dlugosc 52.23 21.01",
            "szerokosc/dlugosc 52.23 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        ("x=21.01 y=52.23", "x=21.01 y=52.23", 52.23, 21.01, LON_LAT),
        # One typo in a label word of five letters or more
        (
            "szerokoscc 52.23 dlugsc 21.01",
            "szerokoscc 52.23 dlugsc 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
        (
            "latitde 52.23 longitude 21.01",
            "latitde 52.23 longitude 21.01",
            52.23,
            21.01,
            LAT_LON,
        ),
    ],
)
def test_extract_point_wgs84_forms_have_one_reading_and_the_right_order(
    command: str, span: str, latitude: float, longitude: float, label_key: str
) -> None:
    match = _only(command)

    assert command[match.start : match.end] == span
    assert [reading.value for reading in match.readings] == [
        _wgs84(latitude, longitude)
    ]
    assert match.readings[0].label_key == label_key
    assert not match.ambiguous
    assert validate_point(match.readings[0].value) is None


@pytest.mark.parametrize(
    ("command", "latitude", "longitude"),
    [
        ("52°13'44\"N 21°00'44\"E", 52.228888889, 21.012222222),
        ("52° 13′ 44″ N, 21° 0′ 44″ E", 52.228888889, 21.012222222),
        ("52°13’44″N 21°00’44″E", 52.228888889, 21.012222222),
        ("N 52°13'44\" E 21°00'44\"", 52.228888889, 21.012222222),
        ("52°13'44.5\"N 21°00'44.25\"E", 52.229027778, 21.012291667),
        ("52°13.5'N 21°0.75'E", 52.225, 21.0125),
        ("52°N 21°E", 52.0, 21.0),
        ("21°E 52°N", 52.0, 21.0),
        ("52,5° 21,25°", 52.5, 21.25),
        ("52º 21º", 52.0, 21.0),
    ],
)
def test_extract_point_degrees_minutes_seconds(
    command: str, latitude: float, longitude: float
) -> None:
    value = _only(f"punkt {command}").readings[0].value

    assert value["input_crs"] == "EPSG:4326"
    assert (value["latitude"], value["longitude"]) == pytest.approx(
        (latitude, longitude), abs=1e-9
    )


def test_extract_point_keeps_typed_wgs84_numbers_exactly() -> None:
    value = _only("punkt 52.2297123456 21.0122").readings[0].value

    assert value == _wgs84(52.2297123456, 21.0122)


@pytest.mark.parametrize(
    "command",
    [
        "w punkcie 52 21",
        "punktu o współrzędnych 52 21",
        "współrzędne: 52 21",
        "wsp. 52 21",
        "dla puntk 52 21",
        "WGS84 52 21",
        "(WGS 84) 52 21",
        "52 21 WGS84",
        "52 21 w układzie WGS84",
        "lokalizacja 52 21",
    ],
)
def test_extract_point_words_about_points_make_bare_integers_a_point(
    command: str,
) -> None:
    assert [r.value for r in _readings(command)] == [_wgs84(52.0, 21.0)]


@pytest.mark.parametrize(
    "command",
    [
        "opady dla 52 21",
        "dla 52.23 21",
        "punkt nr 5 i 7",
        "punkt kontrolny 52 21",
        "wps. 52 21",
        "52 21 do EPSG:2180",
        "637382 486757",
    ],
)
def test_extract_point_bare_integers_are_not_a_point(command: str) -> None:
    assert extract_point(command) == []


# --- extract_point: outside the frame ---------------------------------------


@pytest.mark.parametrize(
    ("command", "latitude", "longitude"),
    [
        ("punkt 40.5 20.1", 40.5, 20.1),
        ("współrzędne punktu 52.5 30.0", 52.5, 30.0),
        ("punkt 49.5 13.9", 49.5, 13.9),
        ("punkt 55.1 20.0", 55.1, 20.0),
        ("szerokosc 21.01 dlugosc 52.23", 21.01, 52.23),
        ("N 60.1 E 21.0", 60.1, 21.0),
        ("punkt -52.5 21", -52.5, 21.0),
        ("punkt 95.0 20.0", 20.0, 95.0),
    ],
)
def test_extract_point_outside_frame_is_read_and_left_to_the_validator(
    command: str, latitude: float, longitude: float
) -> None:
    reading = _only(command).readings[0]

    assert (reading.value["latitude"], reading.value["longitude"]) == (
        latitude,
        longitude,
    )
    assert validate_point(reading.value) == OUTSIDE


@pytest.mark.parametrize(
    "command",
    [
        "40.5 20.1",
        "52.5 30.0",
        "punkt 100 200",
        "punkt 190.5 200.1",
        "52.23 S 21.01 E",
        "52.23 N 21.01 W",
        "52°13'44\"S 21°00'44\"E",
        "52°N 21°W",
    ],
)
def test_extract_point_unmarked_outside_frame_and_unsupported_hemispheres(
    command: str,
) -> None:
    assert extract_point(command) == []


# --- extract_point: PL-1992 -------------------------------------------------

EN = "extractors.point.pl1992_en"
NE = "extractors.point.pl1992_ne"


def _pl1992(easting: float, northing: float) -> dict[str, Any]:
    latitude, longitude = pl1992_to_wgs84(easting, northing)
    return {
        "type": "point",
        "latitude": round(latitude, 9),
        "longitude": round(longitude, 9),
        "input_crs": "EPSG:2180",
        "easting": easting,
        "northing": northing,
    }


@pytest.mark.parametrize(
    "command",
    [
        "punkt 637382 486757",
        "punkt 637382, 486757",
        "punkt 637382,486757",
        "współrzędne punktu 637382 486757",
        "637382 486757 w układzie PL-1992",
        "PL-1992: 637382 486757",
        "637382 486757 EPSG:2180",
    ],
)
def test_extract_point_pl1992_pair_in_both_orders_asks(command: str) -> None:
    match = _only(command)

    assert [reading.value for reading in match.readings] == [
        _pl1992(637382.0, 486757.0),
        _pl1992(486757.0, 637382.0),
    ]
    assert [reading.label_key for reading in match.readings] == [EN, NE]
    assert match.ambiguous
    assert all(validate_point(reading.value) is None for reading in match.readings)


@pytest.mark.parametrize(
    ("command", "easting", "northing", "label_key"),
    [
        # A value above the northing envelope (830000) leaves one order
        ("punkt 850000 300000", 850000.0, 300000.0, EN),
        ("punkt 300000 850000", 850000.0, 300000.0, NE),
        # Labels decide
        ("x=637382 y=486757", 637382.0, 486757.0, EN),
        ("x: 637382, y: 486757", 637382.0, 486757.0, EN),
        ("y=486757 x=637382", 637382.0, 486757.0, NE),
        ("E 637382 N 486757", 637382.0, 486757.0, EN),
        ("N 486757 E 637382", 637382.0, 486757.0, NE),
        ("E=637382 N=486757", 637382.0, 486757.0, EN),
        ("637382 E, 486757 N", 637382.0, 486757.0, EN),
        ("486757 N 637382 E", 637382.0, 486757.0, NE),
        ("x=637382 486757", 637382.0, 486757.0, EN),
        ("x/y: 637382 486757", 637382.0, 486757.0, EN),
        # Decimals need no word about points
        ("637382.2 486757.2", 637382.2, 486757.2, None),
        ("x=637382,2 y=486757,2", 637382.2, 486757.2, EN),
    ],
)
def test_extract_point_pl1992_single_reading(
    command: str, easting: float, northing: float, label_key: str | None
) -> None:
    readings = _readings(command)

    if label_key is None:
        assert [r.value for r in readings][0] == _pl1992(easting, northing)
        return
    assert [reading.value for reading in readings] == [_pl1992(easting, northing)]
    assert readings[0].label_key == label_key
    assert validate_point(readings[0].value) is None


def test_extract_point_pl1992_value_carries_converted_degrees() -> None:
    value = _only("punkt x=637382.204 y=486757.209").readings[0].value

    assert value["input_crs"] == "EPSG:2180"
    assert (value["easting"], value["northing"]) == (637382.204, 486757.209)
    assert (value["latitude"], value["longitude"]) == pytest.approx(
        (52.2297, 21.0122), abs=1e-7
    )


@pytest.mark.parametrize(
    "command",
    [
        "punkt 100000 200000",
        "punkt 637382 950000",
        "punkt 637 382 486 757",
        "x=637382 x=486757",
        "punkt 52.23 637382",
    ],
)
def test_extract_point_pl1992_outside_poland_or_unsupported_forms(command: str) -> None:
    assert extract_point(command) == []


# --- extract_point: other numbers in the command ----------------------------


@pytest.mark.parametrize(
    "command",
    [
        "Dane dla 2020 roku",
        "okres 2000 2020",
        "z lat 2000-2010 52 21",
        "Q1% i Q10%",
        "prawdopodobieństwo 1,5% 52.5%",
        "powiat 1465 oraz 1466",
        "Pobierz arkusz N-34-130-D",
        "arkusz 6.179.12 i 6.179.13",
        "wersja 1.2.3 z dnia 12.10.2020",
        "temperatura 25°C do 30°C",
        "bbox 52.23 21.01 52.5 21.3",
        "x=450000 y=550000 x=460000 y=560000",
        "N 550000-560000 E 450000-460000",
        "Wytnij NMT 530000 382000 530100 382100",
        "punkt 52.2-52.3, 21.0-21.1",
        "dla stacji 349190020 i 349190030",
        "szerokosc 52.23 szerokosc 21.01",
        "szerokosc koryta 12.5 m i dlugosc 100 m",
        "dlugosc rzeki 21.5 km",
    ],
)
def test_extract_point_ignores_numbers_that_are_not_a_point(command: str) -> None:
    assert extract_point(command) == []


def test_extract_point_skips_a_rectangle_but_finds_a_point_beside_it() -> None:
    command = "bbox 52.23 21.01 52.5 21.3 i punkt 52.1 21.2"

    match = _only(command)

    assert command[match.start : match.end] == "52.1 21.2"
    assert match.readings[0].value == _wgs84(52.1, 21.2)


def test_extract_point_finds_the_point_among_years_codes_and_probabilities() -> None:
    command = (
        "Pobierz opady z lat 2010-2020 dla stacji 349190020 i punktu 52.23, 21.01, "
        "prawdopodobieństwo 1%, czas 15 min, arkusz N-34-130-D"
    )

    assert [r.value for r in _readings(command)] == [_wgs84(52.23, 21.01)]


def test_extract_point_several_points_are_several_matches_in_order() -> None:
    command = "porównaj punkt 52.23 21.01 oraz 50.06 19.94 i x=567613 y=244587"

    matches = extract_point(command)

    assert [command[m.start : m.end] for m in matches] == [
        "52.23 21.01",
        "50.06 19.94",
        "x=567613 y=244587",
    ]
    assert [m.readings[0].value["latitude"] for m in matches][:2] == [52.23, 50.06]
    assert matches[2].readings[0].value["input_crs"] == "EPSG:2180"


@pytest.mark.parametrize(
    "command",
    [
        "N 52.23 E 21.01 oraz N 50.06 E 19.94",
        "52.23 N 21.01 E 50.06 N 19.94 E",
        "punkt A: 52.23, 21.01; punkt B: 50.06, 19.94",
    ],
)
def test_extract_point_letters_stay_with_their_own_point(command: str) -> None:
    matches = extract_point(command)

    assert [m.readings[0].value["latitude"] for m in matches] == [52.23, 50.06]
    assert [m.readings[0].value["longitude"] for m in matches] == [21.01, 19.94]


@pytest.mark.parametrize(
    "command", ["punkt 52.23 21.01", "punkt 637382 486757", "N 52.23 E 21.01"]
)
def test_extract_point_readings_survive_a_json_round_trip(command: str) -> None:
    for reading in _readings(command):
        restored = json.loads(json.dumps(reading.value))

        assert restored == reading.value
        assert validate_point(restored) is None


@pytest.mark.parametrize(
    "command", ["punkt 52.23 21.01", "punkt 637382 486757", "x=637382 y=486757"]
)
def test_extract_point_label_arguments_are_formatted_strings(command: str) -> None:
    for reading in _readings(command):
        wanted = {"latitude", "longitude"}
        if reading.value["input_crs"] == "EPSG:2180":
            wanted |= {"easting", "northing"}
        assert reading.label_key.startswith("extractors.point.")
        assert set(reading.label_args) == wanted
        assert all(isinstance(text, str) for text in reading.label_args.values())


# --- read_point_answer ------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "latitude", "longitude"),
    [
        ("52 21", 52.0, 21.0),
        ("52.23 21.01", 52.23, 21.01),
        ("21.01, 52.23", 52.23, 21.01),
        ("52,23 N 21,01 E", 52.23, 21.01),
        ("szerokość 52,23 długość 21,01", 52.23, 21.01),
        ("N 52.23 E 21.01", 52.23, 21.01),
        ("lat 52.23 lon 21.01", 52.23, 21.01),
        ("52°13'44\"N 21°00'44\"E", 52.228888889, 21.012222222),
    ],
)
def test_read_point_answer_reads_any_two_numbers(
    answer: str, latitude: float, longitude: float
) -> None:
    value = _only(answer, read_point_answer).readings[0].value

    assert (value["latitude"], value["longitude"]) == pytest.approx(
        (latitude, longitude), abs=1e-9
    )
    assert validate_point(value) is None


def test_read_point_answer_pl1992_pair_has_both_orders_or_follows_labels() -> None:
    both = _only("637382 486757", read_point_answer)
    labelled = _only("x 637382 y 486757", read_point_answer)

    assert [r.label_key for r in both.readings] == [EN, NE]
    assert [r.value for r in labelled.readings] == [_pl1992(637382.0, 486757.0)]


def test_read_point_answer_outside_frame_goes_to_the_validator() -> None:
    reading = _only("40 20", read_point_answer).readings[0]

    assert validate_point(reading.value) == OUTSIDE


def test_read_point_answer_two_points_are_two_matches() -> None:
    answer = "52.23 21.01 50.06 19.94"

    matches = read_point_answer(answer)

    assert [answer[m.start : m.end] for m in matches] == ["52.23 21.01", "50.06 19.94"]


@pytest.mark.parametrize("answer", ["52.23", "tak", "", "52.23 N", "x 5"])
def test_read_point_answer_needs_two_numbers(answer: str) -> None:
    assert read_point_answer(answer) == []


# --- validate_point ---------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        _wgs84(52.23, 21.01),
        _wgs84(49.0, 14.0),
        _wgs84(55.0, 24.5),
        _wgs84(52, 21),
        _pl1992(637382.0, 486757.0),
        _pl1992(637382.204, 486757.209),
    ],
)
def test_validate_point_accepts_points_inside_the_frame(value: dict[str, Any]) -> None:
    assert validate_point(value) is None
    assert validate_point(json.loads(json.dumps(value))) is None


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(48.999, 21.0), (55.001, 21.0), (52.0, 13.999), (52.0, 24.501), (-52.0, 21.0)],
)
def test_validate_point_frame_edges_are_exact(
    latitude: float, longitude: float
) -> None:
    assert validate_point(_wgs84(latitude, longitude)) == OUTSIDE
    assert (
        validate_point(json.loads(json.dumps(_wgs84(latitude, longitude)))) == OUTSIDE
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "52.23 21.01",
        [52.23, 21.01],
        {},
        {**_wgs84(52.23, 21.01), "type": "bbox"},
        {"type": "point", "latitude": 52.23, "input_crs": "EPSG:4326"},
        {**_wgs84(52.23, 21.01), "latitude": "52.23"},
        {**_wgs84(52.23, 21.01), "latitude": True},
        {**_wgs84(52.23, 21.01), "longitude": math.nan},
        {**_wgs84(52.23, 21.01), "longitude": math.inf},
        {**_wgs84(91.0, 21.01)},
        {**_wgs84(52.23, 181.0)},
        {**_wgs84(52.23, 21.01), "input_crs": "EPSG:3045"},
        {**_wgs84(52.23, 21.01), "input_crs": None},
        {k: v for k, v in _wgs84(52.23, 21.01).items() if k != "input_crs"},
        # PL-1992 needs a consistent pair of metres
        {**_pl1992(637382.0, 486757.0), "easting": None},
        {**_pl1992(637382.0, 486757.0), "northing": "486757"},
        {**_pl1992(637382.0, 486757.0), "northing": False},
        {**_pl1992(637382.0, 486757.0), "easting": 637400.0},
        {**_pl1992(637382.0, 486757.0), "latitude": 52.5},
        {k: v for k, v in _pl1992(637382.0, 486757.0).items() if k != "northing"},
        {**_pl1992(637382.0, 486757.0), "easting": 1e12, "northing": math.nan},
        # Metres do not belong to WGS84 input
        {**_wgs84(52.23, 21.01), "easting": 637382.0, "northing": 486757.0},
    ],
)
def test_validate_point_rejects_structural_problems(value: Any) -> None:
    assert validate_point(value) == INVALID


def test_validate_point_rejects_values_that_json_makes_non_finite() -> None:
    restored = json.loads(
        '{"type": "point", "latitude": NaN, "longitude": 21.0, '
        '"input_crs": "EPSG:4326"}'
    )

    assert validate_point(restored) == INVALID


def test_validate_point_checks_structure_before_the_frame() -> None:
    assert validate_point({**_wgs84(40.0, 21.0), "latitude": "40"}) == INVALID
    assert validate_point({**_pl1992(637382.0, 486757.0), "easting": 1.0}) == INVALID


# --- describe_point ---------------------------------------------------------


@pytest.mark.parametrize(
    ("latitude", "longitude", "shown"),
    [
        (52.2297, 21.0122, {"latitude": "52.2297", "longitude": "21.0122"}),
        (52.5, 21.0, {"latitude": "52.5", "longitude": "21"}),
        (52.12345678, 21.1, {"latitude": "52.123457", "longitude": "21.1"}),
        (50.0, 14.000000001, {"latitude": "50", "longitude": "14"}),
    ],
)
def test_describe_point_wgs84_trims_degrees(
    latitude: float, longitude: float, shown: dict[str, str]
) -> None:
    texts = _Texts()

    assert (
        describe_point(_wgs84(latitude, longitude), texts) == "extractors.display.point"
    )
    assert texts.calls == [("extractors.display.point", shown)]


def test_describe_point_pl1992_shows_the_pair_it_came_from() -> None:
    value = _only("punkt x=637382 y=486757.2").readings[0].value
    texts = _Texts()

    assert describe_point(value, texts) == "extractors.display.point_pl1992"
    ((_, shown),) = texts.calls
    assert (shown["easting"], shown["northing"]) == ("637382", "486757.2")
    assert (float(str(shown["latitude"])), float(str(shown["longitude"]))) == (
        pytest.approx((52.2297, 21.0122), abs=1e-5)
    )


def test_describe_point_works_on_a_json_round_tripped_value() -> None:
    value = _only("punkt N 486757 E 637382").readings[0].value
    original, restored = _Texts(), _Texts()

    describe_point(value, original)
    describe_point(json.loads(json.dumps(value)), restored)

    assert restored.calls == original.calls


# --- grid cells -------------------------------------------------------------


def _cell(ind_x: int, ind_y: int) -> dict[str, Any]:
    return {"type": "grid_cell", "ind_x": ind_x, "ind_y": ind_y}


@pytest.mark.parametrize(
    ("command", "span"),
    [
        ("Opady dla 751/317 metodą POT", "751/317"),
        ("komórka 751_317", "komórka 751_317"),
        ("751_317", "751_317"),
        ("dla komórki 751, 317", "komórki 751, 317"),
        ("komorka 751, 317", "komorka 751, 317"),
        ("komorke 751 317", "komorke 751 317"),
        ("komórka 751/317.", "komórka 751/317"),
        ("komórka nr 751/317", "komórka nr 751/317"),
        ("w komórce siatki PMAXTP 751 317", "komórce siatki PMAXTP 751 317"),
        ("komurka 751 317", "komurka 751 317"),
        ("KOMÓRKA 751, 317", "KOMÓRKA 751, 317"),
        ("cell 751 317", "cell 751 317"),
        ("ind_x 751 ind_y 317", "ind_x 751 ind_y 317"),
        ("ind_x=751, ind_y=317", "ind_x=751, ind_y=317"),
        ("ind_y 317 ind_x 751", "ind_y 317 ind_x 751"),
        ("IND_X: 751 i IND_Y: 317", "IND_X: 751 i IND_Y: 317"),
        ("komórka x 751 y 317", "komórka x 751 y 317"),
        ("komórka x=751, y=317", "komórka x=751, y=317"),
        ("komórka y=317 x=751", "komórka y=317 x=751"),
        ("x=751 y=317 dla komórki", "x=751 y=317"),
    ],
)
def test_extract_grid_cell_forms(command: str, span: str) -> None:
    match = _only(command, extract_grid_cell)

    assert command[match.start : match.end] == span
    assert [reading.value for reading in match.readings] == [_cell(751, 317)]
    assert not match.ambiguous
    assert validate_grid_cell(match.readings[0].value) is None


@pytest.mark.parametrize(
    "command",
    [
        "z dnia 12/10/2020",
        "12/10/2020 oraz 751/317/2",
        "w roku hydrologicznym 2020/2021",
        "wersja 1.2/3",
        "przepływ 3/s",
        "dane 751/317abc",
        "id_751/317",
        "x 751 y 317",
        "ind_x 751",
        "komórka 751",
        "komórka 751 oraz powiat 1465",
        "N-34/12",
        "751 317",
        "751,317",
        "Pobierz opady 2020 2021",
    ],
)
def test_extract_grid_cell_ignores_what_is_not_a_cell(command: str) -> None:
    assert extract_grid_cell(command) == []


def test_extract_grid_cell_several_cells_are_several_matches() -> None:
    matches = extract_grid_cell("komórki 751/317 oraz 752_318")

    assert [m.readings[0].value for m in matches] == [_cell(751, 317), _cell(752, 318)]


def test_extract_grid_cell_first_unlabelled_number_is_ind_x() -> None:
    assert _only("komórka 5, 900", extract_grid_cell).readings[0].value == _cell(5, 900)
    assert _only("ind_y 5 ind_x 900", extract_grid_cell).readings[0].value == _cell(
        900, 5
    )


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("751 317", _cell(751, 317)),
        ("751,317", _cell(751, 317)),
        ("751, 317", _cell(751, 317)),
        ("751/317", _cell(751, 317)),
        ("komórka 751 317", _cell(751, 317)),
        ("x=751 y=317", _cell(751, 317)),
        ("y 317 x 751", _cell(751, 317)),
        ("ind_x=751, ind_y=317", _cell(751, 317)),
        ("0 0", _cell(0, 0)),
    ],
)
def test_read_grid_cell_answer_takes_two_numbers(
    answer: str, expected: dict[str, Any]
) -> None:
    assert _only(answer, read_grid_cell_answer).readings[0].value == expected


@pytest.mark.parametrize("answer", ["751", "tak", "", "x=751"])
def test_read_grid_cell_answer_needs_two_numbers(answer: str) -> None:
    assert read_grid_cell_answer(answer) == []


@pytest.mark.parametrize("value", [_cell(751, 317), _cell(0, 0), _cell(123456, 7)])
def test_validate_grid_cell_accepts_non_negative_integers(
    value: dict[str, Any],
) -> None:
    assert validate_grid_cell(value) is None
    assert validate_grid_cell(json.loads(json.dumps(value))) is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "751/317",
        [751, 317],
        {},
        {**_cell(751, 317), "type": "point"},
        {"type": "grid_cell", "ind_x": 751},
        {"type": "grid_cell", "ind_y": 317},
        _cell(-1, 317),
        _cell(751, -5),
        _cell(True, 317),
        _cell(751, False),
        {**_cell(751, 317), "ind_x": 751.0},
        {**_cell(751, 317), "ind_y": "317"},
        {**_cell(751, 317), "ind_x": None},
        {**_cell(751, 317), "ind_x": math.nan},
    ],
)
def test_validate_grid_cell_rejects_everything_else(value: Any) -> None:
    assert validate_grid_cell(value) == "extractors.errors.invalid_grid_cell"


def test_describe_grid_cell_passes_both_indices_as_text() -> None:
    texts = _Texts()

    assert describe_grid_cell(_cell(751, 317), texts) == "extractors.display.grid_cell"
    assert texts.calls == [
        ("extractors.display.grid_cell", {"ind_x": "751", "ind_y": "317"})
    ]

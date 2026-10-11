"""Behavioral tests for spatial value extraction and validation."""

import pytest

from retman.extractors import EXTRACTORS, VALIDATORS
from retman.extractors.areas import extract_area
from retman.i18n.loader import load_core_texts


@pytest.mark.parametrize(
    ("source", "normalized"),
    [
        ("n-34", "N-34"),
        ("n-34-a", "N-34-A"),
        ("M-33-036", "M-33-36"),
        ("N-34-130-D", "N-34-130-D"),
        ("N-34-130-D-d", "N-34-130-D-d"),
        ("N-34-130-D-d-2", "N-34-130-D-d-2"),
        ("n-34-130-d-d-2-4", "N-34-130-D-d-2-4"),
        ("6.179.12", "6.179.12"),
        ("6.179.12.3", "6.179.12.3"),
        ("6.179.12.15", "6.179.12.15"),
        ("6.179.12.15.4", "6.179.12.15.4"),
        ("6.179.12.15.4.2", "6.179.12.15.4.2"),
    ],
)
def test_extract_area_sheet_systems_and_scales(source: str, normalized: str) -> None:
    matches = extract_area(f"Pobierz arkusz {source}.")

    assert [reading.value for match in matches for reading in match.readings] == [
        {"type": "sheet", "code": normalized}
    ]
    assert VALIDATORS["area"](matches[0].readings[0].value) is None


@pytest.mark.parametrize(
    "code", ["N-36-130-D", "N-34-145-D", "6.179.12.26", "N-34-130-D-d-5-4"]
)
def test_extract_area_does_not_accept_invalid_sheet_or_valid_prefix(code: str) -> None:
    assert extract_area(f"Pobierz {code}") == []
    assert (
        VALIDATORS["area"]({"type": "sheet", "code": code})
        == "extractors.errors.invalid_sheet"
    )


@pytest.mark.parametrize("source", ["powiat 1465", "TERYT: 1465", "kod powiatu 1465"])
def test_extract_area_teryt_requires_introducing_word(source: str) -> None:
    matches = extract_area(source)

    assert [reading.value for match in matches for reading in match.readings] == [
        {"type": "teryt", "code": "1465"}
    ]
    assert VALIDATORS["area"](matches[0].readings[0].value) is None


def test_extract_area_does_not_interpret_year_or_point_as_area() -> None:
    assert extract_area("Dane dla 2020 roku, punkt 52.41 16.93") == []


def test_extract_area_rejects_outside_poland_in_command() -> None:
    assert extract_area("bbox 31.2,52.4,32.1,53.2") == []


def test_extract_area_projected_without_labels_asks_about_axis_order() -> None:
    match = extract_area("Pobierz bbox 450000,550000,460000,560000")[0]

    assert [reading.value for reading in match.readings] == [
        {
            "type": "bbox",
            "min_x": 450000.0,
            "min_y": 550000.0,
            "max_x": 460000.0,
            "max_y": 560000.0,
            "crs": "EPSG:2180",
        },
        {
            "type": "bbox",
            "min_x": 550000.0,
            "min_y": 450000.0,
            "max_x": 560000.0,
            "max_y": 460000.0,
            "crs": "EPSG:2180",
        },
    ]
    assert match.ambiguous
    assert all(VALIDATORS["area"](reading.value) is None for reading in match.readings)


@pytest.mark.parametrize(
    ("source", "expected_x"),
    [
        ("x=450000 y=550000 x=460000 y=560000", 450000.0),
        ("y=450000 x=550000 y=460000 x=560000", 550000.0),
        ("E 450000 N 550000 E 460000 N 560000", 450000.0),
    ],
)
def test_extract_area_projected_axis_labels_disambiguate(
    source: str, expected_x: float
) -> None:
    match = extract_area(source)[0]

    assert len(match.readings) == 1
    assert match.readings[0].value["min_x"] == expected_x


@pytest.mark.parametrize(
    ("source", "order"),
    [
        ("bbox 16.93, 52.41, 17.22, 53.12", "bbox_4326_lon_lat"),
        ("bbox 52.41 16.93; 53.12 17.22", "bbox_4326_lat_lon"),
        ("bbox 52,41 16,93; 53,12 17,22", "bbox_4326_lat_lon"),
    ],
)
def test_extract_area_wgs84_both_orders_and_decimal_comma(
    source: str, order: str
) -> None:
    match = extract_area(source)[0]

    assert [reading.value for reading in match.readings] == [
        {
            "type": "bbox",
            "min_x": 16.93,
            "min_y": 52.41,
            "max_x": 17.22,
            "max_y": 53.12,
            "crs": "EPSG:4326",
        }
    ]
    assert match.readings[0].label_key == f"extractors.area.{order}"
    assert VALIDATORS["area"](match.readings[0].value) is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "16.9-17.1 52.41-53.2",
            {"min_x": 16.9, "min_y": 52.41, "max_x": 17.1, "max_y": 53.2},
        ),
        (
            "od 52.41-53.2 do 16.9-17.1",
            {"min_x": 16.9, "min_y": 52.41, "max_x": 17.1, "max_y": 53.2},
        ),
    ],
)
def test_extract_area_coordinate_ranges(
    source: str, expected: dict[str, float]
) -> None:
    matches = extract_area(source)

    assert len(matches) == 1
    assert all(
        matches[0].readings[0].value[key] == number for key, number in expected.items()
    )


def test_extract_area_range_with_named_axes_uses_original_order() -> None:
    matches = extract_area("N 550000-560000 E 450000-460000")

    assert len(matches) == 1
    assert [reading.value for reading in matches[0].readings] == [
        {
            "type": "bbox",
            "min_x": 450000.0,
            "min_y": 550000.0,
            "max_x": 460000.0,
            "max_y": 560000.0,
            "crs": "EPSG:2180",
        }
    ]


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (
            {
                "type": "bbox",
                "min_x": 22.1,
                "min_y": 52.1,
                "max_x": 27.3,
                "max_y": 53.1,
                "crs": "EPSG:4326",
            },
            "outside_poland",
        ),
        (
            {
                "type": "bbox",
                "min_x": 450000,
                "min_y": 540000,
                "max_x": 460000,
                "max_y": 900000,
                "crs": "EPSG:2180",
            },
            "outside_poland",
        ),
        (
            {
                "type": "bbox",
                "min_x": 17.1,
                "min_y": 52.1,
                "max_x": 16.9,
                "max_y": 53.1,
                "crs": "EPSG:4326",
            },
            "invalid_bbox_order",
        ),
    ],
)
def test_validate_area_rejects_invalid_bbox(
    value: dict[str, object], reason: str
) -> None:
    assert VALIDATORS["area"](value) == f"extractors.errors.{reason}"


def test_extract_area_multiple_kinds_and_spans() -> None:
    text = 'Dla n-34-130-d-d-2-4 i powiat 1465 oraz "C:\\mapy\\mój obszar.gpkg"'

    matches = EXTRACTORS["area"](text)

    assert [text[match.start : match.end] for match in matches] == [
        "n-34-130-d-d-2-4",
        "powiat 1465",
        '"C:\\mapy\\mój obszar.gpkg"',
    ]
    assert [match.readings[0].value for match in matches] == [
        {"type": "sheet", "code": "N-34-130-D-d-2-4"},
        {"type": "teryt", "code": "1465"},
        {"type": "geometry", "path": "C:\\mapy\\mój obszar.gpkg"},
    ]


def test_extract_area_multiple_bboxes_remain_separate_candidates() -> None:
    matches = extract_area(
        "Porównaj 16.9 52.41 17.1 53.2 z 450000 550000 460000 560000"
    )

    assert [len(match.readings) for match in matches] == [1, 2]
    assert [match.readings[0].value["crs"] for match in matches] == [
        "EPSG:4326",
        "EPSG:2180",
    ]


def test_extract_area_bbox_followed_by_sentence_comma() -> None:
    text = "NMT dla n-34-130-d-d-2-4 i bbox 450000 550000 460000 560000, potem"

    matches = extract_area(text)

    assert [text[match.start : match.end] for match in matches] == [
        "n-34-130-d-d-2-4",
        "450000 550000 460000 560000",
    ]
    assert len(matches[1].readings) == 2


def test_extract_area_rendered_bbox_labels_show_axis_interpretations() -> None:
    texts = load_core_texts("pl")
    match = extract_area("450000,550000,460000,560000")[0]

    labels = [
        texts.get(reading.label_key, **reading.label_args) for reading in match.readings
    ]

    assert labels[0] != labels[1]
    assert "E 450000–460000" in labels[0]
    assert "E 550000–560000" in labels[1]

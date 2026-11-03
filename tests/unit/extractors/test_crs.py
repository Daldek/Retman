"""Which system a command names for the result, and when Retman must ask (ADR-009)."""

import pytest

from retman.extractors.crs import extract_crs, read_crs_answer

RECT_1992 = "x=530000 y=382000 x=530100 y=382100"
RECT_WGS = "16.90 52.40 16.91 52.41"


def _codes(matches) -> list[str]:
    return [reading.value for match in matches for reading in match.readings]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        # Output cue before the system, with or without the "EPSG:" prefix
        (f"Wytnij NMT {RECT_WGS}, wynik EPSG:2180", ["EPSG:2180"]),
        (f"Wytnij NMT {RECT_WGS}, wynik w 2180", ["EPSG:2180"]),
        (f"Wycinek DSM {RECT_WGS} do układu 5514", ["EPSG:5514"]),
        (f"Wycinek {RECT_WGS} do ETRS89/TM33 EPSG:3045", ["EPSG:3045", "EPSG:3045"]),
        # Input system right after the rectangle, output after "przelicz do"
        (f"Daj NMT z {RECT_1992} w 2180, przelicz do 3045", ["EPSG:3045"]),
        (f"NMPT z {RECT_1992} PL-1992, do EPSG:3045", ["EPSG:3045"]),
        # No cue, but the code cannot describe WGS84 numbers: it is the result
        (f"Wytnij NMT na {RECT_WGS} WGS84; GeoTIFF EPSG:5514", ["EPSG:5514"]),
        # Unsupported systems are still reported, so Retman can say so
        (f"Wytnij NMT {RECT_WGS} do EPSG:2177", ["EPSG:2177"]),
    ],
)
def test_extract_crs_returns_the_result_system(command: str, expected: list[str]):
    assert _codes(extract_crs(command)) == expected


@pytest.mark.parametrize(
    "command",
    [
        # The system describes the rectangle, not the result
        "Wycinek wysokościowy NMT 530000 382000 530100 382100 PL-1992.",
        "sciagnij wycinek dsm 530000 382000 530100 382100 w pl-1992",
        f"Wytnij NMT z {RECT_1992} w układzie 2180, EVRF2007.",
        # A bare number without any word about systems is not a code
        f"Wytnij NMT {RECT_WGS} 2180",
        # "od" is not "do": short words are never matched with a typo
        f"Wytnij NMT {RECT_WGS} od 2180",
        # An unknown bare code is not guessed to be a near supported one
        f"Wytnij NMT {RECT_WGS} do 2108",
        # Input word spelled exactly wins over a typo-close output stem
        f"układ wejściowy 2180, {RECT_1992}",
    ],
)
def test_extract_crs_leaves_unclear_roles_to_a_question(command: str):
    assert extract_crs(command) == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        (f"wytnij nmt {RECT_WGS} wyink w 2180", "EPSG:2180"),
        (f"wytnij nmt {RECT_WGS} przelic do sjtsk", "EPSG:5514"),
        (f"wytnij nmt {RECT_WGS} uklad wynikowy 3045", "EPSG:3045"),
        (f"wytnij nmt {RECT_WGS} zapisz w puwg92", "EPSG:2180"),
        (f"wytnij nmt {RECT_WGS} WYNIK PL1992", "EPSG:2180"),
        (f"wytnij nmt {RECT_WGS} wynik w krowak", "EPSG:5514"),
    ],
)
def test_extract_crs_tolerates_missing_diacritics_case_and_one_typo(
    command: str, expected: str
):
    assert _codes(extract_crs(command)) == [expected]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("2180", ["EPSG:2180"]),
        ("s-jtsk", ["EPSG:5514"]),
        ("EPSG 3045", ["EPSG:3045"]),
        ("PUWG 1992", ["EPSG:2180"]),
        ("1", []),
    ],
)
def test_read_crs_answer_accepts_bare_codes_and_names(answer: str, expected):
    assert _codes(read_crs_answer(answer)) == expected

"""Paths and project result references are literal user-provided values."""

import pytest

from retman.extractors import EXTRACTORS, VALIDATORS
from retman.extractors.paths import extract_paths
from retman.extractors.results import extract_result_refs


@pytest.mark.parametrize(
    ("source", "path"),
    [
        ("wczytaj dane.shp", "dane.shp"),
        ("z pliku /tmp/mapa.gpkg", "/tmp/mapa.gpkg"),
        ('użyj "dane/powiat granice.shp"', "dane/powiat granice.shp"),
        (r"z pliku C:\hydro\dane.gpkg", r"C:\hydro\dane.gpkg"),
        ("użyj ../dane/wysokość.tif", "../dane/wysokość.tif"),
        ("użyj mapa.shp.", "mapa.shp"),
    ],
)
def test_extract_paths_retains_literal_spelling(source: str, path: str) -> None:
    matches = extract_paths(source)

    assert [reading.value for match in matches for reading in match.readings] == [path]
    assert VALIDATORS["path"](path) is None


def test_extract_paths_multiple_files_and_no_partial_extension() -> None:
    matches = EXTRACTORS["path"]("Porównaj dane.shp i B.gpkg.backup z wynikiem C.tif")

    assert [match.readings[0].value for match in matches] == ["dane.shp", "C.tif"]


@pytest.mark.parametrize("source", ["#3", "wynik 3", "wyniku nr 3", "Wynik #3"])
def test_extract_result_refs_forms(source: str) -> None:
    matches = extract_result_refs(f"Użyj {source} do mapy")

    assert [reading.value for match in matches for reading in match.readings] == [3]
    assert VALIDATORS["result"](matches[0].readings[0].value) is None


def test_extract_result_refs_multiple_and_zero_not_a_result() -> None:
    matches = EXTRACTORS["result"]("Połącz wynik 3 i #12, ale nie #0")

    assert [match.readings[0].value for match in matches] == [3, 12]
    assert VALIDATORS["result"](0) == "extractors.errors.invalid_result"

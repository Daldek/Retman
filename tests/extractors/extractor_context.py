"""Helpers for extractor tests: a context factory and a synthetic station catalog.

The stations are invented for the tests (codes included); they only imitate the
shape of the IMGW lists: hydrological stations with a river, meteorological ones
in capitals, Czech ones with WIGOS codes and diacritics.
"""

from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from retman.extractors.base import ExtractionContext
from retman.extractors.stations import STATION_INDEX_KEY, StationIndex

TODAY = date(2026, 10, 19)

# (code, name, kind, provider, river)
_STATIONS: tuple[tuple[str, str, str, str, str | None], ...] = (
    ("152160180", "Poznań", "hydro", "IMGW-PIB", "Warta"),
    ("352160330", "POZNAŃ-ŁAWICA", "meteo", "IMGW-PIB", None),
    ("352160331", "POZNAŃ-STRZESZYN", "meteo", "IMGW-PIB", None),
    ("152210120", "Warszawa-Bulwary", "hydro", "IMGW-PIB", "Wisła"),
    ("352200375", "WARSZAWA-OKĘCIE", "meteo", "IMGW-PIB", None),
    ("150190060", "Kraków-Bielany", "hydro", "IMGW-PIB", "Wisła"),
    ("350190566", "KRAKÓW-BALICE", "meteo", "IMGW-PIB", None),
    ("150170230", "Opole", "hydro", "IMGW-PIB", "Odra"),
    ("351170375", "OPOLE", "meteo", "IMGW-PIB", None),
    ("150190020", "Łódź", "hydro", "IMGW-PIB", "Ner"),
    ("151160140", "Zator", "hydro", "IMGW-PIB", "Skawa"),
    ("150180110", "Dąbie", "hydro", "IMGW-PIB", "Odra"),
    ("151160270", "Kłodzko", "hydro", "IMGW-PIB", "Nysa Kłodzka"),
    ("151160240", "Bardo", "hydro", "IMGW-PIB", "Nysa Kłodzka"),
    ("151160200", "Nysa", "hydro", "IMGW-PIB", "Nysa Kłodzka"),
    ("151160250", "Kamieniec Ząbkowicki", "hydro", "IMGW-PIB", "Nysa Kłodzka"),
    ("151140111", "Nowy Sącz", "hydro", "IMGW-PIB", "Dunajec"),
    ("151140112", "Nowy Targ", "hydro", "IMGW-PIB", "Dunajec"),
    ("151170100", "Koło", "hydro", "IMGW-PIB", "Warta"),
    ("152170110", "Brzeg", "hydro", "IMGW-PIB", "Odra"),
    ("152170111", "Brzeg", "hydro", "IMGW-PIB", "Brzeźnica"),
    ("150160170", "Mielec", "hydro", "IMGW-PIB", "Wisłoka"),
    ("150180230", "Toruń", "hydro", "IMGW-PIB", "Wisła"),
    ("350160520", "ŁÓDŹ-LUBLINEK", "meteo", "IMGW-PIB", None),
    ("350180100", "KOŁOBRZEG", "meteo", "IMGW-PIB", None),
    ("350210110", "GDAŃSK-RĘBIECHOWO", "meteo", "IMGW-PIB", None),
    ("0-203-1-001000", "Špindlerův Mlýn", "hydro", "CHMI", "Labe"),
    ("0-203-1-001010", "Praha-Chuchle", "hydro", "CHMI", "Vltava"),
    ("0-203-0-11782", "Ostrava-Poruba", "meteo", "CHMI", None),
)


def station_items() -> list[dict[str, Any]]:
    """The catalog as ``stations find`` items."""
    return [
        {
            "station_code": code,
            "name": name,
            "kind": kind,
            "provider": provider,
            "river": river,
        }
        for code, name, kind, provider, river in _STATIONS
    ]


def station_document(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A ``stations find`` document as the tool returns it."""
    found = station_items() if items is None else items
    return {
        "schema": "imgw-result/1",
        "command": "stations find",
        "status": "ok",
        "result": {"items": found, "total": len(found), "limit": None, "offset": 0},
        "notices": [],
    }


def make_context(
    *,
    scope: Mapping[str, Any] | None = None,
    lookup: Callable[[Any], Any] | None = None,
    today: date = TODAY,
    index: StationIndex | None = None,
) -> ExtractionContext:
    """Extraction context with an injectable offline lookup (the catalog by default)."""
    memo: dict[str, Any] = {}
    if index is not None:
        memo[STATION_INDEX_KEY] = index
    return ExtractionContext(
        tool="imgwtools",
        settings={},
        project_dir=Path("."),
        scope=scope or {},
        lookup=lookup or (lambda call: station_document()),
        today=today,
        memo=memo,
    )

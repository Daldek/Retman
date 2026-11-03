"""A synthetic station catalog for offline evaluation of station-name commands.

``retman eval run`` plans commands without a tool store, so a name such as "Poznań"
has no real catalog to be matched against. This module is that catalog: real
place and river names (so commands read naturally and inflection, ambiguity and
typos are exercised), invented codes (they only follow the shape of the real
ones and do not denote any station), in the structure of the ``stations find``
document of IMGWTools. The dataset check and the evaluation run both serve it
through ``catalog_lookup``.
"""

import unicodedata
from collections.abc import Mapping
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolDocument, ToolError

# (kind, code, name, river); IMGW-PIB stations, invented 9-digit codes
_IMGW: tuple[tuple[str, str, str, str | None], ...] = (
    ("hydro", "150000101", "SKOCZÓW", "Wisła"),
    ("hydro", "150000102", "ZATOR", "Wisła"),
    ("hydro", "150000103", "KRAKÓW-BIELANY", "Wisła"),
    ("hydro", "150000104", "SZCZUCIN", "Wisła"),
    ("hydro", "150000105", "SANDOMIERZ", "Wisła"),
    ("hydro", "150000106", "ANNOPOL", "Wisła"),
    ("hydro", "150000107", "PUŁAWY", "Wisła"),
    ("hydro", "150000108", "WARSZAWA-BULWARY", "Wisła"),
    ("hydro", "150000109", "PŁOCK", "Wisła"),
    ("hydro", "150000110", "WŁOCŁAWEK", "Wisła"),
    ("hydro", "150000111", "TORUŃ", "Wisła"),
    ("hydro", "150000112", "TCZEW", "Wisła"),
    ("hydro", "150000113", "KIEZMARK", "Wisła"),
    ("hydro", "150000201", "RACIBÓRZ-MIEDONIA", "Odra"),
    ("hydro", "150000202", "KRAPKOWICE", "Odra"),
    ("hydro", "150000203", "OPOLE", "Odra"),
    ("hydro", "150000204", "BRZEG", "Odra"),
    ("hydro", "150000205", "OŁAWA", "Odra"),
    ("hydro", "150000206", "WROCŁAW-TRESTNO", "Odra"),
    ("hydro", "150000207", "GŁOGÓW", "Odra"),
    ("hydro", "150000208", "NOWA SÓL", "Odra"),
    ("hydro", "150000209", "CIGACICE", "Odra"),
    ("hydro", "150000210", "DĄBIE", "Odra"),
    ("hydro", "150000211", "GRYFINO", "Odra"),
    ("hydro", "150000212", "SŁUBICE", "Odra"),
    ("hydro", "150000301", "CZĘSTOCHOWA", "Warta"),
    ("hydro", "150000302", "SIERADZ", "Warta"),
    ("hydro", "150000303", "KOŁO", "Warta"),
    ("hydro", "150000304", "KONIN", "Warta"),
    ("hydro", "150000305", "PNIEWY", "Warta"),
    ("hydro", "150000306", "POZNAŃ-BOGDANKA", "Warta"),
    ("hydro", "150000307", "OBORNIKI", "Warta"),
    ("hydro", "150000308", "SKWIERZYNA", "Warta"),
    ("hydro", "150000309", "GORZÓW WLKP.", "Warta"),
    ("hydro", "150000401", "KŁODZKO", "Nysa Kłodzka"),
    ("hydro", "150000402", "NYSA", "Nysa Kłodzka"),
    ("hydro", "150000501", "WYSZKÓW", "Bug"),
    ("hydro", "150000502", "MIELNIK", "Bug"),
    ("hydro", "150000503", "OSTROŁĘKA", "Narew"),
    ("hydro", "150000504", "ŁOMŻA", "Narew"),
    ("hydro", "150000505", "PRZEMYŚL", "San"),
    ("hydro", "150000506", "DYNÓW", "San"),
    ("hydro", "150000507", "NOWY SĄCZ", "Dunajec"),
    ("hydro", "150000508", "ŁOWICZ", "Bzura"),
    ("hydro", "150000509", "LEGNICA", "Kaczawa"),
    ("meteo", "250000101", "POZNAŃ-ŁAWICA", None),
    ("meteo", "250000102", "POZNAŃ-STRZESZYN", None),
    ("meteo", "250000103", "WARSZAWA-OKĘCIE", None),
    ("meteo", "250000104", "KRAKÓW-BALICE", None),
    ("meteo", "250000105", "GDAŃSK-ŚWIBNO", None),
    ("meteo", "250000106", "WROCŁAW-STRACHOWICE", None),
    ("meteo", "250000107", "ŁÓDŹ-LUBLINEK", None),
    ("meteo", "250000108", "KATOWICE-MUCHOWIEC", None),
    ("meteo", "250000109", "LUBLIN-RADAWIEC", None),
    ("meteo", "250000110", "RZESZÓW-JASIONKA", None),
    ("meteo", "250000111", "BIAŁYSTOK", None),
    ("meteo", "250000112", "OLSZTYN", None),
    ("meteo", "250000113", "KIELCE-SUKÓW", None),
    ("meteo", "250000114", "OPOLE", None),
    ("meteo", "250000115", "ZIELONA GÓRA", None),
    ("meteo", "250000116", "TORUŃ", None),
    ("meteo", "250000117", "BYDGOSZCZ-SZWEDEROWO", None),
    ("meteo", "250000118", "KOSZALIN", None),
    ("meteo", "250000119", "ELBLĄG-MILEJEWO", None),
    ("meteo", "250000120", "SUWAŁKI", None),
    ("meteo", "250000121", "ZAKOPANE", None),
    ("meteo", "250000122", "KASPROWY WIERCH", None),
    ("meteo", "250000123", "ŚNIEŻKA", None),
    ("meteo", "250000124", "HEL", None),
    ("meteo", "250000125", "ŁEBA", None),
    ("meteo", "250000126", "ŚWINOUJŚCIE", None),
    ("meteo", "250000127", "LESKO", None),
    ("meteo", "250000128", "BIELSKO-BIAŁA", None),
    ("meteo", "250000129", "KŁODZKO", None),
    ("meteo", "250000130", "TARNÓW", None),
    ("meteo", "250000131", "CZĘSTOCHOWA", None),
    ("meteo", "250000132", "SŁUBICE", None),
    ("meteo", "250000133", "LEGNICA", None),
    ("meteo", "250000134", "PIŁA", None),
    ("meteo", "250000135", "RACIBÓRZ", None),
)

# ČHMÚ stations: invented WIGOS-shaped identifiers
_CHMI: tuple[tuple[str, str, str, str | None], ...] = (
    ("hydro", "0-203-1-910001", "Ostrava-Svinov", "Odra"),
    ("hydro", "0-203-1-910002", "Praha-Chuchle", "Vltava"),
    ("hydro", "0-203-1-910003", "Děčín", "Labe"),
    ("hydro", "0-203-1-910004", "Olomouc-Chomoutov", "Morava"),
    ("meteo", "0-203-0-91001", "Brno-Tuřany", None),
    ("meteo", "0-203-0-91002", "Praha-Ruzyně", None),
    ("meteo", "0-203-0-91003", "Ostrava-Mošnov", None),
)


def synthetic_station_items() -> list[dict[str, Any]]:
    """Return the catalog's stations as the items of a ``stations find`` document."""
    items: list[dict[str, Any]] = []
    for provider, stations in (("IMGW-PIB", _IMGW), ("CHMI", _CHMI)):
        for index, (kind, code, name, river) in enumerate(stations):
            items.append(
                {
                    "kind": kind,
                    "station_code": code,
                    "name": name,
                    "river": river,
                    "hydrographic_code": None,
                    "river_order": None,
                    "short_code": None,
                    "latitude": round(49.0 + 6.0 * ((index * 7) % 50) / 50, 4),
                    "longitude": round(14.5 + 9.5 * ((index * 11) % 50) / 50, 4),
                    "provider": provider,
                }
            )
    return items


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold().replace("ł", "l"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def synthetic_station_document(options: Mapping[str, object]) -> ToolDocument:
    """Return the ``stations find`` envelope of the catalog, narrowed as the tool does.

    ``provider`` and ``kind`` filter by equality, ``query`` is a case- and
    diacritics-insensitive fragment of the name or the river.
    """
    items = synthetic_station_items()
    for key in ("provider", "kind"):
        if key in options:
            items = [item for item in items if item[key] == options[key]]
    query = options.get("query")
    if isinstance(query, str):
        needle = _fold(query)
        items = [
            item
            for item in items
            if needle in _fold(str(item["name"])) + " " + _fold(str(item["river"]))
        ]
    return {
        "schema": "imgw-result/1",
        "command": "stations find",
        "check": False,
        "status": "ok",
        "result": {"items": items, "total": len(items), "limit": None, "offset": 0},
        "notices": [],
    }


def catalog_lookup(call: CatalogCall) -> ToolDocument:
    """Offline ``lookup`` that serves the synthetic station catalog and nothing else.

    A lookup of any other command raises ``ToolError("not_found")``, which the
    station extractor reads as "no catalog" for the commands it never makes.
    """
    if call.command == "stations find" and call.options.get("source") == "store":
        return synthetic_station_document(call.options)
    raise ToolError("eval", "not_found", f"no offline answer for {call.command}")

"""The availability check of the Kartograf operations (a network step after consent)."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from kartograf_support import (
    BBOX,
    FIXTURES,
    PARENT,
    PL2000,
    SHEET,
    TERYT,
    OfflineClient,
    Reply,
    context,
    operations,
    settings,
)
from kartograf_support import plan as recorded_plan

from retman.adapters.catalog import CatalogCall, ToolError
from retman.adapters.manifest_adapter import run_check
from retman.core.check import CheckReport
from retman.i18n.loader import load_core_texts

AVAILABILITY = json.loads((FIXTURES / "availability_nmt_sheet.json").read_text("utf-8"))
ELEVATION = "elevation availability"
DEM_SHEET = {"area": SHEET, "resolution": "1m", "vertical_crs": "evrf2007"}
HIERARCHY_DEM = {
    "area": PARENT,
    "product": "dem",
    "target_scale": "scale_10000",
    "resolution": "1m",
    "vertical_crs": "evrf2007",
}
HIERARCHY_ORTHO = {
    "area": PARENT,
    "product": "orthophoto",
    "target_scale": "scale_10000",
    "color": "rgb",
}
CUTOUT = {
    "area": BBOX,
    "product": "dem",
    "target_crs": "epsg_2180",
    "vertical_crs": "evrf2007",
}


def availability() -> dict[str, Any]:
    """A private copy of the recorded availability report, to vary in a test."""
    return copy.deepcopy(AVAILABILITY)


def grids(
    doc: dict[str, Any], resolution: str, vertical_crs: str
) -> list[dict[str, Any]]:
    """The ASC combinations of one grid (resolution and height system)."""
    return [
        item
        for item in doc["combinations"]
        if item["format"] == "ASC"
        and item["resolution"] == resolution
        and item["vertical_crs"] == vertical_crs
    ]


def check(
    tmp_path: Path,
    name: str,
    params: dict[str, Any],
    *,
    queries: dict[str, Reply] | None = None,
    plans: dict[str, Reply] | None = None,
) -> tuple[CheckReport, OfflineClient]:
    """Run the check of an operation the way the product does."""
    client = OfflineClient(settings(tmp_path), queries=queries, plans=plans)
    report = run_check(
        operations()[name], params, context(name, client), load_core_texts("pl")
    )
    return report, client


def plan(name: str, tmp_path: Path) -> dict[str, Any]:
    """The freshness plan of the real Kartograf for an empty store, by ``name``."""
    return recorded_plan(name, tmp_path / "store")


def test_nmt_sheet_newest_complete_year_and_only_sheet_grids_as_alternatives(
    tmp_path: Path,
) -> None:
    report, client = check(
        tmp_path, "download_dem_sheet", DEM_SHEET, queries={ELEVATION: availability()}
    )

    assert report.status == "available"
    assert report.error is None
    assert client.network == [
        (
            "query",
            CatalogCall(ELEVATION, {"product": "nmt", "sheet": "N-34-130-D-d-2-4"}),
        )
    ]
    assert report.items[0] == {
        "key": "selection_available",
        "args": {
            "product": "NMT",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "year": "2025",
        },
    }
    # The XYZ/TBD/TIN archives of the index are not offered: the newest KRON86 sheet
    # grid is the 2013 ASC, not the 2017 XYZ archive
    assert report.items[1:] == [
        {"key": "alternatives", "args": {}},
        {
            "key": "alternative",
            "args": {
                "product": "NMT",
                "resolution": "1m",
                "vertical_crs": "KRON86",
                "year": "2013",
            },
        },
    ]
    assert "komplet" in report.lines[0]
    assert "1m" in report.lines[0]
    assert "EVRF2007" in report.lines[0]
    assert "2025" in report.lines[0]
    assert "KRON86" in report.lines[2]
    assert "2013" in report.lines[2]
    assert "2017" not in report.summary()


def test_nmt_sheet_kron86_selection_is_judged_by_its_own_year(tmp_path: Path) -> None:
    params = {**DEM_SHEET, "vertical_crs": "kron86"}

    report, client = check(
        tmp_path, "download_dem_sheet", params, queries={ELEVATION: availability()}
    )

    assert report.status == "available"
    assert report.items[0]["key"] == "selection_available"
    assert report.items[0]["args"]["year"] == "2013"
    assert report.items[0]["args"]["vertical_crs"] == "KRON86"
    assert [item["args"]["vertical_crs"] for item in report.items[2:]] == ["EVRF2007"]
    assert [item["args"]["year"] for item in report.items[2:]] == ["2025"]
    assert len(client.network) == 1


def test_nmt_sheet_grid_absent_from_the_index_is_unavailable(tmp_path: Path) -> None:
    report, _ = check(
        tmp_path,
        "download_dem_sheet",
        {**DEM_SHEET, "resolution": "5m"},
        queries={ELEVATION: availability()},
    )

    assert report.status == "unavailable"
    assert report.items[0]["key"] == "selection_unavailable"
    assert report.items[0]["args"]["resolution"] == "5m"
    assert "brak danych" in report.lines[0]
    # What the sheet does have is still offered
    assert [item["key"] for item in report.items[1:]] == [
        "alternatives",
        "alternative",
        "alternative",
    ]


def test_nmt_sheet_incomplete_grid_is_partial_with_sheet_counts(tmp_path: Path) -> None:
    doc = availability()
    for item in grids(doc, "1m", "EVRF2007"):
        item["complete"] = False
        item["sheets_full"] = ["N-34-130-D-d-2-4"] if item["year"] == 2025 else []
        item["sheets_partial"] = ["N-34-130-D-d-2-3", "N-34-130-D-d-2-2"]

    report, _ = check(
        tmp_path, "download_dem_sheet", DEM_SHEET, queries={ELEVATION: doc}
    )

    assert report.status == "partial"
    assert report.items[0] == {
        "key": "selection_partial",
        "args": {
            "product": "NMT",
            "resolution": "1m",
            "vertical_crs": "EVRF2007",
            "year": "2025",
            "full": "1",
            "partial": "2",
        },
    }
    assert "1 pełnych" in report.lines[0]
    assert "2 niepełnych" in report.lines[0]
    # An incomplete grid is not offered as an alternative to itself or to others
    assert all(item["args"]["vertical_crs"] != "EVRF2007" for item in report.items[2:])


def test_nmt_100m_is_unknown_and_makes_no_network_call(tmp_path: Path) -> None:
    report, client = check(
        tmp_path,
        "download_dem_sheet",
        {"area": SHEET, "resolution": "100m"},
        queries={ELEVATION: availability()},
    )

    assert report.status == "unknown"
    assert report.error is None
    assert report.items == [{"key": "province_files", "args": {}}]
    assert "województw" in report.lines[0]
    assert client.network == []


def test_hierarchy_dem_asks_the_index_about_the_parent(tmp_path: Path) -> None:
    report, client = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_DEM,
        queries={ELEVATION: availability()},
    )

    assert report.status == "available"
    assert client.network == [
        (
            "query",
            CatalogCall(ELEVATION, {"product": "nmt", "sheet": "N-34-130-D-d-2"}),
        )
    ]
    assert report.items[0]["args"]["year"] == "2025"


def test_hierarchy_pl2000_parent_keeps_only_pl2000_combinations(
    tmp_path: Path,
) -> None:
    doc = availability()
    for item in grids(doc, "1m", "EVRF2007"):
        if item["year"] == 2022:
            item["horizontal"] = "PL-2000"
    params = {**HIERARCHY_DEM, "area": PL2000, "target_scale": "scale_2000"}

    report, client = check(
        tmp_path, "download_sheet_hierarchy", params, queries={ELEVATION: doc}
    )

    # 2025 and 2024 are PL-1992 grids: only the PL-2000 year counts, and the
    # KRON86 grids (all PL-1992) are not alternatives either
    assert report.status == "available"
    assert report.items == [
        {
            "key": "selection_available",
            "args": {
                "product": "NMT",
                "resolution": "1m",
                "vertical_crs": "EVRF2007",
                "year": "2022",
            },
        }
    ]
    assert client.network[0][1].options["sheet"] == "7.171.21"


def test_hierarchy_pl2000_parent_without_pl2000_data_is_unavailable(
    tmp_path: Path,
) -> None:
    params = {**HIERARCHY_DEM, "area": PL2000, "target_scale": "scale_2000"}

    report, _ = check(
        tmp_path,
        "download_sheet_hierarchy",
        params,
        queries={ELEVATION: availability()},
    )

    assert report.status == "unavailable"
    assert [item["key"] for item in report.items] == ["selection_unavailable"]


def test_orthophoto_rgb_reports_published_sheets_and_newest_flight(
    tmp_path: Path,
) -> None:
    report, client = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": plan("plan_orthophoto_parent", tmp_path)},
    )

    assert report.status == "available"
    assert report.items == [
        {
            "key": "orthophoto_sheets",
            "args": {"published": "4", "total": "4", "newest": "2025-04-26"},
        }
    ]
    assert "4 z 4" in report.lines[0]
    assert "2025-04-26" in report.lines[0]
    assert [(kind, call.command) for kind, call in client.network] == [
        ("check", "imagery download")
    ]


def test_orthophoto_newest_flight_is_the_latest_date_of_all_sheets(
    tmp_path: Path,
) -> None:
    doc = plan("plan_orthophoto_parent", tmp_path)
    doc["items"][2]["available_label"] = "2025-08-30_1"
    doc["items"][3]["available_label"] = "2023-05-01_2"

    report, _ = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": doc},
    )

    assert report.items[0]["args"]["newest"] == "2025-08-30"


def test_orthophoto_sheets_in_the_store_add_an_in_store_item(tmp_path: Path) -> None:
    doc = plan("plan_orthophoto_parent", tmp_path)
    doc["items"][0]["status"] = "current"
    doc["items"][1]["status"] = "current"

    report, _ = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": doc},
    )

    assert report.status == "available"
    assert [item["key"] for item in report.items] == ["orthophoto_sheets", "in_store"]
    assert report.items[1]["args"] == {"count": "2"}
    assert "2 z nich jest już w magazynie" in report.lines[1]


def test_orthophoto_some_sheets_without_data_is_partial(tmp_path: Path) -> None:
    doc = plan("plan_orthophoto_parent", tmp_path)
    for item in doc["items"][:2]:
        item["status"] = "check_failed"
        item["available_label"] = None

    report, _ = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": doc},
    )

    assert report.status == "partial"
    assert report.items[0]["args"]["published"] == "2"
    assert report.items[0]["args"]["total"] == "4"


def test_orthophoto_no_sheet_checked_is_unknown(tmp_path: Path) -> None:
    doc = plan("plan_orthophoto_parent", tmp_path)
    for item in doc["items"]:
        item["status"] = "check_failed"
        item["available_label"] = None

    report, _ = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": doc},
    )

    assert report.status == "unknown"
    assert report.items[0]["args"]["published"] == "0"
    assert report.items[0]["args"]["newest"] == "-"


def test_orthophoto_cir_and_bw_are_unknown_without_network(tmp_path: Path) -> None:
    for color in ("cir", "bw"):
        report, client = check(
            tmp_path,
            "download_sheet_hierarchy",
            {**HIERARCHY_ORTHO, "color": color},
            plans={"imagery download": plan("plan_orthophoto_parent", tmp_path)},
        )

        assert report.status == "unknown"
        assert report.items == [{"key": "orthophoto_variant", "args": {}}]
        assert "RGB" in report.lines[0]
        assert client.network == []


def test_orthophoto_no_coverage_is_unavailable_with_the_services_reason(
    tmp_path: Path,
) -> None:
    def refuse(call: CatalogCall) -> dict[str, Any]:
        raise ToolError("kartograf", "no_data", "Brak arkuszy w skorowidzu")

    report, client = check(
        tmp_path,
        "download_sheet_hierarchy",
        HIERARCHY_ORTHO,
        plans={"imagery download": refuse},
    )

    assert report.status == "unavailable"
    assert report.error is None
    assert report.items == [
        {"key": "orthophoto_none", "args": {"detail": "Brak arkuszy w skorowidzu"}}
    ]
    assert "Brak arkuszy w skorowidzu" in report.lines[0]
    assert len(client.network) == 1


def test_cutout_asks_about_the_rectangle_and_judges_without_sheet_system(
    tmp_path: Path,
) -> None:
    doc = availability()
    for item in doc["combinations"]:
        item["horizontal"] = "PL-2000"

    report, client = check(
        tmp_path, "download_elevation_cutout", CUTOUT, queries={ELEVATION: doc}
    )

    assert report.status == "available"
    ((kind, call),) = client.network
    assert kind == "query"
    assert call == CatalogCall(
        ELEVATION,
        {
            "product": "nmt",
            "country": "pl",
            "bbox": [530000, 382000, 530100, 382100],
            "bbox_crs": "EPSG:2180",
        },
    )
    assert report.items[0]["args"] == {
        "product": "NMT",
        "resolution": "1m",
        "vertical_crs": "EVRF2007",
        "year": "2025",
    }
    assert {"key": "cutout_note", "args": {}} in report.items
    assert "WCS" in report.summary()


def test_cutout_of_a_geometry_file_asks_with_the_file(tmp_path: Path) -> None:
    shape = {"type": "geometry", "path": "/data/granica.shp", "layer": None}

    _, client = check(
        tmp_path,
        "download_elevation_cutout",
        {**CUTOUT, "area": shape},
        queries={ELEVATION: availability()},
    )

    ((_, call),) = client.network
    assert call.options == {
        "product": "nmt",
        "country": "pl",
        "geometry": "/data/granica.shp",
    }


def test_bdot10k_teryt_reports_the_county_and_asks_the_plan_check(
    tmp_path: Path,
) -> None:
    report, client = check(
        tmp_path,
        "download_bdot10k",
        {"area": TERYT, "format": "gpkg"},
        plans={"landcover download": plan("plan_bdot10k_teryt", tmp_path)},
    )

    assert report.status == "available"
    assert report.items == [
        {"key": "counties", "args": {"count": "1", "units": "2264"}}
    ]
    assert "2264" in report.lines[0]
    ((kind, call),) = client.network
    assert (kind, call.command) == ("check", "landcover download")
    assert call.options["teryt"] == "2264"
    assert call.options["format"] == "GPKG"


def test_bdot10k_sheet_lists_counties_and_counts_those_in_store(
    tmp_path: Path,
) -> None:
    doc = plan("plan_bdot10k_sheet", tmp_path)
    second = {**doc["items"][0], "unit": "2011", "name": "2011.zip"}
    second["status"] = "current"
    doc["items"].append(second)

    report, client = check(
        tmp_path,
        "download_bdot10k",
        {"area": SHEET, "format": "shp"},
        plans={"landcover download": doc},
    )

    assert report.status == "available"
    assert report.items == [
        {"key": "counties", "args": {"count": "2", "units": "2010, 2011"}},
        {"key": "in_store", "args": {"count": "1"}},
    ]
    assert "2010, 2011" in report.lines[0]
    assert client.network[0][1].options["sheet"] == "N-34-130-D-d-2-4"
    assert client.network[0][1].options["format"] == "SHP"


def test_bdot10k_many_counties_are_shortened_in_the_line(tmp_path: Path) -> None:
    doc = plan("plan_bdot10k_sheet", tmp_path)
    doc["items"] = [
        {**doc["items"][0], "unit": f"{2000 + number}", "name": f"{2000 + number}.zip"}
        for number in range(14)
    ]

    report, _ = check(
        tmp_path,
        "download_bdot10k",
        {"area": SHEET, "format": "shp"},
        plans={"landcover download": doc},
    )

    assert report.items[0]["args"]["count"] == "14"
    assert "2011" in report.items[0]["args"]["units"]
    assert "2012" not in report.items[0]["args"]["units"]
    assert report.items[0]["args"]["units"].endswith("...")


def test_bdot10k_failed_checks_decide_between_unknown_and_partial(
    tmp_path: Path,
) -> None:
    doc = plan("plan_bdot10k_sheet", tmp_path)
    doc["items"].append({**doc["items"][0], "unit": "2011", "name": "2011.zip"})
    params = {"area": SHEET, "format": "shp"}

    doc["items"][0]["status"] = "check_failed"
    partial, _ = check(
        tmp_path, "download_bdot10k", params, plans={"landcover download": doc}
    )
    doc["items"][1]["status"] = "check_failed"
    unknown, _ = check(
        tmp_path, "download_bdot10k", params, plans={"landcover download": doc}
    )

    assert partial.status == "partial"
    assert unknown.status == "unknown"
    assert unknown.error is None


def test_bdot10k_area_without_counties_is_unavailable(tmp_path: Path) -> None:
    doc = plan("plan_bdot10k_sheet", tmp_path)
    doc["items"] = []

    report, _ = check(
        tmp_path,
        "download_bdot10k",
        {"area": SHEET, "format": "shp"},
        plans={"landcover download": doc},
    )

    assert report.status == "unavailable"
    assert report.items == [{"key": "no_counties", "args": {}}]
    assert "żadnego powiatu" in report.lines[0]


def test_client_error_during_the_check_is_an_unknown_report(tmp_path: Path) -> None:
    def fail(call: CatalogCall) -> dict[str, Any]:
        raise ToolError("kartograf", "source_unavailable", "WFS nie odpowiada")

    report, client = check(
        tmp_path, "download_dem_sheet", DEM_SHEET, queries={ELEVATION: fail}
    )

    assert report.status == "unknown"
    assert report.items == []
    assert report.error is not None
    assert "WFS nie odpowiada" in report.error
    assert "Sprawdzenie nie powiodło się" in report.lines[0]
    assert len(client.network) == 1


def test_partial_index_answer_is_flagged_incomplete_and_unknown(tmp_path: Path) -> None:
    doc = availability()
    doc["ok"] = False

    report, _ = check(
        tmp_path, "download_dem_sheet", DEM_SHEET, queries={ELEVATION: doc}
    )

    assert report.status == "unknown"
    assert report.items == [{"key": "incomplete", "args": {}}]
    assert "niepełny" in report.lines[0]


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("download_bdot10k", {"area": TERYT, "format": "gpkg"}),
        ("download_sheet_hierarchy", HIERARCHY_ORTHO),
    ],
)
def test_a_store_kartograf_refuses_is_the_whole_answer_of_the_check(
    tmp_path: Path, name: str, params: dict[str, Any]
) -> None:
    store = tmp_path / "other-files"
    store.mkdir()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")
    client = OfflineClient({**settings(tmp_path), "store_dir": str(store)})

    # Kartograf plans the refusal of the root as its one position and asks the source
    # for nothing: no county or sheet is there to count
    report = run_check(
        operations()[name], params, context(name, client), load_core_texts("pl")
    )

    assert report.status == "unavailable"
    (item,) = report.items
    assert item["key"] == "store_refused"
    assert "odmówi zapisu" in report.lines[0] and str(store) in report.lines[0]

"""The calls Retman makes to Kartograf's command layer for each operation."""

from pathlib import Path
from typing import Any

import pytest
from kartograf_support import (
    BBOX,
    PARENT,
    PL2000,
    PL2000_FINE,
    SHEET,
    TERYT,
    context,
    geometry,
    operations,
)

from retman.adapters.catalog import CatalogCall, ToolError, route_error
from retman.testing import FakeToolClient
from retman.tools.kartograf import calls

SHAPE = {"type": "geometry", "path": "/data/granica.shp", "layer": None}
LAYER = {"type": "geometry", "path": "/data/granica.gpkg", "layer": "zlewnie"}


def build(operation: str, params: dict[str, Any]) -> CatalogCall:
    """The one call of an operation (its builder is named after the operation)."""
    (call,) = getattr(calls, operation)(params, context(operation))
    return call


def test_nmt_sheet_uses_kartograf_values_for_the_chosen_grid() -> None:
    call = build(
        "download_dem_sheet",
        {"area": SHEET, "resolution": "0_5m", "vertical_crs": "kron86"},
    )

    assert call == CatalogCall(
        "elevation download",
        {
            "product": "nmt",
            "sheet": "N-34-130-D-d-2-4",
            "resolution": "0.5m",
            "vertical_crs": "KRON86",
        },
        "dem",
        {"sheet": "area", "scale": "area", "resolution": "resolution"},
    )


def test_nmt_100m_is_province_archives_without_height_system() -> None:
    call = build("download_dem_sheet", {"area": SHAPE, "resolution": "100m"})

    assert call.kind == "dem_archive"
    assert call.options == {
        "product": "nmt",
        "geometry": "/data/granica.shp",
        "country": "pl",
        "resolution": "100m",
    }


def test_geometry_file_of_a_single_sheet_request_is_pl1992() -> None:
    call = build(
        "download_dem_sheet",
        {"area": LAYER, "resolution": "1m", "vertical_crs": "evrf2007"},
    )

    assert call.options["geometry"] == "/data/granica.gpkg"
    assert call.options["layer"] == "zlewnie"
    assert call.options["sheet_system"] == "1992"
    assert call.options["country"] == "pl"
    assert "scale" not in call.options


@pytest.mark.parametrize(
    ("area", "target", "expected"),
    [
        (PARENT, "scale_10000", {"sheet": "N-34-130-D-d-2"}),
        (PL2000, "scale_2000", {"sheet": "7.171.21", "scale": "1:2000"}),
        (
            SHAPE,
            "scale_10000",
            {"geometry": "/data/granica.shp", "country": "pl", "sheet_system": "1992"},
        ),
        (
            SHAPE,
            "scale_500",
            {
                "geometry": "/data/granica.shp",
                "country": "pl",
                "sheet_system": "2000",
                "scale": "1:500",
            },
        ),
    ],
)
def test_hierarchy_scale_and_sheet_system_follow_the_area(
    area: dict[str, Any], target: str, expected: dict[str, str]
) -> None:
    params = {
        "product": "dem",
        "area": area,
        "target_scale": target,
        "resolution": "1m",
        "vertical_crs": "evrf2007",
    }

    call = build("download_sheet_hierarchy", params)

    assert {k: v for k, v in call.options.items() if k in expected} == expected
    assert ("scale" in call.options) == ("scale" in expected)


def test_nmpt_hierarchy_takes_its_own_resolution_parameter() -> None:
    params = {
        "product": "dsm",
        "area": PL2000,
        "target_scale": "scale_5000",
        "resolution_dsm": "0_6m",
        "vertical_crs": "evrf2007",
    }

    call = build("download_sheet_hierarchy", params)

    assert call.options["product"] == "nmpt"
    assert call.options["resolution"] == "0.6m"
    assert call.params["resolution"] == "resolution_dsm"
    assert call.params["scale"] == "target_scale"
    assert call.kind == "dsm"


@pytest.mark.parametrize("color", ["rgb", "cir", "bw"])
def test_orthophoto_call_is_the_imagery_command_that_validates_without_colour(
    color: str,
) -> None:
    """Kartograf's ``imagery download`` has no colour; the handler adds it."""
    params = {
        "product": "orthophoto",
        "area": PARENT,
        "target_scale": "scale_10000",
        "color": color,
    }

    call = build("download_sheet_hierarchy", params)

    assert call.command == "imagery download"
    assert call.options == {"product": "orto", "sheet": "N-34-130-D-d-2"}
    assert call.kind == "orthophoto"


def test_cutout_is_always_the_one_metre_wcs_cutout() -> None:
    params = {
        "product": "dsm",
        "area": BBOX,
        "target_crs": "epsg_5514",
        "vertical_crs": "kron86",
    }

    call = build("download_elevation_cutout", params)

    assert call.options == {
        "product": "nmpt",
        "country": "pl",
        "bbox": [530000, 382000, 530100, 382100],
        "bbox_crs": "EPSG:2180",
        "cutout": True,
        "horizontal_crs": "EPSG:5514",
        "vertical_crs": "KRON86",
    }
    assert call.params["horizontal_crs"] == "target_crs"
    assert call.kind == "dsm"


@pytest.mark.parametrize(
    ("area", "selection"),
    [
        (TERYT, {"teryt": "2264"}),
        (PL2000, {"sheet": "7.171.21"}),
        (
            BBOX,
            {"bbox": [530000, 382000, 530100, 382100], "bbox_crs": "EPSG:2180"},
        ),
        (LAYER, {"geometry": "/data/granica.gpkg", "layer": "zlewnie"}),
        (SHAPE, {"geometry": "/data/granica.shp"}),
    ],
)
def test_bdot10k_hands_every_area_form_to_kartograf(
    area: dict[str, Any], selection: dict[str, object]
) -> None:
    call = build("download_bdot10k", {"area": area, "format": "shp"})

    assert call.command == "landcover download"
    assert call.options == {"product": "bdot10k", **selection, "format": "SHP"}
    assert call.kind == "topographic_vector"


def _rejection(operation: str, params: dict[str, Any]) -> tuple[CatalogCall, ToolError]:
    """What Kartograf's own offline validation says about the built call."""
    kartograf_support = pytest.importorskip("kartograf_support")
    client = kartograf_support.OfflineClient({})
    call = build(operation, params)
    with pytest.raises(ToolError) as caught:
        client.validate(call)
    return call, caught.value


def test_a_rejected_grid_pair_is_routed_to_both_parameters_that_make_it() -> None:
    call, error = _rejection(
        "download_dem_sheet",
        {"area": SHEET, "resolution": "5m", "vertical_crs": "kron86"},
    )

    assert error.code == "invalid_input"
    names = [
        param["name"] for param in operations()["download_dem_sheet"].spec["params"]
    ]
    assert route_error(call, error, names) == ["resolution", "vertical_crs"]


def test_a_scale_the_sheet_system_cannot_have_is_routed_to_the_scale_question() -> None:
    call, error = _rejection(
        "download_sheet_hierarchy",
        {
            "product": "dem",
            "area": PARENT,
            "target_scale": "scale_2000",
            "resolution": "1m",
            "vertical_crs": "evrf2007",
        },
    )

    names = [
        param["name"]
        for param in operations()["download_sheet_hierarchy"].spec["params"]
    ]
    assert error.option == "scale"
    assert route_error(call, error, names) == ["target_scale"]


def test_a_pl2000_sheet_without_scale_is_routed_to_the_area_of_the_nmt_sheet() -> None:
    call, error = _rejection(
        "download_dem_sheet",
        {"area": PL2000, "resolution": "1m", "vertical_crs": "evrf2007"},
    )

    assert route_error(call, error, ["area", "resolution", "vertical_crs"]) == ["area"]


def test_a_finer_pl2000_sheet_is_a_valid_nmt_sheet(tmp_path: Path) -> None:
    kartograf_support = pytest.importorskip("kartograf_support")
    client = kartograf_support.OfflineClient({})

    client.validate(
        build(
            "download_dem_sheet",
            {"area": PL2000_FINE, "resolution": "1m", "vertical_crs": "evrf2007"},
        )
    )
    client.validate(
        build(
            "download_dem_sheet",
            {
                "area": geometry(tmp_path, "zlewnia.gpkg"),
                "resolution": "0_5m",
                "vertical_crs": "kron86",
            },
        )
    )


def test_building_calls_asks_the_tool_nothing() -> None:
    """Builders are pure: the fake client of a context sees no call at all."""
    fake = FakeToolClient()
    ctx = context("download_dem_sheet", fake)

    calls.download_dem_sheet(
        {"area": SHEET, "resolution": "1m", "vertical_crs": "evrf2007"}, ctx
    )

    assert fake.calls == []

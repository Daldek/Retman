"""The offline preview a Kartograf plan shows before the user confirms."""

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
    OfflineClient,
    context,
    geometry,
    operations,
    settings,
)

from retman.adapters.catalog import CatalogCall, PlanView, ToolDriftError, ToolError
from retman.adapters.manifest_adapter import Preview, preview_operation
from retman.i18n.loader import load_core_texts
from retman.testing import FakeToolClient

TEXTS = load_core_texts("pl")

ENVELOPE_ROW = (
    "Obwiednia obszaru",
    "2.0 × 2.0 km (EPSG:2180: E 530000–532000, N 382000–384000)",
)
SQUARE = {"min_x": 530000.0, "min_y": 382000.0, "max_x": 532000.0, "max_y": 384000.0}

NMT = {"resolution": "1m", "vertical_crs": "evrf2007"}
HIERARCHY = {
    "product": "dem",
    "target_scale": "scale_2000",
    "resolution": "1m",
    "resolution_dsm": None,
    "vertical_crs": "evrf2007",
    "color": None,
}
ORTHOPHOTO = {
    **HIERARCHY,
    "product": "orthophoto",
    "resolution": None,
    "vertical_crs": None,
    "color": "rgb",
}
CUTOUT = {"product": "dem", "target_crs": "epsg_2180", "vertical_crs": "evrf2007"}
BDOT = {"format": "gpkg"}


def preview(name: str, params: dict[str, Any], client: Any) -> Preview:
    """The preview of a plan: planning code sees only the offline client half."""
    ctx = context(name, PlanView(client))
    return preview_operation(operations()[name], params, ctx, TEXTS)


def sheets_row(count: int, scale: str, system: str) -> tuple[str, str]:
    return ("Liczba arkuszy", f"{count} × {scale} (PL-{system})")


def fake_envelope(box: list[float]) -> FakeToolClient:
    return FakeToolClient(documents={"geometry envelope": {"bbox": box}})


def lookups(client: FakeToolClient) -> list[CatalogCall]:
    return [call for method, call in client.calls if method == "lookup"]


def test_dem_sheet_leaf_code_is_one_sheet(tmp_path: Path) -> None:
    result = preview(
        "download_dem_sheet",
        {"area": SHEET, **NMT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [sheets_row(1, "1:10000", "1992")]
    assert result.problems == []


def test_dem_sheet_coarser_pl1992_code_expands_to_its_10000_sheets(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_dem_sheet",
        {"area": PARENT, **NMT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [sheets_row(4, "1:10000", "1992")]
    assert result.values["sheet_count"] == 4


@pytest.mark.parametrize("name", ["granica.shp", "zlewnia.gpkg"])
def test_dem_sheet_geometry_shows_envelope_and_sheet_count(
    tmp_path: Path, name: str
) -> None:
    area = geometry(tmp_path, name)

    result = preview(
        "download_dem_sheet",
        {"area": area, **NMT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [ENVELOPE_ROW, sheets_row(4, "1:10000", "1992")]
    assert result.values["envelope"] == {**SQUARE, "crs": "EPSG:2180"}
    assert result.values["sheet_count"] == 4
    assert result.problems == []


def test_dem_sheet_100m_geometry_shows_province_files_instead_of_a_sheet_count(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_dem_sheet",
        {"area": geometry(tmp_path), "resolution": "100m", "vertical_crs": None},
        OfflineClient(settings(tmp_path)),
    )

    assert [label for label, _ in result.rows] == ["Obwiednia obszaru", "Zakres danych"]
    assert "sheet_count" not in result.values
    assert "envelope" in result.values


def test_dem_sheet_tool_rejection_names_every_parameter_it_concerns(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_dem_sheet",
        {"area": SHEET, "resolution": "5m", "vertical_crs": "kron86"},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == []
    (problem,) = result.problems
    assert set(problem.params) == {"resolution", "vertical_crs"}
    assert "KRON86" in problem.text


def test_dem_sheet_pl2000_10000_code_is_a_problem_of_the_area(tmp_path: Path) -> None:
    result = preview(
        "download_dem_sheet",
        {"area": PL2000, **NMT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == []
    assert [problem.params for problem in result.problems] == [("area",)]


def test_dem_sheet_rejection_naming_no_parameter_is_tool_drift() -> None:
    client = FakeToolClient(
        validation={
            "elevation download": ToolError(
                "kartograf", "validation_error", "x", option="no_such_option"
            )
        }
    )

    with pytest.raises(ToolDriftError):
        preview("download_dem_sheet", {"area": SHEET, **NMT}, client)


def test_hierarchy_pl2000_parent_counts_its_descendants(tmp_path: Path) -> None:
    result = preview(
        "download_sheet_hierarchy",
        {"area": PL2000, **HIERARCHY},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [sheets_row(25, "1:2000", "2000")]
    assert result.values["sheet_system"] == "2000"


def test_hierarchy_geometry_counts_sheets_of_the_chosen_scale(tmp_path: Path) -> None:
    result = preview(
        "download_sheet_hierarchy",
        {"area": geometry(tmp_path), **HIERARCHY, "target_scale": "scale_500"},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [ENVELOPE_ROW, sheets_row(54, "1:500", "2000")]
    assert result.values["sheet_count"] == 54


def test_hierarchy_target_not_finer_than_the_sheet_lists_the_scales_that_work(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_sheet_hierarchy",
        {"area": PL2000_FINE, **HIERARCHY, "target_scale": "scale_5000"},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == []
    (problem,) = result.problems
    assert problem.params == ("target_scale", "area")
    text = problem.text
    assert "7.171.21.12" in text
    positions = [text.find(label) for label in ("1:2000", "1:1000", "1:500")]
    assert -1 not in positions
    assert positions == sorted(positions)
    assert "1:5000" not in text.split("Dostępne skale")[1]


def test_hierarchy_sheet_without_any_workable_scale_says_it_has_no_descendants() -> (
    None
):
    def parse(call: CatalogCall) -> dict[str, Any]:
        if "descendants" in call.options:
            raise ToolError(
                "kartograf",
                "validation_error",
                "no descendants",
                option="descendants",
                call=call,
            )
        return {"sheet_system": "2000", "scale": "1:500"}

    result = preview(
        "download_sheet_hierarchy",
        {"area": PL2000_FINE, **HIERARCHY},
        FakeToolClient(documents={"sheet parse": parse}),
    )

    assert result.rows == []
    (problem,) = result.problems
    assert problem.params == ("target_scale", "area")
    assert "7.171.21.12" in problem.text
    assert "Dostępne skale" not in problem.text


def test_hierarchy_orthophoto_for_geometry_is_refused_without_looking_up_sheets(
    tmp_path: Path,
) -> None:
    client = FakeToolClient(
        documents={"geometry envelope": {"bbox": [530000, 382000, 532000, 384000]}}
    )

    result = preview(
        "download_sheet_hierarchy",
        {"area": geometry(tmp_path), **ORTHOPHOTO},
        client,
    )

    assert result.rows == []
    (problem,) = result.problems
    assert set(problem.params) == {"product", "area"}
    assert lookups(client) == []


def test_hierarchy_orthophoto_for_a_sheet_code_counts_sheets(tmp_path: Path) -> None:
    result = preview(
        "download_sheet_hierarchy",
        {"area": PARENT, **ORTHOPHOTO, "target_scale": "scale_10000"},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [sheets_row(4, "1:10000", "1992")]
    assert result.problems == []


def test_cutout_bbox_has_nothing_to_show(tmp_path: Path) -> None:
    result = preview(
        "download_elevation_cutout",
        {"area": BBOX, **CUTOUT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == []
    assert result.problems == []


def test_cutout_geometry_shows_only_the_envelope(tmp_path: Path) -> None:
    result = preview(
        "download_elevation_cutout",
        {"area": geometry(tmp_path), **CUTOUT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [ENVELOPE_ROW]
    assert "sheet_count" not in result.values
    assert result.problems == []


@pytest.mark.parametrize("area", [TERYT, BBOX], ids=["teryt", "bbox"])
def test_bdot10k_county_or_rectangle_has_nothing_to_show(
    tmp_path: Path, area: dict[str, Any]
) -> None:
    result = preview(
        "download_bdot10k", {"area": area, **BDOT}, OfflineClient(settings(tmp_path))
    )

    assert result.rows == []
    assert result.problems == []


def test_bdot10k_geometry_inside_poland_shows_the_envelope(tmp_path: Path) -> None:
    result = preview(
        "download_bdot10k",
        {"area": geometry(tmp_path), **BDOT},
        OfflineClient(settings(tmp_path)),
    )

    assert result.rows == [ENVELOPE_ROW]
    assert result.problems == []


def test_bdot10k_geometry_far_outside_poland_is_a_problem_of_the_area(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_bdot10k",
        {"area": geometry(tmp_path), **BDOT},
        fake_envelope([0, 0, 10, 10]),
    )

    (problem,) = result.problems
    assert problem.params == ("area",)
    assert "Polsk" in problem.text


def test_bdot10k_single_point_geometry_inside_poland_is_accepted(
    tmp_path: Path,
) -> None:
    result = preview(
        "download_bdot10k",
        {"area": geometry(tmp_path), **BDOT},
        fake_envelope([530000, 382000, 530000, 382000]),
    )

    assert result.problems == []
    assert [label for label, _ in result.rows] == ["Obwiednia obszaru"]


def test_find_sheets_without_any_sheet_is_a_problem_of_the_area(tmp_path: Path) -> None:
    client = FakeToolClient(
        documents={
            "geometry envelope": {"bbox": [530000, 382000, 532000, 384000]},
            "sheet find": {"count": 0},
        }
    )

    result = preview("download_dem_sheet", {"area": geometry(tmp_path), **NMT}, client)

    (problem,) = result.problems
    assert problem.params == ("area",)
    assert "żadnego arkusza" in problem.text
    assert all(label != "Liczba arkuszy" for label, _ in result.rows)


CASES: list[tuple[str, dict[str, Any], str]] = [
    ("download_dem_sheet", NMT, "shp"),
    ("download_dem_sheet", {"resolution": "100m", "vertical_crs": None}, "shp"),
    ("download_sheet_hierarchy", {**HIERARCHY, "target_scale": "scale_500"}, "gpkg"),
    ("download_sheet_hierarchy", ORTHOPHOTO, "shp"),
    ("download_elevation_cutout", CUTOUT, "gpkg"),
    ("download_bdot10k", BDOT, "shp"),
]


@pytest.mark.parametrize(
    ("name", "params", "kind"),
    CASES,
    ids=[f"{name}-{i}" for i, (name, _, _) in enumerate(CASES)],
)
def test_preview_never_uses_the_network_verbs(
    tmp_path: Path, name: str, params: dict[str, Any], kind: str
) -> None:
    client = OfflineClient(settings(tmp_path))
    view = PlanView(client)
    area = geometry(tmp_path, "zlewnia.gpkg" if kind == "gpkg" else "granica.shp")

    preview_operation(
        operations()[name],
        {"area": area, **params},
        context(name, view),
        TEXTS,
    )

    assert client.network == []
    assert not any(hasattr(view, verb) for verb in ("run", "check", "query"))

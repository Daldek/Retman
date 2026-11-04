"""The orthophoto cutout of an area, and the land cover planned through the pipeline.

The real Kartograf validates, plans and downloads in process; only the GUGiK image
WCS, its sheet index and CORINE's WMS are stubs (``kartograf_offline``), so the
documents, the grid checks of the cutout and the store are those of the pinned
version.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import rasterio
from kartograf_offline import (
    Corine,
    GugikIndex,
    ImageWcs,
    corine,
    flight,
    gugik_index,
    image_wcs,
)
from kartograf_support import BBOX, OfflineClient, context, operations, settings

from retman.adapters.catalog import ToolError, route_error, run_calls
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.testing import FakeDecisionBackend
from retman.tools.kartograf import calls, checks

NAME = "download_orthophoto_cutout"
ORTHOPHOTO = {
    "product": "orthophoto",
    "area": BBOX,
    "coverage": "standard",
    "resolution": "0_25m",
}
TRUE_ORTHOPHOTO = {"product": "true_orthophoto", "area": BBOX, "resolution": "0_05m"}
# The one PL-1992 1:10000 sheet of BBOX
SHEET = "M-34-27-B-b-1-4"


def run(tmp_path: Path, params: dict[str, Any]) -> HandlerOutput:
    """Run the operation's calls with the real Kartograf into a store of the test."""
    client = OfflineClient(settings(tmp_path))
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(NAME, client, root=tmp_path, output_dir=output_dir)
    return run_calls(operations()[NAME], params, {}, output_dir, ctx)


def test_an_orthophoto_cutout_is_one_rgb_geotiff_on_the_chosen_pixel(
    tmp_path: Path,
) -> None:
    with image_wcs(ImageWcs()) as service:
        output = run(tmp_path, ORTHOPHOTO)

    assert service.requests == [0.25]
    (path,) = output["files"]["orthophoto"]
    assert path.is_relative_to(tmp_path / "store")
    validate_file("orthophoto", path)
    with rasterio.open(path) as image:
        assert (image.count, image.width, image.height) == (3, 400, 400)
    assert output["values"]["resolution"] == "0.25m"
    assert output["values"]["coverage"] == "standard"


def test_a_true_orthophoto_cutout_asks_for_no_service_variant(tmp_path: Path) -> None:
    with image_wcs(ImageWcs()) as service:
        output = run(tmp_path, TRUE_ORTHOPHOTO)

    assert service.requests == [0.05]
    assert output["values"]["product"] == "true-orto"
    assert output["values"]["coverage"] is None


def test_a_cutout_without_any_image_ends_as_no_data(tmp_path: Path) -> None:
    with image_wcs(ImageWcs(value=0)), pytest.raises(ToolError) as caught:
        run(tmp_path, ORTHOPHOTO)

    assert caught.value.tool_code == "no_data"
    assert not list((tmp_path / "store").rglob("*.tif"))


def test_the_true_orthophotos_pixel_is_asked_again_for_the_orthophotomap(
    tmp_path: Path,
) -> None:
    client = OfflineClient(settings(tmp_path))
    params = {**ORTHOPHOTO, "resolution": "0_05m"}
    (call,) = calls.download_orthophoto_cutout(params, context(NAME))

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    assert route_error(call, caught.value, list(params)) == ["resolution"]


def test_the_cutout_check_reads_the_sheet_index_of_the_area(tmp_path: Path) -> None:
    client = OfflineClient(settings(tmp_path))
    ctx = context(NAME, client, root=tmp_path)
    index = GugikIndex([flight(SHEET, "2024-05-11", "79001", orthophoto=True)])

    with gugik_index(index):
        report = checks.download_orthophoto_cutout(ORTHOPHOTO, ctx)
    with gugik_index(GugikIndex()):
        empty = checks.download_orthophoto_cutout(ORTHOPHOTO, ctx)

    assert index.resolved == [SHEET]
    assert report["status"] == "available"
    assert report["items"] == [
        {
            "key": "orthophoto_sheets",
            "args": {"published": "1", "total": "1", "newest": "2024-05-11"},
        },
        {"key": "cutout_note", "args": {}},
    ]
    assert empty["status"] == "unavailable"
    assert [item["key"] for item in empty["items"]] == [
        "orthophoto_none",
        "cutout_note",
    ]


# --- the whole pipeline ------------------------------------------------------


def make_app(tmp_path: Path, rules: dict[str, Any]) -> tuple[Retman, OfflineClient]:
    """A pipeline over the Kartograf operations and an offline client."""
    config = load_config(
        init_config(tmp_path / "config.toml", stores_dir=tmp_path / "stores")
    )
    config = replace(config, collect_commands=False)
    project = tmp_path / "project"
    project.mkdir()
    client = OfflineClient(config.tools["kartograf"])
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"kartograf": client},
    )
    return app, client


def stored(app: Retman, kind: str) -> Path:
    """The one file of ``kind`` the result record of the run names."""
    (record_path,) = (app.workspace.project_dir / app.config.results_dir).glob(
        "*/result.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    (entry,) = record["files"][kind]
    assert entry["store"] == "kartograf"
    return Path(entry["path"])


def asked(plan: Plan) -> set[str]:
    return {question.name for question in plan.questions}


def test_an_orthophoto_cutout_is_planned_offline_and_lands_in_the_store(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "spatial_data": "spatial_data",
            NAME: NAME,
            "orthophoto": "orthophoto",
            "high": "high",
            "0_1m": "0_1m",
        },
    )

    plan = app.plan(
        "Wytnij ortofotomapę wysokiej rozdzielczości w pikselu 10 cm dla "
        "x=530000 y=382000 x=530100 y=382100"
    )
    assert plan.questions == []
    assert client.network == []  # the plan and its preview are offline (N-12)

    with image_wcs(ImageWcs()):
        result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert stored(app, "orthophoto").is_relative_to(tmp_path / "stores" / "kartograf")


def test_corine_asks_for_its_edition_and_lands_in_the_store(tmp_path: Path) -> None:
    app, client = make_app(
        tmp_path,
        {
            "spatial_data": "spatial_data",
            "download_landcover": "download_landcover",
            "corine": "corine",
        },
    )

    plan = app.plan("Pobierz CORINE Land Cover dla arkusza N-34-130-D")
    assert asked(plan) == {"corine_year"}
    (question,) = plan.questions
    keys = [option.key for option in question.options]
    plan = plan.answer("corine_year", str(keys.index("2012") + 1))
    assert plan.questions == []
    assert client.network == []

    with corine(Corine()) as service:
        result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert service.years == [2012]
    assert stored(app, "landcover_raster").suffix == ".png"

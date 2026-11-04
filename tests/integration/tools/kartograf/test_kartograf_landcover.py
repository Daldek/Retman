"""Land cover of an area: CORINE Land Cover and the GUGiK BDOO packages.

The real Kartograf validates, plans and downloads in process; only CORINE's WMS and
BDOO's opendata and PRG are stubs (``kartograf_offline.Corine`` and ``Bdoo``), so the
documents, the segments and the sidecars are those of the pinned version.
"""

from pathlib import Path
from typing import Any

import pytest
from kartograf_offline import Bdoo, Corine, bdoo, corine
from kartograf_support import BBOX, OfflineClient, context, operations, settings

from retman.adapters.catalog import ToolError, route_error, run_calls
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.tools.kartograf import calls, checks

AREA = {"type": "sheet", "code": "N-34-130-D"}
CORINE = {"product": "corine", "area": AREA, "corine_year": "2018"}
BDOO = {"product": "bdoo", "area": BBOX, "bdoo_year": "2023"}
NAME = "download_landcover"


def run(tmp_path: Path, params: dict[str, Any]) -> HandlerOutput:
    """Run the operation's calls with the real Kartograf into a store of the test."""
    client = OfflineClient(settings(tmp_path))
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(NAME, client, root=tmp_path, output_dir=output_dir)
    return run_calls(operations()[NAME], params, {}, output_dir, ctx)


def keys(output: HandlerOutput) -> list[str]:
    return [warning["key"] for warning in output["warnings"]]


def test_corine_without_clms_credentials_is_a_preview_the_result_names(
    tmp_path: Path,
) -> None:
    with corine(Corine()) as service:
        output = run(tmp_path, CORINE)

    assert service.years == [2018]
    (path,) = output["files"]["landcover_raster"]
    assert path.suffix == ".png"
    assert path.is_relative_to(tmp_path / "store")
    validate_file("landcover_raster", path)
    assert output["values"]["preview"] is True
    assert output["values"]["edition"] is None
    # Kartograf says it in an info line only, which a result does not show
    assert keys(output) == ["corine_preview"]


def test_bdoo_of_an_area_is_the_package_of_each_voivodeship_it_touches(
    tmp_path: Path,
) -> None:
    with bdoo(Bdoo(["1261", "1206", "2404"])) as service:
        output = run(tmp_path, BDOO)

    assert sorted(url.rsplit("/", 2)[-2] for url in service.fetched) == ["2023"] * 2
    assert output["values"]["voivodeships"] == ["12", "24"]
    assert output["values"]["missing_voivodeships"] == 0
    for path in output["files"]["topographic_archive"]:
        validate_file("topographic_archive", path)
    assert keys(output) == []


def test_a_voivodeship_package_that_fails_is_a_warning_and_the_others_stay(
    tmp_path: Path,
) -> None:
    with bdoo(Bdoo(["1261", "2404"], missing=["24"])):
        output = run(tmp_path, BDOO)

    assert output["values"]["voivodeships"] == ["12"]
    assert output["values"]["missing_voivodeships"] == 1
    (failed,) = [w for w in output["warnings"] if w["key"] == "failed_voivodeships"]
    assert failed["args"] == {"count": "1", "total": "2", "units": "24"}


@pytest.mark.parametrize(
    ("params", "asked"),
    [
        ({**CORINE, "corine_year": "2019"}, "corine_year"),
        ({**BDOO, "bdoo_year": "2014"}, "bdoo_year"),
    ],
)
def test_a_year_kartograf_refuses_is_asked_again_as_that_products_year(
    tmp_path: Path, params: dict[str, Any], asked: str
) -> None:
    client = OfflineClient(settings(tmp_path))
    (call,) = calls.download_landcover(params, context(NAME))

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    assert route_error(call, caught.value, ["product", "area", asked]) == [asked]


def test_the_bdoo_check_names_the_voivodeships_and_what_the_store_holds(
    tmp_path: Path,
) -> None:
    client = OfflineClient(settings(tmp_path))
    ctx = context(NAME, client, root=tmp_path)

    with bdoo(Bdoo(["1261", "2404"])):
        before = checks.download_landcover(BDOO, ctx)
        run(tmp_path, BDOO)
        after = checks.download_landcover(BDOO, ctx)

    assert before["status"] == "available"
    assert before["items"] == [
        {"key": "voivodeships", "args": {"count": "2", "units": "12, 24"}}
    ]
    assert {"key": "in_store", "args": {"count": "2"}} in after["items"]


def test_the_check_of_a_corine_preview_says_its_edition_cannot_be_known(
    tmp_path: Path,
) -> None:
    client = OfflineClient(settings(tmp_path))

    with corine(Corine()):
        report = checks.download_landcover(CORINE, context(NAME, client, root=tmp_path))

    assert report["status"] == "unknown"
    assert [item["key"] for item in report["items"]] == ["corine_preview"]

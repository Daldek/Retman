"""Small real downloads through Kartograf's real client (GUGiK servers, network).

Run deliberately: ``pytest -m live tests/tools/kartograf/test_kartograf_live.py``. Every
download goes into a store inside ``tmp_path``; the working directory stays empty and
each produced file is checked as the data kind it is delivered as.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from kartograf_support import context, operations, settings

from retman.adapters.catalog import CatalogCall, run_calls
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.tools.kartograf.client import KartografClient

pytestmark = pytest.mark.live

SHEET_5M = {
    "area": {"type": "sheet", "code": "N-34-130-D-d-3-1"},
    "resolution": "5m",
    "vertical_crs": "evrf2007",
}
HIERARCHY_5M = {
    "product": "dem",
    "area": {"type": "sheet", "code": "N-34-130-D-d-3"},
    "target_scale": "scale_10000",
    "resolution": "5m",
    "vertical_crs": "evrf2007",
}
CUTOUT_50M = {
    "product": "dem",
    "area": {
        "type": "bbox",
        "min_x": 530000,
        "min_y": 382000,
        "max_x": 530050,
        "max_y": 382050,
        "crs": "EPSG:2180",
    },
    "target_crs": "epsg_2180",
    "vertical_crs": "evrf2007",
}
BDOT10K_GPKG = {"area": {"type": "teryt", "code": "2264"}, "format": "gpkg"}


@pytest.fixture
def empty_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An empty working directory that must still be empty after the download."""
    folder = tmp_path / "cwd"
    folder.mkdir()
    monkeypatch.chdir(folder)
    yield folder
    assert list(folder.iterdir()) == [], "Kartograf wrote into the working directory"


def real_client(root: Path) -> KartografClient:
    """The real client, with the folder of the metadata cache in place."""
    (root / "data").mkdir(exist_ok=True)
    return KartografClient(settings(root))


def download(operation: str, params: dict[str, Any], root: Path) -> HandlerOutput:
    """Run an operation's calls through the real client into the store of ``root``."""
    out = root / "result"
    out.mkdir()
    client = real_client(root)
    ctx = context(operation, client, root=root, output_dir=out)
    return run_calls(operations()[operation], params, {}, out, ctx)


def delivered(output: HandlerOutput, kind: str, store: Path) -> list[Path]:
    """The files of one kind of a result: in the store and valid for the kind."""
    paths = [Path(path) for path in output["files"][kind]]
    assert paths
    for path in paths:
        assert path.is_file()
        assert path.stat().st_size > 0
        validate_file(kind, path)
    return paths


def test_nmt_sheet_of_5m_evrf2007_is_downloaded_into_the_store(
    tmp_path: Path, empty_cwd: Path
) -> None:
    output = download("download_dem_sheet", SHEET_5M, tmp_path)

    (path,) = delivered(output, "dem", tmp_path / "store")
    assert path.name == "N-34-130-D-d-3-1.asc"
    assert path.is_relative_to(tmp_path / "store")
    assert (tmp_path / "result" / "tool_1_elevation_download.json").is_file()


def test_nmt_hierarchy_of_5m_gives_the_sheets_of_the_parent(
    tmp_path: Path, empty_cwd: Path
) -> None:
    output = download("download_sheet_hierarchy", HIERARCHY_5M, tmp_path)

    paths = delivered(output, "dem", tmp_path / "store")
    assert 1 <= len(paths) <= 4
    assert all(path.name.startswith("N-34-130-D-d-3-") for path in paths)


def test_wcs_cutout_of_50_by_50_m_is_a_valid_geotiff(
    tmp_path: Path, empty_cwd: Path
) -> None:
    output = download("download_elevation_cutout", CUTOUT_50M, tmp_path)

    (path,) = delivered(output, "dem", tmp_path / "store")
    assert path.suffix == ".tif"


def test_bdot10k_of_a_county_is_a_geopackage(tmp_path: Path, empty_cwd: Path) -> None:
    output = download("download_bdot10k", BDOT10K_GPKG, tmp_path)

    (path,) = delivered(output, "topographic_vector", tmp_path / "store")
    assert path.suffix == ".gpkg"


def test_availability_of_a_sheet_lists_the_published_combinations(
    tmp_path: Path, empty_cwd: Path
) -> None:
    client = real_client(tmp_path)

    found = client.query(
        CatalogCall(
            "elevation availability",
            {"product": "nmt", "country": "pl", "sheet": "N-34-130-D-d-2-4"},
        )
    )

    assert found["schema"] == "kartograf-availability/1"
    assert found["combinations"]
    assert {combination["country"] for combination in found["combinations"]} == {"PL"}

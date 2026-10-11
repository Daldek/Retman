"""Offline behavior and small live downloads through Kartograf's public API."""

import time
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest

from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.tools.kartograf.handlers import (
    download_bdot10k,
    download_dem_sheet,
    download_elevation_cutout,
    download_sheet_hierarchy,
)


@pytest.fixture
def kartograf_module() -> Any:
    return pytest.importorskip("kartograf")


def test_download_dem_sheet_rejects_incompatible_5m_datum_before_network(
    tmp_path: Path, kartograf_module: Any
) -> None:
    params = {
        "area": {"type": "sheet", "code": "N-34-130-D-d-2-4"},
        "resolution": "5m",
        "vertical_crs": "kron86",
    }

    with pytest.raises(ValueError, match="EVRF2007"):
        download_dem_sheet(params, {}, tmp_path)

    assert not tuple(tmp_path.iterdir())


def test_download_sheet_hierarchy_reports_partial_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    file = output_dir / "sheet.asc"
    file.write_bytes(b"ncols 1\nnrows 1\n")

    def partial(self: Any, godlo: str, target_scale: str) -> list[Path]:
        assert self.resolution == "5m"
        assert self.vertical_crs == "EVRF2007"
        assert target_scale == "1:10000"
        self.last_result = kartograf_module.DownloadResult(
            succeeded=[file], failed=["sheet_1", "sheet_2"], no_coverage=["sheet_1"]
        )
        return [file]

    monkeypatch.setattr(kartograf_module.DownloadManager, "download_hierarchy", partial)
    params = {
        "product": "dem",
        "area": {"type": "sheet", "code": "N-34-130-D-d-2"},
        "target_scale": "scale_10000",
        "resolution": "5m",
        "vertical_crs": "evrf2007",
    }

    result = download_sheet_hierarchy(params, {}, output_dir)

    assert result["values"]["sheet_count"] == 1
    assert result["values"]["missing_sheets"] == 2
    assert result["warnings"] == [
        {"key": "no_coverage", "args": {"count": "1", "total": "3"}},
        {"key": "failed_sheets", "args": {"count": "1", "total": "3"}},
    ]
    assert result["files"] == {"dem": [file]}


def test_download_sheet_hierarchy_raises_when_all_sheets_lack_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    def no_data(self: Any, godlo: str, target_scale: str) -> list[Path]:
        self.last_result = kartograf_module.DownloadResult(
            failed=["sheet_1", "sheet_2"], no_coverage=["sheet_1", "sheet_2"]
        )
        return []

    monkeypatch.setattr(kartograf_module.DownloadManager, "download_hierarchy", no_data)
    params = {
        "product": "dsm",
        "area": {"type": "sheet", "code": "N-34-130-D-d-2"},
        "target_scale": "scale_10000",
    }

    with pytest.raises(kartograf_module.NoCoverageError):
        download_sheet_hierarchy(params, {}, tmp_path)


def test_download_elevation_cutout_reports_masked_and_nodata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    file = tmp_path / "cutout.tif"
    file.write_bytes(b"II*\x00")
    bbox = {
        "type": "bbox",
        "min_x": 530000,
        "min_y": 382000,
        "max_x": 530100,
        "max_y": 382100,
        "crs": "EPSG:2180",
    }

    def cutout(selected: Any, target_crs: str, **kwargs: Any) -> Any:
        assert selected == kartograf_module.BBox(
            530000, 382000, 530100, 382100, "EPSG:2180"
        )
        assert target_crs == "EPSG:5514"
        assert kwargs["product"] == "nmpt"
        assert kwargs["vertical_crs"] == "KRON86"
        assert kwargs["resolution"] == "1m"
        return kartograf_module.PlCutoutResult(
            path=file, masked_pixels=99, all_nodata=True
        )

    monkeypatch.setattr(kartograf_module, "download_pl_cutout", cutout)
    result = download_elevation_cutout(
        {
            "product": "dsm",
            "area": bbox,
            "target_crs": "epsg_5514",
            "vertical_crs": "kron86",
        },
        {},
        tmp_path,
    )

    assert result["files"] == {"dsm": [file]}
    assert result["warnings"] == [
        {"key": "all_nodata", "args": {}},
        {"key": "masked_pixels", "args": {"count": "99"}},
    ]


def test_download_bdot10k_unpack_shapefiles_inside_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    output_dir = tmp_path / "result"
    output_dir.mkdir()

    def download(self: Any, *, teryt: str, format: str) -> Path:
        assert format == "SHP"
        archive = output_dir / f"county_{teryt}.zip"
        with ZipFile(archive, "w") as target:
            target.writestr("layers/roads.shp", (9994).to_bytes(4, "big"))
            target.writestr("layers/roads.dbf", b"dbf")
            target.writestr("layers/roads.shx", b"shx")
        return archive

    monkeypatch.setattr(kartograf_module.LandCoverManager, "download", download)

    result = download_bdot10k(
        {"area": {"type": "teryt", "code": "2264"}, "format": "shp"},
        {},
        output_dir,
    )

    files = result["files"]["topographic_vector"]
    assert len(files) == 1
    validate_file("topographic_vector", files[0])
    assert files[0].parent.joinpath("roads.dbf").is_file()
    assert files[0].parent.joinpath("roads.shx").is_file()
    assert files[0].is_relative_to(output_dir)
    assert result["values"]["county_count"] == 1


def test_download_bdot10k_rejects_archive_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    output_dir = tmp_path / "result"
    output_dir.mkdir()

    def download(self: Any, *, teryt: str, format: str) -> Path:
        archive = output_dir / "county.zip"
        with ZipFile(archive, "w") as target:
            target.writestr("../../escaped.shp", (9994).to_bytes(4, "big"))
        return archive

    monkeypatch.setattr(kartograf_module.LandCoverManager, "download", download)

    with pytest.raises(kartograf_module.DownloadError):
        download_bdot10k(
            {"area": {"type": "teryt", "code": "2264"}, "format": "shp"},
            {},
            output_dir,
        )

    assert not (tmp_path / "escaped.shp").exists()


def test_download_bdot10k_keeps_successful_county_after_corrupt_shp_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    output_dir = tmp_path / "result"
    output_dir.mkdir()

    def discover(bbox: Any, *, cache: Any) -> list[str]:
        return ["2264", "2261"]

    def download(self: Any, *, teryt: str, format: str) -> Path:
        archive = output_dir / f"{teryt}.zip"
        if teryt == "2264":
            archive.write_bytes(b"not a ZIP")
        else:
            with ZipFile(archive, "w") as target:
                target.writestr("roads.shp", (9994).to_bytes(4, "big"))
                target.writestr("roads.dbf", b"dbf")
                target.writestr("roads.shx", b"shx")
        return archive

    monkeypatch.setattr(kartograf_module, "discover_teryts_for_bbox", discover)
    monkeypatch.setattr(kartograf_module.LandCoverManager, "download", download)

    result = download_bdot10k(
        {
            "area": {
                "type": "bbox",
                "min_x": 1,
                "min_y": 2,
                "max_x": 3,
                "max_y": 4,
                "crs": "EPSG:2180",
            },
            "format": "shp",
        },
        {},
        output_dir,
    )

    assert result["warnings"] == [
        {"key": "failed_counties", "args": {"count": "1", "total": "2"}}
    ]
    files = result["files"]["topographic_vector"]
    assert len(files) == 1
    validate_file("topographic_vector", files[0])
    assert files[0].is_relative_to(output_dir)


def test_download_bdot10k_area_returns_partial_counties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kartograf_module: Any
) -> None:
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    file = output_dir / "county.gpkg"

    def discover(bbox: Any, *, cache: Any) -> list[str]:
        assert bbox == kartograf_module.BBox(1, 2, 3, 4, "EPSG:2180")
        return ["2264", "2261"]

    def download(self: Any, *, teryt: str, format: str) -> Path:
        if teryt == "2264":
            raise kartograf_module.DownloadError("Unavailable county")
        file.write_bytes(b"SQLite format 3\x00")
        return file

    monkeypatch.setattr(kartograf_module, "discover_teryts_for_bbox", discover)
    monkeypatch.setattr(kartograf_module.LandCoverManager, "download", download)

    result = download_bdot10k(
        {
            "area": {
                "type": "bbox",
                "min_x": 1,
                "min_y": 2,
                "max_x": 3,
                "max_y": 4,
                "crs": "EPSG:2180",
            },
            "format": "gpkg",
        },
        {},
        output_dir,
    )

    assert result["warnings"] == [
        {"key": "failed_counties", "args": {"count": "1", "total": "2"}}
    ]
    assert result["files"] == {"topographic_vector": [file]}
    assert result["values"]["missing_counties"] == 1


def _check_live_output(
    label: str,
    result: HandlerOutput,
    output_dir: Path,
    isolated_cwd: Path,
    start_s: float,
) -> None:
    paths = [path for files in result["files"].values() for path in files]
    assert paths
    for kind, files in result["files"].items():
        for path in files:
            assert path.resolve().is_relative_to(output_dir.resolve())
            validate_file(kind, path)
    assert list(isolated_cwd.iterdir()) == []
    print(
        f"{label}: {time.perf_counter() - start_s:.1f}s, "
        f"{len(paths)} files, sizes={[path.stat().st_size for path in paths]} bytes"
    )


@pytest.mark.live
def test_download_dem_sheet_live_small_5m(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("kartograf")
    output_dir = tmp_path / "output"
    isolated_cwd = tmp_path / "cwd"
    output_dir.mkdir()
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    start_s = time.perf_counter()
    result = download_dem_sheet(
        {
            "area": {"type": "sheet", "code": "N-34-130-D-d-3-1"},
            "resolution": "5m",
            "vertical_crs": "evrf2007",
        },
        {},
        output_dir,
    )

    _check_live_output("sheet 5m", result, output_dir, isolated_cwd, start_s)


@pytest.mark.live
def test_download_sheet_hierarchy_live_small_5m(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("kartograf")
    output_dir = tmp_path / "output"
    isolated_cwd = tmp_path / "cwd"
    output_dir.mkdir()
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    start_s = time.perf_counter()
    result = download_sheet_hierarchy(
        {
            "product": "dem",
            "area": {"type": "sheet", "code": "N-34-130-D-d-3"},
            "target_scale": "scale_10000",
            "resolution": "5m",
            "vertical_crs": "evrf2007",
        },
        {},
        output_dir,
    )

    _check_live_output("hierarchy 5m", result, output_dir, isolated_cwd, start_s)


@pytest.mark.live
def test_download_elevation_cutout_live_small_bbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("kartograf")
    output_dir = tmp_path / "output"
    isolated_cwd = tmp_path / "cwd"
    output_dir.mkdir()
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    start_s = time.perf_counter()
    result = download_elevation_cutout(
        {
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
        },
        {},
        output_dir,
    )

    _check_live_output("WCS cutout", result, output_dir, isolated_cwd, start_s)


@pytest.mark.live
def test_download_bdot10k_live_small_sopot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("kartograf")
    output_dir = tmp_path / "output"
    isolated_cwd = tmp_path / "cwd"
    output_dir.mkdir()
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    start_s = time.perf_counter()
    result = download_bdot10k(
        {"area": {"type": "teryt", "code": "2264"}, "format": "gpkg"},
        {},
        output_dir,
    )

    _check_live_output("BDOT10k Sopot", result, output_dir, isolated_cwd, start_s)


@pytest.mark.live
def test_download_bdot10k_live_small_sopot_shp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("kartograf")
    output_dir = tmp_path / "output"
    isolated_cwd = tmp_path / "cwd"
    output_dir.mkdir()
    isolated_cwd.mkdir()
    monkeypatch.chdir(isolated_cwd)

    start_s = time.perf_counter()
    result = download_bdot10k(
        {"area": {"type": "teryt", "code": "2264"}, "format": "shp"},
        {},
        output_dir,
    )

    _check_live_output("BDOT10k Sopot SHP", result, output_dir, isolated_cwd, start_s)
    files = result["files"]["topographic_vector"]
    assert all(path.with_suffix(".dbf").is_file() for path in files)
    assert all(path.with_suffix(".shx").is_file() for path in files)

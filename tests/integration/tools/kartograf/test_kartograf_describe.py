"""What Retman reports of Kartograf's data commands, from recorded documents."""

import json
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from kartograf_support import (
    BBOX,
    SHEET,
    TERYT,
    OfflineClient,
    context,
    document,
    materialise,
    operations,
    settings,
)

from retman.adapters.catalog import ToolError, run_calls
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.testing import FakeToolClient
from retman.tools.kartograf.client import run_from_document

SHEETS_OF_FOUR = {"type": "sheet", "code": "N-34-139-C-a-3"}
NMT = {"resolution": "1m", "vertical_crs": "evrf2007"}
SHAPEFILES = {"format": "shp"}


def run(
    tmp_path: Path, name: str, params: dict[str, Any], command: str, doc: dict[str, Any]
) -> HandlerOutput:
    """Run the operation's calls against a recorded document, as ``execute`` does."""
    materialise(doc)
    client = OfflineClient(settings(tmp_path), runs={command: doc})
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(name, client, root=tmp_path, output_dir=output_dir)
    return run_calls(operations()[name], params, {}, output_dir, ctx)


def keys(output: HandlerOutput) -> list[str]:
    return [warning["key"] for warning in output["warnings"]]


def test_partial_sheets_are_counted_from_the_request_not_read_from_the_document(
    tmp_path: Path,
) -> None:
    """Kartograf calls a run with 1 of 4 sheets ``ok``; the count is computed."""
    doc = document("sheets_one_of_four", tmp_path / "store")

    output = run(
        tmp_path,
        "download_dem_sheet",
        {"area": SHEETS_OF_FOUR, **NMT},
        "elevation download",
        doc,
    )

    assert output["values"]["sheet_count"] == 1
    assert output["values"]["expected_sheets"] == 4
    assert output["values"]["data_dates"] == ["2025-10-21"]
    assert {"key": "sheets_missing", "args": {"count": "1", "total": "4"}} in output[
        "warnings"
    ]
    # Kartograf's own notices stay, under the codes Retman words itself
    assert {"incomplete_campaign", "no_coverage_some"} <= set(keys(output))
    assert list(output["files"]) == ["dem"]
    assert output["files"]["dem"][0].name == "N-34-139-C-a-3-1.asc"


def test_a_complete_single_sheet_has_nothing_missing(tmp_path: Path) -> None:
    doc = document("sheets_one_delivered", tmp_path / "store")
    area = {"type": "sheet", "code": "N-34-139-C-a-3-1"}

    output = run(
        tmp_path, "download_dem_sheet", {"area": area, **NMT}, "elevation download", doc
    )

    assert "sheets_missing" not in keys(output)
    assert output["values"]["expected_sheets"] == 1


def test_a_failed_download_next_to_delivered_sheets_is_a_warning_with_its_detail(
    tmp_path: Path,
) -> None:
    doc = document("sheets_hard_failure", tmp_path / "store")

    output = run(
        tmp_path,
        "download_dem_sheet",
        {"area": SHEETS_OF_FOUR, **NMT},
        "elevation download",
        doc,
    )

    failure = next(w for w in output["warnings"] if w["key"] == "sheets_failed")
    assert "N-34-139-C-a-3-2" in failure["args"]["detail"]
    assert output["values"]["sheet_count"] == 1
    # The run is recorded as partial: the delivered sheet is the result
    assert output["tool"]["calls"][0]["status"] == "partial"


def test_a_request_without_any_delivered_file_is_an_error_with_kartografs_code(
    tmp_path: Path,
) -> None:
    doc = document("sheets_none_delivered", tmp_path / "store")

    with pytest.raises(ToolError) as caught:
        run(
            tmp_path,
            "download_dem_sheet",
            {"area": {"type": "sheet", "code": "N-34-139-C-a-4"}, **NMT},
            "elevation download",
            doc,
        )

    assert caught.value.tool_code == "no_coverage"


def test_the_tools_document_is_saved_whole_and_referenced_with_its_checksum(
    tmp_path: Path,
) -> None:
    doc = document("sheets_one_of_four", tmp_path / "store")

    output = run(
        tmp_path,
        "download_dem_sheet",
        {"area": SHEETS_OF_FOUR, **NMT},
        "elevation download",
        doc,
    )

    audit = output["tool"]["calls"][0]
    saved = json.loads(
        (tmp_path / "result" / audit["document_file"]).read_text("utf-8")
    )
    assert audit["command"] == "elevation download"
    assert audit["schema"] == "kartograf-download/1"
    assert audit["options"]["resolution"] == "1m"
    assert saved["schema"] == "kartograf-download/1"
    assert audit["files"][0]["version"] == "2025-10-21_84183"


def test_nmt_100m_province_files_are_not_sheets(tmp_path: Path) -> None:
    doc = document("sheets_one_delivered", tmp_path / "store")
    doc["files"][0]["file"]["path"] = str(
        tmp_path / "store" / "nmt" / "100m" / "22.zip"
    )

    output = run(
        tmp_path,
        "download_dem_sheet",
        {"area": SHEET, "resolution": "100m"},
        "elevation download",
        doc,
    )

    assert list(output["files"]) == ["dem_archive"]
    assert "sheet_count" not in output["values"]
    assert "sheets_missing" not in keys(output)


def test_a_result_survives_a_count_that_cannot_be_made(tmp_path: Path) -> None:
    """The delivered files are the result even when the offline lookup fails."""
    doc = document("sheets_one_of_four", tmp_path / "store")
    materialise(doc)
    call_run = run_from_document
    client = FakeToolClient(
        runs={"elevation download": lambda call: call_run(call, doc)}
    )
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    ctx = context("download_dem_sheet", client, root=tmp_path, output_dir=output_dir)

    output = run_calls(
        operations()["download_dem_sheet"],
        {"area": SHEETS_OF_FOUR, **NMT},
        {},
        output_dir,
        ctx,
    )

    assert output["values"]["expected_sheets"] is None
    assert "sheets_missing" not in keys(output)
    assert output["values"]["sheet_count"] == 1


def _cutout(tmp_path: Path, extra: dict[str, Any] | None) -> HandlerOutput:
    doc = document("cutout_all_nodata", tmp_path / "store")
    if extra is not None:
        path = Path(doc["files"][0]["file"]["path"])
        path.parent.mkdir(parents=True)
        sidecar = {"schema": "kartograf-meta/1", "extra": extra}
        Path(f"{path}.meta.json").write_text(json.dumps(sidecar), encoding="utf-8")
    params = {
        "product": "dem",
        "area": BBOX,
        "target_crs": "epsg_2180",
        "vertical_crs": "evrf2007",
    }
    return run(tmp_path, "download_elevation_cutout", params, "elevation download", doc)


def test_cutout_reports_the_mask_facts_that_only_its_sidecar_has(
    tmp_path: Path,
) -> None:
    output = _cutout(tmp_path, {"mask": {"masked_pixels": 99}, "all_nodata": True})

    assert output["values"]["masked_pixels"] == 99
    assert output["values"]["all_nodata"] is True
    # The notice of the same fact is not repeated next to the sidecar's
    assert keys(output) == ["all_nodata", "masked_pixels"]
    assert list(output["files"]) == ["dem"]


def test_cutout_without_a_readable_sidecar_still_warns_from_the_notice(
    tmp_path: Path,
) -> None:
    output = _cutout(tmp_path, None)

    assert output["values"]["masked_pixels"] == 0
    assert keys(output) == ["all_nodata"]


def test_bdot10k_geopackages_stay_in_the_store_and_a_failed_county_is_a_warning(
    tmp_path: Path,
) -> None:
    doc = document("bdot10k_gpkg_one_county_failed", tmp_path / "store")

    output = run(
        tmp_path,
        "download_bdot10k",
        {"area": TERYT, "format": "gpkg"},
        "landcover download",
        doc,
    )

    assert [path.name for path in output["files"]["topographic_vector"]] == [
        "0208.gpkg",
        "0261.gpkg",
    ]
    assert output["values"]["county_count"] == 2
    assert output["values"]["missing_counties"] == 1
    assert output["warnings"] == [
        {
            "key": "failed_counties",
            "args": {"count": "1", "total": "3", "units": "0224"},
        }
    ]


def _county_zip(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


SHP = (9994).to_bytes(4, "big") + bytes(20)
LAYERS = {"roads.shp": SHP, "roads.dbf": b"dbf", "roads.shx": b"shx"}


def _shapefile_run(tmp_path: Path, archives: dict[str, Any]) -> HandlerOutput:
    """Run BDOT10k as SHP with ZIPs of the given content per county (None: absent)."""
    doc = document("bdot10k_shp_one_county_failed", tmp_path / "store")
    for item in doc["files"]:
        path = Path(item["file"]["path"])
        content = archives[item["unit"]]
        if isinstance(content, bytes):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        else:
            _county_zip(path, content)
    client = OfflineClient(settings(tmp_path), runs={"landcover download": doc})
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context("download_bdot10k", client, root=tmp_path, output_dir=output_dir)
    return run_calls(
        operations()["download_bdot10k"],
        {"area": TERYT, **SHAPEFILES},
        {},
        output_dir,
        ctx,
    )


def test_bdot10k_shapefiles_are_unpacked_into_the_result_not_the_store(
    tmp_path: Path,
) -> None:
    output = _shapefile_run(tmp_path, {"0208": LAYERS, "0261": LAYERS})

    files = output["files"]["topographic_vector"]
    assert [path.relative_to(tmp_path / "result").as_posix() for path in files] == [
        "bdot10k/0208/roads.shp",
        "bdot10k/0261/roads.shp",
    ]
    for path in files:
        validate_file("topographic_vector", path)
        assert path.with_suffix(".dbf").is_file() and path.with_suffix(".shx").is_file()
    assert not any((tmp_path / "store").rglob("*.shp"))


def test_a_corrupt_or_unsafe_county_archive_is_a_failed_county_not_a_failed_run(
    tmp_path: Path,
) -> None:
    output = _shapefile_run(
        tmp_path, {"0208": LAYERS, "0261": {"../../escaped.shp": SHP}}
    )

    assert [path.parent.name for path in output["files"]["topographic_vector"]] == [
        "0208"
    ]
    assert output["warnings"][0]["args"] == {
        "count": "2",
        "total": "3",
        "units": "0224, 0261",
    }
    assert not (tmp_path / "escaped.shp").exists()
    assert not (tmp_path / "result" / "bdot10k" / "0261").exists()


def test_when_every_county_fails_the_run_fails_with_one_error(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as caught:
        _shapefile_run(tmp_path, {"0208": b"not a zip", "0261": {"readme.txt": b"x"}})

    assert caught.value.tool_code == "all_counties_failed"


def test_a_single_failing_county_is_reported_with_its_own_cause(
    tmp_path: Path,
) -> None:
    doc = document("bdot10k_shp_one_county_failed", tmp_path / "store")
    doc["files"] = doc["files"][:1]
    doc["failed"] = []
    path = Path(doc["files"][0]["file"]["path"])
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a zip")
    client = OfflineClient(settings(tmp_path), runs={"landcover download": doc})
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    ctx = context("download_bdot10k", client, root=tmp_path, output_dir=output_dir)

    with pytest.raises(ToolError) as caught:
        run_calls(
            operations()["download_bdot10k"],
            {"area": TERYT, **SHAPEFILES},
            {},
            output_dir,
            ctx,
        )

    assert caught.value.tool_code == "invalid_archive"

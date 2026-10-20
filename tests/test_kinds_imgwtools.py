"""Kind validators accept the files IMGWTools really writes (offline fixture store).

The validators of ``retman.kinds`` encode the file formats of IMGWTools 3.x; this
test runs the tool's own exporters on its packaged offline store, so a change of
a format in the tool shows here and not after a user confirmed a download.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from retman.kinds import validate_file

imgwtools = pytest.importorskip("imgwtools")
pytest.importorskip("pyarrow")
from imgwtools.testing import build_fixture_store  # noqa: E402


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("imgw") / "store"
    build_fixture_store(root, variant="complete_pl_cz")
    return root


def _run(command: str, root: Path, **options: Any) -> Any:
    return imgwtools.run_command(command, options={"root": str(root), **options})


@pytest.mark.parametrize(
    ("kind", "dataset", "station"),
    [
        ("hydro_series", "pl.imgw.hydro_daily", "149190310"),
        ("meteo_series", "pl.imgw.meteo_precip_daily", "123750000"),
        ("hydro_series", "cz.chmi.hydro_daily", "0-203-1-900001"),
        ("meteo_series", "cz.chmi.meteo_daily", "0-203-0-90001"),
    ],
)
def test_series_export_files_are_valid_series(
    store: Path, tmp_path: Path, kind: str, dataset: str, station: str
) -> None:
    target = tmp_path / "series.csv"

    _run("series export", store, dataset=dataset, station=station, path=str(target))

    validate_file(kind, target)


def test_archive_export_files_are_valid_archive_records(
    store: Path, tmp_path: Path
) -> None:
    entries = _run("store scan", store, kind="archive").to_json()["result"]["items"]
    version = next(
        entry["version"] for entry in entries if entry["slot"].endswith("codz_2024.zip")
    )

    for suffix, format_name in ((".csv", "csv"), (".jsonl", "jsonl")):
        target = tmp_path / f"records{suffix}"
        _run(
            "store export", store, version=version, format=format_name, path=str(target)
        )
        validate_file("archive_records", target)


def test_documents_are_valid_plan_and_report(store: Path, tmp_path: Path) -> None:
    plan = imgwtools.StorePlan("imgw-plan/1", store, datetime.now(UTC), (), {})
    plan_file = plan.to_json(tmp_path / "plan.json")
    envelope = _run("series summary", store, dataset="pl.imgw.hydro_daily")
    report_file = tmp_path / "coverage.json"
    report_file.write_text(
        json.dumps(envelope.to_json(), default=str), encoding="utf-8"
    )

    validate_file("imgw_plan", plan_file)
    validate_file("imgw_report", report_file)

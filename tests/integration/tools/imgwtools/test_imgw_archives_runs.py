"""Archive operations: plan-time review, no network before consent, results."""

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from imgw_ops_support import TEXTS, YEARS, context, execute, operations, station
from imgw_store_files import write_damaged_marker, write_layout, write_server_state
from imgw_support import (
    PlanStatus,
    fixture_store,
    real_client,
    settings_for,
    synthetic_run,
)
from imgwtools import CommandResult, FileResult, archive_files
from imgwtools.store.types import (
    DownloadItem,
    DownloadReport,
    OperationResult,
    PlanItem,
    SeriesReport,
    StorePlan,
    SyncReport,
)

from retman.adapters.catalog import CatalogCall, PlanView, RunStatus, ToolRun
from retman.adapters.manifest_adapter import preview_operation, run_check
from retman.backends.base import Decision
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.testing import FakeDecisionBackend, FakeToolClient

NO_STORE = {"result": {"exists": False, "supported": False, "schema": None}}
READY = {"result": {"exists": True, "supported": True, "schema": "imgw-store/1"}}
SELECTION = {"dataset": "pl_meteo_precip_daily", "years": YEARS}


def preview(operation: str, params: dict[str, Any], client: Any, **kw: Any) -> Any:
    ctx = context(operation, PlanView(client), **kw)
    return preview_operation(operations()[operation], params, ctx, TEXTS)


def envelope(command: str, result: object, *, check: bool = False) -> dict[str, Any]:
    status: RunStatus = "ok"
    return CommandResult(command, check, status, result, ()).to_json()


def make_plan(root: Path, statuses: list[PlanStatus]) -> StorePlan:
    """A real ``imgw-plan/1`` object over the first archives of hydro daily 2020."""
    archives = archive_files("pl.imgw.hydro_daily", years=[2020])
    errors = {"unverifiable": "not published", "check_failed": "HTTP error 500"}
    items = tuple(
        PlanItem(
            archive,
            status,
            None,
            None,
            None,
            None,
            1_000_000 * (number + 1) if status in ("newer", "missing") else None,
            errors.get(status),
        )
        for number, (archive, status) in enumerate(
            zip(archives, statuses, strict=False)
        )
    )
    moment = datetime(2026, 10, 19, 12, 30, tzinfo=UTC)
    return StorePlan("imgw-plan/1", root, moment, items, {"hydro_daily": "outdated"})


STATUSES: list[PlanStatus] = [
    "current",
    "newer",
    "missing",
    "unverifiable",
    "check_failed",
]


# --- plan-time review ---------------------------------------------------------------


def test_download_preview_lists_the_files_and_the_years_they_cover(
    tmp_path: Path,
) -> None:
    client = real_client(tmp_path, tmp_path / "no-store-needed")
    params = {
        "dataset": "pl_hydro_daily",
        "years": {"type": "years", "first": 2000, "last": 2020},
    }

    result = preview("download_hydro_archives", params, client)

    assert result.problems == []
    assert result.rows[0][1].startswith(
        "liczba plików: 252 (codz_2000_01.zip … codz_2020_12.zip)"
    )
    # IMGW numbers hydrological archives by the year the data end in
    assert "1999-11-01 – 2020-10-31 (lata hydrologiczne" in result.rows[1][1]


@pytest.mark.parametrize(
    ("operation", "params"),
    [
        ("check_imgw_archives", SELECTION),
        ("sync_imgw_store", SELECTION),
        ("sync_imgw_store_by_plan", {}),
        ("export_imgw_archive", {**SELECTION, "format": "csv"}),
        ("inspect_imgw_store", {}),
    ],
)
def test_a_store_that_is_not_there_blocks_the_plan_and_is_never_initialised(
    tmp_path: Path, operation: str, params: dict[str, Any]
) -> None:
    client = FakeToolClient(
        documents={"store info": NO_STORE, "store scan": {"result": {"items": []}}}
    )

    result = preview(operation, params, client, inputs={"plan": tmp_path / "plan.json"})

    # Nothing to answer again: the store is the user's decision (init_imgw_store)
    (problem,) = result.problems
    assert problem.params == () and "Utwórz magazyn IMGW" in problem.text
    assert {method for method, _ in client.calls} <= {"validate", "lookup"}
    assert client.network_calls == []


def test_series_need_pyarrow_so_sync_is_blocked_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "retman.tools.imgwtools.preview.tool_installed", lambda _: False
    )

    result = preview(
        "sync_imgw_store", SELECTION, FakeToolClient(documents={"store info": READY})
    )
    listing: dict[str, Any] = {"result": {"items": []}}
    check = preview(
        "check_imgw_archives",
        SELECTION,
        FakeToolClient(documents={"store info": READY, "datasets files": listing}),
    )

    assert "pyarrow" in result.problems[0].text
    assert check.problems == []


def test_export_preview_counts_what_the_store_holds(tmp_path: Path) -> None:
    client = real_client(tmp_path)
    held = {
        "dataset": "pl_meteo_precip_daily",
        "years": {"type": "years", "first": 1995, "last": 1995},
        "format": "csv",
    }
    absent = {
        **held,
        "dataset": "pl_hydro_daily",
        "years": {"type": "years", "first": 2000, "last": 2001},
    }

    found = preview("export_imgw_archive", held, client)
    missing = preview("export_imgw_archive", absent, client)

    assert "w magazynie: 1 z 1 plików archiwów zbioru (format csv)" in found.rows[1][1]
    # The user chose a dataset and years the store lacks: both are asked again
    assert [problem.params for problem in missing.problems] == [("dataset", "years")]
    assert "pl.imgw.hydro_daily z lat 2000–2001" in missing.problems[0].text


def test_sync_by_plan_shows_the_plan_and_refuses_one_of_another_store(
    tmp_path: Path,
) -> None:
    store = fixture_store()
    client = real_client(tmp_path, store)
    mine, other = tmp_path / "mine.json", tmp_path / "other.json"
    make_plan(store, STATUSES).to_json(mine)
    make_plan(tmp_path / "elsewhere", STATUSES).to_json(other)

    where = {"settings": settings_for(tmp_path, store), "inputs": {"plan": mine}}
    shown = preview("sync_imgw_store_by_plan", {}, client, **where)
    where["inputs"] = {"plan": other}
    refused = preview("sync_imgw_store_by_plan", {}, client, **where)

    assert shown.problems == []
    assert shown.rows[1][1] == (
        "plików: 5; do pobrania: 2 (5.0 MB); aktualnych: 1; "
        "sprawdzony 2026-10-19 12:30 UTC"
    )
    assert "innego magazynu" in refused.problems[0].text


def test_init_preview_says_what_will_happen_and_refuses_foreign_data(
    tmp_path: Path,
) -> None:
    def state(folder: Path) -> Any:
        settings = {"store_dir": str(folder)}
        return preview("init_imgw_store", {}, FakeToolClient(), settings=settings)

    empty, foreign, marked, unmarked, keys, damaged = (
        tmp_path / "empty",
        tmp_path / "foreign",
        tmp_path / "marked",
        tmp_path / "unmarked",
        tmp_path / "keys",
        tmp_path / "damaged",
    )
    for folder in (empty, foreign, marked, unmarked, keys, damaged):
        folder.mkdir()
    (foreign / "data.txt").write_text("x")
    # A store the tool built, not a marker written by hand (DEV-10.6)
    shutil.copytree(fixture_store(), marked, dirs_exist_ok=True)
    write_layout(unmarked, "series")
    write_server_state(keys)
    write_damaged_marker(damaged)

    assert state(tmp_path / "new").rows[1][1].startswith("folder nie istnieje")
    assert state(empty).rows[1][1].startswith("pusty folder")
    assert state(marked).rows[1][1].startswith("magazyn już istnieje")
    assert state(unmarked).rows[1][1].startswith("folder ma układ magazynu")
    # The key file of the REST server is not store content: the tool takes the folder
    assert state(keys).rows[1][1].startswith("pusty folder")
    assert "nie jest magazynem IMGW" in state(foreign).problems[0].text
    # A marker the tool cannot read is a damaged store, not "other files"
    (problem,) = state(damaged).problems
    assert "imgw-store.json" in problem.text and "jest nieczytelny" in problem.text
    assert "nie jest magazynem IMGW" not in problem.text


# --- offline runs on the real tool ----------------------------------------------------


def test_export_runs_on_the_real_tool_and_reports_what_the_store_lacks(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    ctx = context(
        "export_imgw_archive",
        real_client(tmp_path),
        settings=settings_for(tmp_path),
        output_dir=out,
    )
    params = {
        "dataset": "pl_meteo_precip_daily",
        "years": {"type": "years", "first": 1995, "last": 1996},
        "format": "csv",
    }

    result = execute("export_imgw_archive", params, ctx)

    assert result.ok, result.error
    (path,) = result.files["archive_records"]
    assert path == out / "1995_o.csv" and path.read_text().startswith("station_code,")
    assert result.values["files"] == 1 and result.values["rows"] > 0
    # The store holds one of the two yearly archives: said, not hidden
    assert any("1 z 2" in warning for warning in result.warnings)
    assert any(
        warning.startswith("Źródłem pochodzenia danych") for warning in result.warnings
    )


def test_init_runs_on_the_real_tool_and_is_idempotent(tmp_path: Path) -> None:
    folder = tmp_path / "new-store"
    out = tmp_path / "out"
    out.mkdir()
    ctx = context(
        "init_imgw_store",
        real_client(tmp_path, folder),
        settings=settings_for(tmp_path, folder),
        output_dir=out,
    )

    first = execute("init_imgw_store", {}, ctx)
    second = execute("init_imgw_store", {}, ctx)

    assert first.ok and second.ok and first.values["store"] == str(folder)
    assert (
        json.loads((folder / "imgw-store.json").read_text())["schema"] == "imgw-store/1"
    )


def test_inspect_runs_on_the_real_tool_and_keeps_both_documents(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    ctx = context(
        "inspect_imgw_store",
        real_client(tmp_path),
        settings=settings_for(tmp_path),
        output_dir=out,
    )

    result = execute("inspect_imgw_store", {"kind": "catalog"}, ctx)

    assert result.ok, result.error
    assert [path.name for path in result.files["imgw_report"]] == [
        "store_info.json",
        "store_entries.json",
    ]
    assert result.values["supported"] is True
    assert result.values["entries_by_kind"] == {"catalog": 2}


# --- network operations: the tool's own result objects, no network -----------


def test_download_reports_files_size_and_what_the_server_does_not_publish(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    content = b"PK\x03\x04" + b"0" * 2000
    digest = hashlib.sha256(content).hexdigest()

    def download(call: CatalogCall) -> ToolRun:
        target = Path(str(call.options["output_dir"])) / "dane" / "codz.zip"
        target.parent.mkdir(parents=True)
        target.write_bytes(content)
        report = DownloadReport(
            "plain",
            out,
            None,
            (
                DownloadItem(
                    "archive:cz.chmi.hydro_daily:a",
                    "https://x/a",
                    "downloaded",
                    target,
                    None,
                    None,
                ),
                DownloadItem(
                    "archive:cz.chmi.hydro_daily:b",
                    "https://x/b",
                    "not_published",
                    None,
                    "not published",
                    None,
                ),
            ),
            (FileResult(target, len(content), digest, "written"),),
            False,
        )
        return synthetic_run("datasets download", report)

    client = FakeToolClient(runs={"datasets download": download})
    params = {
        "dataset": "cz_hydro_daily",
        "years": YEARS,
        "stations": [station("0-203-1-001000", "CHMI")],
    }

    result = execute(
        "download_hydro_archives",
        params,
        context("download_hydro_archives", client, output_dir=out),
    )

    assert result.ok, result.error
    assert result.files["imgw_archive"] == [out / "dane" / "codz.zip"]
    assert result.values["files"] == 1 and result.values["not_published"] == 1
    assert result.values["size"] == "2.0 kB"
    assert "Serwer nie publikuje 1 z 2 żądanych plików" in result.warnings[0]
    # The audit keeps the checksum the tool computed while it wrote the file
    assert result.tool is not None
    assert result.tool["calls"][0]["files"] == [
        {
            "path": str(out / "dane" / "codz.zip"),
            "sha256": digest,
            "version": None,
            "status": "written",
        }
    ]


def test_a_check_saves_the_tools_plan_and_counts_it(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    plan = make_plan(tmp_path / "store", STATUSES)

    def check(call: CatalogCall) -> ToolRun:
        plan.to_json(Path(str(call.options["plan"])))
        return synthetic_run("store check", plan)

    client = FakeToolClient(runs={"store check": check})
    params = {
        "dataset": "pl_hydro_daily",
        "years": {"type": "years", "first": 2020, "last": 2020},
    }

    result = execute(
        "check_imgw_archives",
        params,
        context("check_imgw_archives", client, output_dir=out),
    )

    assert result.ok, result.error
    assert result.files["imgw_plan"] == [out / "plan.json"]
    assert result.values["by_status"] == {
        "current": 1,
        "newer": 1,
        "missing": 1,
        "unverifiable": 1,
        "check_failed": 1,
    }
    assert (
        result.values["to_download"] == 2
        and result.values["bytes_to_download"] == 5_000_000
    )
    assert (result.values["unpublished"], result.values["size_unknown"]) == (1, 0)


def test_sync_reports_new_versions_and_series_and_by_plan_uses_the_saved_plan(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    version = store / "archives" / "v" / "codz.zip"
    version.parent.mkdir(parents=True)
    version.write_bytes(b"PK\x03\x04" + b"0" * 100)
    relative = version.relative_to(store)
    report = SyncReport(
        (
            OperationResult(
                "archive:pl.imgw.hydro_daily:2020/a.zip",
                "new",
                store / relative,
                None,
            ),
            OperationResult(
                "archive:pl.imgw.hydro_daily:2020/b.zip", "unchanged", None, None
            ),
            OperationResult(
                "archive:pl.imgw.hydro_daily:2020/c.zip",
                "stale_plan",
                None,
                "changed",
            ),
        ),
        (SeriesReport("new", store / "series" / "s.json", 3, (), ()),),
        False,
    )
    run = synthetic_run("store sync", report, status="partial")
    run = replace(run, status="partial", failed=())
    client = FakeToolClient(runs={"store sync": run})
    plan_file = tmp_path / "plan.json"
    plan_file.write_text("{}")
    settings = {"store_dir": str(store)}

    result = execute(
        "sync_imgw_store_by_plan",
        {},
        context(
            "sync_imgw_store_by_plan",
            client,
            settings=settings,
            output_dir=tmp_path,
            inputs={"plan": plan_file},
        ),
        inputs={"plan": plan_file},
    )

    assert result.ok, result.error
    assert client.calls[-1] == (
        "run",
        CatalogCall("store sync", {"plan": str(plan_file)}),
    )
    assert (result.values["new_versions"], result.values["new_series"]) == (1, 1)
    assert result.values["items"] == {"new": 1, "unchanged": 1, "stale_plan": 1}
    assert result.values["series"] == {"new": 1, "unchanged": 0, "failed": 0}
    assert result.values["bytes"] == 104
    assert [item["status"] for item in result.values["store_versions"]] == [
        "new",
        "new",
    ]


def test_a_failed_run_is_a_failed_result_not_a_success(tmp_path: Path) -> None:
    run = ToolRun(
        "store sync",
        "failed",
        document=envelope("store sync", {"items": [], "series": []}),
    )
    client = FakeToolClient(runs={"store sync": run})

    result = execute(
        "sync_imgw_store",
        SELECTION,
        context("sync_imgw_store", client, output_dir=tmp_path),
    )

    assert not result.ok and result.error and result.files == {}


def test_the_availability_check_asks_the_servers_and_changes_nothing() -> None:
    plan = make_plan(Path("/stores/imgw"), STATUSES)
    client = FakeToolClient(
        documents={"check:store sync": envelope("store sync", plan, check=True)}
    )
    operation = operations()["sync_imgw_store"]
    # While planning the client has no check at all: the capability is not there
    assert not hasattr(PlanView(client), "check")
    report = run_check(operation, SELECTION, context("sync_imgw_store", client), TEXTS)

    assert report.status == "partial"
    assert report.lines[0] == "Plików: 5; do pobrania: 2 (5.0 MB); już aktualnych: 1."
    assert any(
        "nie publikuje: 1" in line or "serwer nie publikuje: 1" in line
        for line in report.lines
    )
    assert [method for method, _ in client.calls if method != "validate"] == ["check"]


# --- the gate: nothing before confirmation ------------------------------------------


def make_app(tmp_path: Path, client: Any, rules: dict[str, str | Decision]) -> Retman:
    config = load_config(init_config(tmp_path / "config.toml"))
    config = replace(
        config, tools={**config.tools, "imgwtools": settings_for(tmp_path)}
    )
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    backend = FakeDecisionBackend(rules)
    return Retman(
        config, backend, project, operations=operations(), clients={"imgwtools": client}
    )


def test_nothing_reaches_the_network_before_the_user_confirms(tmp_path: Path) -> None:
    listing = real_client(tmp_path).lookup(
        CatalogCall(
            "datasets files", {"dataset": "pl.imgw.hydro_daily", "years": [2020]}
        )
    )
    client = FakeToolClient(documents={"datasets files": listing})
    rules: dict[str, str | Decision] = {
        "imgw_archives": "imgw_archives",
        "download_hydro_archives": "download_hydro_archives",
        "pl_hydro_daily": "pl_hydro_daily",
    }
    app = make_app(tmp_path, client, rules)

    plan = app.plan("Pobierz archiwa dobowych danych hydrologicznych z 2020")

    assert plan.questions == [] and plan.preview_rows
    assert client.network_calls == []
    app.execute(plan.confirm())
    assert [call.command for method, call in client.calls if method == "run"] == [
        "datasets download"
    ]

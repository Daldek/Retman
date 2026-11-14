"""Archive operations: plan-time review, no network before consent, results."""

import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from obserwator import CommandResult, FileResult, archive_files
from obserwator.store.types import (
    DownloadItem,
    DownloadReport,
    OperationResult,
    PlanItem,
    SeriesReport,
    StorePlan,
    SyncReport,
)
from obserwator_ops_support import (
    RAW_STORE,
    TEXTS,
    YEARS,
    context,
    execute,
    operations,
    station,
)
from obserwator_store_files import (
    write_damaged_marker,
    write_layout,
    write_server_state,
)
from obserwator_support import (
    PlanStatus,
    data_root,
    fixture_store,
    raw_root,
    real_client,
    settings_for,
    synthetic_run,
)

from retman.adapters.catalog import CatalogCall, PlanView, RunStatus, ToolRun
from retman.adapters.manifest_adapter import preview_operation, run_check
from retman.backends.base import Decision
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.testing import FakeDecisionBackend, FakeToolClient

NO_STORE = {"result": {"exists": False, "supported": False, "store_schema": None}}
SELECTION = {"dataset": "pl_meteo_precip_daily", "years": YEARS}


def ready(call: CatalogCall) -> dict[str, Any]:
    """``store info`` of a ready root: the raw or the data root, by the folder asked."""
    raw = call.options.get("root") == str(RAW_STORE)
    schema = "obserwator-store/1" if raw else "obserwator-data/1"
    return {"result": {"exists": True, "supported": True, "store_schema": schema}}


def preview(operation: str, params: dict[str, Any], client: Any, **kw: Any) -> Any:
    ctx = context(operation, PlanView(client), **kw)
    return preview_operation(operations()[operation], params, ctx, TEXTS)


def envelope(command: str, result: object, *, check: bool = False) -> dict[str, Any]:
    status: RunStatus = "ok"
    return CommandResult(command, check, status, result, ()).to_json()


def make_plan(root: Path, statuses: list[PlanStatus]) -> StorePlan:
    """A real ``obserwator-plan/1`` object over the first hydro daily 2020 archives."""
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
    return StorePlan(
        "obserwator-plan/1", root, moment, items, {"hydro_daily": "outdated"}
    )


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
    ("operation", "params", "settings"),
    [
        ("check_obserwator_archives", SELECTION, ["raw_store_dir"]),
        ("sync_obserwator_store", SELECTION, ["raw_store_dir", "store_dir"]),
        ("sync_obserwator_store_by_plan", {}, ["raw_store_dir"]),
        (
            "export_obserwator_archive",
            {**SELECTION, "format": "csv"},
            ["raw_store_dir"],
        ),
        ("inspect_obserwator_store", {}, ["store_dir", "raw_store_dir"]),
    ],
)
def test_a_store_that_is_not_there_blocks_the_plan_and_is_never_initialised(
    tmp_path: Path, operation: str, params: dict[str, Any], settings: list[str]
) -> None:
    client = FakeToolClient(
        documents={"store info": NO_STORE, "store scan": {"result": []}}
    )

    result = preview(operation, params, client, inputs={"plan": tmp_path / "plan.json"})

    # Nothing to answer again: the store is the user's decision (init_obserwator_store);
    # each root the operation needs is named by its own setting
    assert len(result.problems) == len(settings)
    for problem, setting in zip(result.problems, settings, strict=True):
        assert problem.params == () and "Utwórz magazyn Obserwatora" in problem.text
        assert f"(ustawienie {setting})" in problem.text
    assert {method for method, _ in client.calls} <= {"validate", "lookup"}
    assert client.network_calls == []


def test_series_need_pyarrow_so_sync_is_blocked_without_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "retman.tools.obserwator.preview.tool_installed", lambda _: False
    )

    result = preview(
        "sync_obserwator_store",
        SELECTION,
        FakeToolClient(documents={"store info": ready}),
    )
    listing: dict[str, Any] = {"result": []}
    check = preview(
        "check_obserwator_archives",
        SELECTION,
        FakeToolClient(documents={"store info": ready, "datasets files": listing}),
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

    settings = settings_for(tmp_path)
    found = preview("export_obserwator_archive", held, client, settings=settings)
    missing = preview("export_obserwator_archive", absent, client, settings=settings)

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
    make_plan(raw_root(store), STATUSES).to_json(mine)
    make_plan(tmp_path / "elsewhere", STATUSES).to_json(other)

    where = {"settings": settings_for(tmp_path, store), "inputs": {"plan": mine}}
    shown = preview("sync_obserwator_store_by_plan", {}, client, **where)
    where["inputs"] = {"plan": other}
    refused = preview("sync_obserwator_store_by_plan", {}, client, **where)

    assert shown.problems == []
    assert shown.rows[1][1] == (
        "plików: 5; do pobrania: 2 (5.0 MB); aktualnych: 1; "
        "sprawdzony 2026-10-19 12:30 UTC"
    )
    assert "innego magazynu" in refused.problems[0].text


def test_init_preview_says_what_will_happen_and_refuses_foreign_data(
    tmp_path: Path,
) -> None:
    def state(folder: Path, kind: str = "data") -> Any:
        # The root under test in its setting, the other one a folder not yet created
        other = str(tmp_path / "other-new")
        settings = (
            {"store_dir": str(folder), "raw_store_dir": other}
            if kind == "data"
            else {"store_dir": other, "raw_store_dir": str(folder)}
        )
        return preview("init_obserwator_store", {}, FakeToolClient(), settings=settings)

    def row(folder: Path, kind: str = "data") -> str:
        # The raw root is shown first, then the data root: a root row, then its state
        text: str = state(folder, kind).rows[3 if kind == "data" else 1][1]
        return text

    folders = (
        "empty",
        "foreign",
        "marked",
        "marked_raw",
        "unmarked",
        "unmarked_raw",
        "keys",
        "damaged",
    )
    for name in folders:
        (tmp_path / name).mkdir()
    empty, foreign, marked, marked_raw, unmarked, unmarked_raw, keys, damaged = (
        tmp_path / name for name in folders
    )
    (foreign / "data.txt").write_text("x")
    # Roots the tool built, not markers written by hand (DEV-10.6)
    shutil.copytree(data_root(fixture_store()), marked, dirs_exist_ok=True)
    shutil.copytree(raw_root(fixture_store()), marked_raw, dirs_exist_ok=True)
    write_layout(unmarked, "series")
    write_layout(unmarked_raw, "archives")
    write_server_state(keys)
    write_damaged_marker(damaged)

    assert row(tmp_path / "new").startswith("folder nie istnieje")
    assert row(empty).startswith("pusty folder")
    assert row(marked).startswith("magazyn już istnieje")
    assert row(marked_raw, "raw").startswith("magazyn już istnieje")
    assert row(unmarked).startswith("folder ma układ magazynu")
    assert row(unmarked_raw, "raw").startswith("folder ma układ magazynu")
    # The key file of the REST server is not store content: the tool takes the folder
    assert row(keys).startswith("pusty folder")
    (problem,) = state(foreign).problems
    assert "zawiera inne pliki" in problem.text and "store_dir" in problem.text
    # A marker the tool cannot read is a damaged root, not "other files"
    (problem,) = state(damaged, "raw").problems
    assert (
        "obserwator-store.json" in problem.text and "jest nieczytelny" in problem.text
    )
    assert "zawiera inne pliki" not in problem.text
    # The raw root named as the data root: never initialised as a second kind
    (problem,) = state(marked_raw).problems
    assert "oczekiwany obserwator-data.json" in problem.text
    assert "ustawienie store_dir" in problem.text


# --- offline runs on the real tool ----------------------------------------------------


def test_export_runs_on_the_real_tool_and_reports_what_the_store_lacks(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    ctx = context(
        "export_obserwator_archive",
        real_client(tmp_path),
        settings=settings_for(tmp_path),
        output_dir=out,
    )
    params = {
        "dataset": "pl_meteo_precip_daily",
        "years": {"type": "years", "first": 1995, "last": 1996},
        "format": "csv",
    }

    result = execute("export_obserwator_archive", params, ctx)

    assert result.ok, result.error
    (path,) = result.files["archive_records"]
    assert path == out / "1995_o.csv" and path.read_text(encoding="utf-8").startswith(
        "station_code,"
    )
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
        "init_obserwator_store",
        real_client(tmp_path, folder),
        settings=settings_for(tmp_path, folder),
        output_dir=out,
    )

    first = execute("init_obserwator_store", {}, ctx)
    second = execute("init_obserwator_store", {}, ctx)

    assert first.ok and second.ok
    assert (first.values["store"], first.values["raw_store"]) == (
        str(data_root(folder)),
        str(raw_root(folder)),
    )
    for root, marker, schema in (
        (raw_root(folder), "obserwator-store.json", "obserwator-store/1"),
        (data_root(folder), "obserwator-data.json", "obserwator-data/1"),
    ):
        written = json.loads((root / marker).read_text(encoding="utf-8"))
        assert written["schema"] == schema
    assert (first.values["raw_schema"], first.values["schema"]) == (
        "obserwator-store/1",
        "obserwator-data/1",
    )


def test_inspect_runs_on_the_real_tool_and_keeps_both_documents(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    ctx = context(
        "inspect_obserwator_store",
        real_client(tmp_path),
        settings=settings_for(tmp_path),
        output_dir=out,
    )

    result = execute("inspect_obserwator_store", {"kind": "catalog"}, ctx)

    assert result.ok, result.error
    assert [path.name for path in result.files["obserwator_report"]] == [
        "store_info.json",
        "store_entries.json",
    ]
    assert result.values["supported"] is True
    assert result.values["entries_by_kind"] == {"catalog": 2}


# --- network operations: the tool's own result objects, no network -----------


def test_download_reports_files_size_and_what_the_server_does_not_publish(
    tmp_path: Path,
) -> None:
    from obserwator.attribution import attribution, provider_origin
    from obserwator.output import write_attribution

    out = tmp_path / "out"
    out.mkdir()
    content = b"PK\x03\x04" + b"0" * 2000
    digest = hashlib.sha256(content).hexdigest()

    def download(call: CatalogCall) -> ToolRun:
        target = Path(str(call.options["output_dir"])) / "dane" / "codz.zip"
        target.parent.mkdir(parents=True)
        target.write_bytes(content)
        # The tool writes the providers' lines beside the archives and lists them
        lines = attribution(provider_origin("CHMI"), processed=False)
        noted = write_attribution(out, lines)
        assert noted is not None
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
            (FileResult(target, len(content), digest, "written"), noted),
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
    assert result.files["obserwator_archive"] == [out / "dane" / "codz.zip"]
    # ATTRIBUTION.txt is a file of its own kind, neither counted nor sized as an archive
    assert result.files["provider_attribution"] == [out / "ATTRIBUTION.txt"]
    assert result.values["files"] == 1 and result.values["not_published"] == 1
    assert result.values["size"] == "2.0 kB"
    assert result.summary is not None and "plików: 1 (2.0 kB)" in result.summary
    assert "Serwer nie publikuje 1 z 2 żądanych plików" in result.warnings[0]
    # The audit keeps the checksum the tool computed while it wrote the file
    assert result.tool is not None
    assert result.tool["calls"][0]["files"][0] == {
        "path": str(out / "dane" / "codz.zip"),
        "sha256": digest,
        "version": None,
        "status": "written",
    }


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
        "check_obserwator_archives",
        params,
        context("check_obserwator_archives", client, output_dir=out),
    )

    assert result.ok, result.error
    assert result.files["obserwator_plan"] == [out / "plan.json"]
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
    version = raw_root(store) / "archives" / "v" / "codz.zip"
    version.parent.mkdir(parents=True)
    version.write_bytes(b"PK\x03\x04" + b"0" * 100)
    report = SyncReport(
        (
            OperationResult(
                "archive:pl.imgw.hydro_daily:2020/a.zip", "new", version, None
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
        False,
    )
    run = synthetic_run("store sync", report, status="partial")
    run = replace(run, status="partial", failed=())
    series = data_root(store) / "series" / "s.json"
    built = synthetic_run(
        "series build", SeriesReport("new", series, 3, (version,), ())
    )
    client = FakeToolClient(runs={"store sync": run, "series build": built})
    plan_file = tmp_path / "plan.json"
    plan_file.write_text("{}")
    settings = settings_for(tmp_path, store)

    by_plan = execute(
        "sync_obserwator_store_by_plan",
        {},
        context(
            "sync_obserwator_store_by_plan",
            client,
            settings=settings,
            output_dir=tmp_path,
            inputs={"plan": plan_file},
        ),
        inputs={"plan": plan_file},
    )
    plan_calls = [call for method, call in client.calls if method == "run"]
    synced = execute(
        "sync_obserwator_store",
        {"dataset": "pl_hydro_daily", "years": YEARS},
        context(
            "sync_obserwator_store", client, settings=settings, output_dir=tmp_path
        ),
    )

    assert by_plan.ok and synced.ok, (by_plan.error, synced.error)
    assert plan_calls == [CatalogCall("store sync", {"plan": str(plan_file)})]
    # A sync by plan writes archives only; the series is built after a selection
    assert by_plan.values["items"] == {"new": 1, "unchanged": 1, "stale_plan": 1}
    assert (by_plan.values["new_versions"], by_plan.values["new_series"]) == (1, 0)
    assert by_plan.values["series"] == {"new": 0, "unchanged": 0, "failed": 0}
    assert by_plan.values["bytes"] == 104
    assert (synced.values["new_versions"], synced.values["new_series"]) == (1, 1)
    assert synced.values["series"] == {"new": 1, "unchanged": 0, "failed": 0}
    assert [
        (item["slot"], item["status"]) for item in synced.values["store_versions"]
    ] == [("archive:pl.imgw.hydro_daily:2020/a.zip", "new"), ("series", "new")]


def test_a_failed_run_is_a_failed_result_not_a_success(tmp_path: Path) -> None:
    run = ToolRun(
        "store sync",
        "failed",
        document=envelope("store sync", {"items": [], "series": []}),
    )
    client = FakeToolClient(runs={"store sync": run})

    result = execute(
        "sync_obserwator_store",
        SELECTION,
        context("sync_obserwator_store", client, output_dir=tmp_path),
    )

    assert not result.ok and result.error and result.files == {}


def test_the_availability_check_asks_the_servers_and_changes_nothing() -> None:
    plan = make_plan(Path("/stores/obserwator"), STATUSES)
    client = FakeToolClient(
        documents={"check:store sync": envelope("store sync", plan, check=True)}
    )
    operation = operations()["sync_obserwator_store"]
    # While planning the client has no check at all: the capability is not there
    assert not hasattr(PlanView(client), "check")
    report = run_check(
        operation, SELECTION, context("sync_obserwator_store", client), TEXTS
    )

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
        config, tools={**config.tools, "obserwator": settings_for(tmp_path)}
    )
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    backend = FakeDecisionBackend(rules)
    return Retman(
        config,
        backend,
        project,
        operations=operations(),
        clients={"obserwator": client},
    )


def test_nothing_reaches_the_network_before_the_user_confirms(tmp_path: Path) -> None:
    listing = real_client(tmp_path).lookup(
        CatalogCall(
            "datasets files", {"dataset": "pl.imgw.hydro_daily", "years": [2020]}
        )
    )
    client = FakeToolClient(documents={"datasets files": listing})
    rules: dict[str, str | Decision] = {
        "obserwator_archives": "obserwator_archives",
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

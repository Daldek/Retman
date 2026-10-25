"""Project operations: plan-time review, no silent store, results on the real tool."""

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from imgw_ops_support import TEXTS, YEARS, context, execute, operations, station
from imgw_store_files import write_layout, write_server_state
from imgw_support import (
    fixture_store,
    isolate_environment,
    real_client,
    settings_for,
    synthetic_run,
)
from imgwtools import CommandResult
from imgwtools.store.types import (
    OperationResult,
    PlanAction,
    ProjectReport,
    StorePlan,
)

from retman.adapters.catalog import CatalogCall, PlanView, ToolRun
from retman.adapters.manifest_adapter import preview_operation, run_check
from retman.backends.base import Decision
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.exceptions import RetmanError
from retman.testing import FakeDecisionBackend, FakeToolClient

NO_STORE = {"result": {"exists": False, "supported": False, "schema": None}}
READY = {"result": {"exists": True, "supported": True, "schema": "imgw-store/1"}}
SERIES = {
    "task": "series",
    "task_name": "przeplywy_raby",
    "dataset": "pl_hydro_daily",
    "selection": "stations",
    "stations": [station("149190310")],
    "period": YEARS,
    "year_type": "hydrological",
}
PMAXTP = {
    "task": "pmaxtp",
    "task_name": "pmaxtp_waw",
    "point": {"type": "point", "latitude": 52.23, "longitude": 21.01},
    "method": "pot",
}


def write_manifest(project: Path, store: Path, tasks: dict[str, bool]) -> None:
    """A manifest by hand (the previews only read the names, commands and pins)."""
    entries: list[dict[str, Any]] = [
        {
            "name": name,
            "command": "series select",
            "files": [],
            "options": {},
            "pinned_at": "2026-10-19T10:00:00Z" if pinned else None,
        }
        for name, pinned in tasks.items()
    ]
    document = {"schema": "imgw-project/1", "store_dir": str(store), "tasks": entries}
    (project / "imgw-project.json").write_text(json.dumps(document))


def preview(operation: str, params: dict[str, Any], client: Any, **kw: Any) -> Any:
    ctx = context(operation, PlanView(client), **kw)
    return preview_operation(operations()[operation], params, ctx, TEXTS)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    folder = tmp_path / "project"
    folder.mkdir()
    return folder


def on_tool(
    tmp_path: Path, project: Path, operation: str, params: dict[str, Any]
) -> Any:
    """Run an operation on the real tool over the fixture store (offline commands)."""
    store = fixture_store()
    out = tmp_path / f"out-{len(list(tmp_path.glob('out-*')))}"
    out.mkdir()
    ctx = context(
        operation,
        real_client(tmp_path, store),
        settings=settings_for(tmp_path, store),
        project_dir=project,
        output_dir=out,
    )
    return execute(operation, params, ctx)


# --- the whole life of a project on the real tool ------------------------------


def test_a_project_is_created_filled_verified_moved_and_emptied(
    tmp_path: Path, project: Path
) -> None:
    created = on_tool(tmp_path, project, "init_imgw_project", {})
    first = on_tool(tmp_path, project, "add_imgw_project_task", SERIES)
    second = on_tool(tmp_path, project, "add_imgw_project_task", PMAXTP)
    status = on_tool(tmp_path, project, "verify_imgw_project", {"depth": "status"})
    verified = on_tool(tmp_path, project, "verify_imgw_project", {"depth": "verify"})
    moved = on_tool(tmp_path, project, "set_imgw_project_store", {})
    removed = on_tool(
        tmp_path, project, "remove_imgw_project_task", {"task_name": "pmaxtp_waw"}
    )

    for result in (created, first, second, status, verified, moved, removed):
        assert result.ok, result.error
    manifest = json.loads((project / "imgw-project.json").read_text())
    assert [task["name"] for task in manifest["tasks"]] == ["przeplywy_raby"]
    assert manifest["tasks"][0]["options"] == {
        "dataset": "pl.imgw.hydro_daily",
        "stations": ["149190310"],
        "variables": ["H", "Q", "T"],
        "years": [2000, 2001, 2002],
        "year_type": "hydrological",
    }
    assert first.values["task_count"] == 1 and second.values["task_count"] == 2
    # Nothing is pinned before a download: said as such, never as a problem
    assert status.values["statuses"] == {
        "przeplywy_raby": "unpinned",
        "pmaxtp_waw": "unpinned",
    }
    assert (status.values["tasks_ok"], status.values["tasks_issues"]) == (2, 0)
    assert [path.name for path in verified.files["imgw_report"]] == [
        "project_verify.json"
    ]
    assert removed.values["task_count"] == 1 and moved.values["pinned"] == []


# --- plan-time review ----------------------------------------------------------


def test_every_operation_on_a_manifest_needs_one(project: Path) -> None:
    client = FakeToolClient(documents={"store info": READY})
    cases: dict[str, dict[str, Any]] = {
        "add_imgw_project_task": SERIES,
        "download_imgw_project": {"update": "pinned"},
        "check_imgw_project": {},
        "verify_imgw_project": {"depth": "status"},
        "remove_imgw_project_task": {"task_name": "a"},
        "set_imgw_project_store": {},
    }

    for operation, params in cases.items():
        result = preview(operation, params, client, project_dir=project)
        (problem,) = result.problems
        assert problem.params == () and "Utwórz projekt danych IMGW" in problem.text
    # ... except the one that creates it, which says so
    created = preview("init_imgw_project", {}, client, project_dir=project)
    assert created.problems == []
    assert created.rows[1][1].endswith("imgw-project.json — zostanie utworzony")


def test_tasks_are_checked_against_the_manifest_and_the_plan_lists_them(
    project: Path,
) -> None:
    write_manifest(project, Path("/stores/imgw"), {"a": True, "b": False})
    client = FakeToolClient(documents={"store info": READY})
    where = {"project_dir": project}

    everything = preview("check_imgw_project", {}, client, **where)
    unknown = preview(
        "verify_imgw_project", {"depth": "verify", "tasks": ["a", "x"]}, client, **where
    )
    duplicate = preview(
        "add_imgw_project_task", {**SERIES, "task_name": "b"}, client, **where
    )
    gone = preview("remove_imgw_project_task", {"task_name": "z"}, client, **where)
    pinned = preview("remove_imgw_project_task", {"task_name": "a"}, client, **where)

    assert everything.rows[2] == ("Zadania w projekcie", "2: a, b")
    assert [p.params for p in unknown.problems] == [("tasks",)]
    assert "x" in unknown.problems[0].text and "a, b" in unknown.problems[0].text
    assert [p.params for p in duplicate.problems] == [("task_name",)]
    assert [p.params for p in gone.problems] == [("task_name",)]
    assert "jest przypięte" in pinned.rows[1][1]


def test_a_project_with_no_tasks_has_nothing_to_download_check_or_verify(
    project: Path,
) -> None:
    write_manifest(project, Path("/stores/imgw"), {})
    client = FakeToolClient(documents={"store info": READY})

    for operation, params in (
        ("download_imgw_project", {"update": "pinned"}),
        ("check_imgw_project", {}),
        ("verify_imgw_project", {"depth": "status"}),
    ):
        (problem,) = preview(operation, params, client, project_dir=project).problems
        assert problem.params == () and "nie ma żadnych zadań" in problem.text


def test_download_never_initialises_a_store_and_needs_the_projects_own_store(
    project: Path,
) -> None:
    write_manifest(project, Path("/stores/imgw"), {"a": False})
    missing = FakeToolClient(documents={"store info": NO_STORE})

    blocked = preview(
        "download_imgw_project", {"update": "pinned"}, missing, project_dir=project
    )
    other = preview(
        "download_imgw_project",
        {"update": "pinned"},
        FakeToolClient(documents={"store info": READY}),
        settings={"store_dir": "/stores/other"},
        project_dir=project,
    )

    # The tool would create a missing store by itself: Retman's plan refuses it first
    assert "Utwórz magazyn IMGW" in blocked.problems[0].text
    assert (
        "/stores/other" in other.problems[0].text
        and "/stores/imgw" in other.problems[0].text
    )
    assert missing.network_calls == []


def test_download_says_what_each_update_mode_does_to_the_pins(project: Path) -> None:
    write_manifest(project, Path("/stores/imgw"), {"a": True, "b": False, "c": False})
    client = FakeToolClient(documents={"store info": READY})
    where = {"project_dir": project}

    restore = preview(
        "download_imgw_project",
        {"update": "pinned", "tasks": ["a", "b"]},
        client,
        **where,
    )
    upgrade = preview("download_imgw_project", {"update": "upgrade"}, client, **where)

    assert (
        restore.rows[3][1] == "nowych zadań do pobrania i przypięcia: 1; "
        "przypiętych do odtworzenia (przypięcia bez zmian): 1"
    )
    assert "wszystkie wybrane zadania (3)" in upgrade.rows[3][1]
    assert "zostanie zmieniony" in upgrade.rows[1][1]


def test_init_refuses_a_project_inside_the_store_and_a_manifest_of_another_store(
    tmp_path: Path, project: Path
) -> None:
    client = FakeToolClient()
    inside = preview(
        "init_imgw_project",
        {},
        client,
        settings={"store_dir": str(tmp_path)},
        project_dir=project,
    )
    write_manifest(project, tmp_path / "elsewhere", {})
    other = preview(
        "init_imgw_project",
        {},
        client,
        settings={"store_dir": str(tmp_path / "store")},
        project_dir=project,
    )
    (project / "imgw-project.json").write_text("{not json")
    broken = preview(
        "init_imgw_project",
        {},
        client,
        settings={"store_dir": str(tmp_path / "store")},
        project_dir=project,
    )

    assert any("leży w magazynie" in problem.text for problem in inside.problems)
    assert "elsewhere" in other.problems[0].text
    assert "Nie można odczytać manifestu" in broken.problems[0].text


def store_folders(tmp_path: Path) -> dict[str, Path]:
    """Store folders a project meets: empty, a layout without a marker, a key file."""
    folders = {name: tmp_path / name for name in ("empty", "unmarked", "keys")}
    for folder in folders.values():
        folder.mkdir()
    write_layout(folders["unmarked"])
    write_server_state(folders["keys"])
    return folders


def test_the_plan_of_a_project_refuses_an_unmarked_layout_and_a_key_file_folder(
    tmp_path: Path, project: Path
) -> None:
    folders = store_folders(tmp_path)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    write_manifest(project, tmp_path / "elsewhere", {})

    def problems(operation: str, folder: Path, where: Path) -> list[str]:
        settings = {"store_dir": str(folder)}
        found = preview(
            operation, {}, FakeToolClient(), settings=settings, project_dir=where
        )
        return [problem.text for problem in found.problems]

    # A project is created and moved with `init` and `set store`: the same refusals
    for operation, where in (
        ("init_imgw_project", fresh),
        ("set_imgw_project_store", project),
    ):
        assert problems(operation, folders["empty"], where) == []
        (unmarked,) = problems(operation, folders["unmarked"], where)
        (keys,) = problems(operation, folders["keys"], where)
        assert "ma układ magazynu IMGW, ale nie ma znacznika" in unmarked
        assert "nie jest jeszcze utworzony" in keys


def test_the_tool_refuses_the_store_folders_that_the_plan_of_a_project_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_environment(monkeypatch)
    outcomes = {}
    for name, folder in store_folders(tmp_path).items():
        where, out = tmp_path / f"project-{name}", tmp_path / f"out-{name}"
        where.mkdir()
        out.mkdir()
        ctx = context(
            "init_imgw_project",
            real_client(tmp_path, folder),
            settings=settings_for(tmp_path, folder),
            project_dir=where,
            output_dir=out,
        )
        result = execute("init_imgw_project", {}, ctx)
        outcomes[name] = (result.ok, result.error_code)

    assert outcomes == {
        "empty": (True, None),
        "unmarked": (False, "store_unavailable"),
        "keys": (False, "store_unavailable"),
    }


def test_an_area_selection_needs_a_geojson_inside_the_project_and_a_catalog(
    tmp_path: Path, project: Path
) -> None:
    write_manifest(project, Path("/stores/imgw"), {})
    good = project / "zlewnia.geojson"
    good.write_text('{"type": "FeatureCollection", "features": []}')
    (project / "tekst.geojson").write_text("to nie jest JSON")
    (project / "punkt.geojson").write_text('{"type": "Point", "coordinates": [1, 2]}')
    outside = tmp_path / "obok.geojson"
    outside.write_text('{"type": "Polygon", "coordinates": []}')
    (project / "link.geojson").symlink_to(good)
    by_area = {k: v for k, v in SERIES.items() if k != "stations"}
    with_catalog = FakeToolClient(
        documents={
            "store info": READY,
            "store scan": {"result": {"items": [{"kind": "catalog"}]}},
        }
    )
    no_catalog = FakeToolClient(
        documents={"store info": READY, "store scan": {"result": {"items": []}}}
    )

    def check(file: str, client: Any = with_catalog) -> Any:
        params = {**by_area, "selection": "area", "area_file": file}
        return preview("add_imgw_project_task", params, client, project_dir=project)

    assert check("zlewnia.geojson").problems == []
    assert check(str(good)).problems == []
    for file, reason in (
        ("brak.geojson", "Nie znaleziono pliku obszaru"),
        ("tekst.geojson", "nie jest poprawnym plikiem GeoJSON"),
        ("punkt.geojson", "nie jest poprawnym plikiem GeoJSON"),
        (str(outside), "musi leżeć w folderze projektu"),
        ("../obok.geojson", "musi leżeć w folderze projektu"),
        ("link.geojson", "musi leżeć w folderze projektu"),
    ):
        (problem,) = check(file).problems
        assert problem.params == ("area_file",) and reason in problem.text, file
    # A valid file is not enough: the stations come from the catalog in the store
    (missing,) = check("zlewnia.geojson", no_catalog).problems
    assert missing.params == () and "katalogu stacji" in missing.text


def test_the_fixed_year_type_is_said_in_the_plan_and_early_years_are_asked_again(
    project: Path,
) -> None:
    write_manifest(project, Path("/stores/imgw"), {})
    client = FakeToolClient()
    semiannual = {**SERIES, "dataset": "pl_hydro_semiannual"}
    del semiannual["year_type"]
    early = {**SERIES, "period": {"type": "years", "first": 1900, "last": 1960}}

    plain = preview("add_imgw_project_task", semiannual, client, project_dir=project)
    refused = preview("add_imgw_project_task", early, client, project_dir=project)

    assert [label for label, _ in plain.rows] == ["Manifest projektu", "Rodzaj roku"]
    assert [p.params for p in refused.problems] == [("period",)]
    assert "od roku 1951" in refused.problems[0].text


def test_a_variable_read_before_the_dataset_was_chosen_is_asked_again(
    tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolate_environment(monkeypatch)
    config = load_config(init_config(tmp_path / "config.toml"))
    config = replace(
        config, tools={**config.tools, "imgwtools": settings_for(tmp_path)}
    )
    write_manifest(project, fixture_store(), {})
    rules: dict[str, str | Decision] = {
        "imgw_projects": "imgw_projects",
        "add_imgw_project_task": "add_imgw_project_task",
        "series": "series",
        "stations": "stations",
    }
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"imgwtools": real_client(tmp_path)},
        today=date(2026, 10, 19),
    )

    plan = app.plan(
        "Dodaj zadanie przeplywy_a: przepływy dla 149190310 "
        "z lat hydrologicznych 2000-2020"
    )

    # Without a dataset "przepływy" is Q, which only the daily series has
    (dataset,) = plan.questions
    assert dataset.name == "dataset"
    assert plan.values["variables"].value == ["Q"]

    # The monthly series has Q_min, Q_mean and Q_max
    monthly = [option.key for option in dataset.options].index("pl_hydro_monthly")
    plan = plan.answer("dataset", str(monthly + 1))

    (question,) = plan.questions
    assert question.name == "variables" and "Q_mean" in (question.error or "")
    plan = plan.answer("variables", "średni przepływ")
    assert plan.questions == []
    assert plan.values["variables"].value == ["Q_mean"]


# --- network operations: the tool's own result objects, no network -------------


def test_a_download_reports_the_state_of_each_task(
    tmp_path: Path, project: Path
) -> None:
    store = tmp_path / "store"
    report = ProjectReport(
        {"a": "upgraded", "b": "failed"},
        (
            OperationResult(
                "archive:pl.imgw.hydro_daily:2020/a.zip",
                "new",
                store / "v",
                None,
                "a",
            ),
            OperationResult(
                None, "failed", None, "brak sieci", "b", "source_unavailable"
            ),
        ),
        False,
    )
    run = replace(synthetic_run("project download", report), status="partial")
    client = FakeToolClient(runs={"project download": run})
    ctx = context(
        "download_imgw_project", client, project_dir=project, output_dir=tmp_path
    )

    result = execute(
        "download_imgw_project", {"update": "upgrade", "tasks": ["a", "b"]}, ctx
    )

    assert result.ok, result.error
    assert client.calls[-1][1].options == {
        "project_dir": str(project),
        "tasks": ["a", "b"],
        "update": "upgrade",
    }
    assert result.values["statuses"] == {"a": "upgraded", "b": "failed"}
    assert (result.values["pinned"], result.values["pinned_count"]) == (["a"], 1)
    assert result.values["files"] == {"new": 1, "failed": 1}
    # The failure of one task is reported, not hidden behind a success
    assert any("brak sieci" in warning for warning in result.warnings)


def project_plan(root: Path) -> StorePlan:
    actions = (
        PlanAction("project download", "missing", "a: zadanie nieprzypięte"),
        PlanAction("project download", "newer", "b: dostępne nowsze dane"),
        PlanAction("project download", "check_failed", "c: brak sieci"),
    )
    return StorePlan(
        "imgw-plan/1", root, datetime(2026, 10, 19, tzinfo=UTC), (), {}, actions
    )


def test_a_check_saves_the_plan_and_names_the_state_of_every_task(
    tmp_path: Path, project: Path
) -> None:
    plan = project_plan(tmp_path / "store")

    def check(call: CatalogCall) -> ToolRun:
        plan.to_json(Path(str(call.options["plan"])))
        return synthetic_run("project check", plan)

    client = FakeToolClient(runs={"project check": check})
    ctx = context(
        "check_imgw_project", client, project_dir=project, output_dir=tmp_path
    )

    result = execute("check_imgw_project", {}, ctx)

    assert result.ok, result.error
    assert result.files["imgw_plan"] == [tmp_path / "plan.json"]
    assert result.values["statuses"] == {
        "a": "missing",
        "b": "newer",
        "c": "check_failed",
    }
    assert result.values["task_count"] == 3


def test_the_availability_check_names_each_task_and_never_downloads(
    project: Path,
) -> None:
    plan = project_plan(Path("/stores/imgw"))
    document = CommandResult("project download", True, "partial", plan, ()).to_json()
    client = FakeToolClient(documents={"check:project download": document})
    ctx = context("download_imgw_project", client, project_dir=project)

    report = run_check(
        operations()["download_imgw_project"], {"update": "pinned"}, ctx, TEXTS
    )

    assert report.status == "partial"
    assert report.lines == [
        "Zadanie „a”: do pobrania i przypięcia (zadanie nieprzypięte).",
        "Zadanie „b”: są nowsze dane (dostępne nowsze dane).",
        "Zadanie „c”: sprawdzenie nie powiodło się (brak sieci).",
    ]
    assert [m for m, _ in client.calls if m != "validate"] == ["check"]


# --- the gate --------------------------------------------------------------------


def test_planning_a_download_neither_touches_the_network_nor_a_missing_store(
    tmp_path: Path,
) -> None:
    config = load_config(init_config(tmp_path / "config.toml"))
    settings = settings_for(tmp_path, tmp_path / "store")
    config = replace(config, tools={**config.tools, "imgwtools": settings})
    project = tmp_path / "project"
    project.mkdir()
    write_manifest(project, tmp_path / "store", {"a": False})
    client = FakeToolClient(documents={"store info": NO_STORE})
    rules: dict[str, str | Decision] = {
        "imgw_projects": "imgw_projects",
        "download_imgw_project": "download_imgw_project",
        "pinned": "pinned",
    }
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"imgwtools": client},
    )

    with pytest.raises(RetmanError) as caught:
        app.plan("Pobierz dane projektu")

    assert "Utwórz magazyn IMGW" in str(caught.value.text)

    assert client.network_calls == [] and not (tmp_path / "store").exists()
    manifest = json.loads((project / "imgw-project.json").read_text())
    assert manifest["tasks"][0]["pinned_at"] is None

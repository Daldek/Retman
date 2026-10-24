"""Call builders of the project operations: golden calls, the tool's own validation."""

from pathlib import Path
from typing import Any

import pytest
from imgw_ops_support import STORE, YEARS, context, operations, station
from imgw_support import isolate_environment, real_client

from retman.adapters.catalog import ToolError, route_error
from retman.testing import FakeToolClient
from retman.tools.imgwtools import calls_projects as calls

PROJECT = Path("/projects/imgw")
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
    "method": "amp",
}


def build(builder: Any, operation: str, params: dict[str, Any], **kw: Any) -> Any:
    return builder(params, context(operation, FakeToolClient(), **kw))


def test_a_series_task_is_whole_years_of_a_year_type_for_the_chosen_stations() -> None:
    params = {**SERIES, "variables": ["Q", "H"]}

    (call,) = build(calls.add_imgw_project_task, "add_imgw_project_task", params)

    assert (call.command, call.options) == (
        "project add",
        {
            "project_dir": str(PROJECT),
            "name": "przeplywy_raby",
            "command": "series select",
            "options": {
                "dataset": "pl.imgw.hydro_daily",
                "years": [2000, 2001, 2002],
                "year_type": "hydrological",
                "stations": ["149190310"],
                "variables": ["Q", "H"],
            },
        },
    )


def test_a_semiannual_series_has_only_hydrological_years_without_asking() -> None:
    params = {**SERIES, "dataset": "pl_hydro_semiannual"}
    del params["year_type"]

    (call,) = build(calls.add_imgw_project_task, "add_imgw_project_task", params)

    assert call.options["options"]["year_type"] == "hydrological"


def test_an_area_selection_passes_the_geojson_by_a_relative_path() -> None:
    params = {
        **SERIES,
        "selection": "area",
        "area_file": str(PROJECT / "zlewnie" / ".." / "zlewnia.geojson"),
    }
    del params["stations"]

    (call,) = build(calls.add_imgw_project_task, "add_imgw_project_task", params)

    assert call.options["geometry"] == "zlewnia.geojson"
    assert "stations" not in call.options["options"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("zlewnia.geojson", "zlewnia.geojson"),
        ("./dane/zlewnia.geojson", "dane/zlewnia.geojson"),
        ("/projects/imgw/dane/z.geojson", "dane/z.geojson"),
        # Outside the folder: left as typed, the preview refuses it
        ("../obok.geojson", "../obok.geojson"),
        ("/inny/z.geojson", "/inny/z.geojson"),
    ],
)
def test_the_area_file_is_relative_to_the_project_folder(
    given: str, expected: str
) -> None:
    assert calls.project_relative(given, PROJECT) == expected


def test_a_pmaxtp_task_stores_the_point_and_the_method() -> None:
    (call,) = build(calls.add_imgw_project_task, "add_imgw_project_task", PMAXTP)

    assert call.options["command"] == "pmaxtp sync"
    assert call.options["options"] == {
        "latitude": 52.23,
        "longitude": 21.01,
        "method": "AMP",
    }


def test_every_project_command_gets_the_project_folder_and_the_configured_store(
    tmp_path: Path,
) -> None:
    named = {"tasks": ["a", "b"]}

    def one(builder: Any, operation: str, params: dict[str, Any], **kw: Any) -> Any:
        return build(builder, operation, params, **kw)[0]

    (init,) = build(calls.init_imgw_project, "init_imgw_project", {})
    (store,) = build(calls.set_imgw_project_store, "set_imgw_project_store", {})
    (remove,) = build(
        calls.remove_imgw_project_task, "remove_imgw_project_task", {"task_name": "a"}
    )
    download = one(
        calls.download_imgw_project,
        "download_imgw_project",
        {"update": "upgrade", **named},
    )
    everything = one(calls.check_imgw_project, "check_imgw_project", {})
    check = one(
        calls.check_imgw_project,
        "check_imgw_project",
        named,
        output_dir=tmp_path,
    )
    status = one(calls.verify_imgw_project, "verify_imgw_project", {"depth": "status"})
    verify = one(calls.verify_imgw_project, "verify_imgw_project", {"depth": "verify"})

    assert (
        init.options
        == store.options
        == {
            "project_dir": str(PROJECT),
            "store_dir": str(STORE),
        }
    )
    assert remove.options == {"project_dir": str(PROJECT), "name": "a"}
    assert download.options == {
        "project_dir": str(PROJECT),
        "tasks": ["a", "b"],
        "update": "upgrade",
    }
    # An omitted "tasks" means every task of the project: the option is not passed
    assert everything.options == {"project_dir": str(PROJECT)}
    assert (
        check.options["plan"] == str(tmp_path / "plan.json")
        and check.kind == "imgw_plan"
    )
    assert (status.command, verify.command) == ("project status", "project verify")
    assert status.kind == "imgw_report"


def test_the_tool_accepts_every_call_the_builders_make(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    client = real_client(tmp_path, tmp_path / "store")
    by_area = {k: v for k, v in SERIES.items() if k != "stations"}
    cases: list[tuple[Any, str, dict[str, Any]]] = [
        (calls.init_imgw_project, "init_imgw_project", {}),
        (calls.add_imgw_project_task, "add_imgw_project_task", SERIES),
        (calls.add_imgw_project_task, "add_imgw_project_task", PMAXTP),
        (
            calls.add_imgw_project_task,
            "add_imgw_project_task",
            {
                **by_area,
                "selection": "area",
                "area_file": str(project / "z.geojson"),
                "dataset": "pl_meteo_precip_daily",
            },
        ),
        (
            calls.download_imgw_project,
            "download_imgw_project",
            {"update": "pinned", "tasks": ["a"]},
        ),
        (calls.check_imgw_project, "check_imgw_project", {}),
        (calls.verify_imgw_project, "verify_imgw_project", {"depth": "verify"}),
        (
            calls.remove_imgw_project_task,
            "remove_imgw_project_task",
            {"task_name": "a"},
        ),
        (calls.set_imgw_project_store, "set_imgw_project_store", {}),
    ]

    for builder, operation, params in cases:
        ctx = context(
            operation,
            client,
            settings={"store_dir": str(tmp_path / "store")},
            project_dir=project,
        )
        for call in builder(params, ctx):
            client.validate(call)


def rejected_as(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    params: dict[str, Any],
) -> list[str]:
    """The parameters the real tool's rejection of the operation's call concerns."""
    isolate_environment(monkeypatch)
    project = tmp_path / "project"
    project.mkdir()
    client = real_client(tmp_path, tmp_path / "store")
    (call,) = getattr(calls, operation)(
        params, context(operation, client, project_dir=project)
    )

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    names = [p["name"] for p in operations()[operation].spec["params"]]
    return route_error(call, caught.value, names)


@pytest.mark.parametrize(
    ("changes", "asked"),
    [
        # "przepływ" was read as Q while the dataset was open; a monthly series has
        # only Q_min, Q_mean and Q_max
        ({"dataset": "pl_hydro_monthly", "variables": ["Q"]}, ["variables"]),
        # A ČHMÚ station for an IMGW-PIB dataset, read before the dataset was chosen
        ({"stations": [station("0-203-1-001000", "CHMI")]}, ["stations"]),
        # The semi-annual series has only hydrological years
        ({"dataset": "pl_hydro_semiannual", "year_type": "calendar"}, ["year_type"]),
        # Not an option of the task's command but of ``project add`` itself
        ({"task_name": "Bad Name!"}, ["task_name"]),
    ],
)
def test_a_series_task_the_tool_rejects_is_a_question_about_the_answer_at_fault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, Any],
    asked: list[str],
) -> None:
    params = {**SERIES, **changes}

    assert rejected_as(tmp_path, monkeypatch, "add_imgw_project_task", params) == asked


def test_a_pmaxtp_point_outside_poland_is_a_question_about_the_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    point = {"type": "point", "latitude": 10.0, "longitude": 21.0}

    asked = rejected_as(
        tmp_path, monkeypatch, "add_imgw_project_task", {**PMAXTP, "point": point}
    )

    assert asked == ["point"]

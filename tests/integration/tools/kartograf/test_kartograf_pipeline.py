"""Kartograf through the whole pipeline: plan, offline preview, check, execute.

The real Kartograf validates and looks things up offline; the network and the store
are an ``OfflineClient`` with recorded documents. ``client.network`` must stay empty
until the user has confirmed (N-12): the plan, its questions and its preview are
all offline.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from kartograf_offline import GugikIndex, flight, gugik_index
from kartograf_support import (
    CHILDREN,
    NEWEST,
    OfflineClient,
    built_store,
    geometry,
    operations,
)

from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.exceptions import RetmanError
from retman.testing import FakeDecisionBackend

AVAILABILITY = Path(__file__).resolve().parents[3] / "fixtures" / "kartograf"


def make_app(
    tmp_path: Path, rules: dict[str, Any], **programmed: Any
) -> tuple[Any, Any]:
    """A pipeline over the Kartograf operations and an offline client."""
    config = load_config(
        init_config(tmp_path / "config.toml", stores_dir=tmp_path / "stores")
    )
    config = replace(config, collect_commands=False)
    project = tmp_path / "project"
    project.mkdir()
    client = OfflineClient(config.tools["kartograf"], **programmed)
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"kartograf": client},
    )
    return app, client


def asked(plan: Plan) -> dict[str, Any]:
    return {question.name: question for question in plan.questions}


def number(plan: Plan, name: str, key: str) -> str:
    """The answer that picks option ``key`` of an open question."""
    return str([option.key for option in asked(plan)[name].options].index(key) + 1)


def test_a_geometry_request_is_validated_and_previewed_before_any_network(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
    )
    geometry(app.workspace.project_dir, "granica.shp")

    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla obszaru z pliku granica.shp")

    assert plan.questions == []
    assert plan.values["area"].value["type"] == "geometry"
    assert dict(plan.preview_rows)["Liczba arkuszy"] == "4 × 1:10000 (PL-1992)"
    assert "Obwiednia obszaru" in dict(plan.preview_rows)
    assert plan.preview_values["sheet_count"] == 4
    assert client.network == []


def test_a_grid_pair_kartograf_refuses_is_asked_again_with_the_reason(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {"download_dem_sheet": "download_dem_sheet", "5m": "5m", "kron86": "kron86"},
    )

    plan = app.plan("Pobierz NMT 5 m KRON86 dla arkusza N-34-130-D-d-2-4")

    # The pair is asked about again: the model's choices are not asked a second time
    assert set(asked(plan)) == {"resolution"}
    assert "EVRF2007" in asked(plan)["resolution"].error
    plan = plan.answer("resolution", number(plan, "resolution", "1m"))
    # 1 m with the KRON86 the command asked for is a pair Kartograf accepts
    assert plan.questions == []
    assert plan.values["vertical_crs"].value == "kron86"
    assert dict(plan.preview_rows)["Liczba arkuszy"] == "1 × 1:10000 (PL-1992)"
    assert client.network == []


def test_an_orthophoto_of_a_geometry_file_asks_for_the_product_and_the_area_again(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_sheet_hierarchy": "download_sheet_hierarchy",
            "orthophoto": "orthophoto",
            "scale_10000": "scale_10000",
            "cir": "cir",
        },
    )
    geometry(app.workspace.project_dir, "granica.shp")

    plan = app.plan(
        "Pobierz ortofotomapę CIR w skali 1:10000 dla obszaru z pliku granica.shp"
    )

    assert set(asked(plan)) == {"product", "area"}
    assert "godła arkusza" in asked(plan)["area"].error
    plan = plan.answer("area", "N-34-130-D-d-2")
    assert asked(plan).keys() == {"product"}
    assert client.network == []


def test_the_availability_check_is_a_separate_step_after_its_own_consent(
    tmp_path: Path,
) -> None:
    availability = json.loads(
        (AVAILABILITY / "availability_nmt_sheet.json").read_text("utf-8")
    )
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
        queries={"elevation availability": availability},
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4")

    assert plan.can_check
    assert "GUGiK" in plan.check_notice()
    assert client.network == []  # planning and the notice used no network
    report = app.check(plan.confirm_check())

    assert [method for method, _ in client.network] == ["query"]
    assert report.status == "available"
    assert any("2025" in line for line in report.lines)
    # The report informs; the plan itself still has to be confirmed
    assert not plan.confirmed and plan.checks == [report]


def _only_result(app: Any) -> tuple[Path, dict[str, Any]]:
    (path,) = (app.workspace.project_dir / app.config.results_dir).glob("*/result.json")
    return path.parent, json.loads(path.read_text(encoding="utf-8"))


def test_executed_sheets_stay_in_the_store_and_the_record_names_the_tool_run(
    tmp_path: Path,
) -> None:
    index = GugikIndex([flight(CHILDREN[0], *NEWEST, full=False)])
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-139-C-a-3")
    assert client.network == []

    with gugik_index(index):
        result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert [method for method, _ in client.network] == ["run"]
    folder, record = _only_result(app)
    store = tmp_path / "stores" / "kartograf"
    (entry,) = record["files"]["dem"]
    assert entry["store"] == "kartograf" and len(entry["sha256"]) == 64
    assert Path(entry["path"]).is_relative_to(store)
    # The first write into the new store marked it (DEV-19.12)
    assert (store / "kartograf-store.json").is_file()
    call = record["tool"]["calls"][0]
    assert call["command"] == "elevation download"
    assert call["schema"] == "kartograf-result/1"
    assert (folder / call["document_file"]).is_file()
    assert record["preview"]["sheet_count"] == 4
    # 1 of 4 sheets: the user is told in words, not only in the record
    assert any("1 z 4" in warning for warning in result.warnings)


def test_a_failed_run_is_a_result_with_retmans_text_of_the_tools_error_code(
    tmp_path: Path,
) -> None:
    app, _ = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-139-C-a-4")

    with gugik_index(GugikIndex()):
        result = app.execute(plan.confirm())

    assert not result.ok
    # The registry code is the code of the result, the reason is in the failure
    assert result.error_code == "no_data"
    assert result.failure is not None
    assert result.failure["details"]["reason"] == "no_coverage"
    assert "GUGiK nie ma danych" in (result.error or "")


def test_an_orthophoto_runs_through_the_provider_and_lands_in_the_store(
    tmp_path: Path,
) -> None:
    index = GugikIndex([flight(CHILDREN[0], "2025-04-26", "82712", orthophoto=True)])
    app, client = make_app(
        tmp_path,
        {
            "download_sheet_hierarchy": "download_sheet_hierarchy",
            "orthophoto": "orthophoto",
            "scale_10000": "scale_10000",
            "cir": "cir",
        },
    )
    plan = app.plan(
        "Pobierz ortofotomapę CIR z arkuszy pod N-34-139-C-a-3 w skali 1:10000"
    )
    assert plan.questions == [], [q.name for q in plan.questions]

    with gugik_index(index):
        result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert client.network == []  # the provider route does not use the command client
    _, record = _only_result(app)
    store = tmp_path / "stores" / "kartograf"
    (entry,) = record["files"]["orthophoto"]
    assert entry["store"] == "kartograf"
    assert Path(entry["path"]).is_relative_to(store)
    assert (store / "kartograf-store.json").is_file()
    assert record["tool"]["calls"][0]["options"]["color"] == "CIR"
    assert record["params"]["color"]["value"] == "cir"


def test_creating_the_store_is_planned_without_a_write_and_made_after_confirmation(
    tmp_path: Path,
) -> None:
    app, client = make_app(tmp_path, {"init_kartograf_store": "init_kartograf_store"})
    store = tmp_path / "stores" / "kartograf"

    plan = app.plan("Utwórz magazyn Kartografa")

    assert plan.questions == []
    assert dict(plan.preview_rows)["Stan magazynu"].startswith("folder nie istnieje")
    assert not store.exists()
    assert client.network == []  # the plan and its preview are offline (N-12)
    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert (store / "kartograf-store.json").is_file()
    assert result.values["store"] == str(store)
    assert "magazyn Kartografa jest gotowy" in result.summary
    _, record = _only_result(app)
    assert record["tool"]["calls"][0]["command"] == "store init"
    # The shared executor runs the call through the command client, once
    assert [(kind, call.command) for kind, call in client.network] == [
        ("run", "store init")
    ]


def test_a_plan_into_a_store_kartograf_refuses_stops_with_the_way_out(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
    )
    store = built_store(tmp_path / "stores" / "kartograf").root
    (store / "kartograf-store.json").unlink()

    with pytest.raises(RetmanError) as caught:
        app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4")

    assert caught.value.code == "validation_error"
    assert "Utwórz magazyn Kartografa" in (caught.value.text or "")
    assert client.network == []
    assert not (store / "kartograf-store.json").exists()

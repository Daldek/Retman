"""The tool reviews a complete plan offline; its rejections become questions again."""

import hashlib
import json
from dataclasses import replace

import pytest

from retman.adapters.catalog import (
    CatalogCall,
    ToolError,
    ToolFile,
    ToolNotice,
    ToolRun,
)
from retman.core.plan import Plan
from retman.exceptions import PlanIncompleteError, PlanNotConfirmedError, RetmanError
from retman.testing import FakeToolClient

SHEET = "N-34-130-D-d-2-4"
DEM = b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n3\n"
RULES = {"fetch_dem": "fetch_dem", "5m": "5m", "kron86": "kron86"}


def reject_pair(call: CatalogCall) -> ToolError | None:
    """The tool refuses 5 m with KRON86 and names both options."""
    if call.options["resolution"] == "5m" and call.options["vertical_crs"] == "KRON86":
        return ToolError(
            "dummy_tool",
            "validation_error",
            "5 m nie ma KRON86",
            options=("resolution", "vertical_crs"),
        )
    return None


@pytest.fixture
def client() -> FakeToolClient:
    return FakeToolClient(validation={"elevation download": reject_pair})


@pytest.fixture
def rejected_plan(create_app, client):
    """The model reads 5 m and KRON86 from the command; the tool refuses the pair."""
    app = create_app(RULES, clients={"dummy_tool": client})
    return app, app.plan(f"Pobierz NMT dla {SHEET} 5 m KRON86")


def test_rejected_combination_asks_both_parameters_again_with_the_reason(
    rejected_plan,
):
    _, plan = rejected_plan

    assert [q.name for q in plan.questions] == ["resolution", "vertical_crs"]
    assert all("5 m nie ma KRON86" in (q.error or "") for q in plan.questions)
    assert "resolution" not in plan.values and "vertical_crs" not in plan.values
    # What the user stated and the tool accepted stays as it was
    assert plan.values["area"].source == "command"
    # The plan is not confirmable while the tool refuses it
    with pytest.raises(PlanIncompleteError):
        plan.confirm()


def test_answers_make_the_plan_reviewable_again_and_show_the_preview(rejected_plan):
    _, plan = rejected_plan

    asked_vertical = plan.answer("resolution", "2")  # 1 m
    done = asked_vertical.answer("vertical_crs", "2")  # KRON86 is fine at 1 m

    assert [q.name for q in asked_vertical.questions] == ["vertical_crs"]
    assert done.questions == [] and done.reopened == {}
    assert done.values["resolution"].source == "user"
    assert done.preview_rows == [("Rodzaj obszaru", "sheet")]
    assert "Rodzaj obszaru: sheet ← podgląd, bez sieci" in done.summary()
    assert done.confirm().confirmed


def test_answering_the_same_values_asks_again_instead_of_rederiving(rejected_plan):
    _, plan = rejected_plan

    again = plan.answer("resolution", "3").answer("vertical_crs", "2")  # 5 m, KRON86

    assert [q.name for q in again.questions] == ["resolution", "vertical_crs"]
    assert again.values["area"].source == "command"


def test_a_value_read_from_the_command_is_asked_not_read_again(create_app):
    app = create_app(RULES, clients={"dummy_tool": FakeToolClient()})

    # The operation's own preview refuses this sheet although the tool validates it
    plan = app.plan("Pobierz NMT dla N-34-130-D-d-2-1 1 m")

    (question,) = [q for q in plan.questions if q.name == "area"]
    assert question.error == "Arkusz N-34-130-D-d-2-1 nie jest dostępny w usłudze."
    assert "area" not in plan.values
    fixed = plan.answer("area", SHEET)
    assert fixed.values["area"].source == "user" and fixed.reopened == {}


def test_a_problem_that_cannot_be_reopened_raises_instead_of_looping(
    create_app, client
):
    app = create_app(RULES, clients={"dummy_tool": client})

    # Fixed values are never asked about; nothing is left to reopen
    with pytest.raises(RetmanError) as caught:
        app.plan(
            f"Pobierz NMT dla {SHEET}",
            known={"resolution": "5m", "vertical_crs": "kron86"},
        )
    assert "5 m nie ma KRON86" in str(caught.value.text)


def test_the_journal_says_why_a_question_was_asked_again(rejected_plan):
    app, plan = rejected_plan

    plan.answer("resolution", "2")
    event = next(e for e in app.journal.entries() if e["event"] == "question")

    assert event["name"] == "resolution" and "5 m nie ma KRON86" in event["reason"]


def test_nothing_reaches_the_network_before_confirmation(create_app):
    client = FakeToolClient(
        documents={"lookup:elevation download": {"ok": True}},
        runs={"elevation download": ToolRun("elevation download", "ok")},
    )
    app = create_app(RULES, clients={"dummy_tool": client})

    plan = app.plan(f"Pobierz NMT dla {SHEET} 1 m")
    restored = Plan.from_dict(json.loads(json.dumps(plan.to_dict())), retman=app)
    restored = restored.change("resolution").answer("resolution", "1")

    assert restored.questions == []
    assert {method for method, _ in client.calls} == {"validate"}
    with pytest.raises(PlanNotConfirmedError):
        app.execute(restored)
    assert client.network_calls == []
    app.execute(restored.confirm())
    assert [method for method, _ in client.network_calls] == ["run"]


def test_a_loaded_plan_is_never_confirmed(create_app):
    app = create_app(RULES, clients={"dummy_tool": FakeToolClient()})
    plan = app.plan(f"Pobierz NMT dla {SHEET} 1 m").confirm()
    state = json.loads(json.dumps(plan.to_dict()))
    state["confirmed"], state["confirmed_at"] = True, "2026-01-01T00:00:00+00:00"

    loaded = Plan.from_dict(state, retman=app)

    assert plan.confirmed and not loaded.confirmed and loaded.confirmed_at is None
    assert loaded.preview_rows == plan.preview_rows
    with pytest.raises(PlanNotConfirmedError):
        app.execute(loaded)


def test_result_references_store_files_and_records_what_the_tool_did(
    create_app, tmp_path
):
    store = tmp_path / "store"

    def download(call: CatalogCall) -> ToolRun:
        store.mkdir(exist_ok=True)
        stored = store / f"{call.options['sheet']}.asc"
        stored.write_bytes(DEM)
        return ToolRun(
            "elevation download",
            "ok",
            files=(ToolFile(stored, hashlib.sha256(DEM).hexdigest(), "v1", "new"),),
            notices=(ToolNotice("warning", "license_terms", "Dane GUGiK, licencja"),),
            document={"schema": "dummy-download/1", "ok": True},
            command_line="dummy elevation download",
            schema="dummy-download/1",
        )

    client = FakeToolClient(runs={"elevation download": download})
    app = create_app(RULES, clients={"dummy_tool": client})
    plan = app.plan(f"Pobierz NMT dla {SHEET} 1 m")

    result = app.execute(plan.confirm())
    saved = json.loads(
        (app.workspace.root / "001_fetch_dem" / "result.json").read_text()
    )

    assert result.ok and result.warnings == [
        "Narzędzie dummy_tool: Dane GUGiK, licencja"
    ]
    # A store file is referenced by absolute path, tool and checksum; nothing is copied
    assert saved["files"]["dem"] == [
        {
            "path": str(store / f"{SHEET}.asc"),
            "store": "dummy_tool",
            "sha256": hashlib.sha256(DEM).hexdigest(),
        }
    ]
    assert not list((app.workspace.root / "001_fetch_dem").glob("*.asc"))
    assert (
        saved["tool"]["calls"][0]["document_file"] == "tool_1_elevation_download.json"
    )
    assert saved["preview"] == {"area_type": "sheet"}
    assert saved["environment"]["tools"] == {"dummy_tool": "1.2.0"}
    # The stored file can be the input of a later operation (chains)
    (found,) = app.workspace.find_by_kind("dem")
    assert found.path == store / f"{SHEET}.asc"


def test_the_client_is_built_lazily_from_the_manifest_with_the_tool_settings(
    create_app, dummy_client, tmp_path
):
    app = create_app(RULES)

    assert dummy_client.BUILT == []  # not before the tool is needed
    app.plan(f"Pobierz NMT dla {SHEET} 1 m")
    app.plan(f"Pobierz NMT dla {SHEET} 5 m")

    assert [{"store_dir": str(tmp_path / "store")}] == dummy_client.BUILT
    assert len(dummy_client.CLIENTS) == 1  # one client per Retman and tool
    assert dummy_client.CLIENTS[0].network_calls == []


def test_a_tool_that_cannot_be_loaded_is_an_error_with_advice(create_app):
    broken = {
        key: replace(operation, client="no_such_tool_module:create_client")
        for key, operation in create_app().operations.items()
    }
    app = create_app(RULES, operations_override=broken)

    with pytest.raises(RetmanError) as caught:
        app.plan(f"Pobierz NMT dla {SHEET} 1 m")

    assert "Nie można załadować narzędzia dummy_tool" in str(caught.value.text)
    assert (caught.value.code, caught.value.details["reason"]) == (
        "missing_dependency",
        "tool_not_installed",
    )


def test_a_problem_without_parameters_stops_planning_with_its_text(
    create_app, monkeypatch
):
    def blocked(params, ctx):
        problem = {"params": [], "key": "sheet_unavailable", "args": {"code": "X"}}
        return {"values": {}, "rows": [], "problems": [problem]}

    monkeypatch.setattr("dummy_tool.hooks.preview_fetch_dem", blocked)
    app = create_app(RULES, clients={"dummy_tool": FakeToolClient()})

    # No parameter can be asked again, so the plan could never become confirmable
    with pytest.raises(RetmanError) as caught:
        app.plan(f"Pobierz NMT dla {SHEET} 1 m")

    assert "Arkusz X nie jest dostępny" in str(caught.value.text)

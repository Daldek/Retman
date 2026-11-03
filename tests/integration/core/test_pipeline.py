"""Consumer-visible planning, confirmation, workspace and audit behavior."""

import hashlib
import json
from pathlib import Path

import pytest

from retman.backends.base import Decision
from retman.config import Thresholds
from retman.core.plan import Plan
from retman.exceptions import (
    OutOfScopeError,
    PlanIncompleteError,
    PlanNotConfirmedError,
    RetmanError,
)
from retman.testing import FakeDecisionBackend

SHEET = "N-34-130-D-d-2-4"


def test_plan_missing_choice_then_user_answer_preserves_sources(create_app):
    app = create_app({"make_dem": "make_dem"})

    original = app.plan(f"Zrób NMT dla arkusza {SHEET}")
    answered = original.answer("style", "1")

    assert [question.name for question in original.questions] == ["style"]
    assert original.values["area"].source == "command"
    assert answered.questions == []
    assert answered.values["style"].value == "raw"
    assert answered.values["style"].source == "user"
    assert not original.confirmed


def test_choice_shows_user_texts_and_asks_model_what_command_states(create_app):
    app = create_app({"make_dem": "make_dem"})

    plan = app.plan(f"Zrób NMT dla arkusza {SHEET}")
    backend = app.backend
    backend.rules["smooth"] = "smooth"  # the model reads the user's own words
    answered = plan.answer("style", "smooth")

    # The user sees short labels in questions and in the plan ...
    assert [option.label for option in plan.questions[0].options] == [
        "Surowy",
        "Wygładzony",
    ]
    assert answered.display["style"] == "Wygładzony"
    assert plan.questions[0].text == "Jaki styl zapisu wybrać?"
    # ... while the model is asked what the command (or answer) states and
    # matches it against descriptions with synonyms ("smooth" exists only there)
    command_call, answer_call = (call for call in backend.calls if "smooth" in call[2])
    assert command_call[1] == answer_call[1] == "Jaki styl zapisu wymienia polecenie?"
    assert command_call[2]["smooth"] == "Wygładzony, smooth — po wygładzeniu"
    assert command_call[2]["unspecified"] == "Nie określono stylu"
    assert answer_call[2] == {
        "raw": "Surowy, raw — bez wygładzania",
        "smooth": "Wygładzony, smooth — po wygładzeniu",
    }


def test_plan_missing_free_value_reasks_with_error(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    plan = app.plan("Zrób NMT bez podania godła")

    incorrect = plan.answer("area", "bez arkusza")
    corrected = incorrect.answer("area", SHEET)

    assert incorrect.questions[0].error
    assert corrected.values["area"].value == {"type": "sheet", "code": SHEET}
    assert corrected.questions == []


def test_plan_ambiguous_free_answer_lists_candidate_readings(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    original = app.plan("Zrób NMT")

    ambiguous = original.answer("area", f"{SHEET} albo N-34-130-D-d-2-3")
    resolved = ambiguous.answer("area", "2")

    assert ambiguous.questions[0].error
    assert len(ambiguous.questions[0].options) == 2
    assert resolved.values["area"].value["code"] == "N-34-130-D-d-2-3"


def test_plan_ambiguous_readings_are_not_selected_implicitly(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    plan = app.plan(f"NMT dla {SHEET} albo N-34-130-D-d-2-3")

    resolved = plan.answer("area", "2")

    assert len(plan.questions[0].options) == 2
    assert resolved.values["area"].value["code"] == "N-34-130-D-d-2-3"
    assert resolved.values["area"].source == "user"


def test_plan_conditional_parameter_and_default_are_visible(create_app):
    app = create_app({"make_dem": "make_dem", "smooth": "smooth"})

    plan = app.plan(f"Pobierz {SHEET}")

    assert plan.values["detail"].value == "high"
    assert plan.values["detail"].source == "default"
    assert "wartość domyślna" in plan.summary()
    assert not plan.questions


def test_plan_low_confidence_unspecified_asks_instead_of_default(create_app):
    unsure = Decision(
        "unspecified",
        {"high": 0.3, "low": 0.1, "unspecified": 0.6},
        0.6,
        "logprobs",
        "offline",
    )
    app = create_app(
        {"make_dem": "make_dem", "smooth": "smooth", "unspecified": unsure},
        thresholds=Thresholds(0.8, 0.8),
    )

    plan = app.plan(f"Pobierz {SHEET}")

    assert [q.name for q in plan.questions] == ["detail"]
    assert "detail" not in plan.values


def test_plan_low_confidence_operation_and_parameter_ask(create_app):
    app = create_app(
        {"make_dem": "make_dem", "raw": "raw"},
        confidence=0.3,
        thresholds=Thresholds(0.8, 0.8),
    )

    plan = app.plan(f"Pobierz {SHEET}")
    selected = plan.answer("operation", "1")
    final = selected.answer("style", "1")

    assert [q.name for q in plan.questions] == ["operation"]
    assert selected.operation == "make_dem"
    assert [q.name for q in selected.questions] == ["style"]
    assert final.values["style"].source == "user"


def test_plan_unknown_confidence_marks_unverified_not_question(create_app):
    unknown = Decision("raw", confidence_method="none", model="offline")
    app = create_app(
        {"make_dem": "make_dem", "raw": unknown}, thresholds=Thresholds(0.95, 0.95)
    )

    plan = app.plan(f"NMT dla {SHEET}")

    assert plan.values["style"].unverified
    assert "niezweryfikowany" in plan.summary()


def test_plan_geometry_path_resolves_from_project_and_must_exist(create_app, make_gpkg):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    folder = app.workspace.project_dir
    make_gpkg(folder / "parcel.gpkg", "parcels")

    resolved = app.plan("NMT z pliku parcel.gpkg")
    missing = app.plan("NMT z pliku absent.gpkg")

    # The one feature table is used and recorded, never left to the tool
    assert resolved.values["area"].value == {
        "type": "geometry",
        "path": str(folder / "parcel.gpkg"),
        "layer": "parcels",
    }
    assert missing.questions[0].error
    assert "absent.gpkg" in missing.questions[0].error


def test_execute_requires_confirmation_and_complete_plan(create_app):
    app = create_app({"make_dem": "make_dem"})
    plan = app.plan(f"NMT dla {SHEET}")

    with pytest.raises(PlanNotConfirmedError):
        app.execute(plan)
    with pytest.raises(PlanIncompleteError):
        plan.confirm()
    assert not app.workspace.root.joinpath("001_make_dem").exists()


def test_execute_handler_failure_is_saved_without_erasing_history(create_app):
    app = create_app({"broken_dem": "broken_dem"})
    first = app.execute(app.plan("Uruchom błędne narzędzie").confirm())
    second = app.execute(app.plan("Uruchom błędne narzędzie").confirm())

    assert not first.ok and not second.ok
    assert first.number == 1 and second.number == 2
    assert "dummy failure" in app.workspace.list_results()[0]["error"]
    assert [entry["number"] for entry in app.workspace.list_results()] == [1, 2]


def test_execute_records_input_output_checksums_and_history(create_app):
    creator = create_app({"make_dem": "make_dem", "raw": "raw"})
    produced = creator.execute(creator.plan(f"NMT dla {SHEET}").confirm())
    copier = create_app({"copy_dem": "copy_dem"})

    planned = copier.plan("Skopiuj NMT z tego projektu")
    result = copier.execute(planned.confirm())
    saved = copier.workspace.list_results()
    journal = copier.journal.entries()

    assert produced.ok and result.ok
    assert result.number == 2
    assert planned.inputs["source"].source == "workspace"
    assert "wynik z przestrzeni roboczej" in planned.summary()
    assert result.files["dem"][0].read_bytes() == produced.files["dem"][0].read_bytes()
    assert (
        saved[1]["inputs"]["source"]["sha256"]
        == hashlib.sha256(produced.files["dem"][0].read_bytes()).hexdigest()
    )
    assert (
        saved[1]["files"]["dem"][0]["sha256"]
        == hashlib.sha256(result.files["dem"][0].read_bytes()).hexdigest()
    )
    assert saved[1]["environment"]["tools"]["dummy_tool"] == "1.2.0"
    assert any(item["event"] == "execution" and item["number"] == 2 for item in journal)
    assert (
        json.loads((copier.workspace.root / "002_copy_dem" / "result.json").read_text())
        == saved[1]
    )


def test_workspace_multiple_matching_results_ask_even_when_newest(create_app):
    creator = create_app({"make_dem": "make_dem", "raw": "raw"})
    creator.execute(creator.plan(f"NMT dla {SHEET}").confirm())
    creator.execute(creator.plan(f"NMT dla {SHEET}").confirm())
    copier = create_app({"copy_dem": "copy_dem"})

    plan = copier.plan("Skopiuj ten NMT")
    chosen = plan.answer("source", "1")

    assert len(plan.questions[0].options) == 2
    assert chosen.inputs["source"].value["number"] == 1
    assert chosen.questions == []


def test_workspace_input_file_validated_before_handler(create_app):
    app = create_app({"copy_dem": "copy_dem"})
    source = app.workspace.project_dir / "file.asc"
    source.write_text("this is not a grid")

    invalid = app.plan("Skopiuj z pliku file.asc")
    source.write_bytes(
        b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\n"
        b"cellsize 1\nNODATA_value -9999\n3\n"
    )
    corrected = invalid.answer("source", "file.asc")

    assert invalid.questions[0].error
    assert corrected.inputs["source"].source == "user"
    assert corrected.inputs["source"].value["path"] == str(source)


def test_workspace_explicit_result_and_file_override_recent_result(create_app):
    creator = create_app({"make_dem": "make_dem", "raw": "raw"})
    first = creator.execute(creator.plan(f"NMT dla {SHEET}").confirm())
    creator.execute(creator.plan(f"NMT dla {SHEET}").confirm())
    copier = create_app({"copy_dem": "copy_dem"})
    selected_result = copier.plan("Skopiuj wynik #1")
    filename = first.files["dem"][0]
    selected_file = copier.plan(f"Skopiuj plik {filename}")

    assert selected_result.inputs["source"].value["number"] == 1
    assert selected_file.inputs["source"].value["path"] == str(filename)
    assert selected_file.inputs["source"].source == "command"


def test_journal_privacy_omits_raw_command_and_answers(create_app):
    app = create_app({"make_dem": "make_dem"}, journal_commands=False)
    plan = app.plan(f"NMT poufne dla {SHEET}").answer("style", "1")
    result = app.execute(plan.confirm())
    audit = json.loads(
        (app.workspace.root / "001_make_dem" / "result.json").read_text()
    )
    events = app.journal.entries()

    assert result.ok
    assert "command" not in audit
    assert all("command" not in event and "answer" not in event for event in events)
    assert "poufne" not in json.dumps(audit, ensure_ascii=False)
    assert all(
        "poufne" not in json.dumps(event, ensure_ascii=False) for event in events
    )
    assert "sha256" in audit["files"]["dem"][0]


def test_plan_round_trip_and_change_value_require_new_confirmation(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    plan = app.plan(f"NMT dla {SHEET}").confirm()
    restored = Plan.from_dict(json.loads(json.dumps(plan.to_dict())), retman=app)

    changed = restored.change("style")
    corrected = changed.answer("style", "2")

    assert restored.summary() == plan.summary()
    assert not changed.confirmed and changed.questions[0].name == "style"
    assert corrected.values["style"].value == "smooth"
    assert corrected.values["detail"].source == "default"
    assert not corrected.confirmed


def test_known_parameter_is_not_overwritten_by_model(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})
    known = {"style": "smooth", "detail": "low"}

    plan = app.plan(f"NMT dla {SHEET}", known=known)

    assert plan.values["style"].source == "known"
    assert plan.values["style"].value == "smooth"
    assert plan.values["detail"].value == "low"
    assert isinstance(app.backend, FakeDecisionBackend)
    assert all(call[2].get("raw") is None for call in app.backend.calls)


def test_known_invalid_value_is_not_silently_replaced(create_app):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})

    with pytest.raises(RetmanError) as caught:
        app.plan(f"NMT dla {SHEET}", known={"style": "not_a_style"})

    assert "Wybierz" in str(caught.value.text)
    assert (caught.value.code, caught.value.details["option"]) == (
        "validation_error",
        "style",
    )


def test_out_of_scope_command_lists_operations_instead_of_planning(create_app):
    app = create_app({"out_of_scope": "out_of_scope"})

    with pytest.raises(OutOfScopeError) as error:
        app.plan("Jaka będzie jutro pogoda w Poznaniu?")

    assert error.value.operations == [
        "Utworzenie NMT",
        "Kopia NMT",
        "Próba z błędem",
        "Próba zapisu poza wynikiem",
        "Zapis w magazynie narzędzia",
        "Pobranie NMT z katalogu narzędzia",
        "Wycinek NMT",
        "Wynik z ostrzeżeniami",
    ]
    assert "Utworzenie NMT" in str(error.value.text)
    assert (error.value.code, error.value.exit_code) == ("unsupported", 15)


@pytest.fixture
def cutout_app(create_app):
    """A cutout: its result system is read by code, not the model (ADR-009)."""
    app = create_app({"cut_dem": "cut_dem"})
    return app, app.backend


def _offered_crs(backend: FakeDecisionBackend) -> bool:
    return any("epsg_2180" in options for _, _, options in backend.calls)


def test_result_system_is_read_by_code_without_the_model(cutout_app):
    app, backend = cutout_app

    plan = app.plan(
        "Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045"
    )

    assert plan.values["target_crs"].value == "epsg_3045"
    assert plan.values["target_crs"].source == "command"
    assert not _offered_crs(backend)


def test_an_optional_parameter_left_unset_is_said_in_the_plan(cutout_app):
    app, _ = cutout_app

    plan = app.plan(
        "Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045"
    )
    masked = app.plan(
        "Daj NMT z x=530000 y=382000 x=530100 y=382100 w 2180, przelicz do 3045, "
        "przytnij do maska_a.shp"
    )

    assert not plan.questions
    assert "mask" not in plan.values
    assert (
        "Maska wycinka: bez maski (cały prostokąt) ← nie podano w "
        "poleceniu, parametr nieobowiązkowy"
    ) in plan.summary().splitlines()
    assert Plan.from_dict(plan.to_dict()).unset == plan.unset
    assert masked.values["mask"].value == "maska_a.shp"
    assert "bez maski" not in masked.summary()
    # An unset parameter can still be chosen with "z"
    changed = plan.change("mask")
    assert [question.name for question in changed.questions] == ["mask"]
    answered = changed.answer("mask", "maska_b.shp")
    assert answered.values["mask"].value == "maska_b.shp"
    assert "mask" not in answered.unset
    app.execute(plan.confirm())
    record = json.loads(
        (app.workspace.root / "001_cut_dem" / "result.json").read_text("utf-8")
    )
    assert record["unset"] == {"mask": "bez maski (cały prostokąt)"}


def test_system_of_the_rectangle_is_not_taken_for_the_result(cutout_app):
    app, backend = cutout_app

    plan = app.plan("Wytnij NMT x=530000 y=382000 x=530100 y=382100 PL-1992")

    assert "target_crs" not in plan.values
    assert "target_crs" in [question.name for question in plan.questions]
    assert not _offered_crs(backend)


def test_unsupported_result_system_asks_and_says_why(cutout_app):
    app, _ = cutout_app

    plan = app.plan("Wytnij NMT 16.90 52.40 16.91 52.41 do EPSG:2177")
    question = next(q for q in plan.questions if q.name == "target_crs")

    assert question.error is not None and "EPSG:2177" in question.error


def test_answer_with_bare_code_or_unsupported_system(cutout_app):
    app, _ = cutout_app
    plan = app.plan("Wytnij NMT 16.90 52.40 16.91 52.41")

    rejected = plan.answer("target_crs", "4326")
    accepted = plan.answer("target_crs", "2180")

    question = next(q for q in rejected.questions if q.name == "target_crs")
    assert question.error is not None and "EPSG:4326" in question.error
    assert accepted.values["target_crs"].value == "epsg_2180"
    assert accepted.values["target_crs"].source == "user"


def _uncertain_style(create_app, **kwargs):
    """Operation sure, style decided with confidence below the 0.9 threshold."""
    return create_app(
        {
            "make_dem": "make_dem",
            "raw": Decision("raw", {"raw": 0.6, "smooth": 0.4}, 0.6, "logprobs"),
        },
        thresholds=Thresholds(operation=0.7, parameter=0.9),
        **kwargs,
    )


def test_journal_keeps_what_the_model_chose_for_plans_never_executed(create_app):
    app = _uncertain_style(create_app)

    plan = app.plan(f"NMT dla {SHEET}").answer("style", "1")
    changed = plan.change("style").answer("style", "2")
    app.record_plan(changed, "rejected")
    plans = [e for e in app.journal.entries() if e["event"] == "plan"]

    assert [p["status"] for p in plans] == ["changed", "rejected"]
    # Which value the user corrected, without inferring it from later questions
    assert plans[0]["changed"] == "style"
    assert plans[0]["values"]["style"] == {"value": "raw", "source": "user"}
    assert plans[1]["values"]["style"] == {"value": "smooth", "source": "user"}
    # The model's choice and its confidence survive even though nothing ran
    style = next(d for d in plans[1]["decisions"] if d["name"] == "style")
    assert (style["key"], style["confidence"], style["method"]) == (
        "raw",
        0.6,
        "logprobs",
    )


def test_journal_records_out_of_scope_decision(create_app):
    app = create_app({"out_of_scope": "out_of_scope"})

    with pytest.raises(OutOfScopeError):
        app.plan("Jaka będzie jutro pogoda?")
    event = app.journal.entries()[-1]

    assert event["event"] == "out_of_scope"
    assert event["decisions"][0]["key"] == "out_of_scope"


def test_collection_is_off_unless_enabled(create_app, tmp_path: Path):
    app = create_app({"make_dem": "make_dem", "raw": "raw"})

    app.execute(app.plan(f"NMT dla {SHEET}").confirm())

    assert not (tmp_path / "collection").exists()


def test_collection_gathers_outcomes_with_commands_answers_and_decisions(
    create_app, tmp_path: Path
):
    app = _uncertain_style(create_app, collect=True, journal_commands=False)

    plan = app.plan(f"NMT dla {SHEET}").answer("style", "2")
    app.record_plan(plan, "rejected")
    app.execute(app.plan(f"NMT dla {SHEET}").answer("style", "1").confirm())
    with pytest.raises(OutOfScopeError):
        create_app({"out_of_scope": "out_of_scope"}, collect=True).plan("Pogoda?")
    lines = (tmp_path / "collection" / "collected.jsonl").read_text("utf-8")
    records = [json.loads(line) for line in lines.splitlines()]

    assert [r["status"] for r in records] == ["rejected", "approved", "out_of_scope"]
    rejected, approved, out_of_scope = records
    # Collected with explicit consent, even when the project journal omits texts
    assert rejected["command"] == f"NMT dla {SHEET}"
    assert rejected["answers"] == {"style": "2"}
    assert rejected["values"]["style"] == {"value": "smooth", "source": "user"}
    assert approved["result"] == {"ok": True, "error": None}
    assert approved["environment"]["tools"] == {"dummy_tool": "1.2.0"}
    assert out_of_scope["command"] == "Pogoda?"
    assert "url" not in json.dumps(records)

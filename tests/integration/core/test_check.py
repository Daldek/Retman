"""The availability check: a separate network step behind its own single-use consent."""

import json

import pytest

from retman.adapters.catalog import CatalogCall, ToolError
from retman.core.plan import Plan
from retman.exceptions import (
    CheckNotConfirmedError,
    PlanIncompleteError,
    PlanNotConfirmedError,
)
from retman.testing import FakeToolClient

SHEET = "N-34-130-D-d-2-4"
RULES = {"fetch_dem": "fetch_dem", "1m": "1m", "evrf2007": "evrf2007"}
AVAILABILITY = "query:elevation availability"


@pytest.fixture
def client() -> FakeToolClient:
    return FakeToolClient(documents={AVAILABILITY: {"complete": True}})


@pytest.fixture
def app(create_app, client):
    return create_app(RULES, clients={"dummy_tool": client})


@pytest.fixture
def plan(app) -> Plan:
    return app.plan(f"Pobierz NMT dla {SHEET} 1 m")


def test_the_check_is_offered_only_for_a_complete_plan_of_an_operation_that_has_one(
    app, create_app
):
    complete = app.plan(f"Pobierz NMT dla {SHEET} 1 m")
    incomplete = app.plan("Pobierz NMT")  # no sheet yet
    without_check = create_app({"make_dem": "make_dem", "raw": "raw"}).plan(
        f"NMT dla {SHEET}"
    )

    assert complete.can_check
    assert not incomplete.can_check and incomplete.questions
    assert not without_check.can_check
    with pytest.raises(PlanIncompleteError):
        incomplete.confirm_check()
    with pytest.raises(PlanIncompleteError):
        without_check.confirm_check()


def test_notice_says_what_the_step_contacts_before_the_user_agrees(plan):
    notice = plan.check_notice()

    assert "osobny krok i jedyny, który łączy się z internetem" in notice
    assert "Zapytam usługę testową o dane dla godła z planu." in notice


def test_check_without_its_own_consent_touches_nothing(app, plan, client):
    with pytest.raises(CheckNotConfirmedError):
        app.check(plan)
    # Confirming the plan is not consent to the check, and the reverse
    plan.confirm()
    with pytest.raises(CheckNotConfirmedError):
        app.check(plan)

    assert client.network_calls == []
    assert not plan.check_confirmed and plan.checks == []


def test_consent_to_the_check_does_not_confirm_the_plan(app, plan, client):
    plan.confirm_check()

    assert plan.check_confirmed and not plan.confirmed
    with pytest.raises(PlanNotConfirmedError):
        app.execute(plan)
    assert client.network_calls == []


def test_consent_is_single_use(app, plan, client):
    plan.confirm_check()
    app.check(plan)

    with pytest.raises(CheckNotConfirmedError):
        app.check(plan)
    assert [method for method, _ in client.network_calls] == ["query"]


def test_checking_informs_without_changing_the_plan_and_asks_for_new_approval(
    app, plan, client
):
    plan.confirm()
    before = {name: entry.value for name, entry in plan.values.items()}

    report = plan.confirm_check() and app.check(plan)

    # The values stay as they were; the user decides after reading the report
    assert {name: entry.value for name, entry in plan.values.items()} == before
    assert report.status == "available" and plan.checks == [report]
    assert not plan.confirmed and plan.confirmed_at is None
    assert "Sprawdzenie dostępności: dane dostępne" in plan.summary()
    assert plan.confirm().confirmed
    assert client.network_calls == [
        ("query", CatalogCall("elevation availability", {"resolution": "1m"}))
    ]


def test_a_check_creates_no_result_and_writes_nothing_in_the_workspace(
    app, plan, tmp_path
):
    plan.confirm_check()
    app.check(plan)

    assert not list(app.workspace.root.glob("[0-9]*"))
    assert [p.name for p in app.workspace.root.iterdir()] == ["journal.jsonl"]


def test_any_change_of_the_plan_withdraws_consent_and_the_old_report(app, plan):
    plan.confirm_check()
    app.check(plan)
    plan.confirm_check()

    changed = plan.change("resolution")

    assert not changed.check_confirmed and changed.checks == []
    assert "Sprawdzenie dostępności" not in changed.summary()
    # A restored plan never carries consent
    restored = Plan.from_dict(json.loads(json.dumps(plan.to_dict())), retman=app)
    assert not restored.check_confirmed
    assert restored.checks == plan.checks


def test_a_failed_check_is_a_report_and_the_plan_is_still_confirmable(create_app):
    def unreachable(call: CatalogCall):
        raise ToolError("dummy_tool", "no_coverage", "brak sieci")

    client = FakeToolClient(documents={AVAILABILITY: unreachable})
    app = create_app(RULES, clients={"dummy_tool": client})
    plan = app.plan(f"Pobierz NMT dla {SHEET} 1 m")

    plan.confirm_check()
    report = app.check(plan)

    assert report.status == "unknown"
    assert report.lines == [
        "Sprawdzenie nie powiodło się: Brak danych dla tego obszaru (brak sieci)."
    ]
    assert plan.confirm().confirmed


def test_the_journal_records_approved_declined_and_interrupted_checks(
    create_app, app, plan
):
    plan.confirm_check()
    app.check(plan)
    app.record_check(plan, "rejected")

    def interrupted(call: CatalogCall):
        raise KeyboardInterrupt

    other = create_app(
        RULES,
        clients={"dummy_tool": FakeToolClient(documents={AVAILABILITY: interrupted})},
    )
    stopped = other.plan(f"Pobierz NMT dla {SHEET} 1 m")
    stopped.confirm_check()
    with pytest.raises(KeyboardInterrupt):
        other.check(stopped)

    events = [e for e in app.journal.entries() if e["event"] == "check"]
    assert [(e["status"], e["result"]) for e in events] == [
        ("approved", "available"),
        ("rejected", None),
        ("approved", None),  # the attempt is on record although it was interrupted
    ]
    approved = events[0]
    assert approved["tool"] == "dummy_tool" and approved["lines"]
    # What was sent is what the plan said
    assert approved["values"]["resolution"]["value"] == "1m"


def test_declining_the_check_uses_no_network(app, plan, client):
    app.record_check(plan, "rejected")

    assert client.network_calls == []


def test_result_records_only_the_checks_of_the_final_plan(app, create_app, client):
    plan = app.plan(f"Pobierz NMT dla {SHEET} 1 m")
    plan.confirm_check()
    app.check(plan)
    final = plan.change("resolution").answer("resolution", "2")

    result = app.execute(final.confirm())
    recorded = json.loads(
        (
            app.workspace.root / f"{result.number:03d}_fetch_dem" / "result.json"
        ).read_text()
    )

    assert "checks" not in recorded  # the check described an older plan

    again = app.plan(f"Pobierz NMT dla {SHEET} 1 m")
    again.confirm_check()
    report = app.check(again)
    second = app.execute(again.confirm())
    saved = json.loads(
        (
            app.workspace.root / f"{second.number:03d}_fetch_dem" / "result.json"
        ).read_text()
    )

    assert saved["checks"] == [report.to_dict()]

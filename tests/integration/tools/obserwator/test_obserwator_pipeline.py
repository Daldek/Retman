"""A plan of operation 9 through the whole pipeline: questions, preview, no network.

The model is programmed, the station catalog is the synthetic one of the
evaluation and the client records every call: what is asserted is the gate of PRD
W-02 and N-12 for Obserwator. The year type is always asked when the command does
not state it, and nothing but offline questions reaches the tool before the user
confirms.
"""

from datetime import date
from pathlib import Path

import pytest
from obserwator_support import isolate_environment

from retman.adapters.catalog import CatalogCall, ToolDocument, ToolError
from retman.backends.base import Decision
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.eval.stations import synthetic_station_document
from retman.exceptions import RetmanError
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend, FakeToolClient
from retman.tools.obserwator import manifest as obserwator_manifest

RULES: dict[str, str | Decision] = {
    "obserwator_series": "obserwator_series",
    "export_station_series": "export_station_series",
    "pl_meteo_precip_daily": "pl_meteo_precip_daily",
    "server": "server",
}
COMMAND = "Pobierz dobowe opady ze stacji Poznań-Ławica z lat 2000–2020"


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_environment(monkeypatch)


def make_app(
    tmp_path: Path,
    store: dict[str, object] | None = None,
    rules: dict[str, str | Decision] = RULES,
) -> tuple[Retman, FakeToolClient]:
    operations = load_operations(
        "pl",
        manifests=[
            (obserwator_manifest.MANIFEST, Path(obserwator_manifest.__file__).parent)
        ],
        version_lookup=lambda _: "3.0.0",
    )
    client = FakeToolClient(
        documents={
            "stations find": lambda call: synthetic_station_document(call.options),
            "store info": {"result": store or {"exists": True, "supported": True}},
            "series summary": {"result": {"items": []}},
            "datasets files": {
                "result": {
                    "items": [
                        {"server_path": "dane/2000_o.zip"},
                        {"server_path": "dane/2020_12_o.zip"},
                    ]
                }
            },
        }
    )
    project = tmp_path / "project"
    project.mkdir()
    config = load_config(init_config(tmp_path / "config.toml"))
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations,
        clients={"obserwator": client},
        today=date(2026, 10, 19),
    )
    return app, client


def test_the_year_type_is_asked_when_the_command_does_not_state_it(tmp_path):
    app, client = make_app(tmp_path)

    plan = app.plan(COMMAND)

    assert plan.operation == "export_station_series"
    assert [question.name for question in plan.questions] == ["year_type"]
    assert plan.values["dataset"].value == "pl_meteo_precip_daily"
    assert plan.values["station"].value["code"] == "250000101"
    assert plan.values["period"].value == {"type": "years", "first": 2000, "last": 2020}
    # No preview and no confirmation while a question is open
    assert plan.preview_rows == []
    assert client.network_calls == []


def test_a_complete_plan_is_previewed_offline_and_offers_the_check(tmp_path):
    app, client = make_app(tmp_path)

    plan = app.plan(COMMAND).answer("year_type", "2")  # calendar years

    assert plan.questions == []
    assert plan.values["year_type"].value == "calendar"
    labels = [label for label, _ in plan.preview_rows]
    assert "Magazyn Obserwatora" in labels and "Pliki archiwów do sprawdzenia" in labels
    assert plan.can_check
    # Planning used the offline half of the client only
    assert client.network_calls == []
    assert {method for method, _ in client.calls} <= {"validate", "lookup"}
    assert not plan.confirmed


def test_a_store_that_does_not_exist_ends_planning_with_store_unavailable(tmp_path):
    rules: dict[str, str | Decision] = {
        "obserwator_series": "obserwator_series",
        "build_obserwator_series": "build_obserwator_series",
        "pl_meteo_precip_daily": "pl_meteo_precip_daily",
    }
    app, _ = make_app(tmp_path, {"exists": False, "supported": False}, rules)

    with pytest.raises(RetmanError) as caught:
        app.plan("Zbuduj szereg dobowych opadów")

    # No value of the command is at fault: the store is a matter of the configuration
    assert caught.value.code == "store_unavailable"
    assert caught.value.details["reason"] == "not_initialised"
    text = str(caught.value.text)
    assert f"({caught.value.details['path']})" in text
    assert "nie jest jeszcze utworzony" in text and "Utwórz magazyn Obserwatora" in text


def no_catalog(call: CatalogCall) -> ToolDocument:
    raise ToolError("obserwator", "not_found", "no station catalog", call=call)


def test_a_station_named_without_a_catalog_is_asked_for_not_widened(tmp_path):
    rules: dict[str, str | Decision] = {
        "obserwator_current": "obserwator_current",
        "fetch_current_observations": "fetch_current_observations",
        "hydro": "hydro",
    }
    app, client = make_app(tmp_path, rules=rules)
    client.documents = {**client.documents, "stations find": no_catalog}

    plan = app.plan("Pobierz aktualne dane hydrologiczne ze stacji Racibórz-Miedonia.")

    # The station is optional (no station: all of them), but a name was given
    (question,) = plan.questions
    assert question.name == "station"
    assert "Nie ma katalogu stacji IMGW" in str(question.error)
    assert "Zbuduj katalog stacji IMGW" in str(question.error)
    assert "station" not in plan.values

    plan = plan.answer("station", "150180060")

    assert plan.questions == []
    assert plan.values["station"].value["code"] == "150180060"


def test_a_required_station_without_a_catalog_says_why_only_codes_are_read(
    tmp_path,
):
    app, client = make_app(tmp_path)
    client.documents = {**client.documents, "stations find": no_catalog}

    plan = app.plan("Pobierz dobowe opady z lat 2000–2020")

    question = next(q for q in plan.questions if q.name == "station")
    assert "rozpoznaję tylko kody stacji" in str(question.error)

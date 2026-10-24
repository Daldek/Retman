"""A plan of operation 9 through the whole pipeline: questions, preview, no network.

The model is programmed, the station catalog is the synthetic one of the
evaluation and the client records every call: what is asserted is the gate of PRD
W-02 and N-12 for IMGWTools. The year type is always asked when the command does
not state it, and nothing but offline questions reaches the tool before the user
confirms.
"""

from datetime import date
from pathlib import Path

import pytest
from imgw_support import isolate_environment

from retman.backends.base import Decision
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.eval.stations import synthetic_station_document
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend, FakeToolClient
from retman.tools.imgwtools import manifest as imgw_manifest

RULES: dict[str, str | Decision] = {
    "imgw_series": "imgw_series",
    "export_station_series": "export_station_series",
    "pl_meteo_precip_daily": "pl_meteo_precip_daily",
    "server": "server",
}
COMMAND = "Pobierz dobowe opady ze stacji Poznań-Ławica z lat 2000–2020"


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_environment(monkeypatch)


def make_app(tmp_path: Path) -> tuple[Retman, FakeToolClient]:
    operations = load_operations(
        "pl",
        manifests=[(imgw_manifest.MANIFEST, Path(imgw_manifest.__file__).parent)],
        version_lookup=lambda _: "3.0.0",
    )
    client = FakeToolClient(
        documents={
            "stations find": lambda call: synthetic_station_document(call.options),
            "store info": {"result": {"exists": True, "supported": True}},
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
        FakeDecisionBackend(RULES),
        project,
        operations=operations,
        clients={"imgwtools": client},
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
    assert "Magazyn IMGW" in labels and "Pliki archiwów do sprawdzenia" in labels
    assert plan.can_check
    # Planning used the offline half of the client only
    assert client.network_calls == []
    assert {method for method, _ in client.calls} <= {"validate", "lookup"}
    assert not plan.confirmed

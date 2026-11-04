"""The offline stand-in of Obserwator used by ``retman eval run`` and its catalog."""

from pathlib import Path

import pytest
from obserwator_support import isolate_environment, settings_for

from retman.adapters.catalog import CatalogCall, ToolError
from retman.config import init_config, load_config
from retman.eval.offline import OfflineObserwatorClient, offline_clients
from retman.eval.stations import catalog_lookup, synthetic_station_items
from retman.registry.loader import load_operations
from retman.tools.obserwator import manifest as obserwator_manifest
from retman.tools.obserwator.client import ObserwatorClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> OfflineObserwatorClient:
    isolate_environment(monkeypatch)
    return OfflineObserwatorClient(ObserwatorClient(settings_for(tmp_path)))


def test_the_synthetic_catalog_serves_only_the_store_search_and_filters_it():
    everything = catalog_lookup(CatalogCall("stations find", {"source": "store"}))
    czech = catalog_lookup(
        CatalogCall("stations find", {"source": "store", "provider": "CHMI"})
    )
    river = catalog_lookup(
        CatalogCall("stations find", {"source": "store", "query": "wisl"})
    )

    assert everything["page"]["total"] == len(synthetic_station_items())
    assert len(everything["result"]) == len(synthetic_station_items())
    assert {item["provider"] for item in czech["result"]} == {"CHMI"}
    assert {item["river"] for item in river["result"]} == {"Wisła"}
    with pytest.raises(ToolError) as caught:
        catalog_lookup(CatalogCall("store info", {}))
    assert caught.value.tool_code == "not_found"


def test_the_stand_in_has_a_complete_store_and_never_runs_anything(client):
    summary = client.lookup(
        CatalogCall("series summary", {"dataset": "pl.imgw.hydro_daily"})
    )
    files = client.lookup(
        CatalogCall(
            "datasets files", {"dataset": "pl.imgw.meteo_precip_daily", "years": [2000]}
        )
    )

    assert client.lookup(CatalogCall("store info", {}))["result"]["supported"]
    assert {item["variable"] for item in summary["result"]} == {"H", "Q", "T"}
    assert files["page"]["total"] == 1  # a pure command goes to the real tool
    for method in (client.run, client.check, client.query):
        with pytest.raises(ToolError) as caught:
            method(CatalogCall("store sync", {}))
        assert caught.value.tool_code == "not_offline"


def test_an_evaluation_gets_the_stand_in_only_for_the_tool_that_needs_one(
    tmp_path, monkeypatch
):
    isolate_environment(monkeypatch)
    operations = load_operations(
        "pl",
        manifests=[
            (obserwator_manifest.MANIFEST, Path(obserwator_manifest.__file__).parent)
        ],
        version_lookup=lambda _: "3.0.0",
    )
    config = load_config(init_config(tmp_path / "config.toml"))

    clients = offline_clients(operations, config)
    without = offline_clients({}, config)

    assert list(clients) == ["obserwator"]
    assert isinstance(clients["obserwator"], OfflineObserwatorClient)
    assert without == {}

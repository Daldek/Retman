"""The offline stand-in of IMGWTools used by ``retman-eval`` and its catalog."""

from pathlib import Path

import pytest
from imgw_support import isolate_environment, settings_for

from retman.adapters.catalog import CatalogCall, ToolError
from retman.config import init_config, load_config
from retman.eval.offline import OfflineImgwClient, offline_clients
from retman.eval.stations import catalog_lookup, synthetic_station_items
from retman.registry.loader import load_operations
from retman.tools.imgwtools import manifest as imgw_manifest
from retman.tools.imgwtools.client import IMGWToolsClient


@pytest.fixture
def client(tmp_path, monkeypatch) -> OfflineImgwClient:
    isolate_environment(monkeypatch)
    return OfflineImgwClient(IMGWToolsClient(settings_for(tmp_path)))


def test_the_synthetic_catalog_serves_only_the_store_search_and_filters_it():
    everything = catalog_lookup(CatalogCall("stations find", {"source": "store"}))
    czech = catalog_lookup(
        CatalogCall("stations find", {"source": "store", "provider": "CHMI"})
    )
    river = catalog_lookup(
        CatalogCall("stations find", {"source": "store", "query": "wisl"})
    )

    assert everything["result"]["total"] == len(synthetic_station_items())
    assert {item["provider"] for item in czech["result"]["items"]} == {"CHMI"}
    assert {item["river"] for item in river["result"]["items"]} == {"Wisła"}
    with pytest.raises(ToolError) as caught:
        catalog_lookup(CatalogCall("store info", {}))
    assert caught.value.code == "not_found"


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
    assert {item["variable"] for item in summary["result"]["items"]} == {"H", "Q", "T"}
    assert files["result"]["total"] == 1  # a pure command goes to the real tool
    for method in (client.run, client.check, client.query):
        with pytest.raises(ToolError) as caught:
            method(CatalogCall("store sync", {}))
        assert caught.value.code == "not_offline"


def test_an_evaluation_gets_the_stand_in_only_for_the_tool_that_needs_one(
    tmp_path, monkeypatch
):
    isolate_environment(monkeypatch)
    operations = load_operations(
        "pl",
        manifests=[(imgw_manifest.MANIFEST, Path(imgw_manifest.__file__).parent)],
        version_lookup=lambda _: "3.0.0",
    )
    config = load_config(init_config(tmp_path / "config.toml"))

    clients = offline_clients(operations, config)
    without = offline_clients({}, config)

    assert list(clients) == ["imgwtools"]
    assert isinstance(clients["imgwtools"], OfflineImgwClient)
    assert without == {}

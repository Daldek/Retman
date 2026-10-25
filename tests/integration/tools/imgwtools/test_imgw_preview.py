"""The offline review of an IMGWTools plan: rows, questions asked again, blockers.

The real client reads the tool's fixture store; ``FakeToolClient`` stands in
where a store state is hard to build (no folder, wrong schema). Everything runs
through ``preview_operation`` as the pipeline does, so every problem and row key
is also resolved to its Polish text. Nothing may reach the network: planning gets
only ``PlanView``, and the suite's socket guard is on.
"""

from pathlib import Path
from typing import Any

import pytest
from imgw_store_files import write_layout, write_server_state
from imgw_support import (
    build_store,
    fixture_store,
    isolate_environment,
    real_client,
    settings_for,
)

from retman.adapters.catalog import CatalogCall, PlanView, ToolError
from retman.adapters.manifest_adapter import Preview, preview_operation
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import FakeToolClient, tool_context
from retman.tools.imgwtools import manifest as imgw_manifest
from retman.tools.imgwtools import preview as preview_module

TEXTS = load_core_texts("pl")
PRECIP = "pl_meteo_precip_daily"
READY = {"result": {"exists": True, "supported": True, "schema": "imgw-store/1"}}


@pytest.fixture(scope="module")
def operations() -> dict[str, Operation]:
    return load_operations(
        "pl",
        manifests=[(imgw_manifest.MANIFEST, Path(imgw_manifest.__file__).parent)],
        version_lookup=lambda _: "3.0.0",
    )


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_environment(monkeypatch)


def station(code: str, provider: str = "IMGW-PIB", kind: str = "meteo") -> dict:
    return {
        "type": "station",
        "provider": provider,
        "kind": kind,
        "code": code,
        "name": "S",
        "river": None,
        "in_catalog": True,
    }


WARSAW = station("123750000")
RABA = station("149190310", kind="hydro")
YEARS = {"type": "years", "first": 2000, "last": 2020}
JANUARY = {"type": "dates", "start": "2001-01-01", "end": "2001-01-31"}


def review(
    operations: dict[str, Operation],
    operation: str,
    params: dict[str, Any],
    tmp_path: Path,
    *,
    client: Any = None,
    store: Path | None = None,
) -> Preview:
    context = tool_context(
        operations[operation],
        client=PlanView(client if client is not None else real_client(tmp_path, store)),
        settings=settings_for(tmp_path, store),
        project_dir=tmp_path,
    )
    return preview_operation(operations[operation], params, context, TEXTS)


def series(**changes: Any) -> dict[str, Any]:
    return {
        "dataset": PRECIP,
        "station": WARSAW,
        "period": JANUARY,
        "year_type": "calendar",
        "data_source": "store",
        **changes,
    }


# --- the store itself -----------------------------------------------------------------


def fake_store(info: dict[str, Any]) -> FakeToolClient:
    return FakeToolClient(documents={"store info": {"result": info}})


def test_a_store_that_does_not_exist_blocks_every_operation_that_needs_it(
    operations, tmp_path
):
    client = fake_store({"exists": False, "supported": False, "schema": None})

    result = review(
        operations, "build_imgw_series", {"dataset": PRECIP}, tmp_path, client=client
    )

    (problem,) = result.problems
    assert problem.params == ()
    assert problem.text.startswith("Magazyn IMGW (")
    assert (
        "nie jest jeszcze utworzony" in problem.text
        and "retman config init" in problem.text
    )
    assert result.rows == []


def test_an_empty_folder_is_not_initialised_but_a_foreign_one_is_refused(
    operations, tmp_path
):
    folder = tmp_path / "folder"
    folder.mkdir()
    client = fake_store({"exists": True, "supported": False, "schema": None})

    empty = review(
        operations,
        "build_imgw_series",
        {"dataset": PRECIP},
        tmp_path,
        client=client,
        store=folder,
    )
    (folder / "notatki.txt").write_text("nie magazyn", encoding="utf-8")
    foreign = review(
        operations,
        "build_imgw_series",
        {"dataset": PRECIP},
        tmp_path,
        client=client,
        store=folder,
    )

    assert "nie jest jeszcze utworzony" in empty.problems[0].text
    assert "zawiera inne pliki i nie jest magazynem IMGW" in foreign.problems[0].text


def test_a_layout_without_a_marker_is_named_and_a_key_file_is_not_content(
    operations, tmp_path
):
    client = fake_store({"exists": True, "supported": False, "schema": None})
    unmarked, keys = tmp_path / "unmarked", tmp_path / "keys"
    unmarked.mkdir()
    keys.mkdir()
    write_layout(unmarked, "archives")
    write_server_state(keys)

    def problem(folder: Path) -> str:
        result = review(
            operations,
            "build_imgw_series",
            {"dataset": PRECIP},
            tmp_path,
            client=client,
            store=folder,
        )
        (found,) = result.problems
        assert found.params == ()
        return found.text

    assert "ma układ magazynu IMGW, ale nie ma znacznika" in problem(unmarked)
    assert "nie jest jeszcze utworzony" in problem(keys)


def test_a_marker_the_tool_cannot_read_is_named_and_not_taken_for_other_files(
    operations, tmp_path
):
    damaged = tmp_path / "damaged"
    damaged.mkdir()
    (damaged / "imgw-store.json").write_text("{", encoding="utf-8")
    client = fake_store({"exists": True, "supported": False, "schema": None})

    result = review(
        operations,
        "build_imgw_series",
        {"dataset": PRECIP},
        tmp_path,
        client=client,
        store=damaged,
    )

    # The tool raises data_error (invalid_marker) for it in a plan and in a run
    (problem,) = result.problems
    assert problem.params == ()
    assert "imgw-store.json" in problem.text and "jest nieczytelny" in problem.text
    assert "inne pliki" not in problem.text


def test_a_store_of_another_schema_is_named(operations, tmp_path):
    client = fake_store({"exists": True, "supported": False, "schema": "imgw-store/9"})

    result = review(
        operations, "build_imgw_series", {"dataset": PRECIP}, tmp_path, client=client
    )

    assert "imgw-store/9" in result.problems[0].text


def test_a_store_that_is_there_but_cannot_write_series_needs_pyarrow(
    operations, tmp_path, monkeypatch
):
    monkeypatch.setattr(preview_module, "tool_installed", lambda name: False)
    client = FakeToolClient(
        documents={"store info": READY, "series summary": {"result": {"items": []}}}
    )

    writing = review(
        operations, "build_imgw_series", {"dataset": PRECIP}, tmp_path, client=client
    )
    reading = review(
        operations,
        "show_station_coverage",
        {"dataset": PRECIP},
        tmp_path,
        client=client,
    )

    assert writing.problems[0].text.startswith("Do szeregów w magazynie IMGW potrzebny")
    assert writing.problems[0].params == ()
    # Reading a series (Parquet index) is not what pyarrow is needed for here
    assert all("pyarrow" not in problem.text for problem in reading.problems)


# --- station series ------------------------------------------------------------------


def test_a_series_in_the_store_shows_what_the_store_covers(operations, tmp_path):
    result = review(operations, "export_station_series", series(), tmp_path)

    assert result.problems == []
    assert result.rows == [
        ("Magazyn IMGW", f"{fixture_store()} (z konfiguracji)"),
        ("Dane w magazynie", "2001-01-01 – 2001-01-31, luk: 0"),
    ]
    assert result.values["store_coverage"] == {
        "first": "2001-01-01",
        "last": "2001-01-31",
        "gaps": 0,
    }


def test_a_period_the_store_covers_only_in_part_says_so(operations, tmp_path):
    wider = {"type": "dates", "start": "2000-12-01", "end": "2001-02-28"}

    result = review(operations, "export_station_series", series(period=wider), tmp_path)

    assert result.problems == []
    assert result.rows[-1] == (
        "Okres w magazynie",
        "magazyn pokrywa tylko część wybranego okresu (2001-01-01 – 2001-01-31)",
    )


@pytest.mark.parametrize(
    ("changes", "asked", "text"),
    [
        (
            {"period": {"type": "dates", "start": "1990-01-01", "end": "1990-12-31"}},
            ("period",),
            "Magazyn ma dane tej stacji tylko za okres 2001-01-01 – 2001-01-31",
        ),
        (
            {"station": station("999999999")},
            ("station", "data_source"),
            "Stacji 999999999 nie ma w szeregu zbioru pl.imgw.meteo_precip_daily",
        ),
        (
            {
                "dataset": "pl_hydro_semiannual",
                "station": RABA,
                "year_type": "hydrological",
            },
            ("data_source",),
            "Magazyn IMGW nie ma szeregu zbioru pl.imgw.hydro_semiannual",
        ),
    ],
)
def test_what_the_store_cannot_serve_is_asked_again_not_found_out_later(
    operations, tmp_path, changes, asked, text
):
    result = review(operations, "export_station_series", series(**changes), tmp_path)

    (problem,) = result.problems
    assert problem.params == asked
    assert text in problem.text


def test_from_the_server_the_missing_series_is_fine_and_the_archives_are_counted(
    operations, tmp_path
):
    params = series(
        dataset="pl_hydro_daily",
        station=RABA,
        period=YEARS,
        year_type="hydrological",
        data_source="server",
    )

    result = review(operations, "export_station_series", params, tmp_path)

    assert result.problems == []
    # 21 hydrological years x 12 monthly country files
    assert result.values["archive_files"] == 252
    assert (
        "Pliki archiwów do sprawdzenia",
        "najwyżej 252: od codz_2000_01.zip do codz_2020_12.zip; "
        "rozmiar nieznany bez sprawdzenia w sieci",
    ) in result.rows
    assert result.rows[0][0] == "Magazyn IMGW"


def test_a_station_the_series_does_not_have_yet_is_not_an_error_from_the_server(
    operations, tmp_path
):
    params = series(station=station("111111111"), data_source="server", period=YEARS)

    result = review(operations, "export_station_series", params, tmp_path)

    assert result.problems == []
    assert (
        "Dane w magazynie",
        "stacji nie ma jeszcze w szeregu; pojawi się po pobraniu archiwów",
    ) in result.rows


def test_years_the_tool_does_not_have_send_the_user_back_to_the_period(
    operations, tmp_path
):
    params = series(
        dataset="pl_hydro_daily",
        station=RABA,
        period={"type": "years", "first": 1900, "last": 1905},
        year_type="hydrological",
        data_source="server",
    )

    result = review(operations, "export_station_series", params, tmp_path)

    (problem,) = result.problems
    assert problem.params == ("period",)
    assert problem.text.startswith("IMGWTools odrzuca ten wybór:")


def test_the_coverage_of_all_stations_says_so_and_a_wrong_station_is_asked_again(
    operations, tmp_path
):
    everything = review(
        operations, "show_station_coverage", {"dataset": PRECIP}, tmp_path
    )
    wrong = review(
        operations,
        "show_station_coverage",
        {"dataset": PRECIP, "station": [station("999999999")]},
        tmp_path,
    )
    empty = review(
        operations,
        "show_station_coverage",
        {"dataset": "pl_hydro_semiannual"},
        tmp_path,
    )

    assert (
        "Stacje",
        "wszystkie stacje zbioru pl.imgw.meteo_precip_daily",
    ) in everything.rows
    assert [p.params for p in wrong.problems] == [("station",)]
    assert [p.params for p in empty.problems] == [("dataset",)]


# --- catalog and PMAXTP ---------------------------------------------------------------


def test_a_search_in_the_store_counts_the_matching_stations(operations, tmp_path):
    result = review(
        operations,
        "find_imgw_stations",
        {"data_source": "store", "provider": "chmi", "kind": "hydro"},
        tmp_path,
    )
    server = review(
        operations, "find_imgw_stations", {"data_source": "server"}, tmp_path
    )

    assert result.problems == []
    assert ("Pasujące stacje", "3 w katalogu magazynu") in result.rows
    assert result.values == {"matches": 3}
    # The server needs no store: nothing to review before the user confirms
    assert (server.rows, server.problems) == ([], [])


def test_a_store_without_a_station_catalog_sends_the_user_to_the_server(
    operations, tmp_path
):
    import imgwtools

    store = tmp_path / "empty-store"
    imgwtools.run_command("store init", options={"root": str(store)})

    result = review(
        operations,
        "find_imgw_stations",
        {"data_source": "store"},
        tmp_path,
        store=store,
    )

    (problem,) = result.problems
    assert problem.params == ("data_source",)
    assert "nie ma katalogu stacji" in problem.text


def test_the_catalog_build_names_the_reference_file_and_checks_the_users_locations(
    operations, tmp_path
):
    good = tmp_path / "polozenia.csv"
    good.write_text("station_code,latitude,longitude\n150000101,50.1,19.9\n", "utf-8")
    bad = tmp_path / "zle.csv"
    bad.write_text("kod;szerokosc\n1;2\n", "utf-8")

    plain = review(
        operations, "build_imgw_station_catalog", {"provider": "imgw_pib"}, tmp_path
    )
    (tmp_path / "reference" / "hydro_stations_locations.csv").write_text(
        "station_code,latitude,longitude\n", "utf-8"
    )
    with_file = review(
        operations,
        "build_imgw_station_catalog",
        {"provider": "imgw_pib", "user_locations": "polozenia.csv"},
        tmp_path,
    )
    invalid = review(
        operations,
        "build_imgw_station_catalog",
        {"provider": "imgw_pib", "user_locations": "zle.csv"},
        tmp_path,
    )
    missing = review(
        operations,
        "build_imgw_station_catalog",
        {"provider": "imgw_pib", "user_locations": "nie-ma.csv"},
        tmp_path,
    )
    czech = review(
        operations, "build_imgw_station_catalog", {"provider": "chmi"}, tmp_path
    )

    assert plain.rows[1][0] == "Położenia stacji (plik statyczny)"
    assert plain.rows[1][1].startswith("brak pliku hydro_stations_locations.csv")
    assert with_file.rows[1][1].startswith("hydro_stations_locations.csv w folderze")
    assert ("Plik z położeniami stacji", "polozenia.csv (1 stacji)") in with_file.rows
    assert [p.params for p in invalid.problems] == [("user_locations",)]
    assert "kolumnami station_code, latitude i longitude" in invalid.problems[0].text
    assert [p.params for p in missing.problems] == [("user_locations",)]
    assert "Nie można odczytać pliku" in missing.problems[0].text
    # The static file is IMGW-PIB's only
    assert [label for label, _ in czech.rows] == ["Magazyn IMGW"]


def test_current_data_say_when_the_answer_is_the_whole_list(operations, tmp_path):
    everything = review(
        operations, "fetch_current_observations", {"source": "hydro"}, tmp_path
    )
    one = review(
        operations,
        "fetch_current_observations",
        {"source": "hydro", "station": RABA},
        tmp_path,
    )
    synop = review(
        operations, "fetch_current_observations", {"source": "synop"}, tmp_path
    )
    both = review(operations, "fetch_imgw_warnings", {}, tmp_path)
    hydro = review(operations, "fetch_imgw_warnings", {"kind": "hydro"}, tmp_path)

    assert everything.rows == [
        ("Zakres", "wszystkie stacje hydrologiczne IMGW-PIB (cała lista)")
    ]
    assert one.rows == []
    assert synop.rows == [
        ("Zakres", "wszystkie stacje synoptyczne IMGW-PIB (cała lista)")
    ]
    assert both.rows == [("Rodzaj ostrzeżeń", "hydrologiczne i meteorologiczne")]
    assert hydro.rows == []


def pmaxtp(**changes: Any) -> dict[str, Any]:
    return {
        "point": {"type": "point", "latitude": 52.23, "longitude": 21.01},
        "method": "pot",
        "storage": "none",
        **changes,
    }


def test_pmaxtp_in_the_store_needs_the_store_and_the_point_must_lie_in_poland(
    operations, tmp_path
):
    plain = review(operations, "get_pmaxtp", pmaxtp(), tmp_path)
    stored = review(operations, "get_pmaxtp", pmaxtp(storage="store"), tmp_path)
    outside = review(
        operations,
        "get_pmaxtp",
        pmaxtp(point={"type": "point", "latitude": 10.0, "longitude": 21.0}),
        tmp_path,
    )

    assert (plain.rows, plain.problems) == ([], [])
    assert stored.rows == [("Magazyn IMGW", f"{fixture_store()} (z konfiguracji)")]
    assert [p.params for p in outside.problems] == [("point",)]


def test_a_cell_the_store_does_not_hold_is_asked_again(operations, tmp_path):
    cell = {"type": "grid_cell", "ind_x": 751, "ind_y": 317}

    missing = review(
        operations, "read_stored_pmaxtp", {"cell": cell, "method": "pot"}, tmp_path
    )

    (problem,) = missing.problems
    assert problem.params == ("cell", "method")
    assert "komórki PMAXTP 751/317 (metoda POT)" in problem.text


def test_a_stored_cell_is_shown_with_its_point(operations, tmp_path):
    cell = {"type": "grid_cell", "ind_x": 751, "ind_y": 317}
    document = {"result": {"method": "POT", "latitude": 52.25, "longitude": 21.0}}
    client = FakeToolClient(documents={"store info": READY, "pmaxtp read": document})

    result = review(
        operations,
        "read_stored_pmaxtp",
        {"cell": cell, "method": "pot"},
        tmp_path,
        client=client,
    )

    assert result.problems == []
    assert (
        "Komórka w magazynie",
        "751/317 (metoda POT), punkt 52.25°N, 21.0°E",
    ) in result.rows


def test_building_a_series_names_the_store_and_needs_it_ready(operations, tmp_path):
    store = build_store(tmp_path / "ready")

    result = review(
        operations, "build_imgw_series", {"dataset": PRECIP}, tmp_path, store=store
    )

    assert result.problems == []
    assert result.rows == [("Magazyn IMGW", f"{store} (z konfiguracji)")]


def test_a_review_asks_the_tool_only_offline_questions(operations, tmp_path):
    client = FakeToolClient(
        documents={
            "store info": READY,
            "series summary": {"result": {"items": []}},
            "datasets files": {"result": {"items": []}},
        }
    )

    review(
        operations,
        "export_station_series",
        series(data_source="server"),
        tmp_path,
        client=client,
    )
    review(
        operations,
        "show_station_coverage",
        {"dataset": PRECIP},
        tmp_path,
        client=client,
    )

    assert client.network_calls == []
    assert {method for method, _ in client.calls} <= {"validate", "lookup"}


def test_an_error_of_a_lookup_that_is_not_an_answer_is_not_swallowed(
    operations, tmp_path
):
    def broken(call: CatalogCall) -> dict:
        raise ToolError("imgwtools", "data_error", "uszkodzony szereg", call=call)

    client = FakeToolClient(documents={"store info": READY, "series summary": broken})

    with pytest.raises(ToolError, match="uszkodzony szereg"):
        review(
            operations,
            "show_station_coverage",
            {"dataset": PRECIP},
            tmp_path,
            client=client,
        )

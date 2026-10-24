"""Results of the IMGWTools operations 1–11: real documents, mapped and validated.

Each test runs an operation through the same ``execute_operation`` the pipeline
uses, with the real client: store-reading commands read the tool's offline
fixture store, live ones are answered by recorded HTTP, and only the commands
that cannot be replayed offline (a store synchronisation, the catalog build)
return runs built from the tool's own result objects. What is asserted is what
reaches the user: the files (kind-validated by ``execute_operation``), the
values, the summary rendered from the operation's template and the warnings.
"""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from imgw_support import (
    PMAXTP_URL,
    HybridClient,
    build_store,
    fixture_store,
    isolate_environment,
    pmaxtp_payload,
    real_client,
    recorded_answers,
    replay_http,
    settings_for,
    synthetic_run,
)

from retman.adapters.catalog import ToolNotice
from retman.adapters.manifest_adapter import execute_operation
from retman.core.result import Result
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import tool_context
from retman.tools.imgwtools import describe
from retman.tools.imgwtools import manifest as imgw_manifest

TEXTS = load_core_texts("pl")
FROZEN = datetime(2026, 10, 19, 12, 30, 5, tzinfo=UTC)
STAMP = "20261019T123005Z"
IMGW_LICENSE_START = "Źródłem pochodzenia danych jest Instytut Meteorologii"
IMGW_LICENSE_END = "także wyjątków dla danych o wysokiej wartości."
PRECIP = "pl.imgw.meteo_precip_daily"
MISSING_PROBABILITY = (
    "W tabeli PMAXTP nie ma prawdopodobieństwa 30 %; dostępne: 1, 2, 5, 10, 20, 50 %."
)


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
    monkeypatch.setattr(describe, "utc_now", lambda: FROZEN)


def execute(
    operations: dict[str, Operation],
    operation: str,
    params: dict[str, Any],
    tmp_path: Path,
    *,
    client: Any = None,
    store: Path | None = None,
) -> Result:
    # Every call gets a project folder of its own: result numbers start at 1 again
    work = tmp_path / f"run{len(list(tmp_path.glob('run*'))) + 1}"
    folder = work / "001_result"
    folder.mkdir(parents=True)
    context = tool_context(
        operations[operation],
        client=client if client is not None else real_client(tmp_path, store),
        settings=settings_for(tmp_path, store),
        project_dir=work,
        output_dir=folder,
    )
    return execute_operation(
        operations[operation], params, {}, folder, 1, {}, {}, TEXTS, context
    )


def table(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


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


def audit_commands(result: Result) -> list[str]:
    assert result.tool is not None
    return [call["command"] for call in result.tool["calls"]]


# --- 1–3: catalog -------------------------------------------------------------------


def test_stations_become_a_station_list_with_the_licence_of_each_provider(
    operations, tmp_path
):
    result = execute(
        operations,
        "find_imgw_stations",
        {"data_source": "store", "kind": "hydro"},
        tmp_path,
    )

    assert result.ok, result.error
    (path,) = result.files["station_list"]
    assert path.name == "stations_hydro.csv"
    rows = table(path)
    assert list(rows[0]) == list(describe.STATION_COLUMNS)
    assert {(row["provider"], row["kind"]) for row in rows} == {
        ("IMGW-PIB", "hydro"),
        ("CHMI", "hydro"),
    }
    assert len(rows) == 6
    assert result.values["count"] == 6
    assert result.values["providers"] == ["CHMI", "IMGW-PIB"]
    assert result.values["data_source"] == "store"
    assert result.values["fetched_at"] == "2026-10-19T12:30:05Z"
    assert result.summary == "Gotowe. Wynik #1: lista stacji (6) zapisana w pliku CSV."
    # Each provider's terms, verbatim, once; nothing else is a warning
    assert len(result.warnings) == 2
    imgw = next(text for text in result.warnings if "IMGW-PIB" in text)
    assert imgw.startswith(IMGW_LICENSE_START) and imgw.endswith(IMGW_LICENSE_END)
    assert any("CC BY 4.0" in text and "ČHMÚ" in text for text in result.warnings)
    assert audit_commands(result) == ["stations find", "datasets providers"]


def test_a_query_names_the_file_and_a_search_without_matches_says_so(
    operations, tmp_path
):
    found = execute(
        operations,
        "find_imgw_stations",
        {
            "data_source": "store",
            "provider": "imgw_pib",
            "query": {"type": "query", "text": "raba", "raw": "Rabie"},
        },
        tmp_path,
    )
    nothing = execute(
        operations,
        "find_imgw_stations",
        {
            "data_source": "store",
            "query": {"type": "query", "text": "zzzz", "raw": "Zzzz"},
        },
        tmp_path,
    )

    assert [path.name for path in found.files["station_list"]] == [
        "stations_imgw_pib_raba.csv"
    ]
    assert found.values["count"] == 3
    assert nothing.ok and nothing.values["count"] == 0
    assert table(nothing.files["station_list"][0]) == []
    assert "Narzędzie nie zwróciło żadnych wierszy." in nothing.warnings


def test_the_registry_and_the_providers_are_kept_as_the_tools_documents(
    operations, tmp_path
):
    result = execute(operations, "list_imgw_datasets", {"provider": "chmi"}, tmp_path)

    assert result.ok, result.error
    names = [path.name for path in result.files["imgw_report"]]
    assert names == ["datasets.json", "providers.json"]
    datasets = json.loads(result.files["imgw_report"][0].read_text("utf-8"))
    assert datasets["schema"] == "imgw-result/1"
    assert {item["provider"] for item in datasets["result"]["items"]} == {"CHMI"}
    assert result.values == {
        "calls": 2,
        "file_count": 2,
        "datasets": 4,
        "providers": 2,
    }
    assert result.summary == "Gotowe. Wynik #1: zbiorów danych: 4, dostawców: 2."


def catalog_report(**changes: Any) -> Any:
    from imgwtools import CatalogReport

    fields: dict[str, Any] = {
        "status": "created",
        "version": Path(
            "/store/stations/versions/2026-10-19_ab12cd34/stations.geojson"
        ),
        "station_count": 812,
        "without_location": 7,
        "from_series": 3,
        "problems": ("Lista meteo niedostępna",),
        "provider": "IMGW-PIB",
    }
    return CatalogReport(**{**fields, **changes})


def test_a_built_catalog_reports_what_it_holds_and_what_is_missing(
    operations, tmp_path
):
    # The tool reports each catalog problem in the report AND as a notice
    problem = ToolNotice("warning", "catalog_problem", "Lista meteo niedostępna")
    notice = ToolNotice("info", "license_terms", "Warunki użycia danych IMGW.")
    client = HybridClient(
        real_client(tmp_path),
        {
            "store catalog": synthetic_run(
                "store catalog", catalog_report(), notices=(problem, notice)
            )
        },
    )

    result = execute(
        operations,
        "build_imgw_station_catalog",
        {"provider": "imgw_pib"},
        tmp_path,
        client=client,
    )

    assert result.ok, result.error
    assert result.files == {}
    assert result.values["station_count"] == 812
    assert result.values["catalog_version"].endswith("stations.geojson")
    assert result.summary == (
        "Gotowe. Wynik #1: katalog stacji IMGW-PIB w magazynie "
        "(812 stacji, bez położenia: 7, stan: created)."
    )
    # ... and the result shows it once
    assert result.warnings == [
        "Narzędzie imgwtools: Lista meteo niedostępna",
        "7 stacji katalogu nie ma położenia (współrzędnych); można je uzupełnić "
        "plikiem z położeniami stacji.",
        "Warunki użycia danych IMGW.",
    ]


# --- 4–6: live data -----------------------------------------------------------------


def test_current_data_are_a_csv_of_the_kind_of_the_source(operations, tmp_path):
    answers = recorded_answers()

    with replay_http(answers["synop_current"]):
        synop = execute(
            operations,
            "fetch_current_observations",
            {"source": "synop"},
            tmp_path,
        )
    with replay_http(answers["hydro_current_station"]):
        hydro = execute(
            operations,
            "fetch_current_observations",
            {"source": "hydro", "station": station("149190310", kind="hydro")},
            tmp_path,
        )

    assert synop.ok, synop.error
    (synop_file,) = synop.files["current_synop"]
    assert synop_file.name == f"synop_current_{STAMP}.csv"
    assert [row["station_name"] for row in table(synop_file)] == [
        "Warszawa",
        "Raba Górna",
    ]
    assert synop.values["rows"] == 2 and synop.values["source"] == "synop"
    assert synop.summary == (
        "Gotowe. Wynik #1: aktualne dane stacji, wierszy: 2 "
        "(pobrano 2026-10-19T12:30:05Z)."
    )
    (hydro_file,) = hydro.files["current_hydro"]
    (row,) = table(hydro_file)
    assert (row["station_code"], row["water_level_cm"], row["flow_m3s"]) == (
        "149190310",
        "182.0",
        "3.41",
    )
    # The data of IMGW-PIB carry its terms, taken from the provider registry
    assert len(hydro.warnings) == 1
    assert hydro.warnings[0].startswith(IMGW_LICENSE_START)
    assert audit_commands(hydro) == ["current hydro", "datasets providers"]


def test_warnings_are_counted_and_the_highest_level_is_kept(operations, tmp_path):
    answers = recorded_answers()

    with replay_http(answers["warnings_hydro"], answers["warnings_meteo"]):
        result = execute(operations, "fetch_imgw_warnings", {}, tmp_path)

    assert result.ok, result.error
    rows = table(result.files["imgw_warnings"][0])
    assert [(row["id"], row["kind"], row["level"]) for row in rows] == [
        ("17", "hydro", "1"),
        ("77", "meteo", "2"),
    ]
    assert result.values["rows"] == 2 and result.values["highest_level"] == 2
    assert result.summary == "Gotowe. Wynik #1: ostrzeżeń w mocy: 2."


def test_hydro_states_are_counted_by_state(operations, tmp_path):
    answers = recorded_answers()

    with replay_http(answers["hydro_states"]):
        result = execute(
            operations, "fetch_hydro_states", {"main_only": False}, tmp_path
        )

    assert result.ok, result.error
    assert len(table(result.files["hydro_states"][0])) == 3
    assert result.values["by_state"] == {"medium": 1, "low": 1, "unknown": 1}
    assert result.summary == "Gotowe. Wynik #1: stanów wody stacji: 3."


# --- 7–8: PMAXTP --------------------------------------------------------------------

POINT = {"type": "point", "latitude": 52.23, "longitude": 21.01}


def pmaxtp_answer(method: str = "P") -> dict[str, Any]:
    url = PMAXTP_URL.format(method=method, lat="52.2300", lon="21.0100")
    return {"url": url, "json": pmaxtp_payload()}


def test_a_pmaxtp_table_is_narrowed_by_probability_and_duration(operations, tmp_path):
    params = {
        "point": POINT,
        "method": "pot",
        "storage": "none",
        "probability": [0.01, 0.1],
        "duration": [15, 60],
    }

    with replay_http(pmaxtp_answer()):
        result = execute(operations, "get_pmaxtp", params, tmp_path)

    assert result.ok, result.error
    (path,) = result.files["pmaxtp_table"]
    assert path.name == "pmaxtp_pot_52.23_21.01.csv"
    rows = table(path)
    assert [(r["duration_min"], r["probability_percent"]) for r in rows] == [
        ("15", "1"),
        ("15", "10"),
        ("60", "1"),
        ("60", "10"),
    ]
    # The attribution columns are filled once, in the first row, like the tool's own
    assert rows[0]["attribution_source"].startswith("Źródłem pochodzenia danych")
    assert rows[0]["attribution_processed"].startswith("Dane Instytutu")
    assert rows[1]["attribution_source"] == ""
    assert result.values["durations_min"] == [15, 30, 45, 60, 90, 120, 180]
    assert result.values["probabilities_percent"] == [1, 2, 5, 10, 20, 50]
    assert result.values["rows"] == 4
    assert [row["duration_min"] for row in result.values["selected"]] == [
        15,
        15,
        60,
        60,
    ]
    assert result.values["method"] == "POT"
    assert "cell" not in result.values
    assert result.summary == (
        "Gotowe. Wynik #1: tabela PMAXTP (metoda POT) dla punktu 52.23°N, 21.01°E, "
        "wierszy: 4."
    )


def test_what_the_table_lacks_is_reported_and_an_empty_selection_gives_the_table(
    operations, tmp_path
):
    partly = {
        "point": POINT,
        "method": "pot",
        "storage": "none",
        "probability": [0.01, 0.3],
        "duration": [15],
    }
    nothing = {**partly, "probability": [0.3], "duration": [20]}

    with replay_http(pmaxtp_answer()):
        some = execute(operations, "get_pmaxtp", partly, tmp_path)
    with replay_http(pmaxtp_answer()):
        none = execute(operations, "get_pmaxtp", nothing, tmp_path)

    assert some.values["rows"] == 1
    assert some.warnings[0] == MISSING_PROBABILITY
    assert none.values["rows"] == 42  # the whole table: 7 durations x 6 probabilities
    assert none.warnings[:3] == [
        MISSING_PROBABILITY,
        "W tabeli PMAXTP nie ma czasu trwania 20 min; "
        "dostępne: 15, 30, 45, 60, 90, 120, 180 min.",
        "Żadna z żądanych wartości nie występuje w tabeli PMAXTP; "
        "zapisano całą tabelę.",
    ]


def test_a_stored_pmaxtp_cell_is_named_and_can_be_read_back_offline(
    operations, tmp_path
):
    store = build_store(tmp_path / "store")
    sync = {
        "point": POINT,
        "method": "pot",
        "storage": "store",
        "probability": [0.01],
        "duration": [15],
    }

    with replay_http(pmaxtp_answer()):
        stored = execute(operations, "get_pmaxtp", sync, tmp_path, store=store)
    read = execute(
        operations,
        "read_stored_pmaxtp",
        {
            "cell": {"type": "grid_cell", "ind_x": 751, "ind_y": 317},
            "method": "pot",
        },
        tmp_path,
        store=store,
    )

    assert stored.ok, stored.error
    assert stored.values["cell"] == {"ind_x": 751, "ind_y": 317}
    assert stored.values["version"].startswith("pmaxtp/versions/POT/751_317/") or (
        "/pmaxtp/versions/POT/751_317/" in stored.values["version"]
    )
    # The tool's own licence notice (a new version) is passed on verbatim
    assert any(text.startswith(IMGW_LICENSE_START) for text in stored.warnings)
    assert read.ok, read.error
    (path,) = read.files["pmaxtp_table"]
    assert path.name == "pmaxtp_pot_751_317.csv"
    assert len(table(path)) == 42
    assert read.values["cell"] == {"ind_x": 751, "ind_y": 317}
    assert read.summary == (
        "Gotowe. Wynik #1: tabela PMAXTP komórki 751/317 (metoda POT), wierszy: 42."
    )


# --- 9–11: station series -----------------------------------------------------------


def export_params(**changes: Any) -> dict[str, Any]:
    return {
        "dataset": "pl_meteo_precip_daily",
        "station": station("123750000"),
        "period": {"type": "dates", "start": "2001-01-01", "end": "2001-01-31"},
        "year_type": "calendar",
        "data_source": "store",
        **changes,
    }


def test_a_series_from_the_store_is_the_tools_csv_with_its_extent(operations, tmp_path):
    result = execute(operations, "export_station_series", export_params(), tmp_path)

    assert result.ok, result.error
    (path,) = result.files["meteo_series"]
    assert path.name == "meteo_precip_daily_123750000_2001-01-01_2001-01-31.csv"
    assert len(table(path)) == 31
    assert result.values["dataset"] == PRECIP
    assert result.values["provider"] == "IMGW-PIB"
    assert result.values["station_code"] == "123750000"
    assert result.values["period"] == {
        "start": "2001-01-01",
        "end": "2001-01-31",
        "year_type": "calendar",
    }
    assert (
        result.values["rows"],
        result.values["first_date"],
        result.values["last_date"],
    ) == (31, "2001-01-01", "2001-01-31")
    assert result.values["missing_rows"] == 0
    assert result.values["series_version"].startswith(
        "series/versions/meteo_precip_daily/"
    )
    assert "archives" not in result.values
    assert result.summary == (
        "Gotowe. Wynik #1: szereg stacji 123750000 "
        "(31 wierszy, 2001-01-01 – 2001-01-31) zapisany w pliku CSV."
    )
    # The tool's licence notice, verbatim, and nothing else
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith(IMGW_LICENSE_START)
    assert audit_commands(result) == ["series export", "series select"]
    assert result.tool is not None
    assert result.tool["calls"][0]["files"][0]["path"] == str(path)


def test_the_variables_of_the_plan_are_the_columns_of_the_file(operations, tmp_path):
    params = export_params(
        dataset="pl_hydro_daily",
        station=station("149190310", kind="hydro"),
        period={"type": "dates", "start": "2023-11-01", "end": "2024-02-29"},
        variables=["Q"],
    )

    result = execute(operations, "export_station_series", params, tmp_path)

    assert result.ok, result.error
    (path,) = result.files["hydro_series"]
    header = list(table(path)[0])
    assert "Q [m3/s]" in header and "H [cm]" not in header
    # The fixture has December 2023 – February 2024 (91 days)
    assert result.values["rows"] == 91
    assert result.values["first_date"] == "2023-12-01"


def test_an_empty_range_is_the_tools_error_with_its_code(operations, tmp_path):
    params = export_params(
        period={"type": "dates", "start": "1990-01-01", "end": "1990-12-31"}
    )

    result = execute(operations, "export_station_series", params, tmp_path)

    assert not result.ok
    assert result.error_code == "data_error"
    assert result.error is not None
    assert result.error.startswith("Dane IMGWTools są nieprawidłowe lub niekompletne:")
    assert "jest pusty w wybranym zakresie" in result.error
    assert result.files == {}


def test_a_series_from_the_server_counts_the_archives_and_reports_the_failed_ones(
    operations, tmp_path
):
    from imgwtools import OperationResult, SeriesReport, SyncReport

    store = fixture_store()
    base = "archive:pl.imgw.meteo_precip_daily:2001"
    report = SyncReport(
        items=(
            OperationResult(f"{base}/2001_01_o.zip", "unchanged", None, None),
            OperationResult(f"{base}/2001_02_o.zip", "created", None, None),
            OperationResult(
                f"{base}/2001_03_o.zip",
                "failed",
                None,
                "HTTP 503",
                error_code="source_unavailable",
            ),
        ),
        series=(SeriesReport("created", None, 2, (), ()),),
        cancelled=False,
    )
    client = HybridClient(
        real_client(tmp_path, store),
        {"store sync": synthetic_run("store sync", report, status="partial")},
    )

    result = execute(
        operations,
        "export_station_series",
        export_params(data_source="server"),
        tmp_path,
        client=client,
    )

    assert result.ok, result.error
    assert result.values["archives"] == {
        "planned": 3,
        "created": 1,
        "unchanged": 1,
        "relabeled": 0,
        "failed": 1,
    }
    assert result.warnings[0] == (
        "Nie udało się przetworzyć 1 z 4 pozycji; szczegóły są w dokumencie "
        "narzędzia w folderze wyniku (tool_*.json)."
    )
    assert result.warnings[1] == (
        "Nie wszystko się udało "
        "(archive:pl.imgw.meteo_precip_daily:2001/2001_03_o.zip): HTTP 503"
    )
    assert audit_commands(result) == ["store sync", "series export", "series select"]


def test_the_coverage_of_a_station_is_kept_as_the_tools_document(operations, tmp_path):
    result = execute(
        operations,
        "show_station_coverage",
        {
            "dataset": "pl_hydro_daily",
            "station": [station("149190310", kind="hydro")],
        },
        tmp_path,
    )

    assert result.ok, result.error
    (path,) = result.files["imgw_report"]
    assert path.name == "coverage.json"
    assert json.loads(path.read_text("utf-8"))["command"] == "series summary"
    assert result.values["stations"] == 1
    assert result.values["variables"] == ["H", "Q", "T"]
    assert (result.values["first"], result.values["last"]) == (
        "2023-12-01",
        "2024-02-29",
    )
    assert result.summary == (
        "Gotowe. Wynik #1: pokrycie danych: stacji 1, od 2023-12-01 do 2024-02-29, "
        f"luk: {result.values['gaps_total']}."
    )


def test_building_a_series_names_the_version_and_says_when_it_was_reused(
    operations, tmp_path
):
    store = build_store(tmp_path / "store")

    reused = execute(
        operations,
        "build_imgw_series",
        {"dataset": "pl_hydro_daily"},
        tmp_path,
        store=store,
    )
    created = execute(
        operations,
        "build_imgw_series",
        {"dataset": "pl_meteo_precip_daily"},
        tmp_path,
        store=store,
    )

    assert reused.ok, reused.error
    assert reused.values["status"] == "reused"
    assert reused.values["dataset"] == "pl.imgw.hydro_daily"
    assert reused.values["stations"] == 2
    assert reused.warnings == []
    assert reused.summary == (
        "Gotowe. Wynik #1: szereg zbioru pl.imgw.hydro_daily w magazynie: reused, "
        "stacji: 2."
    )
    # A new series version brings the provider's terms
    assert created.ok, created.error
    assert created.values["status"] == "created"
    assert created.values["series_version"].endswith("series.json")
    assert len(created.warnings) == 1
    assert created.warnings[0].startswith(IMGW_LICENSE_START)


def test_a_disk_without_hard_links_is_explained_not_quoted(
    operations, tmp_path, monkeypatch
):
    import imgwtools

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise imgwtools.IMGWStoreConflictError(
            "Publikacja wersji wymaga dowiązań twardych",
            details={"reason": "not_atomic"},
        )

    monkeypatch.setattr(imgwtools, "run_command", refuse)

    result = execute(
        operations, "build_imgw_series", {"dataset": "pl_hydro_daily"}, tmp_path
    )

    assert not result.ok
    assert result.error_code == "store_write_unsupported"
    assert result.error is not None
    assert "dowiązaniami twardymi" in result.error
    assert "Publikacja wersji wymaga dowiązań twardych" in result.error

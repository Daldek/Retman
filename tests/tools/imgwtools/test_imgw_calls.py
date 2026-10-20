"""Golden calls of the IMGWTools operations 1–11, validated by the real tool.

Each case is a plan's parameters and the exact catalog calls the builder makes of
them. Every call is then validated offline by the tool itself, so a builder that
drifts from the catalog fails here and not after the user's confirmation.
"""

from pathlib import Path
from typing import Any

import pytest
from imgw_support import isolate_environment, real_client

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError, route_error
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import tool_context
from retman.tools.imgwtools import manifest as imgw_manifest
from retman.tools.imgwtools.calls import PROVIDERS

PRECIP = "pl.imgw.meteo_precip_daily"


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
CZ_HYDRO = station("0-203-1-900001", "CHMI", "hydro")
CZ_METEO = station("0-203-0-90001", "CHMI", "meteo")
YEARS = {"type": "years", "first": 2000, "last": 2020}
DATES = {"type": "dates", "start": "2001-01-01", "end": "2001-01-31"}
PROVIDERS_CALL: tuple[str, dict, str | None] = ("datasets providers", {}, None)


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


def context(
    operations: dict[str, Operation],
    operation: str,
    tmp_path: Path,
    *,
    output_dir: Path | None = None,
) -> ToolContext:
    return tool_context(
        operations[operation],
        client=real_client(tmp_path),
        settings={"store_dir": "/unused", "reference_data_dir": str(tmp_path)},
        project_dir=tmp_path,
        output_dir=output_dir,
    )


def build(
    operations: dict[str, Operation],
    operation: str,
    params: dict[str, Any],
    tmp_path: Path,
    *,
    output_dir: Path | None = None,
) -> list[CatalogCall]:
    from retman.adapters.catalog import load_reference

    builder = load_reference(operations[operation].spec["calls"])
    return builder(
        params, context(operations, operation, tmp_path, output_dir=output_dir)
    )


def summary(calls: list[CatalogCall]) -> list[tuple[str, dict, str | None]]:
    return [(call.command, dict(call.options), call.kind) for call in calls]


CASES: list[tuple[str, dict[str, Any], list[tuple[str, dict, str | None]]]] = [
    (
        "find_imgw_stations",
        {
            "data_source": "server",
            "provider": "chmi",
            "kind": "hydro",
            "query": {"type": "query", "text": "vltav", "raw": "Vltavě"},
        },
        [
            (
                "stations find",
                {
                    "source": "live",
                    "provider": "CHMI",
                    "kind": "hydro",
                    "query": "vltav",
                },
                "station_list",
            ),
            PROVIDERS_CALL,
        ],
    ),
    (
        "find_imgw_stations",
        {"data_source": "store"},
        [("stations find", {"source": "store"}, "station_list"), PROVIDERS_CALL],
    ),
    (
        "build_imgw_station_catalog",
        {"provider": "imgw_pib"},
        [("store catalog", {"provider": "IMGW-PIB"}, None)],
    ),
    (
        "list_imgw_datasets",
        {},
        [
            ("datasets list", {}, "imgw_report"),
            ("datasets providers", {}, "imgw_report"),
        ],
    ),
    (
        "list_imgw_datasets",
        {"provider": "imgw_pib", "kind": "meteo"},
        [
            (
                "datasets list",
                {"provider": "IMGW-PIB", "kind": "meteo"},
                "imgw_report",
            ),
            ("datasets providers", {}, "imgw_report"),
        ],
    ),
    (
        "fetch_current_observations",
        {"source": "hydro", "station": RABA},
        [("current hydro", {"station": "149190310"}, "current_hydro"), PROVIDERS_CALL],
    ),
    (
        "fetch_current_observations",
        {"source": "meteo"},
        [("current meteo", {}, "current_meteo"), PROVIDERS_CALL],
    ),
    (
        "fetch_current_observations",
        {
            "source": "synop",
            "synop_station": {"type": "synop_station", "code": "12375", "name": None},
        },
        [("current synop", {"station": "12375"}, "current_synop"), PROVIDERS_CALL],
    ),
    (
        "fetch_current_observations",
        {
            "source": "synop",
            "synop_station": {"type": "synop_station", "code": None, "name": "Warszaw"},
        },
        [
            ("current synop", {"station_name": "Warszaw"}, "current_synop"),
            PROVIDERS_CALL,
        ],
    ),
    (
        "fetch_imgw_warnings",
        {},
        [("current warnings", {}, "imgw_warnings"), PROVIDERS_CALL],
    ),
    (
        "fetch_imgw_warnings",
        {"kind": "meteo"},
        [("current warnings", {"kind": "meteo"}, "imgw_warnings"), PROVIDERS_CALL],
    ),
    (
        "fetch_hydro_states",
        {"main_only": True},
        [("current hydro-states", {"main_only": True}, "hydro_states"), PROVIDERS_CALL],
    ),
    (
        "get_pmaxtp",
        {
            "point": {"type": "point", "latitude": 52.23, "longitude": 21.01},
            "method": "pot",
            "storage": "none",
        },
        [
            (
                "pmaxtp fetch",
                {"latitude": 52.23, "longitude": 21.01, "method": "POT"},
                "pmaxtp_table",
            ),
            PROVIDERS_CALL,
        ],
    ),
    (
        "get_pmaxtp",
        {
            "point": {"type": "point", "latitude": 50.06, "longitude": 19.94},
            "method": "amp",
            "storage": "store",
            "probability": [0.01],
        },
        [
            (
                "pmaxtp sync",
                {"latitude": 50.06, "longitude": 19.94, "method": "AMP"},
                "pmaxtp_table",
            ),
            PROVIDERS_CALL,
        ],
    ),
    (
        "read_stored_pmaxtp",
        {"cell": {"type": "grid_cell", "ind_x": 751, "ind_y": 317}, "method": "pot"},
        [
            (
                "pmaxtp read",
                {"ind_x": 751, "ind_y": 317, "method": "POT"},
                "pmaxtp_table",
            ),
            PROVIDERS_CALL,
        ],
    ),
    (
        "show_station_coverage",
        {"dataset": "pl_meteo_precip_daily"},
        [("series summary", {"dataset": PRECIP}, "imgw_report")],
    ),
    (
        "show_station_coverage",
        {"dataset": "pl_meteo_precip_daily", "station": [WARSAW]},
        [
            (
                "series summary",
                {"dataset": PRECIP, "stations": ["123750000"]},
                "imgw_report",
            )
        ],
    ),
    (
        "build_imgw_series",
        {"dataset": "pl_hydro_daily"},
        [("series build", {"dataset": "pl.imgw.hydro_daily"}, None)],
    ),
]


@pytest.mark.parametrize(("operation", "params", "expected"), CASES)
def test_builders_make_exactly_these_calls_and_the_tool_accepts_them(
    operations, tmp_path, operation, params, expected
):
    calls = build(operations, operation, params, tmp_path)

    assert summary(calls) == expected
    # The kinds the calls promise are kinds the operation declares as its outputs
    declared = set(operations[operation].spec["outputs"])
    assert {call.kind for call in calls if call.kind} <= declared
    client = real_client(tmp_path)
    for call in calls:
        client.validate(call)


def export_params(**changes: Any) -> dict[str, Any]:
    return {
        "dataset": "pl_meteo_precip_daily",
        "station": WARSAW,
        "period": YEARS,
        "year_type": "calendar",
        "data_source": "server",
        **changes,
    }


def select(options: dict) -> list[tuple[str, dict, str | None]]:
    return [("series select", options, None)]


def test_a_series_export_from_the_server_syncs_the_archives_first(operations, tmp_path):
    calls = build(operations, "export_station_series", export_params(), tmp_path)

    assert summary(calls) == [
        (
            "store sync",
            {"datasets": [PRECIP], "series": True, "years": list(range(2000, 2021))},
            None,
        ),
        (
            "series export",
            {
                "dataset": PRECIP,
                "station": "123750000",
                "start": "2000-01-01",
                "end": "2020-12-31",
                "year_type": "calendar",
            },
            "meteo_series",
        ),
        *select({"dataset": PRECIP, "stations": ["123750000"]}),
    ]
    client = real_client(tmp_path)
    for call in calls:
        client.validate(call)


def test_hydrological_years_are_numbered_like_the_archives_of_the_tool(
    operations, tmp_path
):
    hydrological = build(
        operations,
        "export_station_series",
        export_params(dataset="pl_hydro_daily", station=RABA, year_type="hydrological"),
        tmp_path,
    )
    calendar = build(
        operations,
        "export_station_series",
        export_params(dataset="pl_hydro_daily", station=RABA),
        tmp_path,
    )

    # Hydrological 2000–2020 is 1.11.1999 – 31.10.2020: archives 2000–2020
    assert hydrological[0].options["years"] == list(range(2000, 2021))
    assert hydrological[1].options["start"] == "1999-11-01"
    assert hydrological[1].kind == "hydro_series"
    # Calendar 2000–2020 reaches November 2020, which is archive year 2021
    assert calendar[0].options["years"] == list(range(2000, 2022))


def test_a_czech_series_names_its_station_and_a_whole_history_has_no_years(
    operations, tmp_path
):
    hydro = build(
        operations,
        "export_station_series",
        export_params(dataset="cz_hydro_daily", station=CZ_HYDRO),
        tmp_path,
    )
    meteo = build(
        operations,
        "export_station_series",
        export_params(dataset="cz_meteo_daily", station=CZ_METEO, period=DATES),
        tmp_path,
    )

    assert hydro[0].options["stations"] == ["0-203-1-900001"]
    assert hydro[0].options["years"] == list(range(2000, 2021))
    assert meteo[0].options == {
        "datasets": ["cz.chmi.meteo_daily"],
        "series": True,
        "stations": ["0-203-0-90001"],
    }
    client = real_client(tmp_path)
    for call in (*hydro, *meteo):
        client.validate(call)


def test_the_store_as_the_source_skips_the_sync_and_names_a_file_in_the_result(
    operations, tmp_path
):
    folder = tmp_path / "001_export"
    params = export_params(
        data_source="store", period=DATES, variables=["P", "snow_cover"]
    )

    planning = build(operations, "export_station_series", params, tmp_path)
    running = build(
        operations, "export_station_series", params, tmp_path, output_dir=folder
    )

    assert [call.command for call in running] == ["series export", "series select"]
    # Planning validates the stream form; only a running call has a target
    assert "path" not in planning[0].options
    assert running[0].options["path"] == str(
        folder / "meteo_precip_daily_123750000_2001-01-01_2001-01-31.csv"
    )
    assert running[0].options["variables"] == ["P", "snow_cover"]
    assert running[1].options["variables"] == ["P", "snow_cover"]
    client = real_client(tmp_path)
    for call in running:
        client.validate(call)


def blame(call: CatalogCall, tmp_path: Path) -> ToolError:
    with pytest.raises(ToolError) as caught:
        real_client(tmp_path).validate(call)
    return caught.value


def test_a_rejection_of_the_tool_leads_back_to_the_parameter_that_caused_it(
    operations, tmp_path
):
    names = lambda operation: [  # noqa: E731
        param["name"] for param in operations[operation].spec["params"]
    ]
    half_year = build(
        operations,
        "export_station_series",
        export_params(
            dataset="pl_hydro_semiannual",
            station=RABA,
            data_source="store",
            year_type="calendar",
        ),
        tmp_path,
    )
    outside = build(
        operations,
        "get_pmaxtp",
        {
            "point": {"type": "point", "latitude": 10.0, "longitude": 21.0},
            "method": "pot",
            "storage": "none",
        },
        tmp_path,
    )
    too_early = build(
        operations,
        "export_station_series",
        export_params(
            dataset="pl_hydro_daily",
            station=RABA,
            period={"type": "years", "first": 1900, "last": 1905},
            year_type="hydrological",
        ),
        tmp_path,
    )

    # The half-year series have no calendar years
    error = blame(half_year[0], tmp_path)
    assert route_error(half_year[0], error, names("export_station_series")) == [
        "year_type"
    ]
    # A point outside Poland is a point, not a "latitude" the user never typed
    error = blame(outside[0], tmp_path)
    assert route_error(outside[0], error, names("get_pmaxtp")) == ["point"]
    # Years before the dataset's first year are the period
    error = blame(too_early[0], tmp_path)
    assert route_error(too_early[0], error, names("export_station_series")) == [
        "period"
    ]


def test_the_only_attribution_call_is_the_providers_registry():
    assert (PROVIDERS.command, dict(PROVIDERS.options)) == ("datasets providers", {})

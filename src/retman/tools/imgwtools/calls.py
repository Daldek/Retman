"""Call builders of the IMGWTools operations 1–11 (``calls(params, ctx)``).

Pure functions: they read the plan's parameters and the manifest (``tool_value``,
``option_meta``) and return the catalog calls the generic runner validates while
planning and runs after the user's confirmation. They never touch the file system
or the network and never name the store: the client adds ``root``. A call gets
an output path only when ``ctx.output_dir`` exists, i.e. when it really runs
(while planning the tool validates the stream form, which is valid offline).
Every ``CatalogCall.params`` maps a tool option to the Retman parameter it came
from, so a rejection by the tool becomes a question about that parameter.
"""

from pathlib import Path
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext
from retman.extractors.dates import archive_years, period_dates

# Attribution of the data the mappers write as CSV comes from the provider
# registry; it is an offline call, so it is also validated and audited
PROVIDERS = CatalogCall("datasets providers", {})


def _codes(stations: list[dict[str, Any]]) -> list[str]:
    return [station["code"] for station in stations]


def find_imgw_stations(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 1: ``stations find`` from the server or the store's catalog."""
    options: dict[str, object] = {
        "source": ctx.tool_value("data_source", params["data_source"])
    }
    if "provider" in params:
        options["provider"] = ctx.tool_value("provider", params["provider"])
    if "kind" in params:
        options["kind"] = ctx.tool_value("kind", params["kind"])
    if "query" in params:
        options["query"] = params["query"]["text"]
    return [
        CatalogCall(
            "stations find",
            options,
            kind="station_list",
            params={
                "source": "data_source",
                "provider": "provider",
                "kind": "kind",
                "query": "query",
            },
        ),
        PROVIDERS,
    ]


def build_imgw_station_catalog(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """Operation 2: ``store catalog`` of one provider (writes the store)."""
    options: dict[str, object] = {
        "provider": ctx.tool_value("provider", params["provider"])
    }
    if "user_locations" in params:
        options["user_locations"] = str(ctx.project_dir / params["user_locations"])
    return [
        CatalogCall(
            "store catalog",
            options,
            params={"provider": "provider", "user_locations": "user_locations"},
        )
    ]


def list_imgw_datasets(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 3: the dataset registry and the providers (offline)."""
    options: dict[str, object] = {}
    if "provider" in params:
        options["provider"] = ctx.tool_value("provider", params["provider"])
    if "kind" in params:
        options["kind"] = ctx.tool_value("kind", params["kind"])
    return [
        CatalogCall(
            "datasets list",
            options,
            kind="imgw_report",
            params={"provider": "provider", "kind": "kind"},
        ),
        CatalogCall("datasets providers", {}, kind="imgw_report"),
    ]


def fetch_current_observations(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """Operation 4: ``current hydro|meteo|synop``, all stations or one."""
    source = params["source"]
    options: dict[str, object] = {}
    routes = {"station": "station"}
    if source == "synop":
        routes = {"station": "synop_station", "station_name": "synop_station"}
        station = params.get("synop_station")
        if station is not None:
            if station.get("code") is not None:
                options["station"] = station["code"]
            else:
                options["station_name"] = station["name"]
    elif "station" in params:
        options["station"] = params["station"]["code"]
    return [
        CatalogCall(
            f"current {source}", options, kind=f"current_{source}", params=routes
        ),
        PROVIDERS,
    ]


def fetch_imgw_warnings(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 5: ``current warnings`` of one kind or both."""
    options: dict[str, object] = {}
    if "kind" in params:
        options["kind"] = ctx.tool_value("kind", params["kind"])
    return [
        CatalogCall(
            "current warnings", options, kind="imgw_warnings", params={"kind": "kind"}
        ),
        PROVIDERS,
    ]


def fetch_hydro_states(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 6: ``current hydro-states`` (all stations or the main ones)."""
    return [
        CatalogCall(
            "current hydro-states",
            {"main_only": params["main_only"]},
            kind="hydro_states",
            params={"main_only": "main_only"},
        ),
        PROVIDERS,
    ]


def get_pmaxtp(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 7: ``pmaxtp fetch`` (server only) or ``pmaxtp sync`` (into the store).

    The request has no probability or duration; the two parameters only filter
    the table the mapper writes.
    """
    point = params["point"]
    command = "pmaxtp sync" if params["storage"] == "store" else "pmaxtp fetch"
    return [
        CatalogCall(
            command,
            {
                "latitude": point["latitude"],
                "longitude": point["longitude"],
                "method": ctx.tool_value("method", params["method"]),
            },
            kind="pmaxtp_table",
            params={"latitude": "point", "longitude": "point", "method": "method"},
        ),
        PROVIDERS,
    ]


def read_stored_pmaxtp(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 8: ``pmaxtp read`` of a cell kept in the store."""
    cell = params["cell"]
    return [
        CatalogCall(
            "pmaxtp read",
            {
                "ind_x": cell["ind_x"],
                "ind_y": cell["ind_y"],
                "method": ctx.tool_value("method", params["method"]),
            },
            kind="pmaxtp_table",
            params={"ind_x": "cell", "ind_y": "cell", "method": "method"},
        ),
        PROVIDERS,
    ]


def export_station_series(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """Operation 9: [``store sync``] → ``series export`` → ``series select``.

    From the server the archives of the period are first synchronised into the
    store (and the series rebuilt); from the store the series is exported as it
    is. ``series select`` only names the series version the export read.
    """
    dataset = ctx.tool_value("dataset", params["dataset"])
    meta = ctx.option_meta("dataset", params["dataset"])
    code = params["station"]["code"]
    start, end = period_dates(params["period"], params["year_type"])
    calls: list[CatalogCall] = []
    if params["data_source"] == "server":
        sync: dict[str, object] = {"datasets": [dataset], "series": True}
        if meta["provider"] == "CHMI":
            sync["stations"] = [code]
        # ČHMÚ meteorological files hold a station's whole history: no years
        if dataset != "cz.chmi.meteo_daily":
            sync["years"] = archive_years(start, end, meta["numbering"])
        calls.append(
            CatalogCall(
                "store sync",
                sync,
                params={
                    "datasets": "dataset",
                    "years": "period",
                    "stations": "station",
                },
            )
        )
    export: dict[str, object] = {
        "dataset": dataset,
        "station": code,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "year_type": params["year_type"],
    }
    selection: dict[str, object] = {"dataset": dataset, "stations": [code]}
    if params.get("variables"):
        export["variables"] = list(params["variables"])
        selection["variables"] = list(params["variables"])
    if ctx.output_dir is not None:
        name = f"{meta['slug']}_{code}_{start.isoformat()}_{end.isoformat()}.csv"
        export["output"] = str(Path(ctx.output_dir) / name)
    routes = {
        "dataset": "dataset",
        "station": "station",
        "stations": "station",
        "start": "period",
        "end": "period",
        "year_type": "year_type",
        "variables": "variables",
    }
    calls.append(
        CatalogCall(
            "series export", export, kind=f"{meta['kind']}_series", params=routes
        )
    )
    calls.append(CatalogCall("series select", selection, params=routes))
    return calls


def show_station_coverage(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """Operation 10: ``series summary`` of the dataset's stations (offline)."""
    options: dict[str, object] = {
        "dataset": ctx.tool_value("dataset", params["dataset"])
    }
    if "station" in params:
        options["stations"] = _codes(params["station"])
    return [
        CatalogCall(
            "series summary",
            options,
            kind="imgw_report",
            params={"dataset": "dataset", "stations": "station"},
        )
    ]


def build_imgw_series(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Operation 11: ``series build`` of the dataset from the archives in the store."""
    return [
        CatalogCall(
            "series build",
            {"dataset": ctx.tool_value("dataset", params["dataset"])},
            params={"dataset": "dataset"},
        )
    ]

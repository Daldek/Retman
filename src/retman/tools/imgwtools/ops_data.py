"""The IMGWTools operations 1–11: stations, live data, PMAXTP and station series.

Categories ``imgw_catalog``, ``imgw_current``, ``imgw_pmaxtp`` and ``imgw_series``
(research-imgw 2 and 5.3). The manifest of the tool lists ``OPERATIONS`` among
its own; the archive and project operations live in ``ops_archives`` and
``ops_projects``. Nothing here imports the tool.
"""

from typing import Final

from retman.registry.manifest import OperationSpec, ParamSpec
from retman.tools.imgwtools.params import (
    SERIES_DATASETS,
    dataset_param,
    provider_param,
)

_CALLS: Final = "retman.tools.imgwtools.calls"
_DESCRIBE: Final = "retman.tools.imgwtools.describe"
_PREVIEW: Final = "retman.tools.imgwtools.preview"
_CHECK: Final = "retman.tools.imgwtools.check"


def _kind_param() -> ParamSpec:
    """Build the optional filter: hydrological or meteorological stations, warnings."""
    return {"name": "kind", "type": "choice", "options": ["hydro", "meteo"]}


def _year_type_param() -> ParamSpec:
    """Calendar or hydrological years: read by code, never guessed (ADR-009)."""
    return {
        "name": "year_type",
        "type": "choice",
        "options": ["hydrological", "calendar"],
        "extractor": "year_type",
        "option_values": {"hydrological": "hydrological", "calendar": "calendar"},
        "required": True,
    }


def _method_param() -> ParamSpec:
    return {
        "name": "method",
        "type": "choice",
        "options": ["pot", "amp"],
        "tool_values": {"pot": "POT", "amp": "AMP"},
        "required": True,
    }


OPERATIONS: Final[list[OperationSpec]] = [
    {
        "id": "find_imgw_stations",
        "category": "imgw_catalog",
        "description": "Find IMGW-PIB and CHMI stations by name, river or kind",
        "inputs": [],
        "outputs": ["station_list"],
        "params": [
            {
                "name": "data_source",
                "type": "choice",
                "options": ["server", "store"],
                "tool_values": {"server": "live", "store": "store"},
                "required": True,
            },
            provider_param(required=False),
            _kind_param(),
            {"name": "query", "type": "free", "extractor": "place_query"},
        ],
        "calls": f"{_CALLS}:find_imgw_stations",
        "commands": ["stations find", "datasets providers", "store info"],
        "describe": f"{_DESCRIBE}:describe_find_imgw_stations",
        "preview": f"{_PREVIEW}:preview_find_imgw_stations",
    },
    {
        "id": "build_imgw_station_catalog",
        "category": "imgw_catalog",
        "description": "Build or refresh the station catalog of a provider",
        "inputs": [],
        "outputs": [],
        "params": [
            provider_param(),
            {"name": "user_locations", "type": "free", "extractor": "path"},
        ],
        "calls": f"{_CALLS}:build_imgw_station_catalog",
        "commands": ["store catalog", "store info"],
        "describe": f"{_DESCRIBE}:describe_build_imgw_station_catalog",
        "preview": f"{_PREVIEW}:preview_build_imgw_station_catalog",
        "check": f"{_CHECK}:check_build_imgw_station_catalog",
    },
    {
        "id": "list_imgw_datasets",
        "category": "imgw_catalog",
        "description": "List the datasets and providers IMGWTools offers",
        "inputs": [],
        "outputs": ["imgw_report"],
        "params": [provider_param(required=False), _kind_param()],
        "calls": f"{_CALLS}:list_imgw_datasets",
        "commands": ["datasets list", "datasets providers"],
        "describe": f"{_DESCRIBE}:describe_list_imgw_datasets",
    },
    {
        "id": "fetch_current_observations",
        "category": "imgw_current",
        "description": "Fetch current hydrological, meteorological or synoptic data",
        "inputs": [],
        "outputs": ["current_hydro", "current_meteo", "current_synop"],
        "params": [
            {
                "name": "source",
                "type": "choice",
                "options": ["hydro", "meteo", "synop"],
                "option_meta": {
                    "hydro": {"provider": "IMGW-PIB", "kind": "hydro"},
                    "meteo": {"provider": "IMGW-PIB", "kind": "meteo"},
                    "synop": {"provider": "IMGW-PIB"},
                },
                "required": True,
            },
            {
                "name": "station",
                "type": "free",
                "extractor": "station",
                "depends_on": {"source": ["hydro", "meteo"]},
            },
            {
                "name": "synop_station",
                "type": "free",
                "extractor": "synop_station",
                "depends_on": {"source": ["synop"]},
            },
        ],
        "calls": f"{_CALLS}:fetch_current_observations",
        "commands": [
            "current hydro",
            "current meteo",
            "current synop",
            "datasets providers",
        ],
        "describe": f"{_DESCRIBE}:describe_fetch_current_observations",
        "preview": f"{_PREVIEW}:preview_fetch_current_observations",
    },
    {
        "id": "fetch_imgw_warnings",
        "category": "imgw_current",
        "description": "Fetch current hydrological and meteorological warnings",
        "inputs": [],
        "outputs": ["imgw_warnings"],
        "params": [_kind_param()],
        "calls": f"{_CALLS}:fetch_imgw_warnings",
        "commands": ["current warnings", "datasets providers"],
        "describe": f"{_DESCRIBE}:describe_fetch_imgw_warnings",
        "preview": f"{_PREVIEW}:preview_fetch_imgw_warnings",
    },
    {
        "id": "fetch_hydro_states",
        "category": "imgw_current",
        "description": "Fetch the water state of hydrological stations",
        "inputs": [],
        "outputs": ["hydro_states"],
        "params": [{"name": "main_only", "type": "bool", "required": True}],
        "calls": f"{_CALLS}:fetch_hydro_states",
        "commands": ["current hydro-states", "datasets providers"],
        "describe": f"{_DESCRIBE}:describe_fetch_hydro_states",
    },
    {
        "id": "get_pmaxtp",
        "category": "imgw_pmaxtp",
        "description": "Get PMAXTP maximum precipitation for a point",
        "inputs": [],
        "outputs": ["pmaxtp_table"],
        "params": [
            {"name": "point", "type": "free", "extractor": "point", "required": True},
            _method_param(),
            {
                "name": "storage",
                "type": "choice",
                "options": ["none", "store"],
                "required": True,
            },
            {
                "name": "probability",
                "type": "free",
                "extractor": "probability",
                "multiple": True,
            },
            {
                "name": "duration",
                "type": "free",
                "extractor": "duration",
                "multiple": True,
            },
        ],
        "calls": f"{_CALLS}:get_pmaxtp",
        "commands": ["pmaxtp fetch", "pmaxtp sync", "datasets providers", "store info"],
        "describe": f"{_DESCRIBE}:describe_get_pmaxtp",
        "preview": f"{_PREVIEW}:preview_get_pmaxtp",
        "no_check": "The PMAXTP service gives no availability or update signal: "
        "check_pmaxtp is an offline plan that reports the freshness of a cell as "
        "unverifiable, and the cell is known only after the request itself.",
    },
    {
        "id": "read_stored_pmaxtp",
        "category": "imgw_pmaxtp",
        "description": "Read a PMAXTP grid cell kept in the store",
        "inputs": [],
        "outputs": ["pmaxtp_table"],
        "params": [
            {
                "name": "cell",
                "type": "free",
                "extractor": "grid_cell",
                "required": True,
            },
            _method_param(),
        ],
        "calls": f"{_CALLS}:read_stored_pmaxtp",
        "commands": ["pmaxtp read", "datasets providers", "store info"],
        "describe": f"{_DESCRIBE}:describe_read_stored_pmaxtp",
        "preview": f"{_PREVIEW}:preview_read_stored_pmaxtp",
    },
    {
        "id": "export_station_series",
        "category": "imgw_series",
        "description": "Export the time series of one station to CSV",
        "inputs": [],
        "outputs": ["hydro_series", "meteo_series"],
        "params": [
            dataset_param(SERIES_DATASETS),
            {
                "name": "station",
                "type": "free",
                "extractor": "station",
                "required": True,
            },
            {
                "name": "period",
                "type": "free",
                "extractor": "period",
                "accepts": ["years", "dates"],
                "required": True,
            },
            _year_type_param(),
            {
                "name": "data_source",
                "type": "choice",
                "options": ["server", "store"],
                "required": True,
            },
            {
                "name": "variables",
                "type": "free",
                "extractor": "variables",
                "multiple": True,
            },
        ],
        "calls": f"{_CALLS}:export_station_series",
        "commands": [
            "store sync",
            "series export",
            "series select",
            "series summary",
            "datasets files",
            "store info",
        ],
        "describe": f"{_DESCRIBE}:describe_export_station_series",
        "preview": f"{_PREVIEW}:preview_export_station_series",
        "check": f"{_CHECK}:check_export_station_series",
    },
    {
        "id": "show_station_coverage",
        "category": "imgw_series",
        "description": "Show which years and variables the store holds for stations",
        "inputs": [],
        "outputs": ["imgw_report"],
        "params": [
            dataset_param(SERIES_DATASETS),
            {
                "name": "station",
                "type": "free",
                "extractor": "station",
                "multiple": True,
            },
        ],
        "calls": f"{_CALLS}:show_station_coverage",
        "commands": ["series summary", "store info"],
        "describe": f"{_DESCRIBE}:describe_show_station_coverage",
        "preview": f"{_PREVIEW}:preview_show_station_coverage",
    },
    {
        "id": "build_imgw_series",
        "category": "imgw_series",
        "description": "Build the series of a dataset from the archives in the store",
        "inputs": [],
        "outputs": [],
        "params": [dataset_param(SERIES_DATASETS)],
        "calls": f"{_CALLS}:build_imgw_series",
        "commands": ["series build", "store info"],
        "describe": f"{_DESCRIBE}:describe_build_imgw_series",
        "preview": f"{_PREVIEW}:preview_build_imgw_series",
    },
]

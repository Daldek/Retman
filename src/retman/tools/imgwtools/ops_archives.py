"""The ``imgw_archives`` operations: archive files, the store and its plans.

Eight operations (research-imgw 2 and 5.3, nos. 12-19): downloading archives to
the result folder, checking and synchronising the IMGWTools store, exporting
stored archives and looking into the store. The manifest of the tool lists
``OPERATIONS`` among its own; nothing here imports the tool.
"""

from collections.abc import Sequence

from retman.registry.manifest import OperationSpec, ParamSpec
from retman.tools.imgwtools.params import (
    DATASETS,
    HYDRO_DOWNLOAD_DATASETS,
    METEO_DOWNLOAD_DATASETS,
    SERIES_DATASETS,
    dataset_param,
    provider_param,
)

_CALLS = "retman.tools.imgwtools.calls_archives"
_DESCRIBE = "retman.tools.imgwtools.describe_archives"
_PREVIEW = "retman.tools.imgwtools.preview_archives"
CATEGORY = "imgw_archives"

# ČHMÚ keeps the whole history of a station in one file per element, so the
# tool refuses ``years`` for this dataset
_WHOLE_HISTORY = "cz_meteo_daily"

# Why the download operations offer no availability check (``no_check``, X7)
_NO_DOWNLOAD_CHECK = (
    "The check_command of 'datasets download' is an offline dry run (URLs and "
    "target paths, no request). The tool's one network check of archives is "
    "'store check': it needs a store and takes the series datasets only, and it "
    "is the operation check_imgw_archives. A file the servers do not publish is "
    "reported by the run itself (not_published)."
)


def years_param(datasets: Sequence[str]) -> ParamSpec:
    """Archive years in the numbering of the tool (hydrological for IMGW hydro).

    Applies to every offered dataset except the one of whole-history files.
    """
    spec: ParamSpec = {
        "name": "years",
        "type": "free",
        "extractor": "years",
        "accepts": ["years", "year_list"],
        "required": True,
    }
    applicable = [key for key in datasets if key != _WHOLE_HISTORY]
    if len(applicable) != len(datasets):
        spec["depends_on"] = {"dataset": applicable}
    return spec


def stations_param(datasets: Sequence[str]) -> ParamSpec:
    """ČHMÚ station files are chosen by station; IMGW-PIB archives cover the country."""
    return {
        "name": "stations",
        "type": "free",
        "extractor": "station",
        "multiple": True,
        "required": True,
        "depends_on": {
            "dataset": [key for key in datasets if DATASETS[key]["provider"] == "CHMI"]
        },
    }


def _excluded(offered: Sequence[str], reason: str) -> dict[str, dict[str, str]]:
    """Return the IMGW-PIB download datasets the other operation serves (coverage).

    A ČHMÚ dataset of the other kind is not listed: it needs a combination of
    ``stations`` and ``years`` that no call of this operation makes, so the tool
    refuses it here and nothing is left uncovered (X4 says so if that changes).
    """
    others = [
        DATASETS[key]["tool_value"]
        for key in (*HYDRO_DOWNLOAD_DATASETS, *METEO_DOWNLOAD_DATASETS)
        if key not in offered and DATASETS[key]["provider"] != "CHMI"
    ]
    return {"dataset": dict.fromkeys(others, reason)}


_HYDRO_PARAMS: ParamSpec = {
    "name": "hydro_params",
    "type": "choice",
    "options": ["h", "q", "t", "all"],
    "tool_values": {"h": "H", "q": "Q", "t": "T"},
    "required": True,
    "depends_on": {"dataset": ["pl_hydro_semiannual"]},
}

_STORE_SELECTION: list[ParamSpec] = [
    dataset_param(SERIES_DATASETS),
    years_param(SERIES_DATASETS),
    stations_param(SERIES_DATASETS),
]

OPERATIONS: list[OperationSpec] = [
    {
        "id": "download_hydro_archives",
        "category": CATEGORY,
        "description": "Download the archive files of a hydrological dataset "
        "(IMGW-PIB or ČHMÚ) to the result folder, as published",
        "inputs": [],
        "outputs": ["imgw_archive"],
        "params": [
            dataset_param(HYDRO_DOWNLOAD_DATASETS),
            years_param(HYDRO_DOWNLOAD_DATASETS),
            _HYDRO_PARAMS,
            stations_param(HYDRO_DOWNLOAD_DATASETS),
        ],
        "calls": f"{_CALLS}:download_hydro_archives",
        "commands": ["datasets download"],
        "describe": f"{_DESCRIBE}:describe_download_archives",
        "preview": f"{_PREVIEW}:preview_download_archives",
        "no_check": _NO_DOWNLOAD_CHECK,
        "excluded": _excluded(HYDRO_DOWNLOAD_DATASETS, "download_meteo_archives"),
    },
    {
        "id": "download_meteo_archives",
        "category": CATEGORY,
        "description": "Download the archive files of a meteorological dataset "
        "(IMGW-PIB or ČHMÚ) to the result folder, as published",
        "inputs": [],
        "outputs": ["imgw_archive"],
        "params": [
            dataset_param(METEO_DOWNLOAD_DATASETS),
            years_param(METEO_DOWNLOAD_DATASETS),
            stations_param(METEO_DOWNLOAD_DATASETS),
        ],
        "calls": f"{_CALLS}:download_meteo_archives",
        "commands": ["datasets download"],
        "describe": f"{_DESCRIBE}:describe_download_archives",
        "preview": f"{_PREVIEW}:preview_download_archives",
        "no_check": _NO_DOWNLOAD_CHECK,
        "excluded": _excluded(METEO_DOWNLOAD_DATASETS, "download_hydro_archives"),
    },
    {
        "id": "check_imgw_archives",
        "category": CATEGORY,
        "description": "Check what the IMGW servers have newer or missing "
        "against the store, without downloading data; saves the plan",
        "inputs": [],
        "outputs": ["imgw_plan"],
        "params": [*_STORE_SELECTION],
        "calls": f"{_CALLS}:check_imgw_archives",
        "commands": ["store check"],
        "describe": f"{_DESCRIBE}:describe_check_archives",
        "preview": f"{_PREVIEW}:preview_check_imgw_archives",
    },
    {
        "id": "sync_imgw_store",
        "category": CATEGORY,
        "description": "Download new and missing archives into the IMGW store "
        "and build the series of the datasets",
        "inputs": [],
        "outputs": [],
        "params": [*_STORE_SELECTION],
        "calls": f"{_CALLS}:sync_imgw_store",
        "commands": ["store sync"],
        "describe": f"{_DESCRIBE}:describe_sync_store",
        "preview": f"{_PREVIEW}:preview_sync_imgw_store",
        "check": f"{_PREVIEW}:check_sync_imgw_store",
    },
    {
        "id": "sync_imgw_store_by_plan",
        "category": CATEGORY,
        "description": "Download into the IMGW store exactly what a saved "
        "archive check plan lists",
        "inputs": [{"name": "plan", "kind": "imgw_plan"}],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:sync_imgw_store_by_plan",
        "commands": ["store sync"],
        "describe": f"{_DESCRIBE}:describe_sync_store",
        "preview": f"{_PREVIEW}:preview_sync_imgw_store_by_plan",
        "no_check": "The plan is the result of the separately confirmed check of "
        "check_imgw_archives. The check twin of 'store sync' given a plan returns "
        "that plan unchanged (no request), and the tool itself leaves an item whose "
        "source changed since as stale_plan instead of downloading it.",
    },
    {
        "id": "export_imgw_archive",
        "category": CATEGORY,
        "description": "Export the records of stored archives of a dataset "
        "(current versions) to CSV or JSON Lines in the result folder",
        "inputs": [],
        "outputs": ["archive_records"],
        "params": [
            dataset_param(SERIES_DATASETS),
            years_param(SERIES_DATASETS),
            {
                "name": "format",
                "type": "choice",
                "options": ["csv", "jsonl"],
                "required": True,
            },
        ],
        "calls": f"{_CALLS}:export_imgw_archive",
        "commands": ["store export"],
        "describe": f"{_DESCRIBE}:describe_export_archive",
        "preview": f"{_PREVIEW}:preview_export_imgw_archive",
    },
    {
        "id": "init_imgw_store",
        "category": CATEGORY,
        "description": "Create the empty IMGW store in the configured folder",
        "inputs": [],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:init_imgw_store",
        "commands": ["store init"],
        "describe": f"{_DESCRIBE}:describe_init_store",
        "preview": f"{_PREVIEW}:preview_init_imgw_store",
    },
    {
        "id": "inspect_imgw_store",
        "category": CATEGORY,
        "description": "Describe the IMGW store: its state and the versions "
        "it holds (archives, series, catalogs, PMAXTP cells)",
        "inputs": [],
        "outputs": ["imgw_report"],
        "params": [
            {
                "name": "kind",
                "type": "choice",
                "options": [
                    "archive",
                    "series",
                    "catalog",
                    "pmaxtp",
                    "observation",
                    "problem",
                ],
            },
            provider_param(required=False),
        ],
        "calls": f"{_CALLS}:inspect_imgw_store",
        "commands": ["store info", "store scan"],
        "describe": f"{_DESCRIBE}:describe_inspect_store",
        "preview": f"{_PREVIEW}:preview_inspect_imgw_store",
    },
]

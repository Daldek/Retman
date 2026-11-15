"""The ``obserwator_archives`` operations: archive files, the store and its plans.

Nine operations (research-imgw 2 and 5.3, nos. 12-19, and the synoptic downloads):
downloading archives to the result folder, checking and synchronising the
Obserwator store, exporting stored archives and looking into the store. The
manifest of the tool lists ``OPERATIONS`` among its own; nothing here imports the
tool.
"""

from collections.abc import Sequence

from retman.registry.manifest import OperationSpec, ParamSpec
from retman.tools.obserwator.params import (
    DATASETS,
    HYDRO_DOWNLOAD_DATASETS,
    METEO_DOWNLOAD_DATASETS,
    SERIES_DATASETS,
    SYNOP_DOWNLOAD_DATASETS,
    dataset_param,
    provider_param,
)

_CALLS = "retman.tools.obserwator.calls_archives"
_DESCRIBE = "retman.tools.obserwator.describe_archives"
_PREVIEW = "retman.tools.obserwator.preview_archives"
CATEGORY = "obserwator_archives"

# ČHMÚ keeps the whole history of a station in one file per element, so the
# tool refuses ``years`` for this dataset
_WHOLE_HISTORY = "cz_meteo_daily"

# Why the download operations offer no availability check (``no_check``, X7)
_NO_DOWNLOAD_CHECK = (
    "The check_command of 'datasets download' is an offline dry run (URLs and "
    "target paths, no request). The tool's one network check of archives is "
    "'store check': it needs a store and takes the series datasets only, and it "
    "is the operation check_obserwator_archives. A file the servers do not publish is "
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
    """Station archives are chosen by station; country-wide archives cover them all.

    The ČHMÚ files and the synoptic archives of IMGW-PIB hold one station each;
    the tool needs their stations (or, for the synoptic ones, the running year's
    months, which Retman does not offer).
    """
    return {
        "name": "stations",
        "type": "free",
        "extractor": "station",
        "multiple": True,
        "required": True,
        "depends_on": {
            "dataset": [
                key for key in datasets if DATASETS[key]["archive_scope"] != "country"
            ]
        },
    }


# The download operation that offers each dataset
_DOWNLOADS: dict[str, tuple[str, ...]] = {
    "download_hydro_archives": HYDRO_DOWNLOAD_DATASETS,
    "download_meteo_archives": METEO_DOWNLOAD_DATASETS,
    "download_synop_archives": SYNOP_DOWNLOAD_DATASETS,
}


def _excluded(operation: str) -> dict[str, dict[str, str]]:
    """Return the country-wide datasets the other download operations serve (X4).

    A station dataset (ČHMÚ, IMGW-PIB synop) of another operation is not listed:
    it needs stations of its provider and a combination of ``stations`` and
    ``years`` that no call of this operation makes, so the tool refuses it here
    and nothing is left uncovered (X4 says so if that changes).
    """
    others = {
        DATASETS[key]["tool_value"]: other
        for other, keys in _DOWNLOADS.items()
        if other != operation
        for key in keys
        if DATASETS[key]["archive_scope"] == "country"
    }
    return {"dataset": others}


def _download(operation: str, extra: Sequence[ParamSpec] = ()) -> list[ParamSpec]:
    """Dataset, years and stations of a download operation, then ``extra``."""
    datasets = _DOWNLOADS[operation]
    return [
        dataset_param(datasets),
        years_param(datasets),
        *extra,
        stations_param(datasets),
    ]


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
        "outputs": ["obserwator_archive", "provider_attribution"],
        "params": _download("download_hydro_archives", [_HYDRO_PARAMS]),
        "calls": f"{_CALLS}:download_hydro_archives",
        "commands": ["datasets download"],
        "describe": f"{_DESCRIBE}:describe_download_archives",
        "preview": f"{_PREVIEW}:preview_download_archives",
        "no_check": _NO_DOWNLOAD_CHECK,
        "excluded": _excluded("download_hydro_archives"),
    },
    {
        "id": "download_meteo_archives",
        "category": CATEGORY,
        "description": "Download the archive files of a meteorological dataset "
        "(IMGW-PIB or ČHMÚ) to the result folder, as published",
        "inputs": [],
        "outputs": ["obserwator_archive", "provider_attribution"],
        "params": _download("download_meteo_archives"),
        "calls": f"{_CALLS}:download_meteo_archives",
        "commands": ["datasets download"],
        "describe": f"{_DESCRIBE}:describe_download_archives",
        "preview": f"{_PREVIEW}:preview_download_archives",
        "no_check": _NO_DOWNLOAD_CHECK,
        "excluded": _excluded("download_meteo_archives"),
    },
    {
        "id": "download_synop_archives",
        "category": CATEGORY,
        "description": "Download the archive files of a synoptic dataset of IMGW-PIB "
        "(daily, monthly or at observation times) to the result folder, as published",
        "inputs": [],
        "outputs": ["obserwator_archive", "provider_attribution"],
        "params": _download("download_synop_archives"),
        "calls": f"{_CALLS}:download_synop_archives",
        "commands": ["datasets download"],
        "describe": f"{_DESCRIBE}:describe_download_archives",
        "preview": f"{_PREVIEW}:preview_download_archives",
        "no_check": _NO_DOWNLOAD_CHECK,
        "excluded": _excluded("download_synop_archives"),
    },
    {
        "id": "check_obserwator_archives",
        "category": CATEGORY,
        "description": "Check what the IMGW servers have newer or missing "
        "against the store, without downloading data; saves the plan",
        "inputs": [],
        "outputs": ["obserwator_plan"],
        "params": [*_STORE_SELECTION],
        "calls": f"{_CALLS}:check_obserwator_archives",
        "commands": ["store check"],
        "describe": f"{_DESCRIBE}:describe_check_archives",
        "preview": f"{_PREVIEW}:preview_check_obserwator_archives",
    },
    {
        "id": "sync_obserwator_store",
        "category": CATEGORY,
        "description": "Download new and missing archives into the Obserwator store "
        "and build the series of the datasets",
        "inputs": [],
        "outputs": [],
        "params": [*_STORE_SELECTION],
        "calls": f"{_CALLS}:sync_obserwator_store",
        "commands": ["store sync", "series build"],
        "describe": f"{_DESCRIBE}:describe_sync_store",
        "preview": f"{_PREVIEW}:preview_sync_obserwator_store",
        "check": f"{_PREVIEW}:check_sync_obserwator_store",
    },
    {
        "id": "sync_obserwator_store_by_plan",
        "category": CATEGORY,
        "description": "Download into the Obserwator store exactly what a saved "
        "archive check plan lists",
        "inputs": [{"name": "plan", "kind": "obserwator_plan"}],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:sync_obserwator_store_by_plan",
        "commands": ["store sync"],
        "describe": f"{_DESCRIBE}:describe_sync_store",
        "preview": f"{_PREVIEW}:preview_sync_obserwator_store_by_plan",
        "no_check": "The plan is the result of the separately confirmed check of "
        "check_obserwator_archives. The check twin of 'store sync' given a plan "
        "returns that plan unchanged (no request), and the tool itself leaves an item "
        "whose source changed since as stale_plan instead of downloading it.",
    },
    {
        "id": "export_obserwator_archive",
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
        "calls": f"{_CALLS}:export_obserwator_archive",
        "commands": ["store export"],
        "describe": f"{_DESCRIBE}:describe_export_archive",
        "preview": f"{_PREVIEW}:preview_export_obserwator_archive",
    },
    {
        "id": "init_obserwator_store",
        "category": CATEGORY,
        "description": "Create the empty Obserwator store in the configured folders "
        "(the raw data folder and the data folder)",
        "inputs": [],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:init_obserwator_store",
        "commands": ["store init"],
        "describe": f"{_DESCRIBE}:describe_init_store",
        "preview": f"{_PREVIEW}:preview_init_obserwator_store",
    },
    {
        "id": "inspect_obserwator_store",
        "category": CATEGORY,
        "description": "Describe the Obserwator store: its state and the versions "
        "it holds (archives, series, catalogs, PMAXTP cells, analyses)",
        "inputs": [],
        "outputs": ["obserwator_report"],
        "params": [
            {
                "name": "kind",
                "type": "choice",
                "options": [
                    "archive",
                    "series",
                    "catalog",
                    "pmaxtp",
                    "analyses",
                    "observation",
                    "problem",
                ],
            },
            provider_param(required=False),
        ],
        "calls": f"{_CALLS}:inspect_obserwator_store",
        "commands": ["store info", "store scan"],
        "describe": f"{_DESCRIBE}:describe_inspect_store",
        "preview": f"{_PREVIEW}:preview_inspect_obserwator_store",
    },
]

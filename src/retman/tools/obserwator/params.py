"""Parameter definitions shared by the Obserwator operations (imports no tool).

The datasets are offered by option keys (``pl_hydro_daily``) because a dot
breaks translation keys; ``tool_values`` maps them to the tool's own keys
(``pl.imgw.hydro_daily``). ``option_meta`` carries what builders and
context-aware extractors need to know about a dataset without importing the
tool: its provider, kind (``hydro``/``meteo``), archive year numbering, archive
scope (country-wide or per station) and variables. A drift test compares every
entry with the registry of the installed tool.
"""

from collections.abc import Sequence
from typing import Final, TypedDict

from retman.registry.manifest import ParamSpec


class DatasetInfo(TypedDict):
    """What Retman knows about one Obserwator dataset (see ``DATASETS``)."""

    tool_value: str
    provider: str
    kind: str
    numbering: str
    variables: list[str]
    slug: str
    archive_scope: str
    series: bool


_HYDRO_STATISTICS = [
    f"{letter}_{statistic}"
    for letter in ("H", "Q", "T")
    for statistic in ("min", "mean", "max")
]

# Variables of the daily synoptic data: the climate names for the same quantities,
# then the synoptic ones (the joined lines S and S_T of IMGW-PIB, Obserwator ADR-022)
_SYNOP_DAILY_VARIABLES = [
    "Tmax",
    "Tmin",
    "Tmean",
    "Tground",
    "P",
    "snow_cover",
    "snow_water_equivalent",
    "sunshine",
    "rain_duration",
    "snowfall_duration",
    "sleet_duration",
    "hail_duration",
    "fog_duration",
    "mist_duration",
    "rime_duration",
    "glaze_duration",
    "drifting_snow_duration",
    "blowing_snow_duration",
    "haze_duration",
    "wind_10_duration",
    "wind_15_duration",
    "thunderstorm_duration",
    "dew_duration",
    "hoarfrost_duration",
    "snow_cover_occurrence",
    "lightning_occurrence",
    "isotherm_lower",
    "isotherm_upper",
    "actinometry",
    "cloud_cover",
    "wind_speed",
    "vapour_pressure",
    "humidity",
    "pressure_station",
    "pressure_sea",
    "P_day",
    "P_night",
]

# Option key -> dataset. The first eight are series datasets (the store builds
# series of them and ``series export`` reads them), the rest are downloaded
# only. ``numbering`` is how the dataset's archives are numbered by year:
# ``hydrological`` (1 XI of the previous year – 31 X) or ``calendar``.
# ``archive_scope`` is the tool's: ``country`` archives cover every station, the
# others hold one station each, so a selection of them names the stations.
DATASETS: Final[dict[str, DatasetInfo]] = {
    "pl_hydro_daily": {
        "tool_value": "pl.imgw.hydro_daily",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": ["H", "Q", "T"],
        "slug": "hydro_daily",
        "archive_scope": "country",
        "series": True,
    },
    "pl_hydro_monthly": {
        "tool_value": "pl.imgw.hydro_monthly",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": _HYDRO_STATISTICS,
        "slug": "hydro_monthly",
        "archive_scope": "country",
        "series": True,
    },
    "pl_hydro_semiannual": {
        "tool_value": "pl.imgw.hydro_semiannual",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": _HYDRO_STATISTICS,
        "slug": "hydro_semiannual",
        "archive_scope": "country",
        "series": True,
    },
    "pl_meteo_climate_daily": {
        "tool_value": "pl.imgw.meteo_climate_daily",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["Tmax", "Tmin", "Tmean", "Tground", "P", "snow_cover"],
        "slug": "meteo_climate_daily",
        "archive_scope": "country",
        "series": True,
    },
    "pl_meteo_precip_daily": {
        "tool_value": "pl.imgw.meteo_precip_daily",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["P", "snow_cover", "fresh_snow"],
        "slug": "meteo_precip_daily",
        "archive_scope": "country",
        "series": True,
    },
    "pl_meteo_synop_daily": {
        "tool_value": "pl.imgw.meteo_synop_daily",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": _SYNOP_DAILY_VARIABLES,
        "slug": "meteo_synop_daily",
        "archive_scope": "station_year",
        "series": True,
    },
    "cz_hydro_daily": {
        "tool_value": "cz.chmi.hydro_daily",
        "provider": "CHMI",
        "kind": "hydro",
        "numbering": "calendar",
        "variables": ["H", "Q", "T"],
        "slug": "chmi_hydro_daily",
        "archive_scope": "station_year",
        "series": True,
    },
    "cz_meteo_daily": {
        "tool_value": "cz.chmi.meteo_daily",
        "provider": "CHMI",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["P", "Tmean", "Tmax", "Tmin"],
        "slug": "chmi_meteo_daily",
        "archive_scope": "station_element",
        "series": True,
    },
    "pl_hydro_phenomena": {
        "tool_value": "pl.imgw.hydro_phenomena",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": [],
        "slug": "hydro_phenomena",
        "archive_scope": "country",
        "series": False,
    },
    "pl_warnings_hydro_archive": {
        "tool_value": "pl.imgw.warnings_hydro_archive",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "calendar",
        "variables": [],
        "slug": "warnings_hydro_archive",
        "archive_scope": "country",
        "series": False,
    },
    "pl_meteo_climate_monthly": {
        "tool_value": "pl.imgw.meteo_climate_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_climate_monthly",
        "archive_scope": "country",
        "series": False,
    },
    "pl_meteo_precip_monthly": {
        "tool_value": "pl.imgw.meteo_precip_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_precip_monthly",
        "archive_scope": "country",
        "series": False,
    },
    "pl_meteo_synop_monthly": {
        "tool_value": "pl.imgw.meteo_synop_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_synop_monthly",
        "archive_scope": "country",
        "series": False,
    },
    "pl_meteo_climate_terms": {
        "tool_value": "pl.imgw.meteo_climate_terms",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_climate_terms",
        "archive_scope": "country",
        "series": False,
    },
    "pl_meteo_synop_terms": {
        "tool_value": "pl.imgw.meteo_synop_terms",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_synop_terms",
        "archive_scope": "station_year",
        "series": False,
    },
    "pl_warnings_meteo_archive": {
        "tool_value": "pl.imgw.warnings_meteo_archive",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "warnings_meteo_archive",
        "archive_scope": "country",
        "series": False,
    },
    "pl_actinometric": {
        "tool_value": "pl.imgw.actinometric",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "actinometric",
        "archive_scope": "country",
        "series": False,
    },
}

SERIES_DATASETS: Final[tuple[str, ...]] = tuple(
    key for key, info in DATASETS.items() if info["series"]
)
# The download operations: the synoptic datasets have one of their own, because a
# choice offers at most nine options (ARCHITECTURE 3.4)
SYNOP_DOWNLOAD_DATASETS: Final[tuple[str, ...]] = (
    "pl_meteo_synop_daily",
    "pl_meteo_synop_monthly",
    "pl_meteo_synop_terms",
)
HYDRO_DOWNLOAD_DATASETS: Final[tuple[str, ...]] = tuple(
    key for key, info in DATASETS.items() if info["kind"] == "hydro"
)
METEO_DOWNLOAD_DATASETS: Final[tuple[str, ...]] = tuple(
    key
    for key, info in DATASETS.items()
    if info["kind"] == "meteo" and key not in SYNOP_DOWNLOAD_DATASETS
)

# Option key of the ``provider`` choice -> the tool's provider identifier
PROVIDER_VALUES: Final[dict[str, str]] = {"imgw_pib": "IMGW-PIB", "chmi": "CHMI"}


def dataset_param(
    keys: Sequence[str], *, name: str = "dataset", required: bool = True
) -> ParamSpec:
    """Build a ``choice`` parameter offering the datasets ``keys`` (option keys).

    ``tool_values`` map the keys to the tool's dataset keys and ``option_meta``
    gives each option its provider, kind, archive numbering and scope, variables
    and slug (the scope of the ``station`` and ``variables`` extractors).
    """
    spec: ParamSpec = {
        "name": name,
        "type": "choice",
        "options": list(keys),
        "tool_values": {key: DATASETS[key]["tool_value"] for key in keys},
        "option_meta": {
            key: {
                "provider": DATASETS[key]["provider"],
                "kind": DATASETS[key]["kind"],
                "numbering": DATASETS[key]["numbering"],
                "variables": list(DATASETS[key]["variables"]),
                "slug": DATASETS[key]["slug"],
                "archive_scope": DATASETS[key]["archive_scope"],
            }
            for key in keys
        },
    }
    if required:
        spec["required"] = True
    return spec


def provider_param(*, name: str = "provider", required: bool = True) -> ParamSpec:
    """Build a ``choice`` parameter of the two data providers (IMGW-PIB, ČHMÚ)."""
    spec: ParamSpec = {
        "name": name,
        "type": "choice",
        "options": list(PROVIDER_VALUES),
        "tool_values": dict(PROVIDER_VALUES),
    }
    if required:
        spec["required"] = True
    return spec

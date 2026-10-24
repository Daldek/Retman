"""Parameter definitions shared by the IMGWTools operations (imports no tool).

The datasets are offered by option keys (``pl_hydro_daily``) because a dot
breaks translation keys; ``tool_values`` maps them to the tool's own keys
(``pl.imgw.hydro_daily``). ``option_meta`` carries what builders and
context-aware extractors need to know about a dataset without importing the
tool: its provider, kind (``hydro``/``meteo``), archive year numbering and
variables. A drift test compares every entry with the registry of the
installed tool.
"""

from collections.abc import Sequence
from typing import Final, TypedDict

from retman.registry.manifest import ParamSpec


class DatasetInfo(TypedDict):
    """What Retman knows about one IMGWTools dataset (see ``DATASETS``)."""

    tool_value: str
    provider: str
    kind: str
    numbering: str
    variables: list[str]
    slug: str
    first_year: int | None
    series: bool


_HYDRO_STATISTICS = [
    f"{letter}_{statistic}"
    for letter in ("H", "Q", "T")
    for statistic in ("min", "mean", "max")
]

# Option key -> dataset. The first seven are series datasets (the store builds
# series of them and ``series export`` reads them), the rest are downloaded
# only. ``numbering`` is how the dataset's archives are numbered by year:
# ``hydrological`` (1 XI of the previous year – 31 X) or ``calendar``.
DATASETS: Final[dict[str, DatasetInfo]] = {
    "pl_hydro_daily": {
        "tool_value": "pl.imgw.hydro_daily",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": ["H", "Q", "T"],
        "slug": "hydro_daily",
        "first_year": 1951,
        "series": True,
    },
    "pl_hydro_monthly": {
        "tool_value": "pl.imgw.hydro_monthly",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": _HYDRO_STATISTICS,
        "slug": "hydro_monthly",
        "first_year": 1951,
        "series": True,
    },
    "pl_hydro_semiannual": {
        "tool_value": "pl.imgw.hydro_semiannual",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": _HYDRO_STATISTICS,
        "slug": "hydro_semiannual",
        "first_year": 1951,
        "series": True,
    },
    "pl_meteo_climate_daily": {
        "tool_value": "pl.imgw.meteo_climate_daily",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["Tmax", "Tmin", "Tmean", "Tground", "P", "snow_cover"],
        "slug": "meteo_climate_daily",
        "first_year": 1951,
        "series": True,
    },
    "pl_meteo_precip_daily": {
        "tool_value": "pl.imgw.meteo_precip_daily",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["P", "snow_cover", "fresh_snow"],
        "slug": "meteo_precip_daily",
        "first_year": 1950,
        "series": True,
    },
    "cz_hydro_daily": {
        "tool_value": "cz.chmi.hydro_daily",
        "provider": "CHMI",
        "kind": "hydro",
        "numbering": "calendar",
        "variables": ["H", "Q", "T"],
        "slug": "chmi_hydro_daily",
        "first_year": 1887,
        "series": True,
    },
    "cz_meteo_daily": {
        "tool_value": "cz.chmi.meteo_daily",
        "provider": "CHMI",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": ["P", "Tmean", "Tmax", "Tmin"],
        "slug": "chmi_meteo_daily",
        "first_year": None,
        "series": True,
    },
    "pl_hydro_phenomena": {
        "tool_value": "pl.imgw.hydro_phenomena",
        "provider": "IMGW-PIB",
        "kind": "hydro",
        "numbering": "hydrological",
        "variables": [],
        "slug": "hydro_phenomena",
        "first_year": 1951,
        "series": False,
    },
    "pl_meteo_climate_monthly": {
        "tool_value": "pl.imgw.meteo_climate_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_climate_monthly",
        "first_year": 1951,
        "series": False,
    },
    "pl_meteo_precip_monthly": {
        "tool_value": "pl.imgw.meteo_precip_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_precip_monthly",
        "first_year": 1950,
        "series": False,
    },
    "pl_meteo_synop_monthly": {
        "tool_value": "pl.imgw.meteo_synop_monthly",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_synop_monthly",
        "first_year": 1960,
        "series": False,
    },
    "pl_meteo_climate_terms": {
        "tool_value": "pl.imgw.meteo_climate_terms",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "numbering": "calendar",
        "variables": [],
        "slug": "meteo_climate_terms",
        "first_year": 1951,
        "series": False,
    },
}

SERIES_DATASETS: Final[tuple[str, ...]] = tuple(
    key for key, info in DATASETS.items() if info["series"]
)
HYDRO_DOWNLOAD_DATASETS: Final[tuple[str, ...]] = tuple(
    key for key, info in DATASETS.items() if info["kind"] == "hydro"
)
METEO_DOWNLOAD_DATASETS: Final[tuple[str, ...]] = tuple(
    key for key, info in DATASETS.items() if info["kind"] == "meteo"
)

# Option key of the ``provider`` choice -> the tool's provider identifier
PROVIDER_VALUES: Final[dict[str, str]] = {"imgw_pib": "IMGW-PIB", "chmi": "CHMI"}


def dataset_param(
    keys: Sequence[str], *, name: str = "dataset", required: bool = True
) -> ParamSpec:
    """Build a ``choice`` parameter offering the datasets ``keys`` (option keys).

    ``tool_values`` map the keys to the tool's dataset keys and ``option_meta``
    gives each option its provider, kind, archive numbering, variables and slug
    (the scope of the ``station`` and ``variables`` extractors).
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

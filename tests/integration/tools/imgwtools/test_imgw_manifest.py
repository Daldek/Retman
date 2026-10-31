"""The IMGWTools manifest against the installed tool: drift is a failing test.

The manifest names datasets, option values, kinds and CSV columns of the tool
without importing it; these tests compare each of them with the tool's own
registry, catalog and models, so a release that renames or adds one is noticed
here and not by a user.
"""

import dataclasses
from collections import Counter
from pathlib import Path
from typing import Any

import imgwtools
import pytest
from imgwtools import (
    HydroCurrentData,
    HydroState,
    MeteoCurrentData,
    StationListEntry,
    SynopData,
    WarningData,
)

from retman.adapters.catalog import load_reference
from retman.extractors.coordinates import PMAXTP_LATITUDE, PMAXTP_LONGITUDE
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.tools.imgwtools import describe
from retman.tools.imgwtools import manifest as imgw_manifest
from retman.tools.imgwtools.params import DATASETS, PROVIDER_VALUES, SERIES_DATASETS

MANIFEST = imgw_manifest.MANIFEST
CATALOG = {command.name: command for command in imgwtools.data_commands()}
# Error codes only the REST API of the tool reports; the library never raises them
REST_ONLY = {"forbidden", "method_not_allowed"}


@pytest.fixture(scope="module")
def operations() -> dict[str, Operation]:
    return load_operations(
        "pl",
        manifests=[(MANIFEST, Path(imgw_manifest.__file__).parent)],
        version_lookup=lambda _: "3.0.0",
    )


def test_the_manifest_has_19_operations_in_five_categories(operations):
    assert len(operations) == 19
    assert Counter(operation.category for operation in operations.values()) == {
        "imgw_catalog": 3,
        "imgw_current": 3,
        "imgw_pmaxtp": 2,
        "imgw_series": 3,
        "imgw_archives": 8,
    }


def test_every_reference_of_every_operation_resolves_to_a_function(operations):
    for operation in operations.values():
        for key in ("calls", "describe", "preview", "check"):
            if key in operation.spec:
                assert callable(load_reference(operation.spec[key])), (
                    operation.id,
                    key,
                )
    assert callable(load_reference(MANIFEST["client"]))


def test_the_tool_version_range_is_the_released_major():
    assert MANIFEST["supported_versions"] == ">=3.0.0.dev0,<4"
    assert MANIFEST["distribution"] == "imgwtools"
    assert "imgwtools[store]" in MANIFEST["source"]


def test_the_datasets_of_the_manifest_are_the_datasets_of_the_tool():
    registry = {descriptor.key: descriptor for descriptor in imgwtools.datasets()}

    for key, info in DATASETS.items():
        descriptor = registry[info["tool_value"]]
        assert (descriptor.provider, descriptor.kind) == (
            info["provider"],
            info["kind"],
        )
        assert descriptor.year_type == info["numbering"], key
        assert list(descriptor.variables) == info["variables"], key
        assert descriptor.slug == info["slug"], key
        assert descriptor.first_year == info["first_year"], key
        assert descriptor.in_store == info["series"], key
    # Every dataset with data of its own is offered; station lists and PMAXTP are not
    with_data = {
        descriptor.key
        for descriptor in registry.values()
        if descriptor.kind and descriptor.time_unit != "station_list"
    }
    assert with_data == {info["tool_value"] for info in DATASETS.values()}


def test_the_series_datasets_are_exactly_those_the_catalog_builds_series_of():
    series = {DATASETS[key]["tool_value"] for key in SERIES_DATASETS}

    for command in ("series build", "series export", "series summary"):
        option = next(o for o in CATALOG[command].options if o.name == "dataset")
        assert set(option.choices) == series, command
    store = next(o for o in CATALOG["store sync"].options if o.name == "datasets")
    assert set(store.choices) == series


def option_choices(command: str, option: str) -> set[str]:
    return set(next(o for o in CATALOG[command].options if o.name == option).choices)


CHOICES = [
    ("find_imgw_stations", "provider", "stations find", "provider"),
    ("find_imgw_stations", "kind", "stations find", "kind"),
    ("find_imgw_stations", "data_source", "stations find", "source"),
    ("build_imgw_station_catalog", "provider", "store catalog", "provider"),
    ("list_imgw_datasets", "provider", "datasets list", "provider"),
    ("list_imgw_datasets", "kind", "datasets list", "kind"),
    ("fetch_imgw_warnings", "kind", "current warnings", "kind"),
    ("get_pmaxtp", "method", "pmaxtp fetch", "method"),
    ("get_pmaxtp", "method", "pmaxtp sync", "method"),
    ("read_stored_pmaxtp", "method", "pmaxtp read", "method"),
    ("export_station_series", "dataset", "series export", "dataset"),
    ("export_station_series", "year_type", "series export", "year_type"),
    ("show_station_coverage", "dataset", "series summary", "dataset"),
    ("build_imgw_series", "dataset", "series build", "dataset"),
]


@pytest.mark.parametrize(("operation", "param", "command", "option"), CHOICES)
def test_every_offered_choice_is_a_value_the_tool_accepts_and_none_is_missing(
    operations, operation, param, command, option
):
    spec = operations[operation].parameter(param)
    assert spec is not None
    offered = {spec.get("tool_values", {}).get(key, key) for key in spec["options"]}
    assert offered == option_choices(command, option)


def test_a_source_that_only_the_adapter_names_maps_to_the_tools_source(operations):
    spec = operations["find_imgw_stations"].parameter("data_source")
    assert spec is not None and spec["tool_values"] == {
        "server": "live",
        "store": "store",
    }
    assert set(PROVIDER_VALUES.values()) == option_choices("stations find", "provider")


def test_the_pmaxtp_frame_is_the_frame_of_the_catalog():
    option = {o.name: o for o in CATALOG["pmaxtp fetch"].options}

    assert (option["latitude"].minimum, option["latitude"].maximum) == PMAXTP_LATITUDE
    assert (
        option["longitude"].minimum,
        option["longitude"].maximum,
    ) == PMAXTP_LONGITUDE


def test_the_csv_columns_are_the_fields_of_the_tools_models():
    stations = tuple(field.name for field in dataclasses.fields(StationListEntry))
    assert set(describe.STATION_COLUMNS) == set(stations)
    models: dict[str, Any] = {
        "hydro": HydroCurrentData,
        "meteo": MeteoCurrentData,
        "synop": SynopData,
    }
    for source, model in models.items():
        assert describe.CURRENT_COLUMNS[source] == tuple(model.model_fields), source
    assert tuple(WarningData.model_fields) == describe.WARNING_COLUMNS
    assert tuple(HydroState.model_fields) == describe.HYDRO_STATE_COLUMNS


def test_every_error_code_of_the_tool_has_a_text(operations):
    texts = operations["find_imgw_stations"].texts
    codes = set(imgwtools.ERROR_CODES) - REST_ONLY

    for code in sorted(codes | {"store_write_unsupported", "failed"}):
        assert texts.has(f"errors.{code}"), code

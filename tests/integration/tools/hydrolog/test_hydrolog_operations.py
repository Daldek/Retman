"""The Hydrolog operations against the real tool: calls, previews and results.

Hydrolog computes offline in process, so the builders' calls are judged by the real
``validate_command``, the previews let the real tool compute the plan and the runs
write real ``hydrolog-result/1`` documents into the result folder.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from hydrolog_support import (
    TEXTURE_COUNTS,
    context,
    inflow_network,
    operations,
    rain_network,
    series_file,
    texture_rasters,
    watershed_file,
)

from retman.adapters.catalog import CatalogCall, ToolError, run_calls
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.tools.hydrolog import calls, preview
from retman.tools.hydrolog.client import HydrologClient

EFFECTIVE = {"cn": 72, "rainfall": 50, "amc": "normal"}
HYETOGRAPH = {
    "hyetograph": "euler_ii",
    "rainfall": 38.4,
    "duration": 120,
    "time_step": 5,
}
HYDROGRAPH = {
    "catchment_area": 45.3,
    "cn": 72,
    "concentration_time": 90,
    "hyetograph": "euler_ii",
    "rainfall": 62,
    "duration": 120,
    "time_step": 5,
    "amc": "normal",
}


def run(
    tmp_path: Path, name: str, params: dict[str, Any], inputs: dict[str, Path]
) -> HandlerOutput:
    """Run the operation's calls with the real Hydrolog into a result folder."""
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(name, inputs=inputs, output_dir=output_dir)
    return run_calls(operations()[name], params, inputs, output_dir, ctx)


def test_the_moisture_and_the_shape_are_hydrologs_own_values() -> None:
    params = {**HYDROGRAPH, "amc": "wet", "hyetograph": "beta"}

    (call,) = calls.generate_design_hydrograph(
        params, context("generate_design_hydrograph")
    )

    assert call.options["amc"] == "III"
    assert call.options["hietogram_type"] == "beta"
    assert call.options["uh_model"] == "scs"
    HydrologClient({}).validate(call)


def test_probabilities_become_the_return_periods_hydrolog_takes(
    tmp_path: Path,
) -> None:
    series = series_file(tmp_path)
    ctx = context("estimate_flood_quantiles", inputs={"series": series})
    params = {"distribution": "all", "probability": [0.01, 0.1, 0.002]}

    (call,) = calls.estimate_flood_quantiles(params, ctx)

    assert call.options["return_periods"] == [100.0, 10.0, 500.0]
    assert call.options["input_file"] == str(series)
    # Without probabilities the tool's own periods apply
    (bare,) = calls.estimate_flood_quantiles({"distribution": "all"}, ctx)
    assert "return_periods" not in bare.options


@pytest.mark.parametrize(
    ("command", "options"),
    [
        ("soil hsg", {}),
        ("gui serve", {}),
        # A network routed into files: only the call that names no output is a lookup
        ("route network", {"network_file": "siec.json", "output_dir": "out"}),
        ("route network", {"network_file": "siec.json", "schematic": "siec.svg"}),
    ],
)
def test_a_lookup_never_runs_a_call_that_writes_or_serves(
    command: str, options: dict[str, object]
) -> None:
    with pytest.raises(ToolError) as caught:
        HydrologClient({}).lookup(CatalogCall(command, options))

    assert caught.value.tool_code == "not_offline"


def test_a_network_is_routed_in_memory_while_planning_and_into_files_at_the_run(
    tmp_path: Path,
) -> None:
    network = rain_network(tmp_path)

    (planned,) = calls.route_river_network(
        {}, context("route_river_network", inputs={"network": network})
    )
    (running,) = calls.route_river_network(
        {},
        context(
            "route_river_network",
            inputs={"network": network},
            output_dir=tmp_path / "result",
        ),
    )

    assert set(planned.options) == {"network_file"}
    assert running.options["output_dir"] == str(tmp_path / "result" / "hydrographs")
    assert running.options["schematic"] == str(tmp_path / "result" / "network.svg")
    # The planning call computes and writes nothing
    document = HydrologClient({}).lookup(planned)
    assert document["result"]["outlet"] == "OUT"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["siec.json"]


def test_a_rejected_rainfall_is_asked_again_as_the_rainfall() -> None:
    (call,) = calls.compute_effective_rainfall(
        {**EFFECTIVE, "rainfall": -5}, context("compute_effective_rainfall")
    )

    with pytest.raises(ToolError) as caught:
        HydrologClient({}).validate(call)

    assert caught.value.option == "precipitation_mm"
    assert call.params[caught.value.option] == "rainfall"


def test_the_effective_rainfall_is_a_report_with_its_numbers(tmp_path: Path) -> None:
    output = run(tmp_path, "compute_effective_rainfall", EFFECTIVE, {})

    (path,) = output["files"]["hydrolog_report"]
    validate_file("hydrolog_report", path)
    values = output["values"]
    assert values["precipitation_mm"] == 50
    assert values["effective_mm"] == pytest.approx(7.09, abs=0.01)
    assert values["runoff_coefficient"] == pytest.approx(0.142, abs=0.001)
    (audit,) = output["tool"]["calls"]
    assert audit["command_line"].startswith("hydrolog scs effective --cn 72")


def test_a_wet_catchment_raises_the_curve_number(tmp_path: Path) -> None:
    output = run(
        tmp_path, "compute_effective_rainfall", {**EFFECTIVE, "amc": "wet"}, {}
    )

    assert output["values"]["amc"] == "III"
    assert output["values"]["cn_adjusted"] > 72


def test_the_hyetograph_counts_its_steps(tmp_path: Path) -> None:
    output = run(tmp_path, "build_design_hyetograph", HYETOGRAPH, {})

    values = output["values"]
    assert (values["hyetograph"], values["steps"]) == ("euler_ii", 24)
    assert values["peak_intensity_mm_per_h"] > 38.4 / 2


def test_a_duration_that_is_no_multiple_of_the_step_is_a_warning(
    tmp_path: Path,
) -> None:
    output = run(
        tmp_path, "build_design_hyetograph", {**HYETOGRAPH, "duration": 62}, {}
    )

    assert [warning["key"] for warning in output["warnings"]] == [
        "duration_not_covered"
    ]


def test_the_hydrograph_reports_its_peak_and_volume(tmp_path: Path) -> None:
    output = run(tmp_path, "generate_design_hydrograph", HYDROGRAPH, {})

    values = output["values"]
    assert values["peak_discharge_m3s"] > 0
    assert values["time_to_peak_min"] > 0
    assert values["uh_model"] == "scs"
    # The volume is the effective rainfall over the area
    assert values["total_volume_m3"] == pytest.approx(
        values["effective_mm"] / 1000 * 45.3e6, rel=0.01
    )


def test_a_routed_network_writes_a_table_per_node_and_its_schematic(
    tmp_path: Path,
) -> None:
    network, inflows = inflow_network(tmp_path / "case")

    output = run(
        tmp_path,
        "route_river_network_inflows",
        {},
        {"network": network, "inflows": inflows},
    )

    values = output["values"]
    assert (values["name"], values["outlet"], values["node_count"]) == (
        "Culvert inflow",
        "OUT",
        5,
    )
    assert values["outlet_peak_m3s"] == pytest.approx(0.175, abs=0.001)
    assert values["outlet_time_to_peak_min"] == 25.0
    assert values["outlet_volume_m3"] == 279
    tables = output["files"]["hydrograph_table"]
    assert sorted(path.name for path in tables) == [
        "A.csv",
        "B.csv",
        "J1.csv",
        "OUT.csv",
        "R1.csv",
    ]
    for path in tables:
        assert path.parent == tmp_path / "result" / "hydrographs"
        validate_file("hydrograph_table", path)
    (schematic,) = output["files"]["network_schematic"]
    validate_file("network_schematic", schematic)
    (report,) = output["files"]["hydrolog_report"]
    validate_file("hydrolog_report", report)


def test_a_network_computed_from_rain_needs_no_inflow_table(tmp_path: Path) -> None:
    output = run(
        tmp_path, "route_river_network", {}, {"network": rain_network(tmp_path)}
    )

    values = output["values"]
    assert (values["name"], values["node_count"]) == ("Three subcatchments", 8)
    outlet = next(node for node in values["nodes"] if node["id"] == "OUT")
    assert outlet["peak_m3s"] == values["outlet_peak_m3s"] > 0


def test_the_soil_groups_count_the_cells_of_each_group(tmp_path: Path) -> None:
    rasters = texture_rasters(tmp_path / "soil")

    output = run(tmp_path, "classify_soil_groups", {}, rasters)

    values = output["values"]
    assert values["counts"] == TEXTURE_COUNTS
    assert (values["rows"], values["columns"]) == (2, 3)
    # The shares are of the five classified cells, the cell without data apart
    assert values["percent"] == {"A": 20.0, "B": 40.0, "C": 20.0, "D": 20.0}
    assert values["group_text"] == "A 20%, B 40%, C 20%, D 20%"
    assert values["nodata_cells"] == 1
    (raster,) = output["files"]["hsg_raster"]
    assert raster == tmp_path / "result" / "hsg.tif"
    validate_file("hsg_raster", raster)
    assert output["warnings"] == []


def test_rasters_without_any_classified_cell_are_a_warning(tmp_path: Path) -> None:
    rasters = texture_rasters(tmp_path / "soil", nodata_only=True)

    output = run(tmp_path, "classify_soil_groups", {}, rasters)

    assert output["values"]["percent"] == {}
    assert [warning["key"] for warning in output["warnings"]] == ["no_classified_cells"]


def test_the_flood_quantiles_come_from_the_best_distribution(tmp_path: Path) -> None:
    series = series_file(tmp_path)
    output = run(
        tmp_path,
        "estimate_flood_quantiles",
        {"distribution": "all", "probability": [0.01, 0.1]},
        {"series": series},
    )

    values = output["values"]
    assert values["n_years"] == 12
    assert values["best_distribution"] == values["distributions"][0]
    one, ten = values["quantiles"]
    assert (one["probability_percent"], ten["probability_percent"]) == (1, 10)
    assert one["discharge_m3s"] > ten["discharge_m3s"]
    assert values["quantile_text"].startswith("Q1% ")


def test_the_time_of_concentration_of_a_watershed_file(tmp_path: Path) -> None:
    watershed = watershed_file(tmp_path)

    output = run(
        tmp_path,
        "compute_concentration_time",
        {"method": "kirpich"},
        {"watershed": watershed},
    )

    values = output["values"]
    assert values["method"] == "kirpich"
    assert values["tc_min"] > 0
    assert values["tc_h"] == pytest.approx(values["tc_min"] / 60, abs=0.01)
    assert values["watershed"] == "Potok Testowy"


def test_the_morphometry_of_a_watershed_file(tmp_path: Path) -> None:
    watershed = watershed_file(tmp_path)

    output = run(
        tmp_path, "compute_watershed_morphometry", {}, {"watershed": watershed}
    )

    values = output["values"]
    assert (values["name"], values["area_km2"]) == ("Potok Testowy", 12.0)
    assert values["relief_m"] == 120.0
    assert 0 < values["form_factor"] < 1


# --- previews ------------------------------------------------------------------


def test_a_method_the_watershed_lacks_fields_for_is_asked_again(
    tmp_path: Path,
) -> None:
    watershed = watershed_file(tmp_path, mean_slope_m_per_m=0.05, cn=None)
    ctx = context("compute_concentration_time", inputs={"watershed": watershed})

    output = preview.compute_concentration_time({"method": "nrcs"}, ctx)

    (problem,) = output["problems"]
    assert (problem["key"], problem["params"]) == ("method_fields", ["method"])
    assert problem["args"] == {"method": "nrcs", "missing": "cn"}


def test_a_method_the_watershed_has_fields_for_names_the_watershed(
    tmp_path: Path,
) -> None:
    watershed = watershed_file(tmp_path, mean_slope_m_per_m=0.05)
    ctx = context("compute_concentration_time", inputs={"watershed": watershed})

    output = preview.compute_concentration_time({"method": "nrcs"}, ctx)

    assert output["problems"] == []
    assert output["rows"] == [{"key": "watershed", "args": {"name": "Potok Testowy"}}]


def test_a_watershed_file_hydrolog_cannot_read_ends_the_plan(tmp_path: Path) -> None:
    broken = tmp_path / "zlewnia.json"
    broken.write_text('{"length_km": 6.0}', encoding="utf-8")
    ctx = context("compute_watershed_morphometry", inputs={"watershed": broken})

    output = preview.compute_watershed_morphometry({}, ctx)

    (problem,) = output["problems"]
    assert problem["params"] == []
    assert (problem["code"], problem["reason"]) == ("data_error", "missing_field")
    assert problem["args"]["path"] == str(broken)


def test_the_plan_of_flood_quantiles_shows_the_years_of_the_maxima(
    tmp_path: Path,
) -> None:
    series = series_file(tmp_path, missing=date(2013, 3, 3))
    ctx = context("estimate_flood_quantiles", inputs={"series": series})

    output = preview.estimate_flood_quantiles({"distribution": "gev"}, ctx)

    assert output["problems"] == []
    assert output["rows"] == [
        {
            "key": "annual_maxima",
            "args": {"count": "11", "first": "2011", "last": "2022"},
        },
        {"key": "incomplete_years", "args": {"count": "1", "years": "2013"}},
    ]


def test_a_series_without_flows_ends_the_plan(tmp_path: Path) -> None:
    series = series_file(tmp_path, column="H_max [cm]")
    ctx = context("estimate_flood_quantiles", inputs={"series": series})

    output = preview.estimate_flood_quantiles({"distribution": "all"}, ctx)

    (problem,) = output["problems"]
    assert (problem["code"], problem["reason"]) == ("data_error", "missing_column")


@pytest.mark.parametrize(
    "name", ["build_design_hyetograph", "generate_design_hydrograph"]
)
def test_a_step_longer_than_the_rain_asks_both_again(name: str) -> None:
    params = {**HYDROGRAPH, "duration": 20, "time_step": 30}

    output = getattr(preview, name)(params, context(name))

    (problem,) = output["problems"]
    assert problem["key"] == "step_exceeds_duration"
    assert problem["params"] == ["duration", "time_step"]


def test_a_network_that_reads_inflows_planned_without_them_ends_the_plan(
    tmp_path: Path,
) -> None:
    network, _ = inflow_network(tmp_path)
    ctx = context("route_river_network", inputs={"network": network})

    output = preview.route_river_network({}, ctx)

    (problem,) = output["problems"]
    assert (problem["key"], problem["params"]) == ("network_needs_inflows", [])
    assert problem["args"] == {"node": "A", "path": str(network)}
    assert (problem["code"], problem["reason"]) == ("data_error", "missing_field")


def test_an_inflow_table_without_a_subcatchment_column_ends_the_plan(
    tmp_path: Path,
) -> None:
    network, _ = inflow_network(tmp_path)
    inflows = tmp_path / "doplywy.csv"
    inflows.write_text("time_min,A\n0,0\n5,1\n10,0\n", encoding="utf-8")
    ctx = context(
        "route_river_network_inflows",
        inputs={"network": network, "inflows": inflows},
    )

    output = preview.route_river_network_inflows({}, ctx)

    (problem,) = output["problems"]
    assert problem["key"] == "input_refused"
    assert (problem["code"], problem["reason"]) == ("data_error", "missing_column")
    assert problem["args"]["path"] == str(inflows)


def test_the_plan_of_a_network_names_it_its_nodes_and_its_outlet(
    tmp_path: Path,
) -> None:
    network, inflows = inflow_network(tmp_path / "case")
    ctx = context(
        "route_river_network_inflows",
        inputs={"network": network, "inflows": inflows},
    )

    output = preview.route_river_network_inflows({}, ctx)

    assert output["problems"] == []
    assert output["rows"] == [
        {
            "key": "network",
            "args": {"name": "Culvert inflow", "nodes": "5", "outlet": "OUT"},
        }
    ]
    # The preview wrote nothing beside the inputs
    assert sorted(path.name for path in (tmp_path / "case").iterdir()) == [
        "inflows.csv",
        "network.json",
        "out",
    ]


def test_one_raster_given_for_two_textures_ends_the_plan(tmp_path: Path) -> None:
    rasters = texture_rasters(tmp_path)
    ctx = context(
        "classify_soil_groups",
        inputs={**rasters, "sand": rasters["clay"]},
    )

    output = preview.classify_soil_groups({}, ctx)

    (problem,) = output["problems"]
    assert (problem["key"], problem["params"]) == ("same_texture_raster", [])
    assert problem["args"] == {"path": str(rasters["clay"].resolve())}
    assert (
        preview.classify_soil_groups(
            {}, context("classify_soil_groups", inputs=rasters)
        )["problems"]
        == []
    )

"""Retman results of Hydrolog's computations.

Every computation answers with a ``hydrolog-result/1`` envelope: the mapper keeps the
envelope as the result file (kind ``hydrolog_report``, named after what it holds),
takes the few numbers the summary of the result names and passes on Hydrolog's
warning notices (a parameter outside the typical range of a formula, a skipped
incomplete year, a short sample); info notices stay in the file. The full series
(hyetograph depths, hydrograph ordinates, fitted distributions) are in the file, not
in the values. The commands that write (``route network``, ``soil hsg``) add the
files Hydrolog wrote into the result folder, by their kinds.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolRun, notice_warnings
from retman.exceptions import RetmanError
from retman.extractors.quantities import format_quantity
from retman.registry.manifest import HandlerOutput
from retman.registry.operation import Operation
from retman.tools.hydrolog.calls import REPORT

Runs = Sequence[tuple[CatalogCall, ToolRun]]

# The hydrologic soil groups in the counts of ``soil hsg`` (``nodata`` is apart)
_HSG_GROUPS = ("A", "B", "C", "D")


def _output_dir(ctx: ToolContext) -> Path:
    """Return the result folder of the running operation (``None`` when planning)."""
    if ctx.output_dir is None:
        raise RetmanError("a result is described only while the operation runs")
    return ctx.output_dir


def _report(ctx: ToolContext, name: str, run: ToolRun) -> Path:
    """Write the tool's envelope as it is: JSON whose first key is ``schema``."""
    path = _output_dir(ctx) / name
    path.write_text(
        json.dumps(run.document, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def _result(run: ToolRun) -> Mapping[str, Any]:
    result = run.document.get("result")
    if not isinstance(result, Mapping):
        raise RetmanError(f"{run.command}: the envelope has no result")
    return result


def _rounded(value: Any, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _output(
    operation: Operation,
    ctx: ToolContext,
    run: ToolRun,
    name: str,
    values: dict[str, Any],
) -> HandlerOutput:
    return {
        "values": values,
        "files": {REPORT: [_report(ctx, name, run)]},
        "warnings": notice_warnings(operation, ctx.tool, run.notices),
    }


def compute_concentration_time(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the time of concentration and the watershed values the method used."""
    ((_, run),) = runs
    result = _result(run)
    values = {
        "method": result["method"],
        "tc_min": _rounded(result["tc_min"], 1),
        "tc_h": _rounded(result["tc_h"], 2),
        "watershed": result.get("watershed_name"),
        "parameters": dict(result.get("parameters") or {}),
    }
    return _output(operation, ctx, run, "concentration_time.json", values)


def compute_effective_rainfall(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the effective rainfall, the losses and the runoff coefficient."""
    ((_, run),) = runs
    result = _result(run)
    values = {
        "cn": result["cn"],
        "cn_adjusted": _rounded(result["cn_adjusted"], 1),
        "amc": result["amc"],
        "precipitation_mm": result["total_precipitation_mm"],
        "effective_mm": _rounded(result["total_effective_mm"], 2),
        "retention_mm": _rounded(result["retention_mm"], 2),
        "initial_abstraction_mm": _rounded(result["initial_abstraction_mm"], 2),
        "runoff_coefficient": _rounded(result["runoff_coefficient"], 3),
    }
    return _output(operation, ctx, run, "effective_rainfall.json", values)


def build_design_hyetograph(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the shape, the steps and the peak intensity of the hyetograph."""
    ((_, run),) = runs
    result = _result(run)
    values = {
        "hyetograph": result["hietogram_type"],
        "total_mm": result["total_mm"],
        "duration_min": result["duration_min"],
        "timestep_min": result["timestep_min"],
        "steps": result["n_steps"],
        "peak_intensity_mm_per_h": _rounded(result["peak_intensity_mm_per_h"], 1),
        "parameters": dict(result.get("parameters") or {}),
    }
    return _output(operation, ctx, run, "hyetograph.json", values)


def generate_design_hydrograph(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the peak, its time, the volume and the effective rainfall."""
    ((_, run),) = runs
    result = _result(run)
    values = {
        "peak_discharge_m3s": _rounded(result["peak_discharge_m3s"], 2),
        "time_to_peak_min": result["time_to_peak_min"],
        "total_volume_m3": round(float(result["total_volume_m3"])),
        "effective_mm": _rounded(result["total_effective_mm"], 2),
        "runoff_coefficient": _rounded(result["runoff_coefficient"], 3),
        "cn_adjusted": _rounded(result["cn_adjusted"], 1),
        "tc_min": result["tc_min"],
        "uh_model": result["uh_model"],
    }
    return _output(operation, ctx, run, "hydrograph.json", values)


def _quantiles(distribution: Mapping[str, Any]) -> list[dict[str, float]]:
    """Return the quantiles of a fitted distribution: T, p in percent, discharge."""
    return [
        {
            "return_period": float(period),
            "probability_percent": round(100 / float(period), 6),
            "discharge_m3s": round(float(quantile), 2),
        }
        for period, quantile in zip(
            distribution["return_periods"], distribution["quantiles"], strict=True
        )
    ]


def estimate_flood_quantiles(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the quantiles of the best distribution (lowest AIC) and its sample.

    ``quantile_text`` lists them as ``Q1% 117.26`` for the summary of the result; every
    fitted distribution with its goodness of fit is in the result file.
    """
    ((_, run),) = runs
    result = _result(run)
    best = next(
        item
        for item in result["distributions"]
        if item["distribution_name"] == result["best_distribution"]
    )
    quantiles = _quantiles(best)
    years = [int(year) for year in result.get("hydrological_years") or ()]
    values = {
        "n_years": result["n_years"],
        "hydrological_years": years,
        "incomplete_years": list(result.get("incomplete_years") or ()),
        "best_distribution": result["best_distribution"],
        "distributions": [
            item["distribution_name"] for item in result["distributions"]
        ],
        "quantiles": quantiles,
        "quantile_text": ", ".join(
            f"Q{format_quantity(item['probability_percent'])}% "
            f"{format_quantity(item['discharge_m3s'])}"
            for item in quantiles
        ),
    }
    return _output(operation, ctx, run, "flood_quantiles.json", values)


def compute_watershed_morphometry(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the area, the relief and the shape indicators of the watershed."""
    ((_, run),) = runs
    result = _result(run)
    geometry = result.get("geometry") or {}
    elevation = result.get("elevation") or {}
    shape = result.get("shape_indicators") or {}
    slopes = result.get("slopes") or {}
    values = {
        "name": result.get("name") or "",
        "area_km2": geometry.get("area_km2"),
        "perimeter_km": geometry.get("perimeter_km"),
        "length_km": geometry.get("length_km"),
        "relief_m": _rounded(elevation.get("relief_m"), 1),
        "form_factor": _rounded(shape.get("form_factor"), 3),
        "compactness_coefficient": _rounded(shape.get("compactness_coefficient"), 3),
        "elongation_ratio": _rounded(shape.get("elongation_ratio"), 3),
        "watershed_slope_percent": _rounded(slopes.get("watershed_slope_percent"), 2),
    }
    return _output(operation, ctx, run, "morphometry.json", values)


def _route_network(operation: Operation, runs: Runs, ctx: ToolContext) -> HandlerOutput:
    """Describe the routed network: the outlet's peak, its time and volume, each node.

    The hydrograph table ``<id>.csv`` of every node and the schematic are the files
    Hydrolog wrote into the result folder; the envelope (with the parameters of every
    reach and the schematic document) is the result file.
    """
    ((_, run),) = runs
    result = _result(run)
    nodes = [
        {
            "id": node["id"],
            "type": node["type"],
            "peak_m3s": _rounded(node["peak_m3s"], 3),
            "time_to_peak_min": _rounded(node["time_to_peak_min"], 1),
            "volume_m3": round(float(node["volume_m3"])),
        }
        for node in result["nodes"]
    ]
    outlet = next(node for node in nodes if node["id"] == result["outlet"])
    tables = [item.path for item in run.files if item.path.suffix.lower() == ".csv"]
    schematic = [item.path for item in run.files if item.path.suffix.lower() == ".svg"]
    values = {
        "name": result.get("name") or Path(ctx.inputs["network"]).stem,
        "timestep_min": result["timestep_min"],
        "node_count": len(nodes),
        "outlet": outlet["id"],
        "outlet_peak_m3s": outlet["peak_m3s"],
        "outlet_time_to_peak_min": outlet["time_to_peak_min"],
        "outlet_volume_m3": outlet["volume_m3"],
        "nodes": nodes,
    }
    output = _output(operation, ctx, run, "route_network.json", values)
    output["files"].update(hydrograph_table=tables, network_schematic=schematic)
    return output


def route_river_network(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe a network whose subcatchments hold or compute their flows."""
    return _route_network(operation, runs, ctx)


def route_river_network_inflows(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe a network whose subcatchments read the inflow table."""
    return _route_network(operation, runs, ctx)


def classify_soil_groups(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the raster of the groups A-D: the cells and the share of each group.

    The shares are of the classified cells; the cells without data (no value in one
    of the three rasters) are counted apart. A raster with no classified cell is a
    warning: the groups of such a result are empty.
    """
    ((_, run),) = runs
    result = _result(run)
    counts = {str(key): int(value) for key, value in result["counts"].items()}
    classified = sum(counts.get(group, 0) for group in _HSG_GROUPS)
    percent = {
        group: round(100 * counts.get(group, 0) / classified, 1)
        for group in _HSG_GROUPS
        if classified
    }
    rows, columns = (int(size) for size in result["shape"])
    values = {
        "rows": rows,
        "columns": columns,
        "crs": result["crs"],
        "counts": counts,
        "nodata_cells": counts.get("nodata", 0),
        "percent": percent,
        "group_text": ", ".join(
            f"{group} {format_quantity(share)}%" for group, share in percent.items()
        ),
    }
    output = _output(operation, ctx, run, "soil_groups.json", values)
    output["files"]["hsg_raster"] = [item.path for item in run.files]
    if not classified:
        output["warnings"].append({"key": "no_classified_cells", "args": {}})
    return output

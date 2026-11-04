"""Retman results of Hydrolog's computations.

Every computation answers with a ``hydrolog-result/1`` envelope and writes no file of
its own: the mapper keeps the envelope as the result file (kind ``hydrolog_report``,
named after what it holds), takes the few numbers the summary of the result names and
passes on Hydrolog's warning notices (a parameter outside the typical range of a
formula, a skipped incomplete year, a short sample); info notices stay in the file.
The full series (hyetograph depths, hydrograph ordinates, fitted distributions) are in
the file, not in the values.
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

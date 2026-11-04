"""Hydrolog call builders: Retman parameters to catalog calls (pure, offline).

A builder never imports Hydrolog and never touches the file system; the same builder
serves plan-time validation, the preview and the run. Numbers come in the units of the
tool (mm, km², minutes) from the extractors; an input file is the path of the plan's
input (``ctx.inputs``), which the workspace has already checked against its data kind.
``CatalogCall.params`` routes a rejected option of the tool back to the parameter the
user answers again.
"""

from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext

REPORT = "hydrolog_report"

# The flow column and the date column of an Obserwator series export
# (``date,year,Q [m3/s],Q_flag,...``): Hydrolog finds ``Q [m3/s]`` by the name ``Q``
SERIES_VALUE_COLUMN = "Q"
SERIES_DATE_COLUMN = "date"
# The unit hydrograph of a design hydrograph from numbers: SCS needs only tc, which
# the command states; the other models need parameters no command states (Nash n and
# K, Clark R, Snyder L and Lc)
UNIT_HYDROGRAPH = "scs"


def _input(ctx: ToolContext, name: str) -> str:
    """Return the path of an input of the plan as the option of a call."""
    return str(ctx.inputs[name])


def return_periods(probabilities: list[float]) -> list[float]:
    """Return periods T = 1/p [years] of exceedance probabilities, for Hydrolog.

    Examples
    --------
    >>> return_periods([0.01, 0.1, 0.002])
    [100.0, 10.0, 500.0]
    """
    return [round(1 / probability, 6) for probability in probabilities]


def compute_effective_rainfall(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``scs effective`` of a rainfall total, a curve number and the moisture state."""
    options: dict[str, object] = {
        "cn": params["cn"],
        "precipitation_mm": params["rainfall"],
        "amc": ctx.tool_value("amc", params["amc"]),
    }
    return [
        CatalogCall("scs effective", options, REPORT, {"precipitation_mm": "rainfall"})
    ]


def _rain(params: dict[str, Any], ctx: ToolContext) -> dict[str, object]:
    """Return the design rainfall options: shape, total, duration, time step."""
    return {
        "hietogram_type": ctx.tool_value("hyetograph", params["hyetograph"]),
        "total_mm": params["rainfall"],
        "duration_min": params["duration"],
        "timestep_min": params["time_step"],
    }


_RAIN_ROUTING = {
    "hietogram_type": "hyetograph",
    "total_mm": "rainfall",
    "duration_min": "duration",
    "timestep_min": "time_step",
}


def build_design_hyetograph(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``precip hietogram`` of a shape, a total, a duration and a time step."""
    return [CatalogCall("precip hietogram", _rain(params, ctx), REPORT, _RAIN_ROUTING)]


def generate_design_hydrograph(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``hydrograph generate`` of a catchment given by its area, CN and tc.

    The rainfall is a design hyetograph; the SCS unit hydrograph is named in the call
    (the tool's default), so that the audit shows the model.
    """
    options: dict[str, object] = {
        "area_km2": params["catchment_area"],
        "cn": params["cn"],
        "tc_min": params["concentration_time"],
        "amc": ctx.tool_value("amc", params["amc"]),
        **_rain(params, ctx),
        "uh_model": UNIT_HYDROGRAPH,
    }
    routing = {
        **_RAIN_ROUTING,
        "area_km2": "catchment_area",
        "tc_min": "concentration_time",
    }
    return [CatalogCall("hydrograph generate", options, REPORT, routing)]


def estimate_flood_quantiles(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``stats flood-frequency`` of the daily flows of an Obserwator series export.

    The annual maxima are taken by Hydrolog for the complete hydrological years; the
    probabilities of the command become return periods, without them the tool's
    default periods apply.
    """
    options: dict[str, object] = {
        "input_file": _input(ctx, "series"),
        "value_column": SERIES_VALUE_COLUMN,
        "date_column": SERIES_DATE_COLUMN,
        "distribution": ctx.tool_value("distribution", params["distribution"]),
    }
    if params.get("probability"):
        options["return_periods"] = return_periods(params["probability"])
    return [
        CatalogCall(
            "stats flood-frequency", options, REPORT, {"return_periods": "probability"}
        )
    ]


def compute_concentration_time(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``tc watershed`` of a watershed file by a method.

    A watershed that lacks the fields of the method is refused for ``watershed_file``:
    the routing makes that a question about the method again.
    """
    options: dict[str, object] = {
        "watershed_file": _input(ctx, "watershed"),
        "method": ctx.tool_value("method", params["method"]),
    }
    return [CatalogCall("tc watershed", options, REPORT, {"watershed_file": "method"})]


def compute_watershed_morphometry(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``morphometry watershed`` of a watershed file."""
    options: dict[str, object] = {"watershed_file": _input(ctx, "watershed")}
    return [CatalogCall("morphometry watershed", options, REPORT)]

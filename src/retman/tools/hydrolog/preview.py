"""What a Hydrolog plan shows and checks before the user confirms (offline).

The generic adapter has already had Hydrolog validate every call of the operation
(``validate_command``), which checks the options but reads no file and computes
nothing. The computations neither write nor use the network, and ``route network``
writes nothing while its call names no output (as it does while planning), so the
preview lets the tool compute the plan through the client's offline ``lookup``:
whatever Hydrolog would refuse at the run (a watershed without the fields of the
method, a series without its flow column, a network it cannot route) is refused now,
as a question about the parameter the tool names, or as the error of the input when
no answer can help. The rule a time step needs (not longer than the rain) is Retman's
own, because Hydrolog's refusal names no option. What the computation tells about an
input (the years of a series, the name of a watershed or a network) becomes rows of
the plan; its results are shown only after the run. ``soil hsg`` writes its raster
in any case, so only Retman's own rule is checked before it runs.
"""

from collections import Counter
from pathlib import Path
from typing import Any

from retman.adapters.catalog import (
    CallBuilder,
    ToolContext,
    ToolDocument,
    ToolError,
    route_error,
)
from retman.registry.manifest import PreviewOutput, PreviewProblem
from retman.tools.hydrolog import calls

# The field Hydrolog names when a subcatchment has no hydrograph of its own, cannot
# compute one and reads no inflow table
_FLOWS_FIELD = "discharge_m3s"
# The inputs of ``soil hsg``: one texture raster each
_TEXTURE_INPUTS = ("clay", "sand", "silt")


def _refusal(ctx: ToolContext, err: ToolError) -> PreviewProblem:
    """Hydrolog's refusal of a computation as a problem of the plan.

    A refusal routed to a parameter asks it again (a watershed that lacks the fields
    of a method asks for another method); any other one is about the input file and
    ends planning with Hydrolog's registry code and reason, the file as its path.
    """
    tool_details: dict[str, Any] = dict(err.details.get("tool_details") or {})
    routed = route_error(err.call, err, list(ctx.specs))
    if routed:
        missing = tool_details.get("missing")
        if tool_details.get("reason") == "missing_field" and missing:
            return {
                "params": routed,
                "key": "method_fields",
                "args": {
                    "method": str(tool_details.get("method", "")),
                    "missing": ", ".join(str(name) for name in missing),
                },
            }
        return {"params": routed, "key": "tool_refused", "args": {"detail": err.detail}}
    args = {"detail": err.detail}
    if isinstance(tool_details.get("path"), str):
        args["path"] = tool_details["path"]
    return {
        "params": [],
        "key": "input_refused",
        "args": args,
        "code": err.code,
        "reason": str(err.details.get("reason") or err.tool_code),
    }


def _dry_run(
    builder: CallBuilder, params: dict[str, Any], ctx: ToolContext
) -> tuple[list[ToolDocument], list[PreviewProblem]]:
    """Let Hydrolog compute the calls offline; the envelopes, or the first refusal."""
    documents: list[ToolDocument] = []
    for call in builder(params, ctx):
        try:
            documents.append(ctx.client.lookup(call))
        except ToolError as err:
            if err.call is None:
                err.call = call
            return documents, [_refusal(ctx, err)]
    return documents, []


def _output(problems: list[PreviewProblem]) -> PreviewOutput:
    return {"values": {}, "rows": [], "problems": problems}


def _rain_problems(params: dict[str, Any]) -> list[PreviewProblem]:
    """Refuse a time step longer than the rain: the hyetograph would have no step.

    Either value may be the wrong one, so both are asked again.
    """
    if params["time_step"] <= params["duration"]:
        return []
    return [
        {
            "params": ["duration", "time_step"],
            "key": "step_exceeds_duration",
            "args": {
                "time_step": str(params["time_step"]),
                "duration": str(params["duration"]),
            },
        }
    ]


def compute_concentration_time(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Check that the watershed has the fields of the method; name the watershed."""
    documents, problems = _dry_run(calls.compute_concentration_time, params, ctx)
    output = _output(problems)
    if documents:
        _watershed_row(output, documents[0].get("result") or {})
    return output


def _watershed_row(output: PreviewOutput, result: dict[str, Any]) -> None:
    name = result.get("watershed_name") or result.get("name")
    if name:
        output["rows"].append({"key": "watershed", "args": {"name": str(name)}})


def compute_effective_rainfall(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Let Hydrolog check the rainfall and the curve number."""
    _, problems = _dry_run(calls.compute_effective_rainfall, params, ctx)
    return _output(problems)


def build_design_hyetograph(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Check the time step against the duration, then let Hydrolog check the rest."""
    problems = _rain_problems(params)
    if not problems:
        _, problems = _dry_run(calls.build_design_hyetograph, params, ctx)
    return _output(problems)


def generate_design_hydrograph(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Check the time step against the duration, then let Hydrolog check the rest."""
    problems = _rain_problems(params)
    if not problems:
        _, problems = _dry_run(calls.generate_design_hydrograph, params, ctx)
    return _output(problems)


def estimate_flood_quantiles(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Check the series and show the hydrological years of its annual maxima.

    Hydrolog takes the maxima of the complete hydrological years only: the plan says
    how many there are and which years were left out, so a short or gappy series is
    seen before the run.
    """
    documents, problems = _dry_run(calls.estimate_flood_quantiles, params, ctx)
    output = _output(problems)
    if not documents:
        return output
    result = documents[0].get("result") or {}
    years = [int(year) for year in result.get("hydrological_years") or ()]
    skipped = [int(year) for year in result.get("incomplete_years") or ()]
    output["values"] = {"hydrological_years": years, "incomplete_years": skipped}
    if years:
        output["rows"].append(
            {
                "key": "annual_maxima",
                "args": {
                    "count": str(len(years)),
                    "first": str(min(years)),
                    "last": str(max(years)),
                },
            }
        )
    if skipped:
        output["rows"].append(
            {
                "key": "incomplete_years",
                "args": {
                    "count": str(len(skipped)),
                    "years": ", ".join(str(year) for year in skipped),
                },
            }
        )
    return output


def compute_watershed_morphometry(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Check the watershed file; name the watershed."""
    documents, problems = _dry_run(calls.compute_watershed_morphometry, params, ctx)
    output = _output(problems)
    if documents:
        _watershed_row(output, documents[0].get("result") or {})
    return output


def _route_network(
    builder: CallBuilder, params: dict[str, Any], ctx: ToolContext, *, inflows: bool
) -> PreviewOutput:
    """Let Hydrolog route the network in memory; name it, its nodes and its outlet.

    While planning the call names no output, so Hydrolog computes the network and
    writes nothing: a document it cannot read or an inflow table without the column
    of a subcatchment ends the plan before the user confirms. A subcatchment without
    flows, planned without an inflow table, is said as such: the command has to name
    the table, which makes it the other operation.
    """
    (call,) = builder(params, ctx)
    try:
        document = ctx.client.lookup(call)
    except ToolError as err:
        if err.call is None:
            err.call = call
        tool_details: dict[str, Any] = dict(err.details.get("tool_details") or {})
        if (
            not inflows
            and tool_details.get("reason") == "missing_field"
            and tool_details.get("field") == _FLOWS_FIELD
        ):
            return _output(
                [
                    {
                        "params": [],
                        "key": "network_needs_inflows",
                        "args": {
                            "node": str(tool_details.get("node_id", "")),
                            "path": str(ctx.inputs["network"]),
                        },
                        "code": err.code,
                        "reason": "missing_field",
                    }
                ]
            )
        return _output([_refusal(ctx, err)])
    result = document.get("result") or {}
    output = _output([])
    output["rows"].append(
        {
            "key": "network",
            "args": {
                "name": str(result.get("name") or Path(ctx.inputs["network"]).stem),
                "nodes": str(len(result.get("nodes") or ())),
                "outlet": str(result.get("outlet", "")),
            },
        }
    )
    return output


def route_river_network(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Check that the network routes without an inflow table; describe it."""
    return _route_network(calls.route_river_network, params, ctx, inflows=False)


def route_river_network_inflows(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Check that the network routes with the inflow table; describe it."""
    return _route_network(calls.route_river_network_inflows, params, ctx, inflows=True)


def classify_soil_groups(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Refuse one file given for two of the clay, sand and silt rasters.

    Hydrolog would classify such a texture without complaint and the groups would be
    wrong. The command writes the raster, so nothing is computed before the run.
    """
    paths = Counter(Path(ctx.inputs[name]).resolve() for name in _TEXTURE_INPUTS)
    repeated = [path for path, count in paths.items() if count > 1]
    if not repeated:
        return _output([])
    return _output(
        [
            {
                "params": [],
                "key": "same_texture_raster",
                "args": {"path": str(repeated[0])},
                "code": "validation_error",
                "reason": "same_input",
            }
        ]
    )

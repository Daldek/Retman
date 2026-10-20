"""Call builders and result mapper of the dummy tool's catalog-backed operation."""

from dataclasses import replace
from typing import Any

from retman.adapters.catalog import (
    CatalogCall,
    ToolContext,
    ToolRun,
    default_describe,
)
from retman.registry.manifest import HandlerOutput
from retman.registry.operation import Operation


def fetch_dem(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """One catalog call; a sheet or a geometry file, tool values via the manifest."""
    area = params["area"]
    options: dict[str, object] = {
        "product": "nmt",
        "resolution": ctx.tool_value("resolution", params["resolution"]),
        "vertical_crs": ctx.tool_value("vertical_crs", params["vertical_crs"]),
    }
    if area["type"] == "sheet":
        options["sheet"] = area["code"]
    else:
        options["geometry"] = area["path"]
        options["layer"] = area["layer"]
    return [
        CatalogCall(
            "elevation download",
            options,
            kind="dem",
            params={"sheet": "area", "geometry": "area", "layer": "area"},
        )
    ]


def fetch_twice(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """A composite operation: the same command for the sheet and its neighbour."""
    (first,) = fetch_dem(params, ctx)
    return [
        first,
        replace(first, options={**first.options, "sheet": "N-34-130-D-d-2-3"}),
    ]


def describe_fetch_dem(
    operation: Operation,
    params: dict[str, Any],
    runs: list[tuple[CatalogCall, ToolRun]],
    ctx: ToolContext,
) -> HandlerOutput:
    """The generic mapping plus the resolution actually requested from the tool."""
    output = default_describe(operation, params, runs, ctx)
    output["values"]["resolution"] = runs[0][0].options["resolution"]
    return output

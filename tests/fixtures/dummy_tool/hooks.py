"""Preview and availability check of the dummy tool."""

from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext
from retman.registry.manifest import CheckOutput, PreviewOutput, PreviewProblem


def preview_fetch_dem(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Offline: one extra row; sheets ending in ``-2-1`` are reported as unavailable."""
    area = params["area"]
    problems: list[PreviewProblem] = []
    if area.get("code", "").endswith("-2-1"):
        problems.append(
            {
                "params": ["area"],
                "key": "sheet_unavailable",
                "args": {"code": area["code"]},
            }
        )
    return {
        "values": {"area_type": area["type"]},
        "rows": [{"key": "area_kind", "args": {"kind": area["type"]}}],
        "problems": problems,
    }


def check_fetch_dem(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """A network step: asks the tool's availability query through the client."""
    document = ctx.runner.query(
        CatalogCall("elevation availability", {"resolution": params["resolution"]})
    )
    return {
        "status": "available" if document.get("complete") else "partial",
        "items": [{"key": "selection", "args": {"resolution": params["resolution"]}}],
    }

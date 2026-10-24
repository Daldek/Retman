"""What a Kartograf plan shows and checks before the user confirms (offline).

The generic adapter has already had Kartograf validate every call of the
operation (``validate_command``), so these previews run only for requests the tool
accepts. They add what that validation cannot know: how many sheets a sheet code or
a geometry file stands for, the extent of a geometry file, and the rules that are
Retman's own (an orthophoto only for sheet codes, BDOT10k only inside Poland).
Everything goes through the client's offline lookups; nothing here uses the
network or writes.
"""

from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.extractors.areas import validate_area
from retman.registry.manifest import PreviewOutput
from retman.tools.kartograf import calls
from retman.tools.kartograf.areas import envelope, sheet_count

_METRES_PER_KM = 1000


def _empty() -> PreviewOutput:
    return {"values": {}, "rows": [], "problems": []}


def _outside_poland(box: tuple[float, ...]) -> bool:
    """Whether an EPSG:2180 rectangle lies outside the ranges Poland fits in.

    The same conservative ranges as every rectangle the user types; a point (a
    degenerate envelope) is widened to one metre, which only the order check of
    the validator cares about.
    """
    min_x, min_y, max_x, max_y = box
    probe = {
        "type": "bbox",
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max(max_x, min_x + 1),
        "max_y": max(max_y, min_y + 1),
        "crs": "EPSG:2180",
    }
    return validate_area(probe) == "extractors.errors.outside_poland"


def _envelope(
    params: dict[str, Any], ctx: ToolContext, output: PreviewOutput
) -> tuple[float, ...] | None:
    """Add the extent of a geometry file to the preview; ``None`` for other areas."""
    area = params["area"]
    if area["type"] != "geometry":
        return None
    box = envelope(area, ctx.client)
    min_x, min_y, max_x, max_y = box
    output["values"]["envelope"] = {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "crs": "EPSG:2180",
    }
    output["rows"].append(
        {
            "key": "envelope",
            "args": {
                "min_x": f"{min_x:.0f}",
                "min_y": f"{min_y:.0f}",
                "max_x": f"{max_x:.0f}",
                "max_y": f"{max_y:.0f}",
                "width_km": f"{(max_x - min_x) / _METRES_PER_KM:.1f}",
                "height_km": f"{(max_y - min_y) / _METRES_PER_KM:.1f}",
            },
        }
    )
    return box


def _scale_choices(code: str, ctx: ToolContext) -> list[str]:
    """Labels of the target scales a PL-2000 sheet can be expanded into."""
    labels: list[str] = []
    for key in ctx.specs["target_scale"].get("options", []):
        scale = "1:" + key.removeprefix("scale_")
        if scale == "1:10000":  # PL-2000 sheets are never requested in this scale
            continue
        try:
            ctx.client.lookup(
                CatalogCall("parse", {"sheet": code, "descendants": scale})
            )
        except ToolError:
            continue
        labels.append(
            ctx.operation.text(f"params.target_scale.options.{key}.label")
            if ctx.operation is not None
            else scale
        )
    return labels


def _sheets(call: CatalogCall, ctx: ToolContext, output: PreviewOutput) -> None:
    """Return the sheet count row of a sheet request, or why it has no sheets."""
    try:
        counted = sheet_count(call, ctx.client)
    except ToolError as err:
        # Kartograf's validation passes a target that is not finer than a PL-2000
        # sheet; only counting the descendants notices
        if err.option != "descendants":
            raise
        code = str(call.options["sheet"])
        allowed = _scale_choices(code, ctx)
        output["problems"].append(
            {
                "params": ["target_scale", "area"],
                "key": "scale_unavailable" if allowed else "no_descendants",
                "args": {"code": code, "allowed": ", ".join(allowed)},
            }
        )
        return
    if counted is None:
        output["rows"].append({"key": "province_files", "args": {}})
        return
    output["values"].update(
        sheet_count=counted.count,
        sheet_scale=counted.scale,
        sheet_system=counted.system,
    )
    if counted.count == 0:
        output["problems"].append({"params": ["area"], "key": "no_sheets", "args": {}})
        return
    output["rows"].append(
        {
            "key": "sheets",
            "args": {
                "count": str(counted.count),
                "scale": counted.scale,
                "system": counted.system,
            },
        }
    )


def download_dem_sheet(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview the extent of a geometry file and how many NMT sheets the area needs."""
    output = _empty()
    _envelope(params, ctx, output)
    (call,) = calls.download_dem_sheet(params, ctx)
    _sheets(call, ctx, output)
    return output


def download_sheet_hierarchy(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Extent, sheet count, and the rule that an orthophoto needs a sheet code."""
    output = _empty()
    if params["product"] == "orthophoto" and params["area"]["type"] != "sheet":
        # The provider class that applies the colour takes sheet codes only; both
        # parameters are asked again, so the user may change either
        output["problems"].append(
            {"params": ["product", "area"], "key": "orthophoto_needs_sheet", "args": {}}
        )
        return output
    _envelope(params, ctx, output)
    (call,) = calls.download_sheet_hierarchy(params, ctx)
    _sheets(call, ctx, output)
    return output


def download_elevation_cutout(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the extent of a geometry file: the cutout is one rectangle around it."""
    output = _empty()
    _envelope(params, ctx, output)
    return output


def download_bdot10k(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview the extent of a geometry file, which must lie in Poland.

    Kartograf's offline validation does not refuse a file far outside Poland; the
    run would fail only after the county service (network) found no county.
    """
    output = _empty()
    box = _envelope(params, ctx, output)
    if box is not None and _outside_poland(box):
        output["problems"].append(
            {"params": ["area"], "key": "outside_poland", "args": {}}
        )
    return output

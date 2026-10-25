"""What a Kartograf plan shows and checks before the user confirms (offline).

The generic adapter has already had Kartograf validate every call of the
operation (``validate_command``), so these previews run only for requests the tool
accepts. They add what that validation cannot know: whether the store folder is one
Kartograf will write into, how many sheets a sheet code or a geometry file stands for,
the extent of a geometry file, and the rules that are Retman's own (an orthophoto
only for sheet codes, BDOT10k only inside Poland). Everything goes through the
client's offline lookups and the store folder itself; nothing here uses the network
or writes.
"""

from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.extractors.areas import validate_area
from retman.registry.manifest import PreviewOutput, PreviewProblem
from retman.stores import KartografStore, kartograf_store_state
from retman.tools.kartograf import calls
from retman.tools.kartograf.areas import envelope, sheet_count

_METRES_PER_KM = 1000


def _empty() -> PreviewOutput:
    return {"values": {}, "rows": [], "problems": []}


# The problem of the plan for each state of a store folder that Kartograf refuses
_STORE_PROBLEMS = {
    "no_marker": "store_no_marker",
    "foreign": "store_not_kartograf",
    "not_a_directory": "store_not_kartograf",
    "unreadable": "store_marker_unreadable",
    "unsupported": "store_unsupported",
    "nested": "store_nested",
}


def store_problems(ctx: ToolContext, found: KartografStore) -> list[PreviewProblem]:
    """Why Kartograf will refuse the store folder; empty when it will take it.

    A missing or an empty folder is marked by the first write, so only a layout without
    its marker, a folder with other files, a marker that cannot be used and a store in
    another store are problems. Each blocks the plan and names no parameter: the folder
    is a matter of the configuration, not of an answer.
    """
    key = _STORE_PROBLEMS.get(found.state)
    if key is None:
        return []
    args = {"path": str(ctx.store_dir), "schema": found.detail, "other": found.detail}
    return [{"params": [], "key": key, "args": args}]


def _refused(ctx: ToolContext) -> PreviewOutput | None:
    """Return the plan of an operation that writes into a store Kartograf refuses.

    The tool judges the folder when it writes, which is after the user confirmed, so
    the plan has to: a plan whose run would end at its first byte is no plan. The
    problem replaces everything else the preview would say; ``None`` means that
    Kartograf will take the folder.
    """
    problems = store_problems(ctx, kartograf_store_state(ctx.store_dir))
    return {"values": {}, "rows": [], "problems": problems} if problems else None


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
                CatalogCall("sheet parse", {"sheet": code, "descendants": scale})
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
    if (refused := _refused(ctx)) is not None:
        return refused
    output = _empty()
    _envelope(params, ctx, output)
    (call,) = calls.download_dem_sheet(params, ctx)
    _sheets(call, ctx, output)
    return output


def download_sheet_hierarchy(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Extent, sheet count, and the rule that an orthophoto needs a sheet code."""
    if (refused := _refused(ctx)) is not None:
        return refused
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
    if (refused := _refused(ctx)) is not None:
        return refused
    output = _empty()
    _envelope(params, ctx, output)
    return output


def download_bdot10k(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview the extent of a geometry file, which must lie in Poland.

    Kartograf's offline validation does not refuse a file far outside Poland; the
    run would fail only after the county service (network) found no county.
    """
    if (refused := _refused(ctx)) is not None:
        return refused
    output = _empty()
    box = _envelope(params, ctx, output)
    if box is not None and _outside_poland(box):
        output["problems"].append(
            {"params": ["area"], "key": "outside_poland", "args": {}}
        )
    return output


def init_kartograf_store(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview what ``store init`` does to the folder; a folder it refuses blocks.

    The tool marks a missing or an empty folder, marks a folder with the layout of a
    store once it has verified that layout (a layout that is not its store's is refused
    when it runs) and leaves a store that has its marker as it is. It marks neither a
    folder with other files nor a store inside another. A layout without its marker is
    no problem here: it is what the operation is for.
    """
    folder = str(ctx.store_dir)
    found = kartograf_store_state(ctx.store_dir)
    problems = [] if found.state == "no_marker" else store_problems(ctx, found)
    if problems:
        return {"values": {}, "rows": [], "problems": problems}
    return {
        "values": {"store": folder, "store_state": found.state},
        "rows": [
            {"key": "store", "args": {"path": folder}},
            {"key": f"store_{found.state}", "args": {}},
        ],
        "problems": [],
    }

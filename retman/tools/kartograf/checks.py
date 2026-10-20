"""The optional availability check of the Kartograf operations (a network step).

The user confirms it separately from the plan (ARCHITECTURE 6.5); it reads what
GUGiK's indexes hold for the plan's area and writes nothing. It reports, never
decides: the user changes the plan or confirms it. Elevation data are asked of
``elevation availability`` (years, resolutions, height systems, completeness);
orthophoto sheets and BDOT10k counties have no availability report, so their
freshness plans (``check_command``) are read instead.
"""

from collections import Counter
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.core.check import CheckStatus
from retman.registry.manifest import CheckItem, CheckOutput
from retman.tools.kartograf import calls
from retman.tools.kartograf.areas import sheet_count

# The options of a download call that say which area to ask about
_AREA_OPTIONS = ("product", "country", "sheet", "bbox", "bbox_crs", "geometry", "layer")
_SYSTEM = {"1992": "PL-1992", "2000": "PL-2000"}
# The WCS cutout has this one resolution; the call leaves it out
_CUTOUT_RESOLUTION = "1m"
# A freshness plan item whose source has the sheet
_PUBLISHED = ("missing", "current", "newer")
# Counties named in one line
_SHOWN_COUNTIES = 12

Combination = dict[str, Any]


def _system(call: CatalogCall) -> str | None:
    """The sheet system a sheet request is in (``None`` for a cutout)."""
    if "sheet_system" in call.options:
        return _SYSTEM[str(call.options["sheet_system"])]
    if "sheet" in call.options:
        return _SYSTEM["2000" if "." in str(call.options["sheet"]) else "1992"]
    return None


def _grid_order(item: Combination) -> tuple[float, str]:
    return float(str(item["resolution"]).removesuffix("m")), str(item["vertical_crs"])


def _newest_complete(found: list[Combination]) -> dict[tuple[str, str], Combination]:
    """The newest complete combination of each (resolution, height system)."""
    newest: dict[tuple[str, str], Combination] = {}
    for item in found:
        key = (str(item["resolution"]), str(item["vertical_crs"]))
        if item["complete"] and item["year"] > newest.get(key, {"year": 0})["year"]:
            newest[key] = item
    return newest


def _selection(
    chosen: list[Combination], args: dict[str, str]
) -> tuple[CheckStatus, CheckItem]:
    """The verdict on the plan's own grid and the line that says it."""
    complete = [item for item in chosen if item["complete"]]
    if complete:
        year = max(item["year"] for item in complete)
        return "available", {
            "key": "selection_available",
            "args": {**args, "year": str(year)},
        }
    if chosen:
        best = max(chosen, key=lambda item: item["year"])
        return "partial", {
            "key": "selection_partial",
            "args": {
                **args,
                "year": str(best["year"]),
                "full": str(len(best["sheets_full"])),
                "partial": str(len(best["sheets_partial"])),
            },
        }
    return "unavailable", {"key": "selection_unavailable", "args": args}


def _elevation(call: CatalogCall, ctx: ToolContext) -> CheckOutput:
    """Is the chosen NMT/NMPT grid published for the area, and what else is?"""
    options = call.options
    resolution = str(options.get("resolution", _CUTOUT_RESOLUTION))
    if resolution == "100m":
        return {"status": "unknown", "items": [{"key": "province_files", "args": {}}]}
    vertical_crs = str(options["vertical_crs"])
    args = {
        "product": str(options["product"]).upper(),
        "resolution": resolution,
        "vertical_crs": vertical_crs,
    }
    document = ctx.runner.query(
        CatalogCall(
            "elevation availability",
            {name: value for name, value in options.items() if name in _AREA_OPTIONS},
        )
    )
    if not document.get("ok", True):
        return {"status": "unknown", "items": [{"key": "incomplete", "args": {}}]}
    system = _system(call)
    # Sheet files (ASC grids) are what these operations download; the archive
    # formats of the same index are source files they do not offer
    found = [
        item
        for item in document["combinations"]
        if item["country"] == "PL"
        and item["format"] == "ASC"
        and (system is None or item["horizontal"] == system)
    ]
    chosen = [
        item
        for item in found
        if item["resolution"] == resolution and item["vertical_crs"] == vertical_crs
    ]
    status, line = _selection(chosen, args)
    items = [line]
    if options.get("cutout"):
        # The WCS composes the newest flights itself; the sheet index only
        # approximates what it can serve
        items.append({"key": "cutout_note", "args": {}})
    others = [
        item
        for key, item in sorted(
            _newest_complete(found).items(), key=lambda pair: _grid_order(pair[1])
        )
        if key != (resolution, vertical_crs)
    ]
    if others:
        items.append({"key": "alternatives", "args": {}})
    items.extend(
        {
            "key": "alternative",
            "args": {
                "product": args["product"],
                "resolution": str(item["resolution"]),
                "vertical_crs": str(item["vertical_crs"]),
                "year": str(item["year"]),
            },
        }
        for item in others
    )
    return {"status": status, "items": items}


def download_dem_sheet(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """NMT sheets: the years and grids GUGiK's index has for the sheet code or file."""
    (call,) = calls.download_dem_sheet(params, ctx)
    return _elevation(call, ctx)


def _orthophoto(call: CatalogCall, ctx: ToolContext) -> CheckOutput:
    """The newest RGB flight GUGiK's sheet index lists for each sheet of the request."""
    try:
        plan = ctx.runner.check(call)
    except ToolError as err:
        if err.code != "no_coverage":
            raise
        return {
            "status": "unavailable",
            "items": [{"key": "orthophoto_none", "args": {"detail": err.detail}}],
        }
    items = plan["items"]
    statuses = Counter(item["status"] for item in items)
    published = sum(statuses[name] for name in _PUBLISHED)
    counted = sheet_count(call, ctx.client)
    total = counted.count if counted is not None else len(items)
    flights = sorted(
        str(item["available_label"]).split("_")[0]
        for item in items
        if item["available_label"]
    )
    status: CheckStatus
    if published == 0:
        status = "unknown" if statuses["check_failed"] else "unavailable"
    elif published < total:
        status = "partial"
    else:
        status = "available"
    lines: list[CheckItem] = [
        {
            "key": "orthophoto_sheets",
            "args": {
                "published": str(published),
                "total": str(total),
                "newest": flights[-1] if flights else "-",
            },
        }
    ]
    if statuses["current"]:
        lines.append({"key": "in_store", "args": {"count": str(statuses["current"])}})
    return {"status": status, "items": lines}


def download_sheet_hierarchy(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """NMT/NMPT: the index report of the parent; orthophoto: the sheet index (RGB)."""
    (call,) = calls.download_sheet_hierarchy(params, ctx)
    if params["product"] != "orthophoto":
        return _elevation(call, ctx)
    if params["color"] != "rgb":
        # The sheet index reports the RGB flights only; the other variants show up
        # as "no data" sheet by sheet when they are downloaded
        return {
            "status": "unknown",
            "items": [{"key": "orthophoto_variant", "args": {}}],
        }
    return _orthophoto(call, ctx)


def download_elevation_cutout(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """The cutout: the index of sheets is a proxy for what the WCS composes."""
    (call,) = calls.download_elevation_cutout(params, ctx)
    return _elevation(call, ctx)


def download_bdot10k(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """The counties an area touches and whether their packages are in the store."""
    (call,) = calls.download_bdot10k(params, ctx)
    items = ctx.runner.check(call)["items"]
    if not items:
        return {"status": "unavailable", "items": [{"key": "no_counties", "args": {}}]}
    statuses = Counter(item["status"] for item in items)
    units = [str(item["unit"]) for item in items]
    status: CheckStatus
    if statuses["check_failed"] == len(items):
        status = "unknown"
    elif statuses["check_failed"]:
        status = "partial"
    else:
        status = "available"
    shown = ", ".join(units[:_SHOWN_COUNTIES])
    if len(units) > _SHOWN_COUNTIES:
        shown += ", ..."
    lines: list[CheckItem] = [
        {"key": "counties", "args": {"count": str(len(units)), "units": shown}}
    ]
    if statuses["current"]:
        lines.append({"key": "in_store", "args": {"count": str(statuses["current"])}})
    return {"status": status, "items": lines}

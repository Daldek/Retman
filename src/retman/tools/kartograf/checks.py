"""The optional availability check of the Kartograf operations (a network step).

The user confirms it separately from the plan (ARCHITECTURE 6.5); it reads what
GUGiK's indexes hold for the plan's area and writes nothing. It reports, never
decides: the user changes the plan or confirms it. Elevation data are asked of
``elevation availability`` (years, resolutions, height systems, completeness);
orthophoto sheets (also those standing in for an orthophoto cutout), BDOT10k counties,
BDOO voivodeships, CORINE and SoilGrids layers have no availability report, so their
freshness plans (``check_command``) are read instead.
"""

from collections import Counter
from collections.abc import Mapping
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
# Units (counties, voivodeships) named in one line
_SHOWN_UNITS = 12
# The segment of a CORINE WMS preview (no CLMS credentials): no cheap signal
_PREVIEW_SEGMENT = "_preview"
# The plan track of the computed hydrologic soil groups (the others are its inputs)
_HSG_TRACK = "hsg"

Combination = dict[str, Any]


def _system(call: CatalogCall) -> str | None:
    """Return the sheet system a sheet request is in (``None`` for a cutout)."""
    if "sheet_system" in call.options:
        return _SYSTEM[str(call.options["sheet_system"])]
    if "sheet" in call.options:
        return _SYSTEM["2000" if "." in str(call.options["sheet"]) else "1992"]
    return None


def _grid_order(item: Combination) -> tuple[float, str]:
    return float(str(item["resolution"]).removesuffix("m")), str(item["vertical_crs"])


def _newest_complete(found: list[Combination]) -> dict[tuple[str, str], Combination]:
    """Return the newest complete combination of each (resolution, height system)."""
    newest: dict[tuple[str, str], Combination] = {}
    for item in found:
        key = (str(item["resolution"]), str(item["vertical_crs"]))
        if item["complete"] and item["year"] > newest.get(key, {"year": 0})["year"]:
            newest[key] = item
    return newest


def _selection(
    chosen: list[Combination], args: dict[str, str]
) -> tuple[CheckStatus, CheckItem]:
    """Return the verdict on the plan's own grid and the line that says it."""
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
    """Report whether the chosen NMT/NMPT grid is published, and what else is."""
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


def _refused(plan: Mapping[str, Any]) -> CheckOutput | None:
    """Return the report of a plan that lists the refusal of the store, else ``None``.

    A root that a write turns away with ``conflict`` (``nested_store``, ``not_empty``)
    is the one position of the plan: the track ``store``, the action ``conflict`` and
    the text of the refusal as its ``error``. The plan is ok and asks nothing of the
    source, so there are no sheets or counties to count; the run raises the same
    ``conflict``.
    """
    for item in plan["items"]:
        if item.get("track") == "store" and item.get("action") == "conflict":
            detail = str(item.get("error") or "")
            return {
                "status": "unavailable",
                "items": [{"key": "store_refused", "args": {"detail": detail}}],
            }
    return None


def _orthophoto(
    call: CatalogCall, ctx: ToolContext, *, words: str = "orthophoto"
) -> CheckOutput:
    """Check the newest flight GUGiK's index lists for each requested sheet.

    ``words`` names the product in the keys of the lines (``orthophoto``: the RGB
    orthophotomap, ``true_orthophoto``: the true orthophoto of selected cities).
    """
    try:
        plan = ctx.runner.check(call)
    except ToolError as err:
        if err.tool_code != "no_data":
            raise
        return {
            "status": "unavailable",
            "items": [{"key": f"{words}_none", "args": {"detail": err.detail}}],
        }
    if (refused := _refused(plan)) is not None:
        return refused
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
            "key": f"{words}_sheets",
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
    """Check the cutout: the index of sheets is a proxy for what the WCS composes."""
    (call,) = calls.download_elevation_cutout(params, ctx)
    return _elevation(call, ctx)


def download_orthophoto_cutout(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """Check the cutout: the sheet index of the area is a proxy for what WCS composes.

    The cutout itself has no cheap signal (Kartograf's plan cannot tell without
    downloading), so the index of the PL-1992 sheets of the same area is asked
    instead, as for the elevation cutout.
    """
    (cutout,) = calls.download_orthophoto_cutout(params, ctx)
    area = {
        name: value for name, value in cutout.options.items() if name in _AREA_OPTIONS
    }
    sheets = CatalogCall(
        cutout.command, {**area, "sheet_system": "1992"}, cutout.kind, cutout.params
    )
    words = "orthophoto" if params["product"] == "orthophoto" else "true_orthophoto"
    report = _orthophoto(sheets, ctx, words=words)
    return {
        "status": report["status"],
        "items": [*report["items"], {"key": "cutout_note", "args": {}}],
    }


def _shown(units: list[str]) -> str:
    """Return the units of a plan for one line (the first of many and an ellipsis)."""
    shown = ", ".join(units[:_SHOWN_UNITS])
    return shown + ", ..." if len(units) > _SHOWN_UNITS else shown


def _verdict(statuses: Counter[str], count: int) -> CheckStatus:
    """Return ``unknown`` when no position was checked, ``partial`` when some were."""
    if statuses["check_failed"] == count:
        return "unknown"
    return "partial" if statuses["check_failed"] else "available"


def download_bdot10k(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """Check the counties an area touches and whether their packages are stored."""
    (call,) = calls.download_bdot10k(params, ctx)
    plan = ctx.runner.check(call)
    if (refused := _refused(plan)) is not None:
        return refused
    items = plan["items"]
    if not items:
        return {"status": "unavailable", "items": [{"key": "no_counties", "args": {}}]}
    statuses = Counter(item["status"] for item in items)
    units = [str(item["unit"]) for item in items]
    lines: list[CheckItem] = [
        {"key": "counties", "args": {"count": str(len(units)), "units": _shown(units)}}
    ]
    if statuses["current"]:
        lines.append({"key": "in_store", "args": {"count": str(statuses["current"])}})
    return {"status": _verdict(statuses, len(items)), "items": lines}


def download_landcover(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """CORINE: the edition the CLMS catalogue announces; BDOO: the voivodeships.

    Without CLMS credentials CORINE is a WMS preview, which has no cheap signal;
    BDOO has none either, so its plan lists the voivodeships of the area (PRG) and
    what the store holds.
    """
    (call,) = calls.download_landcover(params, ctx)
    plan = ctx.runner.check(call)
    if (refused := _refused(plan)) is not None:
        return refused
    items = plan["items"]
    if not items:
        key = "no_voivodeships" if params["product"] == "bdoo" else "corine_none"
        return {"status": "unavailable", "items": [{"key": key, "args": {}}]}
    statuses = Counter(item["status"] for item in items)
    status = _verdict(statuses, len(items))
    lines: list[CheckItem] = []
    if params["product"] == "bdoo":
        units = [str(item["unit"]) for item in items]
        lines.append(
            {
                "key": "voivodeships",
                "args": {"count": str(len(units)), "units": _shown(units)},
            }
        )
    elif any(str(item["segment"]).endswith(_PREVIEW_SEGMENT) for item in items):
        status = "unknown"
        lines.append({"key": "corine_preview", "args": {}})
    else:
        editions = sorted(
            {str(item["available_label"]) for item in items if item["available_label"]}
        )
        if editions:
            lines.append(
                {"key": "corine_edition", "args": {"edition": ", ".join(editions)}}
            )
    if statuses["check_failed"]:
        lines.append(
            {
                "key": "landcover_unchecked",
                "args": {"count": str(statuses["check_failed"])},
            }
        )
    # Neither BDOO nor the CORINE preview has a signal: a stored position is one
    # with a local version, whatever its status
    stored = sum(item["local_label"] is not None for item in items)
    if stored:
        lines.append({"key": "in_store", "args": {"count": str(stored)}})
    if statuses["newer"]:
        lines.append({"key": "soil_newer", "args": {"count": str(statuses["newer"])}})
    return {"status": status, "items": lines}


def _soil(call: CatalogCall, ctx: ToolContext) -> CheckOutput:
    """Compare the SoilGrids layers of a request with what the store holds.

    The plan compares each layer with the edition the SoilGrids service announces
    (its GetCapabilities); the groups of ``soil hsg`` are computed, not published,
    and are ``current`` when their stored inputs are.
    """
    plan = ctx.runner.check(call)
    if (refused := _refused(plan)) is not None:
        return refused
    layers = [item for item in plan["items"] if item.get("track") != _HSG_TRACK]
    computed = [item for item in plan["items"] if item.get("track") == _HSG_TRACK]
    statuses = Counter(item["status"] for item in layers)
    status: CheckStatus
    if not layers or statuses["check_failed"] == len(layers):
        status = "unknown"
    elif statuses["check_failed"]:
        status = "partial"
    else:
        status = "available"
    editions = sorted(
        {str(item["available_label"]) for item in layers if item["available_label"]}
    )
    lines: list[CheckItem] = []
    if editions:
        lines.append(
            {
                "key": "soil_edition",
                "args": {"edition": ", ".join(editions), "count": str(len(layers))},
            }
        )
    if statuses["check_failed"] or not layers:
        lines.append(
            {"key": "soil_unchecked", "args": {"count": str(statuses["check_failed"])}}
        )
    if statuses["current"]:
        lines.append({"key": "in_store", "args": {"count": str(statuses["current"])}})
    if statuses["newer"]:
        lines.append({"key": "soil_newer", "args": {"count": str(statuses["newer"])}})
    if any(item["status"] == "current" for item in computed):
        lines.append({"key": "hsg_current", "args": {}})
    return {"status": status, "items": lines}


def download_soil_layer(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """Check the SoilGrids edition of the layer and whether the store holds it."""
    (call,) = calls.download_soil_layer(params, ctx)
    return _soil(call, ctx)


def classify_soil_hsg(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """Check the clay, sand and silt layers of the groups and the stored groups."""
    (call,) = calls.classify_soil_hsg(params, ctx)
    return _soil(call, ctx)

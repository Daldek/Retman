"""Kartograf call builders: Retman parameters to catalog calls (pure, offline).

A builder never imports Kartograf and never touches the file system; the same
builder serves plan-time validation, the preview, the check and the run. The
environment of a call (store, cache, workers, update mode) is added by the
client from ``[tools.kartograf]``, never here.
"""

from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext

# The one scale of PL-1992 sheets (GUGiK calls the module 1:5000)
_PL1992_SCALE = "1:10000"


def _scale(target_scale: str) -> str:
    """Kartograf's scale label of an option key: ``scale_2000`` is ``1:2000``."""
    return "1:" + target_scale.removeprefix("scale_")


def _area(area: dict[str, Any]) -> tuple[dict[str, object], dict[str, str]]:
    """Kartograf area options of an area reading, and their routing to ``area``."""
    kind = area["type"]
    if kind == "sheet":
        return {"sheet": area["code"]}, {"sheet": "area"}
    if kind == "teryt":
        return {"teryt": area["code"]}, {"teryt": "area"}
    if kind == "bbox":
        bbox = [area["min_x"], area["min_y"], area["max_x"], area["max_y"]]
        return (
            {"bbox": bbox, "bbox_crs": area["crs"]},
            {"bbox": "area", "bbox_crs": "area"},
        )
    options: dict[str, object] = {"geometry": area["path"]}
    if area.get("layer") is not None:
        options["layer"] = area["layer"]
    return options, {"geometry": "area", "layer": "area"}


def _sheets(
    params: dict[str, Any],
    ctx: ToolContext,
    *,
    tool_product: str,
    kind: str,
    target: str | None,
) -> CatalogCall:
    """Sheets of a product for a sheet code or a geometry file.

    ``kind`` is the Retman data kind (``dem``, ``dsm``, ``orthophoto``) and
    ``target`` the scale the user chose for a hierarchy (``None``: the sheet
    itself). Kartograf takes the sheet system from a code and has ONE scale for
    PL-1992 (1:10000; a coarser code expands by itself and ``scale`` is
    rejected), so ``scale`` is passed only where it names something: a PL-2000
    code, or a PL-1992 code with a target other than 1:10000 (which Kartograf
    then rejects, routed to ``target_scale``). For a geometry file the system
    follows from the target: 1:10000 is PL-1992, any other scale PL-2000.
    """
    area = params["area"]
    options: dict[str, object] = {"product": tool_product}
    routing: dict[str, str] = {}
    resolution = None
    if kind != "orthophoto":
        name = "resolution_dsm" if kind == "dsm" else "resolution"
        resolution = params[name]
        options["resolution"] = ctx.tool_value(name, resolution)
        routing["resolution"] = name
        if "vertical_crs" in params:  # NMT 100 m has no height system
            options["vertical_crs"] = ctx.tool_value(
                "vertical_crs", params["vertical_crs"]
            )
    area_options, area_routing = _area(area)
    options.update(area_options)
    routing.update(area_routing)
    if area["type"] == "sheet":
        system = "2000" if "." in area["code"] else "1992"
        if target is not None and not (system == "1992" and target == _PL1992_SCALE):
            options["scale"] = target
            routing["scale"] = "target_scale"
        elif target is None:
            # a PL-2000 1:10000 code asks for a scale this operation never
            # passes: the user's way out is another sheet
            routing["scale"] = "area"
    else:
        options["country"] = "pl"
        system = "1992" if target in (None, _PL1992_SCALE) else "2000"
        if resolution != "100m":  # province files take no sheet system
            options["sheet_system"] = system
            if target is not None:
                routing["sheet_system"] = "target_scale"
        if system == "2000" and resolution != "100m":
            options["scale"] = target
            routing["scale"] = "target_scale"
    command = "imagery download" if kind == "orthophoto" else "elevation download"
    return CatalogCall(
        command, options, "dem_archive" if resolution == "100m" else kind, routing
    )


def download_dem_sheet(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """NMT sheets of a sheet code or of the sheets a geometry file touches."""
    return [_sheets(params, ctx, tool_product="nmt", kind="dem", target=None)]


def download_sheet_hierarchy(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """NMT, NMPT or orthophoto sheets descending from a parent sheet.

    The orthophoto call is the RGB ``imagery download``: it exists to let
    Kartograf validate the request offline; the colour the user chose is applied
    by the handler, which downloads through the provider class.
    """
    product = params["product"]
    return [
        _sheets(
            params,
            ctx,
            tool_product=ctx.tool_value("product", product),
            kind=product,
            target=_scale(params["target_scale"]),
        )
    ]


def download_elevation_cutout(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """One 1 m WCS cutout of a rectangle or of the envelope of a geometry file."""
    area_options, routing = _area(params["area"])
    options: dict[str, object] = {
        "product": ctx.tool_value("product", params["product"]),
        "country": "pl",
        **area_options,
        "cutout": True,
        "horizontal_crs": ctx.tool_value("target_crs", params["target_crs"]),
        "vertical_crs": ctx.tool_value("vertical_crs", params["vertical_crs"]),
    }
    routing["horizontal_crs"] = "target_crs"
    return [CatalogCall("elevation download", options, params["product"], routing)]


def download_bdot10k(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """Build the call for the current BDOT10k package of each county in an area."""
    area_options, routing = _area(params["area"])
    options: dict[str, object] = {
        "product": "bdot10k",
        **area_options,
        "format": ctx.tool_value("format", params["format"]),
    }
    return [CatalogCall("landcover download", options, "topographic_vector", routing)]

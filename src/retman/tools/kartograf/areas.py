"""What a request covers, asked of Kartograf offline through the client.

Kartograf reports sheets without GUGiK data only as notice text, so the count of
missing sheets after a run is the number of sheets the request covers minus the
files delivered, and the preview shows the same number before the user confirms.
The count is derived from the very call that is validated and run, so it cannot
drift from what is requested. The envelope of a geometry file is the other fact of
the area that a plan shows.
"""

from dataclasses import dataclass
from typing import Any

from retman.adapters.catalog import CatalogCall, PlanClient

# The offline lookup of the envelope of a geometry file: Kartograf offers it as a
# function (``get_overall_bbox``), not as a catalog command
ENVELOPE = "geometry envelope"

# The one scale of PL-1992 sheets, and of the sheets of the true orthophoto
_PL1992_SCALE = "1:10000"
_TRUE_ORTHO_SCALE = "1:5000"
# The options of a call that give an area other than a sheet code
_AREA_OPTIONS = ("geometry", "layer", "bbox", "bbox_crs")


@dataclass(frozen=True)
class SheetCount:
    """``count`` sheets of ``scale`` in the sheet system ``system`` (1992 or 2000)."""

    count: int
    scale: str
    system: str


def _denominator(scale: str) -> int:
    return int(scale.split(":")[1])


def sheet_count(call: CatalogCall, client: PlanClient) -> SheetCount | None:
    """Return the sheets ``call`` requests; ``None`` for NMT 100 m (province files).

    Raises
    ------
    ToolError
        Kartograf refuses the sheet code, the scale or the geometry file (e.g. a
        target scale that is not finer than the sheet): the caller decides what
        that means.
    """
    options = call.options
    if options.get("resolution") == "100m":
        return None
    if "geometry" in options or "bbox" in options:
        own_scale = _TRUE_ORTHO_SCALE if options.get("product") == "true-orto" else None
        scale = str(options.get("scale", own_scale or _PL1992_SCALE))
        system = str(options["sheet_system"])
        area = {name: options[name] for name in _AREA_OPTIONS if name in options}
        found = client.lookup(
            CatalogCall("sheet find", {**area, "scale": scale, "sheet_system": system})
        )
        return SheetCount(int(found["count"]), scale, system)
    code = str(options["sheet"])
    own = client.lookup(CatalogCall("sheet parse", {"sheet": code}))
    system, scale = str(own["sheet_system"]), str(own["scale"])
    target = options.get("scale")
    if target is None and system == "1992" and _denominator(scale) > 10000:
        # A coarser PL-1992 code expands by itself into its 1:10000 sheets
        target = _PL1992_SCALE
    if target is None or target == scale:
        return SheetCount(1, scale, system)
    below = client.lookup(
        CatalogCall("sheet parse", {"sheet": code, "descendants": target})
    )
    return SheetCount(int(below["descendants"]["count"]), str(target), system)


def envelope(area: dict[str, Any], client: PlanClient) -> tuple[float, ...]:
    """Return the rectangle of a geometry area: min x, min y, max x, max y.

    In EPSG:2180, whatever the system of the file.
    """
    options: dict[str, object] = {"geometry": area["path"]}
    if area.get("layer") is not None:
        options["layer"] = area["layer"]
    document = client.lookup(CatalogCall(ENVELOPE, options))
    return tuple(float(value) for value in document["bbox"])

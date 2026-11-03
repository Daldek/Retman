"""The manifest offers exactly the grids Kartograf's registry has.

Retman asks the user for a resolution and a height system as two choices; Kartograf
accepts only some pairs of them. Every pair the manifest can build is validated by
Kartograf itself and the accepted ones are compared with the registry of the
installed Kartograf, so that a grid added or dropped there (or an option missing in
the manifest) fails here instead of in front of a user.
"""

from collections.abc import Callable
from typing import Any

import pytest
from kartograf_support import PARENT, SHEET, OfflineClient, context

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.tools.kartograf import calls

Pair = tuple[str, str | None]

CLIENT = OfflineClient({})


def _nmt(
    ctx: ToolContext, resolution: str, vertical_crs: str | None
) -> list[CatalogCall]:
    params: dict[str, Any] = {"area": SHEET, "resolution": resolution}
    if vertical_crs is not None:
        params["vertical_crs"] = vertical_crs
    return calls.download_dem_sheet(params, ctx)


def _nmpt(
    ctx: ToolContext, resolution: str, vertical_crs: str | None
) -> list[CatalogCall]:
    params: dict[str, Any] = {
        "product": "dsm",
        "area": PARENT,
        "target_scale": "scale_10000",
        "resolution_dsm": resolution,
    }
    if vertical_crs is not None:
        params["vertical_crs"] = vertical_crs
    return calls.download_sheet_hierarchy(params, ctx)


Builder = Callable[[ToolContext, str, str | None], list[CatalogCall]]

# Kartograf's product: operation, call builder, name of the resolution parameter
PRODUCTS: dict[str, tuple[str, Builder, str]] = {
    "nmt": ("download_dem_sheet", _nmt, "resolution"),
    "nmpt": ("download_sheet_hierarchy", _nmpt, "resolution_dsm"),
}


def manifest_pairs(product: str) -> tuple[set[Pair], set[str], set[str]]:
    """The pairs of option values Kartograf accepts, with the option keys used.

    Every resolution of the manifest is combined with every height system of the
    manifest (100 m of NMT without one, as the manifest asks); a pair is accepted
    when Kartograf's offline validation takes the call. The pairs are in the
    tool's own values.
    """
    operation, build, resolution_name = PRODUCTS[product]
    ctx = context(operation)
    resolutions = list(ctx.specs[resolution_name]["options"])
    systems: list[str | None] = list(ctx.specs["vertical_crs"]["options"])
    accepted: set[Pair] = set()
    used_resolutions: set[str] = set()
    used_systems: set[str] = set()
    for resolution in resolutions:
        # NMT 100 m has no height system and the manifest never asks for one
        for system in [None] if resolution == "100m" else systems:
            (call,) = build(ctx, resolution, system)
            try:
                CLIENT.validate(call)
            except ToolError as err:
                assert err.tool_code == "validation_error"
                continue
            used_resolutions.add(resolution)
            if system is not None:
                used_systems.add(system)
            accepted.add(
                (
                    ctx.tool_value(resolution_name, resolution),
                    None if system is None else ctx.tool_value("vertical_crs", system),
                )
            )
    return accepted, used_resolutions, used_systems


def registry_pairs(product: str) -> set[Pair]:
    """The pairs of Kartograf's own registry for Poland (rows without a format)."""
    listed = CLIENT.lookup(CatalogCall("elevation list-sources", {"product": product}))
    pairs: set[Pair] = set()
    for source in listed["sources"]:
        select = source["select"]
        if select["country"] != "pl" or "format" in select:
            continue
        systems = select.get("vertical_crs")
        if systems is None:
            pairs.add((select["resolution"], None))
            continue
        for system in [systems] if isinstance(systems, str) else systems:
            pairs.add((select["resolution"], system))
    return pairs


@pytest.mark.parametrize("product", ["nmt", "nmpt"])
def test_accepted_pairs_of_the_manifest_are_the_pairs_of_the_registry(
    product: str,
) -> None:
    accepted, _, _ = manifest_pairs(product)

    assert accepted == registry_pairs(product)


def test_nmt_has_eight_height_system_pairs_and_the_100m_province_files() -> None:
    accepted, _, _ = manifest_pairs("nmt")

    assert len({pair for pair in accepted if pair[1] is not None}) == 8
    assert ("100m", None) in accepted
    assert len(accepted) == 9


def test_nmpt_has_five_pairs() -> None:
    accepted, _, _ = manifest_pairs("nmpt")

    assert len(accepted) == 5
    assert all(pair[1] is not None for pair in accepted)


@pytest.mark.parametrize("product", ["nmt", "nmpt"])
def test_every_option_of_the_grid_choices_is_accepted_in_some_pair(
    product: str,
) -> None:
    operation, _, resolution_name = PRODUCTS[product]
    ctx = context(operation)
    _, resolutions, systems = manifest_pairs(product)

    assert resolutions == set(ctx.specs[resolution_name]["options"])
    assert systems == set(ctx.specs["vertical_crs"]["options"])

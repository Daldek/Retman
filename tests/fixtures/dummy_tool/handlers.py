"""Deterministic offline handlers exercising the generic adapter."""

from pathlib import Path
from typing import Any

from retman.registry.manifest import HandlerOutput

_DEM = (
    b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n3\n"
)


def make_dem(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Produce a valid minimal ESRI ASCII Grid without downloading anything."""
    destination = output_dir / "dem.asc"
    destination.write_bytes(_DEM)
    return {
        "values": {"cells": 1, "style": params["style"]},
        "files": {"dem": [destination]},
        "warnings": [],
    }


def copy_dem(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Use the selected DEM input and output a separate copy."""
    destination = output_dir / "copy.asc"
    destination.write_bytes(inputs["source"].read_bytes())
    return {"values": {"cells": 1}, "files": {"dem": [destination]}, "warnings": []}


def broken_dem(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Raise a tool exception to exercise the failure result and audit trail."""
    raise RuntimeError("dummy failure")


def escape_dem(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Return a file outside the permitted result directory."""
    destination = output_dir.parent / "escape.asc"
    destination.write_bytes(_DEM)
    return {"values": {}, "files": {"dem": [destination]}, "warnings": []}

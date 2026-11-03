"""Folders in the states of a Kartograf store that the tool never writes itself.

A ready store comes from ``kartograf.testing`` (the ``kartograf_store_template``
fixture, DEV-10.6); what is made by hand here is a layout of product trees, the marker
of another tool and a marker the tool would not write. The names are the tool's own,
spelled out here and not taken from ``retman.stores``: a drift of the constants of
Retman must break a test, not follow the code.
"""

import json
from pathlib import Path

MARKER = "kartograf-store.json"
IMGW_MARKER = "imgw-store.json"


def write_product_files(folder: Path, tree: str = "nmt") -> None:
    """Make a file of a version in a product tree: the layout of a store."""
    version = folder / tree / "a_variant" / "versions" / "N-34" / "2026-10-12_48293a01"
    version.mkdir(parents=True)
    (version / "data.bin").write_text("x", encoding="utf-8")


def write_marker(folder: Path, schema: str = "kartograf-store/1") -> None:
    """Write a marker of Kartograf with all the fields of the schema it names."""
    folder.mkdir(parents=True, exist_ok=True)
    fields = {
        "schema": schema,
        "tool": "kartograf",
        "created_at": "2026-10-12T08:30:45+00:00",
        "producer_version": "0.8.0",
    }
    (folder / MARKER).write_text(json.dumps(fields), encoding="utf-8")


def write_other_marker(folder: Path) -> None:
    """Write the marker of an IMGWTools store: the file name is what tools look at."""
    folder.mkdir(parents=True, exist_ok=True)
    fields = {"schema": "imgw-store/1", "tool": "imgwtools"}
    (folder / IMGW_MARKER).write_text(json.dumps(fields), encoding="utf-8")

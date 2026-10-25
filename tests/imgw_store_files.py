"""Folders in the states of an IMGWTools store, for the tests of the store checks.

The marker is the document ``imgw store init`` writes, field for field, and the
names are the tool's own, spelled out here and not taken from ``retman.stores``: a
drift of the constants of Retman must break a test, not follow the code.
"""

import json
from pathlib import Path

MARKER = {
    "schema": "imgw-store/1",
    "tool": "imgw",
    "created_at": "2026-10-24T10:00:00Z",
    "producer_version": "3.0.0",
    "created_by": "imgwtools 3.0.0",
}


def write_marker(folder: Path, **changes: object) -> None:
    """Write ``imgw-store.json`` as the tool writes it; ``changes`` replace fields."""
    document = json.dumps({**MARKER, **changes})
    (folder / "imgw-store.json").write_text(document, encoding="utf-8")


def write_layout(folder: Path, tree: str = "archives") -> None:
    """Make a tree of a store in ``folder``: with or without a marker, a layout."""
    (folder / tree).mkdir()


def write_server_state(folder: Path) -> None:
    """The key file of the tool's REST server, which a default store also holds."""
    (folder / "api_keys.json").write_text("{}", encoding="utf-8")

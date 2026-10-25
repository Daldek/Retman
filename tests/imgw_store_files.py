"""Folders in the states of an IMGWTools store that the tool never writes itself.

A ready store comes from ``imgwtools.testing`` (the ``imgw_store_template`` fixture,
DEV-10.6); what is hand-made here is a layout without its marker and the key file of
the REST server. The names are the tool's own, spelled out here and not taken from
``retman.stores``: a drift of the constants of Retman must break a test, not follow
the code.
"""

from pathlib import Path


def write_layout(folder: Path, tree: str = "archives") -> None:
    """Make a tree of a store in ``folder``: with or without a marker, a layout."""
    (folder / tree).mkdir()


def write_server_state(folder: Path) -> None:
    """The key file of the tool's REST server, which a default store also holds."""
    (folder / "api_keys.json").write_text("{}", encoding="utf-8")


def write_damaged_marker(folder: Path) -> None:
    """A marker the tool cannot read (it is not JSON): the store is damaged."""
    (folder / "imgw-store.json").write_text("{", encoding="utf-8")

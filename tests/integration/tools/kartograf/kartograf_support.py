"""Helpers of the Kartograf tool tests (plain functions: a ``conftest.py`` in a
subfolder would clash with ``tests/conftest.py`` under ``mypy tests/``).

The tests run the real Kartograf offline wherever they can (validation, lookups);
only what needs the network or a store is replaced, by ``OfflineClient`` or by
recorded ``kartograf-download/1`` documents (``tests/fixtures/kartograf``).
"""

import json
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("kartograf")

from retman.adapters.catalog import (  # noqa: E402
    CatalogCall,
    ToolContext,
    ToolDocument,
    ToolError,
    ToolRun,
)
from retman.eval.placeholders import write_geopackage, write_shapefile  # noqa: E402
from retman.registry.loader import load_operations  # noqa: E402
from retman.registry.operation import Operation  # noqa: E402
from retman.testing import tool_context  # noqa: E402
from retman.tools.kartograf import client as kartograf_client  # noqa: E402
from retman.tools.kartograf.client import (  # noqa: E402
    KartografClient,
    run_from_document,
)
from retman.tools.kartograf.manifest import MANIFEST  # noqa: E402

TOOL_DIR = Path(kartograf_client.__file__).parent
FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "kartograf"

SHEET = {"type": "sheet", "code": "N-34-130-D-d-2-4"}
PARENT = {"type": "sheet", "code": "N-34-130-D-d-2"}
PL2000 = {"type": "sheet", "code": "7.171.21"}
PL2000_FINE = {"type": "sheet", "code": "7.171.21.12"}
TERYT = {"type": "teryt", "code": "2264"}
BBOX = {
    "type": "bbox",
    "min_x": 530000,
    "min_y": 382000,
    "max_x": 530100,
    "max_y": 382100,
    "crs": "EPSG:2180",
}

# What a GeoTIFF, a GeoPackage, a ZIP and an ESRI ASCII grid start with (the kinds
# check exactly this)
_ASC = (
    b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n3\n"
)
_CONTENT = {
    ".asc": _ASC,
    ".tif": b"II*\x00" + bytes(12),
    ".gpkg": b"SQLite format 3\x00" + bytes(100),
    ".zip": b"PK\x03\x04" + bytes(20),
}


@cache
def operations() -> dict[str, Operation]:
    """The four Kartograf operations as the registry loads them (version 0.8.0)."""
    return load_operations(
        "pl", manifests=[(MANIFEST, TOOL_DIR)], version_lookup=lambda _: "0.8.0"
    )


def settings(root: Path) -> dict[str, Any]:
    """``[retman.tools.kartograf]`` as the settings validate it, inside ``root``."""
    return {
        "store_dir": str(root / "store"),
        "cache_file": str(root / "data" / "kartograf_cache.db"),
        "workers": 2,
        "update": "local",
    }


def context(
    name: str,
    client: Any = None,
    *,
    root: Path | None = None,
    output_dir: Path | None = None,
) -> ToolContext:
    """A ``ToolContext`` of one operation; ``root`` gives it the tool settings."""
    return tool_context(
        operations()[name],
        client=client,
        settings=settings(root) if root is not None else None,
        output_dir=output_dir,
    )


def document(name: str, store: Path) -> dict[str, Any]:
    """A recorded document with its ``<store>`` placeholder replaced."""
    text = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    return dict(json.loads(text.replace("<store>", str(store))))


def materialise(doc: Mapping[str, Any]) -> None:
    """Create the files a ``kartograf-download/1`` document lists (valid content)."""
    for item in doc["files"]:
        path = Path(item["file"]["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_CONTENT[path.suffix])


def geometry(folder: Path, name: str = "granica.shp") -> dict[str, Any]:
    """A geometry area over a real placeholder file inside ``folder``."""
    path = folder / name
    folder.mkdir(parents=True, exist_ok=True)
    if name.endswith(".shp"):
        write_shapefile(path)
        return {"type": "geometry", "path": str(path), "layer": None}
    write_geopackage(path)
    return {"type": "geometry", "path": str(path), "layer": "obszar"}


Reply = ToolDocument | Callable[[CatalogCall], ToolDocument]


class OfflineClient(KartografClient):
    """Kartograf's real client with the network and the store replaced.

    Validation, command lines and lookups are Kartograf's own (offline); ``run``,
    ``check`` and ``query`` answer from programmed documents by command and record
    every use in ``network``, which must stay empty until the user has confirmed.
    """

    def __init__(
        self,
        client_settings: Mapping[str, Any],
        *,
        runs: Mapping[str, Reply] | None = None,
        plans: Mapping[str, Reply] | None = None,
        queries: Mapping[str, Reply] | None = None,
    ) -> None:
        super().__init__(client_settings)
        self.runs = dict(runs or {})
        self.plans = dict(plans or {})
        self.queries = dict(queries or {})
        self.network: list[tuple[str, CatalogCall]] = []

    @staticmethod
    def _answer(programmed: Mapping[str, Reply], call: CatalogCall) -> ToolDocument:
        try:
            reply = programmed[call.command]
        except KeyError:
            raise ToolError(
                "kartograf", "not_programmed", call.command, call=call
            ) from None
        return reply(call) if callable(reply) else reply

    def run(self, call: CatalogCall) -> ToolRun:
        """The programmed document of the command as a run."""
        self.network.append(("run", call))
        doc = self._answer(self.runs, call)
        return run_from_document(call, doc, self.command_line(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """The programmed freshness plan."""
        self.network.append(("check", call))
        return self._answer(self.plans, call)

    def query(self, call: CatalogCall) -> ToolDocument:
        """The programmed answer of a query."""
        self.network.append(("query", call))
        return self._answer(self.queries, call)

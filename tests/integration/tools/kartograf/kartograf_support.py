"""Helpers of the Kartograf tool tests (plain functions: a ``conftest.py`` in a
subfolder would clash with ``tests/conftest.py`` under ``mypy tests/``).

The tests run the real Kartograf in process, offline (``kartograf_offline``): the
documents the helpers return are those the pinned version writes, and the store is a
real store in a folder of the test. Only what needs the network is a stub there; what
cannot be produced that way (the answer of the availability service, a WCS cutout) is a
recorded document of the tool (``tests/fixtures/kartograf``).
"""

import json
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from functools import cache
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("kartograf")

import kartograf  # noqa: E402
from kartograf.testing import FixtureStore, build_fixture_store  # noqa: E402
from kartograf_offline import (  # noqa: E402
    Counties,
    GugikIndex,
    bdot10k_counties,
    flight,
    gugik_index,
)

from retman.adapters.catalog import (  # noqa: E402
    CatalogCall,
    ToolContext,
    ToolDocument,
    ToolError,
    ToolRun,
)
from retman.adapters.manifest_adapter import execute_operation  # noqa: E402
from retman.core.result import Result  # noqa: E402
from retman.eval.placeholders import write_geopackage, write_shapefile  # noqa: E402
from retman.i18n.loader import load_core_texts  # noqa: E402
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
TEXTS = load_core_texts("pl")

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

# The sheet of the scenarios that expands into four 1:10000 sheets, and those sheets
NMT_OPTIONS = {"product": "nmt", "resolution": "1m", "vertical_crs": "EVRF2007"}
FOUR = "N-34-139-C-a-3"
CHILDREN = tuple(f"{FOUR}-{number}" for number in range(1, 5))
# A sheet whose four children the index has no flight of
NO_FLIGHT = "N-34-139-C-a-4"
NEWEST = ("2025-10-21", "84183")
# Three counties of an area, the second of which cannot be downloaded
COUNTIES = ("0208", "0224", "0261")


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
    """A recorded document of the tool with its ``<store>`` placeholder replaced."""
    text = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    return dict(json.loads(text.replace("<store>", str(store))))


def geometry(folder: Path, name: str = "granica.shp") -> dict[str, Any]:
    """A geometry area over a real placeholder file inside ``folder``."""
    path = folder / name
    folder.mkdir(parents=True, exist_ok=True)
    if name.endswith(".shp"):
        write_shapefile(path)
        return {"type": "geometry", "path": str(path), "layer": None}
    write_geopackage(path)
    return {"type": "geometry", "path": str(path), "layer": "obszar"}


def built_store(root: Path) -> FixtureStore:
    """A store as ``kartograf.testing`` builds it (DEV-10.6): marker, versions, links"""
    return build_fixture_store(root)


def execute(name: str, ctx: ToolContext) -> Result:
    """Run an operation without parameters the way ``Retman.execute`` does.

    The files of a result go into ``ctx.output_dir``, which must exist.
    """
    folder = ctx.output_dir
    assert folder is not None
    return execute_operation(operations()[name], {}, {}, folder, 1, {}, {}, TEXTS, ctx)


# --- documents of the real Kartograf, offline ---------------------------------------


def _children(*numbers: int, full: bool = True) -> list[Any]:
    """The flights of the sheets ``FOUR-<number>`` (the newest flight of the tests)."""
    return [flight(CHILDREN[number - 1], *NEWEST, full=full) for number in numbers]


def _one_delivered() -> tuple[GugikIndex, str]:
    """One sheet, with a full flight."""
    return GugikIndex(_children(1)), CHILDREN[0]


def _one_of_four() -> tuple[GugikIndex, str]:
    """One of four sheets has a flight, which is not a full one; the others none."""
    return GugikIndex(_children(1, full=False)), FOUR


def _hard_failure() -> tuple[GugikIndex, str]:
    """Two of four sheets have a flight; the file of the second fails to transfer."""
    index = GugikIndex(_children(1, 2), failing=[_children(2)[0].url])
    return index, FOUR


def _none_delivered() -> tuple[GugikIndex, str]:
    """None of the four sheets has a flight."""
    return GugikIndex(), NO_FLIGHT


# What the stubbed GUGiK index holds in each scenario of an NMT sheet request, and the
# sheet requested: a coarse sheet expands into its four children
SHEET_SCENARIOS: dict[str, Callable[[], tuple[GugikIndex, str]]] = {
    "one_delivered": _one_delivered,
    "one_of_four": _one_of_four,
    "hard_failure": _hard_failure,
    "none_delivered": _none_delivered,
}


def sheets(name: str, store: Path) -> dict[str, Any]:
    """The ``kartograf-result/1`` envelope of a request for NMT 1 m EVRF2007 sheets.

    The real ``run_command`` writes the files into ``store``; ``name`` is a key of
    ``SHEET_SCENARIOS``.
    """
    index, sheet = SHEET_SCENARIOS[name]()
    with gugik_index(index):
        result = kartograf.run_command(
            "elevation download",
            {**NMT_OPTIONS, "sheet": sheet},
            root=store,
            cache=False,
        )
    return result.to_dict()


def bdot10k(file_format: str, store: Path) -> dict[str, Any]:
    """The envelope of BDOT10k of an area of three counties, the second one failing."""
    with bdot10k_counties(Counties(COUNTIES, failing=["0224"])):
        result = kartograf.run_command(
            "landcover download",
            {"product": "bdot10k", "sheet": SHEET["code"], "format": file_format},
            root=store,
            cache=False,
        )
    return result.to_dict()


def plan(name: str, store: Path) -> dict[str, Any]:
    """The ``kartograf-plan/1`` of an empty ``store`` for a request, by ``name``.

    ``plan_orthophoto_parent`` is the RGB orthophoto of the four sheets of ``PARENT``,
    ``plan_bdot10k_teryt`` and ``plan_bdot10k_sheet`` are BDOT10k of one county, given
    as a TERYT code and found by a sheet.
    """
    with ExitStack() as stack:
        if name == "plan_orthophoto_parent":
            flights = [
                flight(
                    f"{PARENT['code']}-{number}", "2025-04-26", "82712", orthophoto=True
                )
                for number in range(1, 5)
            ]
            stack.enter_context(gugik_index(GugikIndex(flights)))
            command = "imagery download"
            options: dict[str, object] = {"product": "orto", "sheet": PARENT["code"]}
        elif name == "plan_bdot10k_teryt":
            stack.enter_context(bdot10k_counties(Counties([TERYT["code"]])))
            command = "landcover download"
            options = {"product": "bdot10k", "teryt": TERYT["code"], "format": "GPKG"}
        else:
            stack.enter_context(bdot10k_counties(Counties(["2010"])))
            command = "landcover download"
            options = {"product": "bdot10k", "sheet": SHEET["code"], "format": "SHP"}
        checked = kartograf.check_command(command, options, root=store, cache=False)
    assert checked.result is not None
    return checked.result.to_dict()


# --- clients ---------------------------------------------------------------------

Reply = ToolDocument | Callable[[CatalogCall], ToolDocument]


class RecordingClient(KartografClient):
    """Kartograf's real client, which remembers every use of the network or the store.

    ``network`` must stay empty until the user has confirmed (N-12): the plan, its
    questions and its preview are all offline.
    """

    def __init__(self, client_settings: Mapping[str, Any]) -> None:
        super().__init__(client_settings)
        self.network: list[tuple[str, CatalogCall]] = []

    def run(self, call: CatalogCall) -> ToolRun:
        """Run the command and record it."""
        self.network.append(("run", call))
        return super().run(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        """Plan the command and record it."""
        self.network.append(("check", call))
        return super().check(call)

    def query(self, call: CatalogCall) -> ToolDocument:
        """Run the query and record it."""
        self.network.append(("query", call))
        return super().query(call)


class OfflineClient(RecordingClient):
    """The recording client with programmed answers for the commands that have one.

    Validation, command lines and lookups are Kartograf's own, and so is every command
    without an answer here. ``runs`` are ``kartograf-result/1`` envelopes, ``plans``
    freshness plans and ``queries`` answers of the availability service, by command; an
    answer may be a function of the call (it can raise a ``ToolError``).
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
        """The programmed envelope of the command as a run, else the real run."""
        if call.command not in self.runs:
            return super().run(call)
        self.network.append(("run", call))
        doc = self._answer(self.runs, call)
        return run_from_document(call, doc, self.command_line(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """The programmed freshness plan, else the real one."""
        if call.command not in self.plans:
            return super().check(call)
        self.network.append(("check", call))
        return self._answer(self.plans, call)

    def query(self, call: CatalogCall) -> ToolDocument:
        """The programmed answer of a query, else the real one."""
        if call.command not in self.queries:
            return super().query(call)
        self.network.append(("query", call))
        return self._answer(self.queries, call)

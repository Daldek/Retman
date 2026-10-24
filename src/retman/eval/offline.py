"""Offline tool clients for an evaluation run (``retman eval run``).

Planning calls the tool offline: it validates every call, looks up a station
catalog or what a store holds, and previews. An evaluation must not depend on
the user's stores, so IMGWTools gets a client that answers those lookups from
fixed documents (``retman.eval.stations`` for the stations) and leaves
validation and the pure catalog commands to the real tool. Running, checking
or querying is never allowed: evaluation plans and never executes.
"""

from collections.abc import Mapping
from typing import Any, NoReturn, cast

from retman.adapters.catalog import (
    CatalogCall,
    RunClient,
    ToolDocument,
    ToolError,
    ToolRun,
    create_client,
)
from retman.config import Config
from retman.eval.stations import synthetic_station_document, synthetic_station_items
from retman.exceptions import RetmanError
from retman.registry.operation import Operation
from retman.tools.imgwtools.params import DATASETS

_COVERAGE_FIRST = "1951-01-01"
_COVERAGE_LAST = "2025-12-31"
_ENVELOPE = {"schema": "imgw-result/1", "check": False, "status": "ok", "notices": []}


def _document(command: str, result: object) -> ToolDocument:
    return {**_ENVELOPE, "command": command, "result": result}


def _page(command: str, items: list[dict[str, Any]]) -> ToolDocument:
    result = {"items": items, "total": len(items), "limit": None, "offset": 0}
    return _document(command, result)


class OfflineImgwClient:
    """The real IMGWTools client for validation, fixed answers for the store.

    The store is "initialised and complete": ``store info`` says so, ``series
    summary`` covers every requested station for the whole dataset, a PMAXTP
    cell is "stored" and the station catalog is the synthetic one. Pure catalog
    commands (``datasets files``…) go to the real tool.
    """

    def __init__(self, real: RunClient) -> None:
        self._real = real

    def validate(self, call: CatalogCall) -> None:
        """Validate ``call`` with the real tool (offline)."""
        self._real.validate(call)

    def command_line(self, call: CatalogCall) -> str:
        """Return the real tool's command line (offline)."""
        return self._real.command_line(call)

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Answer with a fixed document for the store, the tool's for pure commands."""
        options = call.options
        if call.command == "stations find" and options.get("source") == "store":
            return synthetic_station_document(options)
        if call.command == "store info":
            return _document(
                "store info",
                {"exists": True, "supported": True, "schema": "imgw-store/1"},
            )
        if call.command == "series summary":
            return self._summary(call)
        if call.command == "pmaxtp read":
            data = {"ks": {"15": {"1": 1.0}}, "sg": {}, "rb": {}}
            return _document(
                "pmaxtp read",
                {
                    "method": options.get("method", "POT"),
                    "latitude": 52.25,
                    "longitude": 21.0,
                    "data": data,
                },
            )
        return self._real.lookup(call)

    @staticmethod
    def _summary(call: CatalogCall) -> ToolDocument:
        """Full coverage of every variable for the requested (or every) station."""
        options = call.options
        dataset = next(
            info
            for info in DATASETS.values()
            if info["tool_value"] == options["dataset"]
        )
        requested = options.get("stations")
        codes = (
            [str(code) for code in cast(list[object], requested)]
            if isinstance(requested, list)
            else [
                item["station_code"]
                for item in synthetic_station_items()
                if item["provider"] == dataset["provider"]
                and item["kind"] == dataset["kind"]
            ]
        )
        chosen = options.get("variables")
        variables = (
            [str(name) for name in cast(list[object], chosen)]
            if isinstance(chosen, list)
            else dataset["variables"]
        )
        items: list[dict[str, Any]] = [
            {
                "station_code": code,
                "variable": variable,
                "unit": "",
                "period": None,
                "first": _COVERAGE_FIRST,
                "last": _COVERAGE_LAST,
                "with_value": 0,
                "accumulated": 0,
                "gaps": [],
            }
            for code in codes
            for variable in variables
        ]
        return _page("series summary", items)

    @staticmethod
    def _refuse(call: CatalogCall) -> NoReturn:
        raise ToolError(
            "eval", "not_offline", f"evaluation never runs {call.command!r}", call=call
        )

    def run(self, call: CatalogCall) -> ToolRun:
        """Never: an evaluation plans and does not execute."""
        self._refuse(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        """Never: an evaluation does not check availability."""
        self._refuse(call)

    def query(self, call: CatalogCall) -> ToolDocument:
        """Never: an evaluation uses no network."""
        self._refuse(call)


def offline_clients(
    operations: Mapping[str, Operation], config: Config
) -> dict[str, RunClient]:
    """Offline clients for the tools among ``operations`` that have one.

    Only IMGWTools needs a stand-in; the other tools' clients are built from
    their manifests as usual.
    """
    clients: dict[str, RunClient] = {}
    for operation in operations.values():
        if (
            operation.tool == "imgwtools"
            and operation.client is not None
            and "imgwtools" not in clients
        ):
            settings = config.tools.get("imgwtools")
            if settings is None:
                raise RetmanError("[retman.tools.imgwtools] is missing in the config")
            clients["imgwtools"] = OfflineImgwClient(
                create_client(operation.client, settings)
            )
    return clients

"""Helpers of the IMGWTools adapter tests: the real tool, offline.

Documents come from the real tool run without a network: the offline fixture
store of ``imgwtools.testing`` for everything that reads or builds a store, and
recorded HTTP answers (``replay_http``) for the live endpoints. ``replay_http``
patches ``httpx`` below the tool's own code; nothing opens a socket.
"""

import json
import shutil
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from retman.adapters.catalog import (
    CatalogCall,
    ToolDocument,
    ToolNotice,
    ToolRun,
)
from retman.tools.imgwtools.client import IMGWToolsClient

# A synthetic PMAXTP answer (the real endpoint's structure, invented numbers):
# 7 durations x 6 probabilities in each of the tables ks, sg and rb
PMAXTP_DURATIONS = ("15", "30", "45", "60", "90", "120", "180")
PMAXTP_PROBABILITIES = ("1", "2", "5", "10", "20", "50")
PMAXTP_URL = "https://powietrze.imgw.pl/tpmax-api/point/{method}/KS/{lat}/{lon}"


def pmaxtp_payload(ind_x: int = 751, ind_y: int = 317) -> dict[str, Any]:
    """The JSON body of the PMAXTP endpoint for the cell ``ind_x``/``ind_y``."""

    def table(scale: float) -> dict[str, dict[str, float]]:
        return {
            duration: {
                probability: round(scale * (index + 1) * (7 - position) / 2, 1)
                for position, probability in enumerate(PMAXTP_PROBABILITIES)
            }
            for index, duration in enumerate(PMAXTP_DURATIONS)
        }

    return {
        "point": {
            "indX": ind_x,
            "indY": ind_y,
            "dataLon": 21.0,
            "dataLat": 52.25,
        },
        "data": {"ks": table(5.0), "sg": table(6.0), "rb": table(0.5)},
    }


@cache
def fixture_store() -> Path:
    """A read-only IMGWTools store with PL and CZ data (built once per process).

    Tests that write a store build their own with ``build_store``.
    """
    root = Path(tempfile.mkdtemp(prefix="retman-imgw-test-")) / "store"
    build_store(root)
    return root


def build_store(root: Path) -> Path:
    """The tool's offline fixture store (``complete_pl_cz``) in the empty ``root``."""
    from imgwtools.testing import build_fixture_store

    build_fixture_store(root, variant="complete_pl_cz")
    return root


def copy_store(tmp_path: Path) -> Path:
    """A private, writable copy of the fixture store."""
    target = tmp_path / "store"
    shutil.copytree(fixture_store(), target)
    return target


def recorded_answers() -> dict[str, dict[str, Any]]:
    """The recorded answers of the live endpoints that ship with the tool, by case."""
    from imgwtools.testing import fixture_files

    document = json.loads(
        fixture_files().joinpath("contract_recordings.json").read_text("utf-8")
    )
    return {item["case"]: item for item in document["interactions"]}


@contextmanager
def replay_http(*answers: Mapping[str, Any]) -> Iterator[list[str]]:
    """Answer ``httpx`` requests from ``answers`` (method, url, status, json).

    Every answer serves one request; a request without an answer is a connection
    error, as in the tool's own fixtures. Yields the list of the URLs requested.
    """
    queues: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for answer in answers:
        queues.setdefault((answer.get("method", "GET"), answer["url"]), []).append(
            answer
        )
    requested: list[str] = []

    def handle(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        queue = queues.get((request.method, str(request.url)))
        if not queue:
            raise httpx.ConnectError(
                f"no recorded answer: {request.url}", request=request
            )
        answer = queue.pop(0)
        return httpx.Response(
            answer.get("status", 200), json=answer.get("json"), request=request
        )

    with patch.object(httpx.HTTPTransport, "handle_request", handle):
        yield requested


def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore ``IMGW_DATA_DIR`` after the test: the client exports it once."""
    monkeypatch.setenv("IMGW_DATA_DIR", "unset-by-test")


def settings_for(tmp_path: Path, store: Path | None = None) -> dict[str, Any]:
    """The ``[retman.tools.imgwtools]`` table of a test: a store and a reference dir."""
    reference = tmp_path / "reference"
    reference.mkdir(exist_ok=True)
    return {
        "store_dir": str(store if store is not None else fixture_store()),
        "reference_data_dir": str(reference),
    }


def real_client(tmp_path: Path, store: Path | None = None) -> IMGWToolsClient:
    """The real client over ``store`` (the shared fixture store by default)."""
    return IMGWToolsClient(settings_for(tmp_path, store))


def synthetic_run(
    command: str,
    result: object,
    *,
    status: str = "ok",
    notices: tuple[ToolNotice, ...] = (),
) -> ToolRun:
    """A run whose document is the tool's own envelope around ``result``.

    ``result`` is a public result object of the tool (a dataclass or a model);
    the envelope is built with ``CommandResult.to_json`` and the run is mapped
    exactly as the client maps a real one, for commands that cannot be replayed
    offline (they need a server).
    """
    from imgwtools import CommandResult

    envelope = CommandResult(command, False, status, result, ())
    document = envelope.to_json()
    return ToolRun(
        command,
        status,  # type: ignore[arg-type]
        files=(),
        failed=IMGWToolsClient._failures(command, status, document),
        notices=notices,
        document=document,
        command_line=f"imgw {command}",
        schema="imgw-result/1",
    )


class HybridClient:
    """The real client, except that some commands return a prepared run."""

    def __init__(self, real: IMGWToolsClient, runs: Mapping[str, ToolRun]) -> None:
        self.real = real
        self.runs = dict(runs)

    def validate(self, call: CatalogCall) -> None:
        self.real.validate(call)

    def command_line(self, call: CatalogCall) -> str:
        return self.real.command_line(call)

    def lookup(self, call: CatalogCall) -> ToolDocument:
        return self.real.lookup(call)

    def run(self, call: CatalogCall) -> ToolRun:
        return self.runs.get(call.command) or self.real.run(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        return self.real.check(call)

    def query(self, call: CatalogCall) -> ToolDocument:
        return self.real.query(call)

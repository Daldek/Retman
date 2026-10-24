"""Shared fixtures: network isolation for offline tests (STANDARDS 10.4)."""

import ipaddress
import logging
import socket
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from retman.adapters.catalog import RunClient
from retman.backends.base import Decision
from retman.config import Thresholds, init_config, load_config
from retman.core.pipeline import Retman
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import FakeDecisionBackend


def pytest_addoption(parser: pytest.Parser) -> None:
    """Options for ``live`` tests; server addresses are never stored in the repo."""
    parser.addoption(
        "--live-openai-url",
        default=None,
        help="Base URL of an OpenAI-compatible server for live tests, e.g. .../v1",
    )
    parser.addoption(
        "--live-openai-model",
        default=None,
        help="Model name on the --live-openai-url server",
    )


def _is_loopback(address: Any) -> bool:
    if isinstance(address, tuple) and address:
        host = address[0]
    else:
        # AF_UNIX sockets and other local transports
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


@pytest.fixture(autouse=True)
def _block_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Fail any non-loopback connection unless the test is marked ``live``."""
    if request.node.get_closest_marker("live"):
        yield
        return
    original_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if not _is_loopback(address):
            raise RuntimeError(
                f"Network access in an offline test: {address!r} (mark it live)"
            )
        return original_connect(self, address)

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host not in (None, "localhost") and not _is_loopback((host,)):
            raise RuntimeError(
                f"Name resolution in an offline test: {host!r} (mark it live)"
            )
        return original_getaddrinfo(host, *args, **kwargs)

    original_getaddrinfo = socket.getaddrinfo
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield


@pytest.fixture(autouse=True)
def _isolate_logger() -> Iterator[None]:
    """Undo the handler the command line puts on the logger of Retman (DEV-12.1)."""
    logger = logging.getLogger("retman")
    handlers, level, propagate = list(logger.handlers), logger.level, logger.propagate
    yield
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


# --- The dummy tool (tests/fixtures/dummy_tool) for core, adapter and CLI tests.
# They live here because a conftest.py in a test subfolder would clash with this
# one under ``mypy tests/`` (duplicate module name).

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def dummy_client(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The dummy tool's client module with fresh recorders for this test."""
    monkeypatch.syspath_prepend(str(FIXTURES))
    import dummy_tool.client as module

    monkeypatch.setattr(module, "BUILT", [])
    monkeypatch.setattr(module, "CLIENTS", [])
    monkeypatch.setattr(module, "PROGRAM", {})
    return module


@pytest.fixture
def make_gpkg() -> Callable[..., Path]:
    """Create a minimal real GeoPackage (a SQLite file) with feature tables."""

    def make(path: Path, *tables: str) -> Path:
        with closing(sqlite3.connect(path)) as database:
            database.execute(
                "CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)"
            )
            database.executemany(
                "INSERT INTO gpkg_contents VALUES (?, ?)",
                [(table, "features") for table in tables],
            )
            database.commit()
        return path

    return make


@pytest.fixture
def operations(monkeypatch: pytest.MonkeyPatch) -> dict[str, Operation]:
    """The dummy tool's operations as the registry loads them (version 1.2)."""
    monkeypatch.syspath_prepend(str(FIXTURES))
    from dummy_tool.manifest import MANIFEST

    return load_operations(
        "pl",
        manifests=[(MANIFEST, FIXTURES / "dummy_tool")],
        version_lookup=lambda _: "1.2.0",
    )


@pytest.fixture
def create_app(
    tmp_path: Path, operations: dict[str, Operation], dummy_client: ModuleType
) -> Callable[..., Retman]:
    """Construct an isolated pipeline on the dummy package, not Kartograf.

    The project folder is ``tmp_path / "project"`` and the dummy tool's store
    ``tmp_path / "store"``: a store lives outside the project, like a real one.
    """
    config = load_config(init_config(tmp_path / "config.toml"))
    project = tmp_path / "project"
    project.mkdir()

    def create(
        rules: dict[str, str | Decision] | None = None,
        *,
        confidence: float = 1.0,
        journal_commands: bool = True,
        thresholds: Thresholds | None = None,
        collect: bool = False,
        clients: Mapping[str, RunClient] | None = None,
        operations_override: dict[str, Operation] | None = None,
    ) -> Retman:
        decision = replace(
            config.decision, thresholds=thresholds or config.decision.thresholds
        )
        settings = replace(
            config,
            decision=decision,
            journal_commands=journal_commands,
            collect_commands=collect,
            collect_path=tmp_path / "collection" / "collected.jsonl",
            tools={
                **config.tools,
                "dummy_tool": {"store_dir": str(tmp_path / "store")},
            },
        )
        return Retman(
            settings,
            FakeDecisionBackend(rules, confidence=confidence),
            project,
            operations=operations_override or operations,
            clients=clients,
        )

    return create

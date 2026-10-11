"""Shared fixtures: network isolation for offline tests (STANDARDS 10.4)."""

import ipaddress
import socket
from collections.abc import Iterator
from typing import Any

import pytest


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

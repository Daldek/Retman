"""Client factory of the dummy tool: a recording fake, built from the settings."""

from collections.abc import Mapping
from typing import Any

from retman.testing import FakeToolClient

# Settings of every client built through the manifest key ``client``
BUILT: list[Mapping[str, Any]] = []
# The clients built, in order, and the keyword arguments of the next ones
CLIENTS: list[FakeToolClient] = []
PROGRAM: dict[str, Any] = {}


def create_client(settings: Mapping[str, Any]) -> FakeToolClient:
    """Build the tool's client from its ``[tools.dummy_tool]`` table."""
    BUILT.append(settings)
    client = FakeToolClient(**PROGRAM)
    CLIENTS.append(client)
    return client

"""Helpers of the archive and project operation tests: operations, contexts, runs."""

from functools import cache
from pathlib import Path
from typing import Any

import retman.tools.imgwtools as package
from retman.adapters.catalog import PlanClient, ToolContext
from retman.adapters.manifest_adapter import execute_operation
from retman.core.result import Result
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import tool_context
from retman.tools.imgwtools.manifest import MANIFEST

STORE = Path("/stores/imgw")
PROJECT = Path("/projects/imgw")
TEXTS = load_core_texts("pl")
YEARS = {"type": "years", "first": 2000, "last": 2002}


@cache
def operations() -> dict[str, Operation]:
    """The operations of the real manifest, as the registry loads them."""
    return load_operations(
        "pl",
        manifests=[(MANIFEST, Path(package.__file__).parent)],
        version_lookup=lambda _: "3.0.0",
    )


def station(
    code: str, provider: str = "IMGW-PIB", kind: str = "hydro"
) -> dict[str, Any]:
    """A ``station`` value as the extractor reads a code (no catalog)."""
    return {
        "type": "station",
        "provider": provider,
        "kind": kind,
        "code": code,
        "name": None,
        "river": None,
        "in_catalog": False,
    }


def context(
    operation: str,
    client: PlanClient,
    *,
    settings: dict[str, Any] | None = None,
    project_dir: Path | None = None,
    output_dir: Path | None = None,
    inputs: dict[str, Path] | None = None,
) -> ToolContext:
    """A ``ToolContext`` of ``operation`` (the store ``/stores/imgw`` by default)."""
    return tool_context(
        operations()[operation],
        client=client,
        settings=settings if settings is not None else {"store_dir": str(STORE)},
        project_dir=project_dir or PROJECT,
        output_dir=output_dir,
        inputs=inputs,
    )


def execute(
    operation: str,
    params: dict[str, Any],
    ctx: ToolContext,
    *,
    inputs: dict[str, Path] | None = None,
) -> Result:
    """Run the operation the way ``Retman.execute`` does (after the plan's consent)."""
    return execute_operation(
        operations()[operation],
        params,
        inputs or {},
        ctx.output_dir or Path("."),
        1,
        {},
        {},
        TEXTS,
        ctx,
    )

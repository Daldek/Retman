"""Availability checks of the IMGWTools operations (``check`` hooks).

A check is the one step that reaches the network before an operation runs, and
the user confirms it separately (ARCHITECTURE 6.5). It asks the tool for its
freshness plan (``check_command``: HEAD requests and server listings, nothing is
downloaded or written) and summarises how much of the plan's selection the
source can serve.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from retman.adapters.catalog import ToolContext
from retman.registry.manifest import CheckItem, CheckOutput
from retman.tools.imgwtools.calls import (
    build_imgw_station_catalog,
    export_station_series,
)
from retman.tools.imgwtools.plans import (
    UNPUBLISHED,
    plan_refusal,
    refusal_check_output,
)

_MEGABYTE = 1_000_000


@dataclass(frozen=True)
class PlanSummary:
    """Counts of an ``imgw-plan/1`` document: archives by freshness, bytes, actions."""

    total: int
    to_download: int
    current: int
    unpublished: int
    failed: int
    size_bytes: int | None
    actions: dict[str, str]


def summarize_plan(document: Mapping[str, Any]) -> PlanSummary:
    """Count the items and actions of a check's document.

    ``to_download`` are the ``newer`` and ``missing`` archives; ``size_bytes`` is
    the sum of their sizes when the server reported them (``None`` when it
    reported none). ``actions`` maps each planned command to its status.
    """
    result = document.get("result")
    plan: Mapping[str, Any] = result if isinstance(result, dict) else {}
    items = [item for item in plan.get("items") or () if isinstance(item, dict)]
    states = Counter(str(item.get("status")) for item in items)
    unpublished = sum(
        1
        for item in items
        if item.get("status") == "unverifiable" and item.get("error") == UNPUBLISHED
    )
    sizes = [
        item["content_length"]
        for item in items
        if item.get("status") in ("newer", "missing")
        and isinstance(item.get("content_length"), int)
    ]
    actions = {
        str(action.get("command")): str(action.get("status"))
        for action in plan.get("actions") or ()
        if isinstance(action, dict)
    }
    return PlanSummary(
        total=len(items),
        to_download=states["newer"] + states["missing"],
        current=states["current"],
        unpublished=unpublished,
        failed=states["check_failed"],
        size_bytes=sum(sizes) if sizes else None,
        actions=actions,
    )


def _refusal(document: Mapping[str, Any]) -> CheckOutput | None:
    """Return the report of a plan that lists the refusal of the store, else ``None``.

    The plan of a write into a root the tool turns away has no item to count, and its
    one action is no state of a catalog: the report says that the write is refused.
    """
    result = document.get("result")
    refusal = plan_refusal(result) if isinstance(result, dict) else None
    return None if refusal is None else refusal_check_output(refusal)


def _status(
    summary: PlanSummary, document: Mapping[str, Any]
) -> Literal["available", "partial", "unavailable", "unknown"]:
    if document.get("status") == "cancelled":
        return "unknown"
    if summary.total and summary.failed == summary.total:
        return "unavailable"
    if summary.failed or summary.unpublished:
        return "partial"
    return "available"


def check_build_imgw_station_catalog(
    params: dict[str, Any], ctx: ToolContext
) -> CheckOutput:
    """Operation 2: are the station lists reachable and is the catalog out of date."""
    (call,) = build_imgw_station_catalog(params, ctx)
    document = ctx.runner.check(call)
    if (refused := _refusal(document)) is not None:
        return refused
    summary = summarize_plan(document)
    items: list[CheckItem] = []
    state = summary.actions.get("store catalog")
    if state is not None:
        items.append({"key": f"catalog_{state}", "args": {}})
    if summary.total:
        items.append(
            {
                "key": "sources",
                "args": {
                    "reachable": str(summary.total - summary.failed),
                    "total": str(summary.total),
                },
            }
        )
    return {"status": _status(summary, document), "items": items}


def check_export_station_series(
    params: dict[str, Any], ctx: ToolContext
) -> CheckOutput:
    """Operation 9: how many archives the synchronisation would fetch, and how big.

    The store as the source needs no network: there is nothing to ask the server.
    """
    if params["data_source"] != "server":
        return {"status": "available", "items": [{"key": "from_store", "args": {}}]}
    sync = next(
        call
        for call in export_station_series(params, ctx)
        if call.command == "store sync"
    )
    document = ctx.runner.check(sync)
    if (refused := _refusal(document)) is not None:
        return refused
    summary = summarize_plan(document)
    items: list[CheckItem] = []
    if summary.total:
        args = {
            "to_download": str(summary.to_download),
            "total": str(summary.total),
            "current": str(summary.current),
        }
        if summary.size_bytes is None:
            items.append({"key": "archives_unsized", "args": args})
        else:
            size = f"{summary.size_bytes / _MEGABYTE:.1f}"
            items.append({"key": "archives", "args": {**args, "size": size}})
    if summary.unpublished:
        items.append(
            {"key": "items_unpublished", "args": {"count": str(summary.unpublished)}}
        )
    if summary.failed:
        items.append({"key": "items_failed", "args": {"count": str(summary.failed)}})
    return {"status": _status(summary, document), "items": items}

"""Reading ``imgw-plan/1`` documents: counts and sizes for previews, checks, results.

A plan is what ``store check`` and the check twin of ``store sync`` return: the
freshness of each archive file (``current``, ``newer``, ``missing``,
``unverifiable``, ``check_failed``) with the size the server reports. The plan of
a store write that the tool will refuse lists that refusal as its one action and
no archive. Everything here is
plain data handling.
"""

from collections import Counter
from collections.abc import Mapping
from typing import Any, Final, Literal

from retman.registry.manifest import CheckItem, CheckOutput

# The ``error`` of a plan item that the server does not publish
# (``imgwtools.fetch.UNPUBLISHED``; a test compares it with the installed tool)
UNPUBLISHED: Final = "not published"
PLAN_STATUSES: Final = ("current", "newer", "missing", "unverifiable", "check_failed")
# The states of a series in ``series_state`` that need a (re)build
_SERIES_TO_BUILD: Final = ("outdated", "missing")

_UNITS: Final = ("B", "kB", "MB", "GB", "TB")


def format_bytes(size: int) -> str:
    """Format a size with a decimal unit and one decimal place: ``320.5 MB``."""
    value = float(size)
    unit = 0
    while value >= 1000 and unit < len(_UNITS) - 1:
        value /= 1000
        unit += 1
    return f"{size} B" if unit == 0 else f"{value:.1f} {_UNITS[unit]}"


def plan_items(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return the items of an ``imgw-plan/1`` document (objects only)."""
    items = plan.get("items")
    return [item for item in items if isinstance(item, Mapping)] if items else []


def plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Count a plan: items by status, what a sync would download and its size.

    ``bytes_to_download`` adds up the sizes the server reports for the ``newer`` and
    ``missing`` items; ``size_unknown`` counts those that report none. An item the
    server does not publish is ``unpublished``, one it cannot compare ``no_signal``.
    """
    items = plan_items(plan)
    by_status = Counter(str(item.get("status")) for item in items)
    wanted = [item for item in items if item.get("status") in ("newer", "missing")]
    sizes = [item.get("content_length") for item in wanted]
    unverifiable = [item for item in items if item.get("status") == "unverifiable"]
    unpublished = sum(item.get("error") == UNPUBLISHED for item in unverifiable)
    failures = [
        str(item.get("error") or "")
        for item in items
        if item.get("status") == "check_failed"
    ]
    series = plan.get("series_state")
    return {
        "items": len(items),
        "by_status": {status: by_status.get(status, 0) for status in PLAN_STATUSES},
        "to_download": len(wanted),
        "bytes_to_download": sum(size for size in sizes if isinstance(size, int)),
        "size_unknown": sum(not isinstance(size, int) for size in sizes),
        "unpublished": unpublished,
        "no_signal": len(unverifiable) - unpublished,
        "first_failure": failures[0] if failures else "",
        "series_to_build": sorted(
            slug
            for slug, state in (series.items() if isinstance(series, Mapping) else ())
            if state in _SERIES_TO_BUILD
        ),
        "requests": plan.get("requests"),
    }


def plan_refusal(plan: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Return the action of a plan that says the write will be refused, or ``None``.

    A store write turns a root away with ``conflict`` when the root lies in, holds or
    nests a store of any tool (``nested_store``) or holds other files and is no store
    (``not_empty``). The plan of such a write does not fail: it lists one action with
    ``action`` ``conflict``, the ``reason``, the root as ``path`` and the tool's own
    wording as ``detail``, lists no archive and asks the server for nothing; the run
    raises the same ``conflict``.
    """
    for action in plan.get("actions") or ():
        if isinstance(action, Mapping) and action.get("action") == "conflict":
            return action
    return None


def refusal_check_output(action: Mapping[str, Any]) -> CheckOutput:
    """Report a plan whose write the tool will refuse: nothing can be served."""
    return {
        "status": "unavailable",
        "items": [
            {"key": "store_refused", "args": {"detail": str(action.get("detail", ""))}}
        ],
    }


def plan_check_output(plan: Mapping[str, Any]) -> CheckOutput:
    """Build the availability report of a freshness plan of an archive selection.

    ``available``: every file is on the server and can be served; ``partial``: some
    are not published, cannot be compared or could not be checked; ``unavailable``:
    none is published, or the tool will refuse to write the store; ``unknown``: no
    check succeeded.
    """
    refusal = plan_refusal(plan)
    if refusal is not None:
        return refusal_check_output(refusal)
    summary = plan_summary(plan)
    by_status: dict[str, int] = summary["by_status"]
    total = summary["items"]
    failed = by_status["check_failed"]
    problems = failed + summary["unpublished"] + summary["no_signal"]
    status: Literal["available", "partial", "unavailable", "unknown"]
    if total == 0 or failed == total:
        status = "unknown"
    elif summary["unpublished"] == total:
        status = "unavailable"
    elif problems == 0:
        status = "available"
    else:
        status = "partial"
    items: list[CheckItem] = [
        {
            "key": "arch_summary",
            "args": {
                "total": str(total),
                "to_download": str(summary["to_download"]),
                "current": str(by_status["current"]),
                "size": format_bytes(summary["bytes_to_download"]),
            },
        }
    ]
    if summary["size_unknown"]:
        items.append(
            {
                "key": "arch_size_unknown",
                "args": {"count": str(summary["size_unknown"])},
            }
        )
    if summary["unpublished"]:
        items.append(
            {
                "key": "arch_unpublished",
                "args": {"count": str(summary["unpublished"])},
            }
        )
    if summary["no_signal"]:
        items.append(
            {"key": "arch_no_signal", "args": {"count": str(summary["no_signal"])}}
        )
    if failed:
        items.append(
            {
                "key": "arch_failed",
                "args": {"count": str(failed), "detail": summary["first_failure"]},
            }
        )
    if summary["series_to_build"]:
        items.append(
            {
                "key": "arch_series",
                "args": {"names": ", ".join(summary["series_to_build"])},
            }
        )
    return {"status": status, "items": items}

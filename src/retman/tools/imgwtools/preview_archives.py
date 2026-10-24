"""Offline previews and the availability check of the ``imgw_archives`` operations.

``preview(params, ctx) -> PreviewOutput`` runs while planning, so it uses only the
offline half of the client (catalog lookups of the tool: file listings, the store's
state and entries) and the user's own files: no network, nothing is written. A
store that cannot serve the operation is a blocking problem of the plan, never a
silent initialisation. ``check_sync_imgw_store`` is the one network step (the
user confirms it separately): the freshness plan of the selection.
"""

import json
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from retman.adapters.catalog import ToolContext, ToolError
from retman.registry.manifest import (
    CheckOutput,
    PreviewOutput,
    PreviewProblem,
    PreviewRow,
)
from retman.stores import imgw_store_state
from retman.tools.imgwtools.calls_archives import (
    archive_files_call,
    expected_archives,
    selected_years,
    stored_archives,
    sync_imgw_store,
    years_text,
)
from retman.tools.imgwtools.folders import same_folder
from retman.tools.imgwtools.plans import (
    format_bytes,
    plan_check_output,
    plan_summary,
)
from retman.tools.imgwtools.preview import store_problems, store_rows


def _blocked(problems: list[PreviewProblem]) -> PreviewOutput:
    return {"values": {}, "rows": [], "problems": problems}


def _listing(
    params: Mapping[str, Any], ctx: ToolContext
) -> tuple[list[PreviewRow], dict[str, Any]]:
    """Rows for the files a selection names, from the tool's offline listing.

    The size of the archives is not known without a request, which the row says.
    """
    document = ctx.client.lookup(archive_files_call(params, ctx))
    result = document.get("result")
    raw = result.get("items") if isinstance(result, Mapping) else None
    items = [item for item in raw or () if isinstance(item, Mapping)]
    if not items:
        return [], {"files": 0}
    names = [PurePosixPath(str(item["server_path"])).name for item in items]
    values: dict[str, Any] = {
        "files": len(items),
        "first_file": names[0],
        "last_file": names[-1],
    }
    if len(items) == 1:
        rows: list[PreviewRow] = [{"key": "arch_file", "args": {"name": names[0]}}]
    else:
        rows = [
            {
                "key": "arch_files",
                "args": {
                    "count": str(len(items)),
                    "first": names[0],
                    "last": names[-1],
                },
            }
        ]
    starts = [str(item["period_start"]) for item in items if item.get("period_start")]
    ends = [str(item["period_end"]) for item in items if item.get("period_end")]
    if starts and ends:
        numbering = ctx.option_meta("dataset", params["dataset"])["numbering"]
        rows.append(
            {
                "key": f"arch_span_{numbering}",
                "args": {"start": min(starts), "end": max(ends)},
            }
        )
        values.update(span_start=min(starts), span_end=max(ends))
    return rows, values


def preview_download_archives(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the files that would be downloaded to the result folder (no store)."""
    rows, values = _listing(params, ctx)
    return {"values": values, "rows": rows, "problems": []}


def _store_listing(
    params: dict[str, Any], ctx: ToolContext, *, write: bool
) -> PreviewOutput:
    problems = store_problems(ctx, write=write)
    if problems:
        return _blocked(problems)
    rows, values = _listing(params, ctx)
    return {
        "values": {**values, "store": str(ctx.store_dir)},
        "rows": [*store_rows(ctx), *rows],
        "problems": [],
    }


def preview_check_imgw_archives(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the store that is compared and the files of the selection."""
    return _store_listing(params, ctx, write=False)


def preview_sync_imgw_store(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview the store that is written (series need ``pyarrow``) and the files."""
    return _store_listing(params, ctx, write=True)


def check_sync_imgw_store(params: dict[str, Any], ctx: ToolContext) -> CheckOutput:
    """Ask the servers what the synchronisation would download (a network step).

    The check twin of ``store sync`` lists the directories and sends ``HEAD``
    requests; nothing is downloaded or written.
    """
    (call,) = sync_imgw_store(params, ctx)
    plan = ctx.runner.check(call).get("result")
    if not isinstance(plan, Mapping):
        raise ToolError(ctx.tool, "internal_error", "the tool returned no plan")
    return plan_check_output(plan)


def preview_sync_imgw_store_by_plan(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the plan file: its store, what it lists and its age (read only).

    A plan of another store is refused here: the tool would refuse it after the
    confirmation.
    """
    problems = store_problems(ctx, write=True)
    if problems:
        return _blocked(problems)
    plan = json.loads(ctx.inputs["plan"].read_text(encoding="utf-8"))
    if not same_folder(plan.get("root"), ctx.store_dir):
        return _blocked(
            [
                {
                    "params": [],
                    "key": "arch_plan_other_store",
                    "args": {
                        "plan_store": str(plan.get("root")),
                        "store": str(ctx.store_dir),
                    },
                }
            ]
        )
    summary = plan_summary(plan)
    by_status = summary["by_status"]
    return {
        "values": {"store": str(ctx.store_dir), **summary},
        "rows": [
            *store_rows(ctx),
            {
                "key": "arch_plan",
                "args": {
                    "total": str(summary["items"]),
                    "to_download": str(summary["to_download"]),
                    "size": format_bytes(summary["bytes_to_download"]),
                    "current": str(by_status["current"]),
                    "checked_at": str(plan.get("checked_at", ""))[:16].replace(
                        "T", " "
                    ),
                },
            },
        ],
        "problems": [],
    }


def preview_export_imgw_archive(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the archives of the selection the store holds; none is a problem."""
    problems = store_problems(ctx, write=False)
    if problems:
        return _blocked(problems)
    archives = stored_archives(params, ctx)
    dataset = ctx.tool_value("dataset", params["dataset"])
    if not archives:
        reopened: list[str] = [name for name in ("dataset", "years") if name in params]
        if "years" in params:
            key, args = (
                "arch_nothing_to_export",
                {
                    "dataset": dataset,
                    "years": years_text(params["years"]),
                },
            )
        else:
            key, args = "arch_nothing_to_export_all", {"dataset": dataset}
        return _blocked([{"params": reopened, "key": key, "args": args}])
    expected = expected_archives(params, ctx)
    found = str(len(archives))
    if expected is None:
        row: PreviewRow = {
            "key": "arch_export_found",
            "args": {"found": found, "format": params["format"]},
        }
    else:
        row = {
            "key": "arch_export",
            "args": {
                "found": found,
                "total": str(expected),
                "format": params["format"],
            },
        }
    return {
        "values": {
            "store": str(ctx.store_dir),
            "found": len(archives),
            "expected": expected,
            "years": selected_years(params["years"]) if "years" in params else None,
        },
        "rows": [*store_rows(ctx), row],
        "problems": [],
    }


def preview_init_imgw_store(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Preview what initialising would do to the folder; a foreign one is refused.

    The tool creates a store only in a missing or empty folder (or finds its own):
    it never takes over a folder with other files.
    """
    folder = str(ctx.store_dir)
    state = imgw_store_state(ctx.store_dir)
    if state.state in ("foreign", "not_a_directory", "unreadable"):
        return _blocked(
            [{"params": [], "key": "store_not_imgw", "args": {"path": folder}}]
        )
    if state.state == "unsupported":
        return _blocked(
            [
                {
                    "params": [],
                    "key": "store_unsupported",
                    "args": {"path": folder, "schema": state.detail},
                }
            ]
        )
    return {
        "values": {"store": folder, "store_state": state.state},
        "rows": [*store_rows(ctx), {"key": f"arch_store_{state.state}", "args": {}}],
        "problems": [],
    }


def preview_inspect_imgw_store(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the store that is read (an omitted filter is shown by the plan)."""
    problems = store_problems(ctx, write=False)
    if problems:
        return _blocked(problems)
    return {
        "values": {"store": str(ctx.store_dir)},
        "rows": store_rows(ctx),
        "problems": [],
    }

"""Offline previews and the availability check of ``obserwator_archives`` operations.

``preview(params, ctx) -> PreviewOutput`` runs while planning, so it uses only the
offline half of the client (catalog lookups of the tool: file listings, the store's
state and entries) and the user's own files: no network, nothing is written. A
store that cannot serve the operation is a blocking problem of the plan, never a
silent initialisation. ``check_sync_obserwator_store`` is the one network step (the
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
from retman.stores import OBSERWATOR_MARKERS, ObserwatorRoot, obserwator_store_state
from retman.tools.obserwator.calls_archives import (
    archive_files_call,
    expected_archives,
    inspected_roots,
    selected_years,
    stored_archives,
    sync_obserwator_store,
    years_text,
)
from retman.tools.obserwator.folders import root_dir, same_folder
from retman.tools.obserwator.plans import (
    format_bytes,
    plan_check_output,
    plan_summary,
)
from retman.tools.obserwator.preview import (
    BOTH_ROOTS,
    ROOT_SETTINGS,
    blocking_problem,
    store_problem,
    store_problems,
    store_rows,
)


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
    raw = result if isinstance(result, list) else None
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
    """Preview the roots and the files of a selection.

    The raw root is compared or written; the data root too where the series are
    built (``write``).
    """
    kinds: tuple[ObserwatorRoot, ...] = BOTH_ROOTS if write else ("raw",)
    problems = store_problems(ctx, write=write, kinds=kinds)
    if problems:
        return _blocked(problems)
    rows, values = _listing(params, ctx)
    return {
        "values": {**values, "store": str(root_dir(ctx, "raw"))},
        "rows": [*store_rows(ctx, kinds), *rows],
        "problems": [],
    }


def preview_check_obserwator_archives(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the store that is compared and the files of the selection."""
    return _store_listing(params, ctx, write=False)


def preview_sync_obserwator_store(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the store that is written (series need ``pyarrow``) and the files."""
    return _store_listing(params, ctx, write=True)


def check_sync_obserwator_store(
    params: dict[str, Any], ctx: ToolContext
) -> CheckOutput:
    """Ask the servers what the synchronisation would download (a network step).

    The check twin of ``store sync`` lists the directories and sends ``HEAD``
    requests; nothing is downloaded or written.
    """
    sync, _ = sync_obserwator_store(params, ctx)
    plan = ctx.runner.check(sync).get("result")
    if not isinstance(plan, Mapping):
        raise ToolError(ctx.tool, "internal_error", "the tool returned no plan")
    return plan_check_output(plan)


def preview_sync_obserwator_store_by_plan(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the plan file: its raw root, what it lists and its age (read only).

    A plan of another raw root is refused here: the tool would refuse it after the
    confirmation.
    """
    problems = store_problems(ctx, write=True, kinds=("raw",))
    if problems:
        return _blocked(problems)
    raw = root_dir(ctx, "raw")
    plan = json.loads(ctx.inputs["plan"].read_text(encoding="utf-8"))
    if not same_folder(plan.get("root"), raw):
        return _blocked(
            [
                blocking_problem(
                    "arch_plan_other_store",
                    "validation_error",
                    "plan_other_store",
                    plan_store=plan.get("root"),
                    store=raw,
                )
            ]
        )
    summary = plan_summary(plan)
    by_status = summary["by_status"]
    return {
        "values": {"store": str(raw), **summary},
        "rows": [
            *store_rows(ctx, ("raw",)),
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


def preview_export_obserwator_archive(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the archives of the selection the raw root holds; none is a problem."""
    problems = store_problems(ctx, write=False, kinds=("raw",))
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
            "store": str(root_dir(ctx, "raw")),
            "found": len(archives),
            "expected": expected,
            "years": selected_years(params["years"]) if "years" in params else None,
        },
        "rows": [*store_rows(ctx, ("raw",)), row],
        "problems": [],
    }


def preview_init_obserwator_store(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview what initialising would do to each root; a foreign folder is refused.

    The tool writes the marker of the kind into a missing or empty folder and into
    one that has the layout of a root of the kind (after verifying it; a layout
    that is not a root's is refused when it runs), or finds its own marker. It
    never takes over a folder with other files or a root of the other kind, nor
    one whose marker it cannot read (``data_error``).
    """
    problems: list[PreviewProblem] = []
    rows: list[PreviewRow] = []
    values: dict[str, Any] = {}
    for kind in BOTH_ROOTS:
        folder = root_dir(ctx, kind)
        state = obserwator_store_state(folder, kind=kind)
        prefix = "raw_" if kind == "raw" else ""
        values[f"{prefix}store"] = str(folder)
        values[f"{prefix}store_state"] = state.state
        if state.state in ("foreign", "not_a_directory", "unsupported", "wrong_root"):
            problems.append(store_problem(state.state, ctx, kind, schema=state.detail))
        elif state.state == "unreadable":
            # ``store init`` reads the marker itself and ends with this error
            problems.append(
                blocking_problem(
                    "store_marker_unreadable",
                    "data_error",
                    "invalid_marker",
                    path=folder,
                    setting=ROOT_SETTINGS[kind],
                    marker=OBSERWATOR_MARKERS[kind],
                )
            )
        else:
            rows.extend(store_rows(ctx, (kind,)))
            rows.append({"key": f"arch_store_{state.state}", "args": {}})
    if problems:
        return _blocked(problems)
    return {"values": values, "rows": rows, "problems": []}


def preview_inspect_obserwator_store(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the roots that are read (an omitted filter is shown by the plan)."""
    kinds = tuple(inspected_roots(params, ctx))
    problems = store_problems(ctx, write=False, kinds=kinds)
    if problems:
        return _blocked(problems)
    return {
        "values": {"store": str(ctx.store_dir), "raw_store": str(root_dir(ctx, "raw"))},
        "rows": store_rows(ctx, kinds),
        "problems": [],
    }

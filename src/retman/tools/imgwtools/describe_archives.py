"""Result mappers of the ``imgw_archives`` operations (nos. 12-19).

``describe(operation, params, runs, ctx) -> HandlerOutput`` runs after the generic
runner has executed the builder's calls. It maps the tool's documents to the files
of the operation's kinds and to short ``values``; the licence terms and the
failures of a partial run come from ``base_output``.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError, ToolRun
from retman.registry.manifest import HandlerOutput
from retman.registry.operation import Operation
from retman.tools.imgwtools.calls_archives import expected_archives
from retman.tools.imgwtools.describe import (
    base_output,
    items_of,
    output_dir,
    result_of,
    run_of,
    write_report,
)
from retman.tools.imgwtools.plans import format_bytes, plan_summary

Runs = Sequence[tuple[CatalogCall, ToolRun]]


def _result(run: ToolRun) -> Mapping[str, Any]:
    result = result_of(run)
    return result if isinstance(result, Mapping) else {}


def _size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def describe_download_archives(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the downloaded files (as published), their size and what is missing."""
    output = base_output(operation, params, runs, ctx)
    (_, run) = runs[0]
    items = items_of(run)
    status = Counter(str(item.get("status")) for item in items)
    paths = [
        Path(str(item["path"]))
        for item in items
        if item.get("status") == "downloaded" and item.get("path")
    ]
    output["files"] = {"imgw_archive": paths}
    total = sum(_size(path) for path in paths)
    output["values"].update(
        files=len(paths),
        bytes=total,
        size=format_bytes(total),
        not_published=status["not_published"],
        failed=status["failed"],
    )
    if status["not_published"]:
        output["warnings"].insert(
            0,
            {
                "key": "arch_not_published",
                "args": {
                    "count": str(status["not_published"]),
                    "total": str(len(items)),
                },
            },
        )
    return output


def describe_check_archives(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the ``imgw-plan/1`` file the tool wrote and the counts of its items."""
    output = base_output(operation, params, runs, ctx)
    (call, run) = runs[0]
    output["files"] = {"imgw_plan": [Path(str(call.options["plan"]))]}
    summary = plan_summary(_result(run))
    output["values"].update(
        summary, size_to_download=format_bytes(summary["bytes_to_download"])
    )
    return output


def describe_sync_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe what the synchronisation did in the store: items, series, new versions.

    The store is not a result file (the audit keeps the paths); ``store_versions``
    lists the versions the run created, relative to the store.
    """
    output = base_output(operation, params, runs, ctx)
    (_, run) = runs[0]
    result = _result(run)
    items = [item for item in result.get("items", ()) if isinstance(item, Mapping)]
    series = [item for item in result.get("series", ()) if isinstance(item, Mapping)]
    by_status = Counter(str(item.get("status")) for item in items)
    made = [item for item in items if item.get("status") in ("created", "relabeled")]
    versions = [
        {"slot": item.get("slot"), "status": item["status"], "path": item["version"]}
        for item in made
        if item.get("version")
    ] + [
        {"slot": "series", "status": "created", "path": item["version"]}
        for item in series
        if item.get("status") == "created" and item.get("version")
    ]
    created = [item for item in made if item["status"] == "created"]
    series_by_status = Counter(str(item.get("status")) for item in series)
    output["values"].update(
        items=dict(by_status),
        series={
            state: series_by_status[state] for state in ("created", "reused", "failed")
        },
        created=len(created),
        series_created=series_by_status["created"],
        bytes=sum(
            _size(ctx.store_dir / str(item["version"]))
            for item in created
            if item.get("version")
        ),
        store_versions=versions,
    )
    return output


def _records(path: Path) -> int:
    """Return the records of an export: CSV data rows or JSON Lines."""
    with path.open("rb") as stream:
        lines = sum(1 for line in stream if line.strip())
    return max(lines - 1, 0) if path.suffix == ".csv" else lines


def describe_export_archive(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the exported record files; a selection held only in part is said.

    No calls means the store holds nothing of the selection (the preview blocks
    that plan, so it can only be a store that changed since): a failure.
    """
    if not runs:
        raise ToolError(
            ctx.tool, "not_found", "the store holds no archive of the selection"
        )
    output = base_output(operation, params, runs, ctx)
    paths = [Path(str(call.options["path"])) for call, _ in runs]
    output["files"] = {"archive_records": paths}
    output["values"].update(
        files=len(paths),
        format=str(runs[0][0].options["format"]),
        rows=sum(_records(path) for path in paths),
    )
    expected = expected_archives(params, ctx)
    if expected is not None and expected > len(paths):
        output["warnings"].insert(
            0,
            {
                "key": "arch_export_partial",
                "args": {"found": str(len(paths)), "total": str(expected)},
            },
        )
    return output


def describe_init_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the store folder the tool initialised (it is idempotent)."""
    output = base_output(operation, params, runs, ctx)
    result = _result(runs[0][1])
    output["values"].update(
        store=str(result.get("root") or ctx.store_dir), schema=result.get("schema")
    )
    return output


def describe_inspect_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the two documents as reports: the state and the entries by kind."""
    output = base_output(operation, params, runs, ctx)
    info, scan = run_of(runs, "store info"), run_of(runs, "store scan")
    folder = output_dir(ctx)
    output["files"] = {
        "imgw_report": [
            write_report(folder / "store_info.json", info.document),
            write_report(folder / "store_entries.json", scan.document),
        ]
    }
    state = _result(info)
    entries = items_of(scan)
    problems = [str(problem) for problem in state.get("problems") or ()]
    problems.extend(
        str(entry.get("problem") or entry.get("problem_code"))
        for entry in entries
        if entry.get("kind") == "problem"
    )
    output["values"].update(
        supported=state.get("supported"),
        contracts=state.get("contracts"),
        entries_by_kind=dict(Counter(str(entry.get("kind")) for entry in entries)),
        problems=problems,
        entries=len(entries),
        problem_count=len(problems),
    )
    return output

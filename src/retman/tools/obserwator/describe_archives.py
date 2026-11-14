"""Result mappers of the ``obserwator_archives`` operations (nos. 12-19).

``describe(operation, params, runs, ctx) -> HandlerOutput`` runs after the generic
runner has executed the builder's calls. It maps the tool's documents to the files
of the operation's kinds and to short ``values``; the licence terms and the
failures of a partial run come from ``base_output``.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError, ToolRun
from retman.registry.manifest import HandlerOutput
from retman.registry.operation import Operation
from retman.tools.obserwator.calls_archives import expected_archives
from retman.tools.obserwator.describe import (
    base_output,
    items_of,
    output_dir,
    result_of,
    run_of,
    set_files,
    write_report,
)
from retman.tools.obserwator.folders import root_dir
from retman.tools.obserwator.plans import format_bytes, plan_summary

Runs = Sequence[tuple[CatalogCall, ToolRun]]

# The file of the providers' lines that the tool writes beside the files of a plain
# download and lists in ``files[]`` with them (Nogat DEV-20.5)
ATTRIBUTION_FILE: Final = "ATTRIBUTION.txt"


def _result(run: ToolRun) -> Mapping[str, Any]:
    result = result_of(run)
    return result if isinstance(result, Mapping) else {}


def _size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def describe_download_archives(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the downloaded files (as published), their size and what is missing.

    The tool's ``ATTRIBUTION.txt`` is a file of its own kind, not an archive: it
    is neither counted nor sized with them.
    """
    output = base_output(operation, params, runs, ctx)
    (_, run) = runs[0]
    items = items_of(run)
    status = Counter(str(item.get("status")) for item in items)
    files: dict[str, list[Path]] = {"obserwator_archive": []}
    for file in run.files:
        kind = (
            "provider_attribution"
            if file.path.name == ATTRIBUTION_FILE
            else "obserwator_archive"
        )
        files.setdefault(kind, []).append(file.path)
    set_files(output, files)
    paths = files["obserwator_archive"]
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
    """Describe the ``obserwator-plan/1`` file the tool wrote and its item counts."""
    output = base_output(operation, params, runs, ctx)
    (call, run) = runs[0]
    output["files"] = {"obserwator_plan": [Path(str(call.options["plan"]))]}
    summary = plan_summary(_result(run))
    output["values"].update(
        summary, size_to_download=format_bytes(summary["bytes_to_download"])
    )
    return output


def describe_sync_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe what the synchronisation did: items, new versions, the series built.

    The roots are not result files (the audit keeps the paths); ``store_versions``
    lists the versions the run made: archives (``new`` and ``relabeled``, relative
    to the raw root) and a new series (its path in the data root). A sync by plan
    builds no series.
    """
    output = base_output(operation, params, runs, ctx)
    result = _result(run_of(runs, "store sync"))
    items = [item for item in result.get("items", ()) if isinstance(item, Mapping)]
    built = [_result(run) for call, run in runs if call.command == "series build"]
    by_status = Counter(str(item.get("status")) for item in items)
    made = [item for item in items if item.get("status") in ("new", "relabeled")]
    versions = [
        {"slot": item.get("slot"), "status": item["status"], "path": item["version"]}
        for item in made
        if item.get("version")
    ] + [
        {"slot": "series", "status": "new", "path": item["version"]}
        for item in built
        if item.get("status") == "new" and item.get("version")
    ]
    new = [item for item in made if item["status"] == "new"]
    series_by_status = Counter(str(item.get("status")) for item in built)
    raw = root_dir(ctx, "raw")
    output["values"].update(
        items=dict(by_status),
        series={
            state: series_by_status[state] for state in ("new", "unchanged", "failed")
        },
        new_versions=len(new),
        new_series=series_by_status["new"],
        bytes=sum(
            _size(raw / str(item["version"])) for item in new if item.get("version")
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
    paths = [file.path for _, run in runs for file in run.files]
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
    """Describe the two roots the tool initialised (it is idempotent)."""
    output = base_output(operation, params, runs, ctx)
    roots = {
        str(call.options["kind"]): _result(run)
        for call, run in runs
        if call.command == "store init"
    }
    raw, data = roots.get("raw", {}), roots.get("data", {})
    output["values"].update(
        store=str(data.get("root") or ctx.store_dir),
        raw_store=str(raw.get("root") or root_dir(ctx, "raw")),
        schema=data.get("schema"),
        raw_schema=raw.get("schema"),
    )
    return output


def describe_inspect_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the documents of each root as reports: its state and its entries.

    The data root's reports are ``store_info.json`` and ``store_entries.json``,
    the raw root's ``raw_store_info.json`` and ``raw_store_entries.json``.
    """
    output = base_output(operation, params, runs, ctx)
    folder = output_dir(ctx)
    raw = str(root_dir(ctx, "raw"))
    reports: list[Path] = []
    entries: list[dict[str, Any]] = []
    problems: list[str] = []
    contracts: object = None
    supported = True
    for call, run in runs:
        prefix = "raw_" if call.options.get("root") == raw else ""
        if call.command == "store info":
            state = _result(run)
            reports.append(
                write_report(folder / f"{prefix}store_info.json", run.document)
            )
            problems.extend(str(problem) for problem in state.get("problems") or ())
            supported = supported and bool(state.get("supported"))
            contracts = contracts or state.get("contracts")
        elif call.command == "store scan":
            found = items_of(run)
            reports.append(
                write_report(folder / f"{prefix}store_entries.json", run.document)
            )
            entries.extend(found)
            problems.extend(
                str(entry.get("problem") or entry.get("problem_code"))
                for entry in found
                if entry.get("kind") == "problem"
            )
    output["files"] = {"obserwator_report": reports}
    output["values"].update(
        supported=supported,
        contracts=contracts,
        entries_by_kind=dict(Counter(str(entry.get("kind")) for entry in entries)),
        problems=problems,
        entries=len(entries),
        problem_count=len(problems),
    )
    return output

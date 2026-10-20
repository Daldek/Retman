"""Result mappers of the ``imgw_projects`` operations (nos. 20-26).

The commands change or read the manifest ``imgw-project.json`` in the project
folder (and, downloading, the store), so most results are audit only: the files of
the result are the plan of a check and the report of a verification. The values say
which tasks exist, which are pinned and in what state.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolRun
from retman.registry.manifest import HandlerOutput
from retman.registry.operation import Operation
from retman.tools.imgwtools.describe import (
    base_output,
    output_dir,
    result_of,
    write_report,
)
from retman.tools.imgwtools.plans import format_bytes, plan_summary
from retman.tools.imgwtools.projects import MANIFEST_FILE

Runs = Sequence[tuple[CatalogCall, ToolRun]]

# Task states after a download that mean the task has pins
_PINNED = ("current", "content_match", "upgraded")
# States of a verified task that call for the user's attention
_ISSUES = ("missing", "changed", "failed", "cancelled")


def _result(run: ToolRun) -> Mapping[str, Any]:
    result = result_of(run)
    return result if isinstance(result, Mapping) else {}


def _file_results(result: Mapping[str, Any]) -> dict[str, int]:
    """The per-file outcomes of a project report, counted by status."""
    files = result.get("files") or ()
    return dict(
        Counter(str(item.get("status")) for item in files if isinstance(item, Mapping))
    )


def describe_project_manifest(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """The project after init, add, remove or set-store: its tasks and their pins."""
    output = base_output(operation, params, runs, ctx)
    project = _result(runs[0][1])
    tasks = [task for task in project.get("tasks") or () if isinstance(task, Mapping)]
    names = [str(task.get("name")) for task in tasks]
    output["values"].update(
        manifest=str(ctx.project_dir / MANIFEST_FILE),
        store=str(project.get("store_dir") or ctx.store_dir),
        tasks=names,
        task_count=len(names),
        pinned=[str(task.get("name")) for task in tasks if task.get("pinned_at")],
    )
    if "task_name" in params:
        output["values"]["task"] = params["task_name"]
    return output


def describe_download_project(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """The state of each task after the download and the outcome of each pinned file."""
    output = base_output(operation, params, runs, ctx)
    result = _result(runs[0][1])
    tasks = result.get("tasks")
    statuses = {str(name): str(state) for name, state in (tasks or {}).items()}
    pinned = [name for name, state in statuses.items() if state in _PINNED]
    output["values"].update(
        manifest=str(ctx.project_dir / MANIFEST_FILE),
        tasks=list(statuses),
        task_count=len(statuses),
        pinned=pinned,
        pinned_count=len(pinned),
        statuses=statuses,
        files=_file_results(result),
    )
    return output


def describe_check_project(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """The plan file the tool wrote, its counts and the state of each task."""
    output = base_output(operation, params, runs, ctx)
    call, run = runs[0]
    plan = _result(run)
    output["files"] = {"imgw_plan": [Path(str(call.options["plan"]))]}
    # Each task adds one ``project download`` action: "<task>: <what is missing>"
    statuses = {
        str(action["detail"]).partition(": ")[0]: str(action["status"])
        for action in plan.get("actions") or ()
        if isinstance(action, Mapping) and action.get("command") == "project download"
    }
    summary = plan_summary(plan)
    output["values"].update(
        summary,
        size_to_download=format_bytes(summary["bytes_to_download"]),
        manifest=str(ctx.project_dir / MANIFEST_FILE),
        tasks=list(statuses),
        task_count=len(statuses),
        statuses=statuses,
    )
    return output


def describe_verify_project(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """The report of ``project status`` or ``project verify`` and the state per task."""
    output = base_output(operation, params, runs, ctx)
    call, run = runs[0]
    name = f"{call.command.replace(' ', '_')}.json"
    output["files"] = {
        "imgw_report": [write_report(output_dir(ctx) / name, run.document)]
    }
    tasks = _result(run).get("tasks")
    statuses = {str(task): str(state) for task, state in (tasks or {}).items()}
    output["values"].update(
        manifest=str(ctx.project_dir / MANIFEST_FILE),
        tasks=list(statuses),
        task_count=len(statuses),
        tasks_issues=sum(state in _ISSUES for state in statuses.values()),
        tasks_ok=sum(state not in _ISSUES for state in statuses.values()),
        statuses=statuses,
        files=_file_results(_result(run)),
    )
    return output

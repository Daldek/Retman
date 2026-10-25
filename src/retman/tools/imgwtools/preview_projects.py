"""Offline previews and the availability check of the ``imgw_projects`` operations.

``preview(params, ctx) -> PreviewOutput`` runs while planning: it reads the manifest
``imgw-project.json`` and the user's files with the standard library and asks the
tool only for offline lookups. No network, nothing is written. What the user must
see before confirming is shown as rows: the manifest (the only file outside the
result folder these operations write), the store, the tasks an omitted ``tasks``
stands for. A problem that is no answer of the user (no manifest, another store,
an empty project) blocks the plan; one that names parameters asks them again.
``check_download_imgw_project`` is the one network step (separate consent): the
freshness plan of the project's tasks.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.registry.manifest import (
    CheckItem,
    CheckOutput,
    PreviewOutput,
    PreviewProblem,
    PreviewRow,
)
from retman.stores import imgw_store_state
from retman.tools.imgwtools.calls_projects import download_imgw_project
from retman.tools.imgwtools.folders import inside, same_folder
from retman.tools.imgwtools.params import DATASETS
from retman.tools.imgwtools.plans import plan_check_output, plan_items
from retman.tools.imgwtools.preview import store_problems, store_rows
from retman.tools.imgwtools.projects import Manifest, load_manifest

_GEOJSON_TYPES = ("Polygon", "MultiPolygon", "Feature", "FeatureCollection")
CheckStatus = Literal["available", "partial", "unavailable", "unknown"]

# The state of a task in the check plan -> the key of its line in the report
_STATE_KEYS = {
    "missing": "proj_state_missing",
    "newer": "proj_state_newer",
    "current": "proj_state_current",
    "unverifiable": "proj_state_unverifiable",
    "check_failed": "proj_state_failed",
}


def _problem(key: str, *names: str, **args: str) -> PreviewProblem:
    """Build a problem of the plan; without ``names`` it blocks (nothing to answer)."""
    return {"params": list(names), "key": key, "args": args}


def _outcome(
    problems: list[PreviewProblem],
    rows: list[PreviewRow],
    values: dict[str, Any],
) -> PreviewOutput:
    """Return the preview, or only the problems when there are any.

    Blocking problems (no parameter to ask again) come first: asking a parameter
    again would be pointless while the plan cannot be confirmed anyway.
    """
    if problems:
        blocking = [problem for problem in problems if not problem["params"]]
        return {"values": {}, "rows": [], "problems": blocking or problems}
    return {"values": values, "rows": rows, "problems": []}


def _manifest_problems(manifest: Manifest) -> list[PreviewProblem]:
    if manifest.state == "missing":
        return [_problem("proj_manifest_missing", path=str(manifest.path))]
    if manifest.state == "invalid":
        return [
            _problem(
                "proj_manifest_invalid", path=str(manifest.path), detail=manifest.detail
            )
        ]
    return []


def _tasks_problems(
    params: Mapping[str, Any], manifest: Manifest
) -> list[PreviewProblem]:
    """Return the task problems: an empty project, or a named task that is missing."""
    if not manifest.tasks:
        return [_problem("proj_no_tasks", path=str(manifest.path))]
    unknown = [name for name in params.get("tasks", ()) if name not in manifest.names]
    if unknown:
        return [
            _problem(
                "proj_tasks_unknown",
                "tasks",
                names=", ".join(unknown),
                known=", ".join(manifest.names),
            )
        ]
    return []


def _manifest_row(kind: str, manifest: Manifest) -> PreviewRow:
    """Return ``new``, ``exists``, ``write`` (changed by the operation) or ``read``."""
    return {"key": f"proj_manifest_{kind}", "args": {"path": str(manifest.path)}}


def _tasks_row(manifest: Manifest) -> PreviewRow:
    """Return the row of the tasks the project holds (``tasks`` says which apply)."""
    return {
        "key": "proj_tasks",
        "args": {"count": str(len(manifest.tasks)), "names": ", ".join(manifest.names)},
    }


def _project_store_row(ctx: ToolContext, manifest: Manifest) -> PreviewRow:
    """Return the row of the store the manifest points at; read-only runs use it."""
    store = str(manifest.store)
    if manifest.store is not None and same_folder(manifest.store, ctx.store_dir):
        return {"key": "proj_store", "args": {"path": store}}
    return {
        "key": "proj_store_other",
        "args": {"path": store, "configured": str(ctx.store_dir)},
    }


def _other_store(ctx: ToolContext, manifest: Manifest) -> list[PreviewProblem]:
    """Return a problem when the project does not use the store the operation writes."""
    if manifest.store is not None and not same_folder(manifest.store, ctx.store_dir):
        return [
            _problem(
                "proj_other_store",
                manifest_store=str(manifest.store),
                store=str(ctx.store_dir),
            )
        ]
    return []


def _refused_store(ctx: ToolContext) -> list[PreviewProblem]:
    """Return a problem when the folder is one the tool will not use as a store.

    A project takes a store, a missing folder and an empty one (the store is made
    later). The tool refuses a layout without its marker and a folder that holds only
    the state file of its REST server, which ``store init`` would turn into a store.
    """
    folder = str(ctx.store_dir)
    state = imgw_store_state(ctx.store_dir)
    if state.state in ("foreign", "not_a_directory", "unreadable"):
        return [_problem("store_not_imgw", path=folder)]
    if state.state == "unsupported":
        return [_problem("store_unsupported", path=folder, schema=state.detail)]
    if state.state == "no_marker":
        return [_problem("store_no_marker", path=folder)]
    if state.state == "empty" and any(ctx.store_dir.iterdir()):
        return [_problem("store_missing", path=folder)]
    return []


# --- 20: init ---------------------------------------------------------------


def preview_init_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest to create, the store it will point at and what exists."""
    manifest = load_manifest(ctx.project_dir)
    problems = _refused_store(ctx)
    if inside(ctx.store_dir, ctx.project_dir):
        problems.append(
            _problem(
                "proj_inside_store",
                project=str(ctx.project_dir),
                store=str(ctx.store_dir),
            )
        )
    # A missing manifest is what the operation creates; a broken one is not replaced
    if manifest.state == "invalid":
        problems += _manifest_problems(manifest)
    else:
        problems += _other_store(ctx, manifest)
    kind = "exists" if manifest.state == "ready" else "new"
    return _outcome(
        problems,
        [*store_rows(ctx), _manifest_row(kind, manifest)],
        {"manifest": str(manifest.path), "store": str(ctx.store_dir), "state": kind},
    )


# --- 21: add a task ---------------------------------------------------------


def _symlink_below(folder: Path, path: Path) -> bool:
    """Whether a part of ``path`` below ``folder`` (lexically) is a symbolic link."""
    try:
        relative = path.relative_to(folder)
    except ValueError:
        return False
    current = folder
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _area_problems(
    params: Mapping[str, Any], ctx: ToolContext, manifest: Manifest
) -> list[PreviewProblem]:
    """Check the GeoJSON file that selects stations and the catalog to be read."""
    given = str(params["area_file"])
    path = Path(given)
    absolute = path if path.is_absolute() else ctx.project_dir / path
    if not absolute.is_file():
        return [_problem("proj_area_missing", "area_file", file=given)]
    # The tool keeps the file by a relative path and refuses ``..`` and symbolic links
    if (
        ".." in path.parts
        or _symlink_below(ctx.project_dir, absolute)
        or not inside(ctx.project_dir, absolute)
    ):
        return [
            _problem(
                "proj_area_outside",
                "area_file",
                file=given,
                project=str(ctx.project_dir),
            )
        ]
    try:
        document = json.loads(absolute.read_text(encoding="utf-8"))
        valid = isinstance(document, dict) and document.get("type") in _GEOJSON_TYPES
    except (OSError, ValueError):
        valid = False
    if not valid:
        return [_problem("proj_area_invalid", "area_file", file=given)]
    problems = _other_store(ctx, manifest) or store_problems(ctx, write=False)
    if problems:
        return problems
    provider = ctx.option_meta("dataset", params["dataset"])["provider"]
    catalog = ctx.client.lookup(
        CatalogCall("store scan", {"kind": "catalog", "provider": provider})
    ).get("result")
    entries = catalog.get("items") if isinstance(catalog, Mapping) else None
    return [] if entries else [_problem("proj_catalog_missing", provider=provider)]


def preview_add_imgw_project_task(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest that gets the task and what the omitted parameters mean."""
    manifest = load_manifest(ctx.project_dir)
    problems = _manifest_problems(manifest)
    if problems:
        return _outcome(problems, [], {})
    if params["task_name"] in manifest.names:
        problems.append(
            _problem(
                "proj_task_exists",
                "task_name",
                name=params["task_name"],
                tasks=", ".join(manifest.names),
            )
        )
    rows = [_manifest_row("write", manifest)]
    if params["task"] == "series":
        first_year = DATASETS[params["dataset"]]["first_year"]
        if first_year is not None and params["period"]["first"] < first_year:
            problems.append(
                _problem(
                    "proj_period_early",
                    "period",
                    dataset=ctx.tool_value("dataset", params["dataset"]),
                    first_year=str(first_year),
                )
            )
        if "area_file" in params:
            problems += _area_problems(params, ctx, manifest)
        if "year_type" not in params:
            rows.append({"key": "proj_year_type_fixed", "args": {}})
    return _outcome(
        problems, rows, {"manifest": str(manifest.path), "tasks": manifest.names}
    )


# --- 22: download -----------------------------------------------------------


def preview_download_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the tasks, the pins restored or changed and the store that is written.

    The tool initialises a missing store by itself when downloading, so a store that
    is not initialised blocks the plan: that is ``init_imgw_store``'s decision.
    """
    manifest = load_manifest(ctx.project_dir)
    problems = _manifest_problems(manifest)
    if not problems:
        problems = [
            *_tasks_problems(params, manifest),
            *(_other_store(ctx, manifest) or store_problems(ctx, write=True)),
        ]
    selected = [
        task
        for task in manifest.tasks
        if "tasks" not in params or task.name in params["tasks"]
    ]
    pinned = sum(task.pinned for task in selected)
    if params.get("update") == "upgrade":
        update: PreviewRow = {
            "key": "proj_download_upgrade",
            "args": {"count": str(len(selected))},
        }
    else:
        update = {
            "key": "proj_download_pinned",
            "args": {"new": str(len(selected) - pinned), "pinned": str(pinned)},
        }
    return _outcome(
        problems,
        [
            *store_rows(ctx),
            _manifest_row("write", manifest),
            _tasks_row(manifest),
            update,
        ],
        {
            "manifest": str(manifest.path),
            "store": str(ctx.store_dir),
            "tasks": [task.name for task in selected],
            "pinned": [task.name for task in selected if task.pinned],
        },
    )


def check_download_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> CheckOutput:
    """Ask the servers about the project's tasks (a network step; nothing is changed).

    The check twin of ``project download`` lists the server directories and sends
    ``HEAD`` requests for the archives of the tasks; the tool reports each task as
    ``missing`` (nothing pinned yet, or pins missing in the store), ``newer`` (newer
    data exist; only ``upgrade`` changes pins), ``current``, ``unverifiable`` or
    ``check_failed``.
    """
    (call,) = download_imgw_project(params, ctx)
    plan = ctx.runner.check(call).get("result")
    if not isinstance(plan, Mapping):
        raise ToolError(ctx.tool, "internal_error", "the tool returned no plan")
    tasks: list[CheckItem] = []
    failed = 0
    for action in plan.get("actions") or ():
        if (
            not isinstance(action, Mapping)
            or action.get("command") != "project download"
        ):
            continue
        name, _, detail = str(action.get("detail")).partition(": ")
        state = str(action.get("status"))
        failed += state == "check_failed"
        tasks.append(
            {
                "key": _STATE_KEYS.get(state, "proj_state_unverifiable"),
                "args": {"name": name, "detail": detail},
            }
        )
    archives = plan_check_output(plan) if plan_items(plan) else None
    status: CheckStatus
    if not tasks or failed == len(tasks):
        status = "unknown"
    elif archives is not None and archives["status"] == "unavailable":
        status = "unavailable"
    elif failed or (archives is not None and archives["status"] != "available"):
        status = "partial"
    else:
        status = "available"
    return {
        "status": status,
        "items": [*tasks, *(archives["items"] if archives else [])],
    }


# --- 23, 24: read-only ------------------------------------------------------


def _read_only(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    manifest = load_manifest(ctx.project_dir)
    problems = _manifest_problems(manifest)
    if not problems:
        problems = _tasks_problems(params, manifest)
    return _outcome(
        problems,
        [
            _manifest_row("read", manifest),
            _project_store_row(ctx, manifest),
            _tasks_row(manifest),
        ],
        {
            "manifest": str(manifest.path),
            "store": str(manifest.store),
            "tasks": params.get("tasks", manifest.names),
        },
    )


def preview_check_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest and store that are read and the tasks that are checked."""
    return _read_only(params, ctx)


def preview_verify_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest and store that are read and the tasks that are verified."""
    return _read_only(params, ctx)


# --- 25, 26: manifest edits -------------------------------------------------


def preview_remove_imgw_project_task(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest that loses the task; a missing task is asked again."""
    manifest = load_manifest(ctx.project_dir)
    problems = _manifest_problems(manifest)
    name = params["task_name"]
    task = next((task for task in manifest.tasks if task.name == name), None)
    if not problems and task is None:
        problems = [
            _problem(
                "proj_task_missing",
                "task_name",
                name=name,
                tasks=", ".join(manifest.names) or "—",
            )
        ]
    rows = [_manifest_row("write", manifest)]
    if task is not None and task.pinned:
        rows.append({"key": "proj_task_pinned", "args": {"name": name}})
    return _outcome(
        problems,
        rows,
        {
            "manifest": str(manifest.path),
            "pinned": task.pinned if task is not None else False,
        },
    )


def preview_set_imgw_project_store(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Preview the manifest that is changed and the configured store it points at."""
    manifest = load_manifest(ctx.project_dir)
    problems = _manifest_problems(manifest) or _refused_store(ctx)
    rows = [*store_rows(ctx), _manifest_row("write", manifest)]
    if manifest.store is not None and same_folder(manifest.store, ctx.store_dir):
        rows.append({"key": "proj_store_same", "args": {"path": str(ctx.store_dir)}})
    return _outcome(
        problems,
        rows,
        {
            "manifest": str(manifest.path),
            "store": str(ctx.store_dir),
            "previous_store": str(manifest.store),
        },
    )

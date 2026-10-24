"""Call builders of the ``imgw_projects`` operations (nos. 20-26).

The project is the folder Retman runs in (``ctx.project_dir``) and its store the
configured one (``ctx.store_dir``); both are passed explicitly, as the project
commands take them. The manifest ``imgw-project.json`` is written by the tool
alone. Nothing here touches the file system.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext
from retman.tools.imgwtools.calls_archives import PLAN_FILE, selected_years

# The tool rejects a task option as ``options.<name>`` (the client names it so) and
# the user's answer it was made from is asked again. What the extractors could not
# know offline, e.g. the variables of a dataset chosen after they were read, is
# thus a question and not drift. Options the manifest fixes are not listed.
_SERIES_ROUTES = {
    "name": "task_name",
    "geometry": "area_file",
    "options.dataset": "dataset",
    "options.stations": "stations",
    "options.years": "period",
    "options.year_type": "year_type",
    "options.variables": "variables",
}
_PMAXTP_ROUTES = {
    "name": "task_name",
    "options.latitude": "point",
    "options.longitude": "point",
    "options.method": "method",
}


def _project(ctx: ToolContext) -> dict[str, object]:
    return {"project_dir": str(ctx.project_dir)}


def _tasks(params: Mapping[str, Any]) -> dict[str, object]:
    """Return the ``tasks`` option when the user named tasks; unset means every task."""
    return {"tasks": list(params["tasks"])} if "tasks" in params else {}


def project_relative(value: str, project_dir: Path) -> str:
    """Return a path inside the project folder as the tool wants it: relative, POSIX.

    A path outside the folder is returned as typed: the preview refuses it and the
    tool would too, so it is never run.
    """
    path = Path(value)
    absolute = path if path.is_absolute() else project_dir / path
    try:
        return (
            Path(os.path.normpath(absolute))
            .relative_to(os.path.normpath(project_dir))
            .as_posix()
        )
    except ValueError:
        return value


def init_imgw_project(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``project init``: a manifest without tasks, pointing at the configured store."""
    return [
        CatalogCall("project init", {**_project(ctx), "store_dir": str(ctx.store_dir)})
    ]


def _series_task(params: Mapping[str, Any], ctx: ToolContext) -> dict[str, object]:
    """Return the options of a ``series select`` task: whole years in a year type.

    A semi-annual series exists only in hydrological years, which the manifest does
    not ask for; the dataset's own numbering is then the year type.
    """
    meta = ctx.option_meta("dataset", params["dataset"])
    options: dict[str, object] = {
        "dataset": ctx.tool_value("dataset", params["dataset"]),
        "years": selected_years(params["period"]),
        "year_type": params.get("year_type", meta["numbering"]),
    }
    if "stations" in params:
        options["stations"] = [station["code"] for station in params["stations"]]
    if "variables" in params:
        options["variables"] = list(params["variables"])
    return options


def add_imgw_project_task(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``project add``: a station series selection or a PMAXTP cell as a task.

    The task is only recorded in the manifest, unpinned; ``project download`` runs
    it. A selection by area passes the GeoJSON file (inside the project folder), and
    the tool then adds the stations of the catalog that lie in it.
    """
    base = {**_project(ctx), "name": params["task_name"]}
    if params["task"] == "pmaxtp":
        point = params["point"]
        options: dict[str, object] = {
            "latitude": point["latitude"],
            "longitude": point["longitude"],
            "method": ctx.tool_value("method", params["method"]),
        }
        return [
            CatalogCall(
                "project add",
                {**base, "command": "pmaxtp sync", "options": options},
                params=_PMAXTP_ROUTES,
            )
        ]
    call: dict[str, object] = {
        **base,
        "command": "series select",
        "options": _series_task(params, ctx),
    }
    if "area_file" in params:
        call["geometry"] = project_relative(params["area_file"], ctx.project_dir)
    return [CatalogCall("project add", call, params=_SERIES_ROUTES)]


def download_imgw_project(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``project download``: restore the pins (``pinned``) or re-pin (``upgrade``)."""
    return [
        CatalogCall(
            "project download",
            {
                **_project(ctx),
                **_tasks(params),
                "update": ctx.tool_value("update", params["update"]),
            },
        )
    ]


def check_imgw_project(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``project check``; the tool writes the ``imgw-plan/1`` file into the result."""
    options = {**_project(ctx), **_tasks(params)}
    if ctx.output_dir is not None:
        options["plan"] = str(ctx.output_dir / PLAN_FILE)
    return [CatalogCall("project check", options, kind="imgw_plan")]


def verify_imgw_project(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``project status`` (existence and sidecars) or ``project verify`` (SHA-256)."""
    command = f"project {ctx.tool_value('depth', params['depth'])}"
    return [
        CatalogCall(command, {**_project(ctx), **_tasks(params)}, kind="imgw_report")
    ]


def remove_imgw_project_task(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``project remove``: the task leaves the manifest, the store is untouched."""
    return [
        CatalogCall(
            "project remove",
            {**_project(ctx), "name": params["task_name"]},
            params={"name": "task_name"},
        )
    ]


def set_imgw_project_store(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``project set-store``: point the project at the configured store.

    The tool first verifies the SHA-256 of every pinned file in the new store.
    """
    return [
        CatalogCall(
            "project set-store", {**_project(ctx), "store_dir": str(ctx.store_dir)}
        )
    ]

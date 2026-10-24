"""The ``imgw_projects`` operations: data projects pinned by a manifest.

Seven operations (research-imgw 2 and 5.3, nos. 20-26) over the project commands of
IMGWTools. The project is the folder Retman runs in, its manifest
``imgw-project.json`` is written by the tool alone, and its store is the configured
one. The manifest of the tool lists ``OPERATIONS`` among its own; nothing here
imports the tool.
"""

from retman.registry.manifest import OperationSpec, ParamSpec
from retman.tools.imgwtools.params import SERIES_DATASETS, dataset_param

_CALLS = "retman.tools.imgwtools.calls_projects"
_DESCRIBE = "retman.tools.imgwtools.describe_projects"
_PREVIEW = "retman.tools.imgwtools.preview_projects"
CATEGORY = "imgw_projects"

# A semi-annual series exists only in hydrological years, so the year type is not
# asked for it (the tool refuses ``calendar``)
_FREE_YEAR_TYPE = [key for key in SERIES_DATASETS if key != "pl_hydro_semiannual"]


def _task_name() -> ParamSpec:
    return {
        "name": "task_name",
        "type": "free",
        "extractor": "identifier",
        "required": True,
    }


def _tasks() -> ParamSpec:
    """Build the ``tasks`` parameter: the tasks to work on; omitted, every task."""
    return {
        "name": "tasks",
        "type": "free",
        "extractor": "identifier",
        "multiple": True,
    }


_SERIES_TASK: dict[str, list[str]] = {"task": ["series"]}

_ADD_TASK_PARAMS: list[ParamSpec] = [
    {
        "name": "task",
        "type": "choice",
        "options": ["series", "pmaxtp"],
        "required": True,
    },
    _task_name(),
    {**dataset_param(SERIES_DATASETS), "depends_on": _SERIES_TASK},
    {
        "name": "selection",
        "type": "choice",
        "options": ["stations", "area"],
        "required": True,
        "depends_on": _SERIES_TASK,
    },
    {
        "name": "stations",
        "type": "free",
        "extractor": "station",
        "multiple": True,
        "required": True,
        "depends_on": {"task": ["series"], "selection": ["stations"]},
    },
    {
        "name": "area_file",
        "type": "free",
        "extractor": "path",
        "required": True,
        "depends_on": {"task": ["series"], "selection": ["area"]},
    },
    {
        "name": "period",
        "type": "free",
        "extractor": "period",
        # The tool selects whole years of a year type, so dates are not accepted
        "accepts": ["years"],
        "required": True,
        "depends_on": _SERIES_TASK,
    },
    {
        "name": "year_type",
        "type": "choice",
        "options": ["hydrological", "calendar"],
        "extractor": "year_type",
        "option_values": {"hydrological": "hydrological", "calendar": "calendar"},
        "required": True,
        "depends_on": {"task": ["series"], "dataset": _FREE_YEAR_TYPE},
    },
    {
        "name": "variables",
        "type": "free",
        "extractor": "variables",
        "multiple": True,
        "depends_on": _SERIES_TASK,
    },
    {
        "name": "point",
        "type": "free",
        "extractor": "point",
        "required": True,
        "depends_on": {"task": ["pmaxtp"]},
    },
    {
        "name": "method",
        "type": "choice",
        "options": ["pot", "amp"],
        "tool_values": {"pot": "POT", "amp": "AMP"},
        "required": True,
        "depends_on": {"task": ["pmaxtp"]},
    },
]

OPERATIONS: list[OperationSpec] = [
    {
        "id": "init_imgw_project",
        "category": CATEGORY,
        "description": "Create the IMGW data project (manifest imgw-project.json) "
        "in the project folder, pointing at the configured store",
        "inputs": [],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:init_imgw_project",
        "commands": ["project init"],
        "describe": f"{_DESCRIBE}:describe_project_manifest",
        "preview": f"{_PREVIEW}:preview_init_imgw_project",
    },
    {
        "id": "add_imgw_project_task",
        "category": CATEGORY,
        "description": "Add a task to the IMGW data project: the series of "
        "stations for years, or a PMAXTP cell of a point",
        "inputs": [],
        "outputs": [],
        "params": _ADD_TASK_PARAMS,
        "calls": f"{_CALLS}:add_imgw_project_task",
        "commands": ["project add"],
        "describe": f"{_DESCRIBE}:describe_project_manifest",
        "preview": f"{_PREVIEW}:preview_add_imgw_project_task",
    },
    {
        "id": "download_imgw_project",
        "category": CATEGORY,
        "description": "Download the data of the project tasks into the store "
        "and pin the versions in the manifest",
        "inputs": [],
        "outputs": [],
        "params": [
            {
                "name": "update",
                "type": "choice",
                "options": ["pinned", "upgrade"],
                "required": True,
            },
            _tasks(),
        ],
        "calls": f"{_CALLS}:download_imgw_project",
        "commands": ["project download"],
        "describe": f"{_DESCRIBE}:describe_download_project",
        "preview": f"{_PREVIEW}:preview_download_imgw_project",
        "check": f"{_PREVIEW}:check_download_imgw_project",
    },
    {
        "id": "check_imgw_project",
        "category": CATEGORY,
        "description": "Check whether the data of the project tasks are up to "
        "date on the servers, without downloading; saves the plan",
        "inputs": [],
        "outputs": ["imgw_plan"],
        "params": [_tasks()],
        "calls": f"{_CALLS}:check_imgw_project",
        "commands": ["project check"],
        "describe": f"{_DESCRIBE}:describe_check_project",
        "preview": f"{_PREVIEW}:preview_check_imgw_project",
    },
    {
        "id": "verify_imgw_project",
        "category": CATEGORY,
        "description": "Verify the pinned files of the project: their state or "
        "their SHA-256 sums, offline",
        "inputs": [],
        "outputs": ["imgw_report"],
        "params": [
            {
                "name": "depth",
                "type": "choice",
                "options": ["status", "verify"],
                "required": True,
            },
            _tasks(),
        ],
        "calls": f"{_CALLS}:verify_imgw_project",
        "commands": ["project status", "project verify"],
        "describe": f"{_DESCRIBE}:describe_verify_project",
        "preview": f"{_PREVIEW}:preview_verify_imgw_project",
    },
    {
        "id": "remove_imgw_project_task",
        "category": CATEGORY,
        "description": "Remove a task from the IMGW data project manifest "
        "(the versions in the store stay)",
        "inputs": [],
        "outputs": [],
        "params": [_task_name()],
        "calls": f"{_CALLS}:remove_imgw_project_task",
        "commands": ["project remove"],
        "describe": f"{_DESCRIBE}:describe_project_manifest",
        "preview": f"{_PREVIEW}:preview_remove_imgw_project_task",
    },
    {
        "id": "set_imgw_project_store",
        "category": CATEGORY,
        "description": "Point the IMGW data project at the configured store, "
        "after verifying the pinned files in it",
        "inputs": [],
        "outputs": [],
        "params": [],
        "calls": f"{_CALLS}:set_imgw_project_store",
        "commands": ["project set-store"],
        "describe": f"{_DESCRIBE}:describe_project_manifest",
        "preview": f"{_PREVIEW}:preview_set_imgw_project_store",
    },
]

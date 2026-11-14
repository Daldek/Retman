"""Offline plan review of the Obserwator operations (``preview`` hooks).

Everything here runs while planning, so it uses only the offline half of the
client (``ctx.client.lookup``) and the user's own files: no network, nothing is
written (PRD N-12). A preview adds rows to the plan (what the store holds, how
many archives would be fetched) and reports problems: those that name
parameters are asked again, those without parameters block the plan (a store
that does not exist is a matter of the configuration, not of an answer). The
shared helpers (``store_rows``, ``store_problems``) are also used by the
operations of the archive module.
"""

import csv
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext, ToolError
from retman.exceptions import ErrorCode
from retman.extractors.dates import period_dates
from retman.registry.manifest import PreviewOutput, PreviewProblem, PreviewRow
from retman.stores import (
    OBSERWATOR_MARKERS,
    OBSERWATOR_REFERENCE_FILE,
    OBSERWATOR_SCHEMAS,
    ObserwatorRoot,
    obserwator_store_state,
    tool_installed,
)
from retman.tools.obserwator.calls import (
    build_obserwator_station_catalog,
    export_station_series,
    find_obserwator_stations,
)
from retman.tools.obserwator.describe import document_items
from retman.tools.obserwator.folders import root_dir

_LOCATION_COLUMNS = ("station_code", "latitude", "longitude")


def _row(key: str, **args: object) -> PreviewRow:
    return {"key": key, "args": {name: str(value) for name, value in args.items()}}


def _problem(key: str, params: list[str], **args: object) -> PreviewProblem:
    return {
        "params": params,
        "key": key,
        "args": {name: str(value) for name, value in args.items()},
    }


def blocking_problem(
    key: str, code: ErrorCode, reason: str, **args: object
) -> PreviewProblem:
    """Build a problem no answer solves; planning ends with ``code``/``reason``."""
    return {**_problem(key, [], **args), "code": code, "reason": reason}


# The problem of the plan and the reason of its ``store_unavailable`` (the reasons of
# ``retman doctor check``) for each state of a root folder Obserwator cannot use
STORE_PROBLEMS: dict[str, tuple[str, str]] = {
    "missing": ("store_missing", "not_initialised"),
    "empty": ("store_missing", "not_initialised"),
    "no_marker": ("store_no_marker", "no_marker"),
    "unreadable": ("store_marker_unreadable", "marker_unreadable"),
    "unsupported": ("store_unsupported", "marker_unsupported"),
    "wrong_root": ("store_wrong_root", "wrong_root"),
    "foreign": ("store_not_obserwator", "foreign_folder"),
    "not_a_directory": ("store_not_obserwator", "not_a_directory"),
}
# The setting that names each root (ADR-034)
ROOT_SETTINGS: dict[ObserwatorRoot, str] = {
    "data": "store_dir",
    "raw": "raw_store_dir",
}


def store_problem(
    state: str, ctx: ToolContext, kind: ObserwatorRoot = "data", **args: object
) -> PreviewProblem:
    """Build the blocking problem of the root of ``kind`` in ``state``."""
    key, reason = STORE_PROBLEMS[state]
    return blocking_problem(
        key,
        "store_unavailable",
        reason,
        path=root_dir(ctx, kind),
        setting=ROOT_SETTINGS[kind],
        marker=OBSERWATOR_MARKERS[kind],
        **args,
    )


def _output(
    rows: list[PreviewRow] | None = None,
    problems: list[PreviewProblem] | None = None,
    values: dict[str, Any] | None = None,
) -> PreviewOutput:
    return {"values": values or {}, "rows": rows or [], "problems": problems or []}


_ROW_KEYS: dict[ObserwatorRoot, str] = {"data": "store", "raw": "raw_store"}
# The roots of an operation that reads the raw root and writes the data root
BOTH_ROOTS: tuple[ObserwatorRoot, ...] = ("raw", "data")


def store_rows(
    ctx: ToolContext, kinds: tuple[ObserwatorRoot, ...] = ("data",)
) -> list[PreviewRow]:
    """Return the plan rows naming the root folders the operation reads or writes."""
    return [_row(_ROW_KEYS[kind], path=root_dir(ctx, kind)) for kind in kinds]


def _root_problem(ctx: ToolContext, kind: ObserwatorRoot) -> PreviewProblem | None:
    """Why the root of ``kind`` cannot serve an operation, or ``None``.

    The state comes from the tool's own ``store info`` of the folder (an offline
    lookup that never fails on a missing folder and reads a root of either kind);
    what it cannot tell, such as an empty folder, a layout without its marker or a
    root of the other kind, Retman reads from the folder by the tool's rules.
    """
    folder = root_dir(ctx, kind)
    document = ctx.client.lookup(CatalogCall("store info", {"root": str(folder)}))
    result: Any = document.get("result")
    info: dict[str, Any] = result if isinstance(result, dict) else {}
    if not info.get("exists"):
        return store_problem("missing", ctx, kind)
    if info.get("supported") and info.get("store_schema") == OBSERWATOR_SCHEMAS[kind]:
        return None
    found = obserwator_store_state(folder, kind=kind)
    if found.state == "unsupported":
        return store_problem("unsupported", ctx, kind, schema=found.detail)
    state = found.state
    if state not in ("empty", "no_marker", "unreadable", "wrong_root"):
        # Any other file means a folder the tool refuses to turn into a root
        state = "foreign"
    return store_problem(state, ctx, kind)


def store_problems(
    ctx: ToolContext, *, write: bool, kinds: tuple[ObserwatorRoot, ...] = ("data",)
) -> list[PreviewProblem]:
    """Why the configured roots of ``kinds`` cannot serve the operation; empty if fine.

    Every problem is blocking and has no parameter the user could answer again: it
    is a matter of the configuration (``retman config init``,
    ``[retman.tools.obserwator] store_dir`` and ``raw_store_dir``). ``write``
    operations also need ``pyarrow`` (Parquet series), which the tool imports on
    demand.
    """
    problems = [
        problem for kind in kinds if (problem := _root_problem(ctx, kind)) is not None
    ]
    if write and not problems and not tool_installed("pyarrow"):
        problems.append(
            blocking_problem("pyarrow_missing", "missing_dependency", "pyarrow_missing")
        )
    return problems


def _unknown_station(err: ToolError) -> bool:
    """Tell whether the tool says a station is not in the series of the dataset."""
    return err.tool_code == "validation_error" and err.option in ("station", "stations")


# --- operations 1-3: catalog -----------------------------------------------------


def preview_find_obserwator_stations(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 1: from the store, how many stations of the catalog match."""
    if params["data_source"] != "store":
        return _output()
    problems = store_problems(ctx, write=False)
    if problems:
        return _output(problems=problems)
    (call, *_) = find_obserwator_stations(params, ctx)
    try:
        matches = len(document_items(ctx.client.lookup(call)))
    except ToolError as err:
        if err.tool_code in ("not_found", "store_unavailable"):
            return _output(
                problems=[_problem("station_catalog_missing", ["data_source"])]
            )
        raise
    return _output(
        rows=[*store_rows(ctx), _row("station_matches", count=matches)],
        values={"matches": matches},
    )


def _location_rows(path: Path) -> tuple[int, str | None]:
    """Rows of a user's station-location CSV, or the key of what is wrong with it."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source)
            header = next(reader, None)
            if header is None or not set(_LOCATION_COLUMNS) <= set(header):
                return 0, "user_locations_invalid"
            return sum(1 for row in reader if row), None
    except UnicodeDecodeError:
        return 0, "user_locations_invalid"
    except OSError:
        return 0, "user_locations_missing"


def preview_build_obserwator_station_catalog(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 2: both roots, the reference file and the user's locations file."""
    problems = store_problems(ctx, write=True, kinds=BOTH_ROOTS)
    if problems:
        return _output(problems=problems)
    _, call = build_obserwator_station_catalog(params, ctx)
    rows = store_rows(ctx, BOTH_ROOTS)
    if call.options["provider"] == "IMGW-PIB":
        reference = Path(ctx.settings["reference_data_dir"]) / OBSERWATOR_REFERENCE_FILE
        rows.append(
            _row(
                "reference_present" if reference.is_file() else "reference_absent",
                path=reference.parent,
                file=OBSERWATOR_REFERENCE_FILE,
            )
        )
    if "user_locations" in call.options:
        path = Path(str(call.options["user_locations"]))
        count, reason = _location_rows(path)
        if reason is not None:
            return _output(
                problems=[_problem(reason, ["user_locations"], path=path.name)]
            )
        rows.append(_row("user_locations_file", name=path.name, count=count))
    return _output(rows=rows)


# --- operations 4-6: live data -----------------------------------------------------


def preview_fetch_current_observations(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 4: say so when the answer is the whole list of stations."""
    source = params["source"]
    named = "synop_station" if source == "synop" else "station"
    if named in params:
        return _output()
    return _output(rows=[_row(f"all_{source}")])


def preview_fetch_imgw_warnings(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 5: without a kind both hydrological and meteorological warnings."""
    return _output() if "kind" in params else _output(rows=[_row("warnings_both")])


# --- operations 7-8: PMAXTP --------------------------------------------------------


def preview_get_pmaxtp(params: dict[str, Any], ctx: ToolContext) -> PreviewOutput:
    """Operation 7: a stored cell needs a raw root that can be written."""
    if params["storage"] != "store":
        return _output()
    problems = store_problems(ctx, write=True, kinds=("raw",))
    rows = store_rows(ctx, ("raw",)) if not problems else []
    return _output(rows=rows, problems=problems)


def preview_read_stored_pmaxtp(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 8: the cell must be in the raw root (read offline)."""
    problems = store_problems(ctx, write=False, kinds=("raw",))
    if problems:
        return _output(problems=problems)
    cell = params["cell"]
    label = f"{cell['ind_x']}/{cell['ind_y']}"
    method = ctx.tool_value("method", params["method"])
    try:
        document = ctx.client.lookup(
            CatalogCall(
                "pmaxtp read",
                {"ind_x": cell["ind_x"], "ind_y": cell["ind_y"], "method": method},
                params={"ind_x": "cell", "ind_y": "cell", "method": "method"},
            )
        )
    except ToolError as err:
        if err.tool_code == "not_found":
            return _output(
                problems=[
                    _problem(
                        "pmaxtp_cell_missing",
                        ["cell", "method"],
                        cell=label,
                        method=method,
                    )
                ]
            )
        raise
    result = document.get("result")
    data: dict[str, Any] = result if isinstance(result, dict) else {}
    return _output(
        rows=[
            *store_rows(ctx, ("raw",)),
            _row(
                "pmaxtp_cell",
                cell=label,
                method=method,
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
            ),
        ]
    )


# --- operations 9-11: station series -----------------------------------------------


@dataclass(frozen=True)
class _Coverage:
    """What the series of a station in the store covers."""

    first: str | None
    last: str | None
    gaps: int


def _coverage(
    ctx: ToolContext, dataset: str, codes: list[str], variables: list[str] | None
) -> _Coverage | ToolError:
    """Return the store's coverage of stations, or the ``ToolError`` that says why not.

    A missing series (``not_found``), a station outside it or a variable it does
    not have are answers, not failures; anything else is raised.
    """
    options: dict[str, object] = {"dataset": dataset}
    if codes:
        options["stations"] = codes
    if variables:
        options["variables"] = variables
    try:
        document = ctx.client.lookup(CatalogCall("series summary", options))
    except ToolError as err:
        if (
            err.tool_code == "not_found"
            or _unknown_station(err)
            or (err.tool_code == "validation_error" and err.option == "variables")
        ):
            return err
        raise
    items = document_items(document)
    firsts = [item["first"] for item in items if item.get("first")]
    lasts = [item["last"] for item in items if item.get("last")]
    return _Coverage(
        min(firsts) if firsts else None,
        max(lasts) if lasts else None,
        sum(len(item.get("gaps") or ()) for item in items),
    )


def _archives_row(
    ctx: ToolContext, call: CatalogCall
) -> tuple[PreviewRow | None, PreviewProblem | None]:
    """How many archive files the synchronisation would look at (``datasets files``)."""
    options: dict[str, object] = {"dataset": call.options["datasets"][0]}  # type: ignore[index]
    for key in ("years", "stations"):
        if key in call.options:
            options[key] = call.options[key]
    try:
        document = ctx.client.lookup(CatalogCall("datasets files", options))
    except ToolError as err:
        routes = {"years": "period", "stations": "station"}
        if err.tool_code == "validation_error" and err.option in routes:
            return None, _problem(
                "archives_rejected", [routes[err.option]], detail=err.detail
            )
        raise
    items = document_items(document)
    if not items:
        return None, None
    names = [PurePosixPath(str(item["server_path"])).name for item in items]
    return _row("archives", count=len(items), first=names[0], last=names[-1]), None


def preview_export_station_series(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 9: what the data root holds, or which archives would be fetched."""
    server = params["data_source"] == "server"
    kinds: tuple[ObserwatorRoot, ...] = BOTH_ROOTS if server else ("data",)
    problems = store_problems(ctx, write=server, kinds=kinds)
    if problems:
        return _output(problems=problems)
    dataset = ctx.tool_value("dataset", params["dataset"])
    code = params["station"]["code"]
    start, end = period_dates(params["period"], params["year_type"])
    rows = store_rows(ctx, kinds)
    coverage = _coverage(ctx, dataset, [code], params.get("variables"))
    values: dict[str, Any] = {"period": [start.isoformat(), end.isoformat()]}
    if isinstance(coverage, ToolError):
        if coverage.option == "variables":
            problem = _problem(
                "variables_not_in_series", ["variables"], detail=coverage.detail
            )
            return _output(problems=[problem])
        if not server:
            if coverage.tool_code == "not_found":
                problem = _problem("series_missing", ["data_source"], dataset=dataset)
            else:
                problem = _problem(
                    "station_not_in_series",
                    ["station", "data_source"],
                    station=code,
                    dataset=dataset,
                )
            return _output(problems=[problem])
        # From the server the series appears with the archives: nothing is wrong
        rows.append(
            _row(
                "store_no_series"
                if coverage.tool_code == "not_found"
                else "store_no_station"
            )
        )
    else:
        first, last = coverage.first, coverage.last
        values["store_coverage"] = {"first": first, "last": last, "gaps": coverage.gaps}
        if first and last:
            if not server and (last < start.isoformat() or first > end.isoformat()):
                return _output(
                    problems=[
                        _problem(
                            "period_outside_coverage",
                            ["period"],
                            first=first,
                            last=last,
                        )
                    ]
                )
            rows.append(
                _row("store_coverage", first=first, last=last, gaps=coverage.gaps)
            )
            if first > start.isoformat() or last < end.isoformat():
                rows.append(_row("period_partial", first=first, last=last))
    if server:
        sync = next(
            call
            for call in export_station_series(params, ctx)
            if call.command == "store sync"
        )
        row, rejected = _archives_row(ctx, sync)
        if rejected is not None:
            return _output(problems=[rejected])
        if row is not None:
            rows.append(row)
            values["archive_files"] = int(row["args"]["count"])
    return _output(rows=rows, values=values)


def preview_show_station_coverage(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 10: the series must exist; what the summary will cover."""
    problems = store_problems(ctx, write=False)
    if problems:
        return _output(problems=problems)
    dataset = ctx.tool_value("dataset", params["dataset"])
    codes = [station["code"] for station in params.get("station", [])]
    coverage = _coverage(ctx, dataset, codes, None)
    if isinstance(coverage, ToolError):
        if coverage.tool_code == "not_found":
            return _output(
                problems=[_problem("series_missing", ["dataset"], dataset=dataset)]
            )
        return _output(
            problems=[
                _problem(
                    "station_not_in_series",
                    ["station"],
                    station=", ".join(codes),
                    dataset=dataset,
                )
            ]
        )
    rows = store_rows(ctx)
    if not codes:
        rows.append(_row("all_stations", dataset=dataset))
    if coverage.first and coverage.last:
        rows.append(
            _row(
                "store_coverage",
                first=coverage.first,
                last=coverage.last,
                gaps=coverage.gaps,
            )
        )
    return _output(rows=rows)


def preview_build_obserwator_series(
    params: dict[str, Any], ctx: ToolContext
) -> PreviewOutput:
    """Operation 11: the series is built from the raw root into the data root."""
    problems = store_problems(ctx, write=True, kinds=BOTH_ROOTS)
    rows = store_rows(ctx, BOTH_ROOTS) if not problems else []
    return _output(rows=rows, problems=problems)

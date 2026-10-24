"""Results of IMGWTools commands: files, values and warnings of each operation.

``base_output`` and the small writers (``write_report``, ``csv_write``) are
shared by every operation of the adapter; the ``describe_*`` functions are the
manifest's ``describe`` hooks (``describe(operation, params, runs, ctx) ->
HandlerOutput``), run after the generic runner has executed the operation's
calls. They only map the tools' JSON documents: tables become CSV files of the
kind the user asked for, every other document is kept as it is (kind
``imgw_report``), the licence notices of the provider are passed on verbatim
(IMGWTools AGENTS.md, rule 12) and a partial run is reported, never hidden.
"""

import csv
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from retman.adapters.catalog import (
    CatalogCall,
    ToolContext,
    ToolRun,
    failure_warnings,
    notice_warnings,
)
from retman.exceptions import RetmanError
from retman.extractors.dates import period_dates
from retman.registry.manifest import HandlerOutput, HandlerWarning
from retman.registry.operation import Operation

LICENSE_CODE: Final = "license_terms"
# Failed units listed one by one in the warnings; the rest is only counted
MAX_FAILURES_SHOWN: Final = 5

Runs = Sequence[tuple[CatalogCall, ToolRun]]

# CSV columns of the tables Retman writes itself (the models' fields in the
# order the tool declares them); a drift test compares them with the tool.
STATION_COLUMNS: Final = (
    "provider",
    "kind",
    "station_code",
    "name",
    "river",
    "hydrographic_code",
    "river_order",
    "short_code",
    "latitude",
    "longitude",
)
CURRENT_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "hydro": (
        "station_code",
        "station_name",
        "river",
        "province",
        "latitude",
        "longitude",
        "water_level_cm",
        "water_level_date",
        "flow_m3s",
        "flow_date",
        "water_temp_c",
        "water_temp_date",
        "ice_phenomenon",
        "overgrowth",
    ),
    "meteo": (
        "station_code",
        "station_name",
        "latitude",
        "longitude",
        "air_temp_c",
        "air_temp_date",
        "wind_speed_ms",
        "humidity_percent",
        "precipitation_10min_mm",
    ),
    "synop": (
        "station_code",
        "station_name",
        "measurement_date",
        "measurement_hour",
        "temperature_c",
        "wind_speed_ms",
        "wind_direction",
        "humidity_percent",
        "precipitation_mm",
        "pressure_hpa",
        "visibility_m",
        "cloud_cover",
    ),
}
WARNING_COLUMNS: Final = (
    "id",
    "kind",
    "event",
    "level",
    "region",
    "description",
    "valid_from",
    "valid_to",
    "probability",
)
HYDRO_STATE_COLUMNS: Final = (
    "station_code",
    "name",
    "river",
    "latitude",
    "longitude",
    "water_state",
)
PMAXTP_COLUMNS: Final = (
    "duration_min",
    "probability_percent",
    "ks_mm",
    "sg_mm",
    "rb_mm",
    "attribution_source",
    "attribution_processed",
)
# A measurement column of a series file: ``P [mm]``, ``H [cm]``
_MEASUREMENT: Final = re.compile(r"^\S+ \[[^\]]+\]$")


def utc_now() -> datetime:
    """The current time in UTC (replaced by tests)."""
    return datetime.now(UTC)


def utc_stamp() -> str:
    """The current UTC time as a file-name part, e.g. ``20261019T120000Z``."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def slug(text: str) -> str:
    """An ASCII file-name part: ``"Poznań-Ławica"`` becomes ``"poznan_lawica"``."""
    folded = unicodedata.normalize(
        "NFKD", text.casefold().replace("ł", "l").replace("ø", "o")
    )
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")


def output_dir(ctx: ToolContext) -> Path:
    """The result folder of the running operation (``None`` only while planning)."""
    if ctx.output_dir is None:
        raise RetmanError("a result is described only while the operation runs")
    return ctx.output_dir


def write_report(path: Path, document: Mapping[str, Any]) -> Path:
    """Write a tool document as it is: JSON whose first key is ``schema``."""
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def _cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple | dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def csv_write(
    path: Path, columns: Sequence[str], rows: Iterable[Sequence[object]]
) -> Path:
    """Write a UTF-8 CSV file (header first; the tool's CRLF line ends)."""
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(value) for value in row])
    return path


def result_of(run: ToolRun) -> Any:
    """The ``result`` of a run's ``imgw-result/1`` document."""
    return run.document.get("result")


def document_items(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The items of a list command's document (a ``Page``); empty if there are none."""
    result = document.get("result")
    items = result.get("items") if isinstance(result, dict) else None
    return [item for item in items if isinstance(item, dict)] if items else []


def items_of(run: ToolRun) -> list[dict[str, Any]]:
    """The items of a list command's result (``Page``); empty if there are none."""
    return document_items(run.document)


def run_of(runs: Runs, command: str) -> ToolRun:
    """The first run of ``command``; the builders always include the ones they need."""
    for call, run in runs:
        if call.command == command:
            return run
    raise RetmanError(f"the operation ran no {command!r} command")


def table_rows(
    items: Iterable[Mapping[str, Any]], columns: Sequence[str]
) -> list[list[object]]:
    """Rows of ``columns`` from the items (missing keys are empty)."""
    return [[item.get(column) for column in columns] for item in items]


def license_notice(provider: Mapping[str, Any]) -> str:
    """The provider's licence text as the tool words it in its own notices.

    ``provider`` is an item of ``datasets providers``: the attribution, the
    note on processing and the terms of use, joined as in ``license_terms``.
    """
    license_ = provider.get("license")
    attribution = license_.get("attribution") if isinstance(license_, dict) else None
    parts = [attribution, provider.get("processed_attribution"), provider.get("notice")]
    return ". ".join(str(part).rstrip(".") for part in parts if part) + "."


def provider_licenses(runs: Runs, provider_ids: Iterable[str]) -> list[str]:
    """Licence notices of the given providers from the run of ``datasets providers``."""
    wanted = set(provider_ids)
    return [
        license_notice(item)
        for item in items_of(run_of(runs, "datasets providers"))
        if item.get("id") in wanted
    ]


def provider_attribution(runs: Runs, provider_id: str) -> tuple[str, str]:
    """Source and processing attribution of a provider (for CSV columns)."""
    for item in items_of(run_of(runs, "datasets providers")):
        if item.get("id") == provider_id:
            license_ = item.get("license")
            source = license_.get("attribution") if isinstance(license_, dict) else ""
            return str(source or ""), str(item.get("processed_attribution") or "")
    return "", ""


def _total(run: ToolRun) -> int:
    """How many units a run handled, for the "failed of total" warning."""
    result = result_of(run)
    if not isinstance(result, dict):
        return len(run.failed)
    total = 0
    for key in ("items", "files", "series", "actions"):
        value = result.get(key)
        total += len(value) if isinstance(value, list) else 0
    tasks = result.get("tasks")
    total += len(tasks) if isinstance(tasks, dict) else 0
    return max(total, len(run.failed))


def _run_warnings(
    operation: Operation, ctx: ToolContext, run: ToolRun
) -> list[HandlerWarning]:
    notices = [notice for notice in run.notices if notice.code != LICENSE_CODE]
    warnings = notice_warnings(operation, ctx.tool, notices)
    if run.status == "partial" or run.failed:
        warnings.append(
            {
                "key": "partial_items",
                "args": {"failed": str(len(run.failed)), "total": str(_total(run))},
            }
        )
    warnings.extend(failure_warnings(run.failed[:MAX_FAILURES_SHOWN]))
    return warnings


def base_output(
    operation: Operation,
    params: dict[str, Any],
    runs: Runs,
    ctx: ToolContext,
    *,
    licenses: Sequence[str] = (),
) -> HandlerOutput:
    """The generic mapping of runs to a result, with the licence terms.

    Files are the runs' files by the call's ``kind``. Warnings: the tool's
    warning notices, a partial run (how many units failed of how many, the first
    ones named) and, last, every licence notice of the tool plus ``licenses``
    (text the mapper derived itself), each once and verbatim.
    """
    files: dict[str, list[Path]] = {}
    warnings: list[HandlerWarning] = []
    texts: list[str] = []
    for call, run in runs:
        if call.kind is not None:
            files.setdefault(call.kind, []).extend(item.path for item in run.files)
        warnings.extend(_run_warnings(operation, ctx, run))
        texts.extend(n.text for n in run.notices if n.code == LICENSE_CODE)
    texts.extend(licenses)
    unique = list(dict.fromkeys(texts))
    warnings.extend({"key": LICENSE_CODE, "args": {"text": text}} for text in unique)
    values: dict[str, Any] = {
        "calls": len(runs),
        "file_count": sum(len(paths) for paths in files.values()),
    }
    if unique:
        values["license"] = unique
    return {"values": values, "files": files, "warnings": warnings}


def add_warnings(output: HandlerOutput, warnings: Iterable[HandlerWarning]) -> None:
    """Add warnings to a result before its licence terms, which stay last."""
    current = output["warnings"]
    cut = len(current)
    while cut > 0 and current[cut - 1]["key"] == LICENSE_CODE:
        cut -= 1
    current[cut:cut] = list(warnings)


def set_files(output: HandlerOutput, files: dict[str, list[Path]]) -> None:
    """Replace the files of a result (the mapper wrote them) and recount them."""
    output["files"] = files
    output["values"]["file_count"] = sum(len(paths) for paths in files.values())


def _fetched_at() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _no_rows(output: HandlerOutput, rows: int) -> None:
    if rows == 0:
        add_warnings(output, [{"key": "no_rows", "args": {}}])


def describe_find_imgw_stations(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 1: the stations as ``station_list`` CSV (all the tool's fields)."""
    items = items_of(run_of(runs, "stations find"))
    providers = sorted({str(item["provider"]) for item in items if "provider" in item})
    output = base_output(
        operation, params, runs, ctx, licenses=provider_licenses(runs, providers)
    )
    query = params.get("query")
    parts = [params.get("provider"), params.get("kind")]
    parts.append(slug(query["text"]) if query else None)
    name = "_".join(["stations", *(part for part in parts if part)]) + ".csv"
    path = csv_write(
        output_dir(ctx) / name, STATION_COLUMNS, table_rows(items, STATION_COLUMNS)
    )
    set_files(output, {"station_list": [path]})
    output["values"].update(
        count=len(items),
        providers=providers,
        data_source=params["data_source"],
        fetched_at=_fetched_at(),
    )
    _no_rows(output, len(items))
    return output


def describe_build_imgw_station_catalog(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 2: what the catalog build wrote (nothing is returned as a file)."""
    result = result_of(run_of(runs, "store catalog"))
    output = base_output(operation, params, runs, ctx)
    output["values"].update(
        status=result["status"],
        station_count=result["station_count"],
        without_location=result["without_location"],
        from_series=result["from_series"],
        provider=result["provider"],
        catalog_version=result["version"],
    )
    if result["without_location"]:
        add_warnings(
            output,
            [
                {
                    "key": "stations_without_location",
                    "args": {"count": str(result["without_location"])},
                }
            ],
        )
    return output


def describe_list_imgw_datasets(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 3: the registry and the providers, as the tool's documents."""
    datasets, providers = (
        run_of(runs, "datasets list"),
        run_of(runs, "datasets providers"),
    )
    output = base_output(operation, params, runs, ctx)
    folder = output_dir(ctx)
    set_files(
        output,
        {
            "imgw_report": [
                write_report(folder / "datasets.json", datasets.document),
                write_report(folder / "providers.json", providers.document),
            ]
        },
    )
    output["values"].update(
        datasets=len(items_of(datasets)), providers=len(items_of(providers))
    )
    return output


def describe_fetch_current_observations(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 4: current data of the stations as CSV of the source's kind."""
    source = params["source"]
    items = items_of(run_of(runs, f"current {source}"))
    output = base_output(
        operation, params, runs, ctx, licenses=provider_licenses(runs, ["IMGW-PIB"])
    )
    columns = CURRENT_COLUMNS[source]
    path = csv_write(
        output_dir(ctx) / f"{source}_current_{utc_stamp()}.csv",
        columns,
        table_rows(items, columns),
    )
    set_files(output, {f"current_{source}": [path]})
    output["values"].update(rows=len(items), source=source, fetched_at=_fetched_at())
    _no_rows(output, len(items))
    return output


def describe_fetch_imgw_warnings(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 5: the warnings as CSV; no warning in force is a normal result."""
    items = items_of(run_of(runs, "current warnings"))
    output = base_output(
        operation, params, runs, ctx, licenses=provider_licenses(runs, ["IMGW-PIB"])
    )
    path = csv_write(
        output_dir(ctx) / f"warnings_{utc_stamp()}.csv",
        WARNING_COLUMNS,
        table_rows(items, WARNING_COLUMNS),
    )
    set_files(output, {"imgw_warnings": [path]})
    levels = [item["level"] for item in items if isinstance(item.get("level"), int)]
    output["values"].update(
        rows=len(items),
        highest_level=max(levels) if levels else None,
        fetched_at=_fetched_at(),
    )
    return output


def describe_fetch_hydro_states(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 6: the water state of every station as CSV, counted by state."""
    items = items_of(run_of(runs, "current hydro-states"))
    output = base_output(
        operation, params, runs, ctx, licenses=provider_licenses(runs, ["IMGW-PIB"])
    )
    path = csv_write(
        output_dir(ctx) / f"hydro_states_{utc_stamp()}.csv",
        HYDRO_STATE_COLUMNS,
        table_rows(items, HYDRO_STATE_COLUMNS),
    )
    set_files(output, {"hydro_states": [path]})
    states = Counter(str(item.get("water_state") or "unknown") for item in items)
    output["values"].update(
        rows=len(items), by_state=dict(states), fetched_at=_fetched_at()
    )
    _no_rows(output, len(items))
    return output


def _number(text: str) -> int | float:
    """A key of the PMAXTP table (``"15"``, ``"0.5"``) as a number."""
    value = float(text)
    return int(value) if value.is_integer() else value


def pmaxtp_rows(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The rows of a PMAXTP table: duration × probability, with ks, sg and rb.

    ``data`` is the ``data`` part of the tool's result: ``ks``, ``sg`` and ``rb``
    are ``{duration: {probability: value}}`` with plain numbers as text keys.
    """
    tables = {key: data.get(key) or {} for key in ("ks", "sg", "rb")}
    durations = sorted({d for table in tables.values() for d in table}, key=float)
    rows: list[dict[str, Any]] = []
    for duration in durations:
        probabilities = sorted(
            {p for table in tables.values() for p in table.get(duration, {})},
            key=float,
        )
        for probability in probabilities:
            rows.append(
                {
                    "duration_min": _number(duration),
                    "probability_percent": _number(probability),
                    **{
                        f"{key}_mm": tables[key].get(duration, {}).get(probability)
                        for key in ("ks", "sg", "rb")
                    },
                }
            )
    return rows


def _percent(probability: float) -> float:
    return round(probability * 100, 9)


def _selection(
    rows: list[dict[str, Any]], params: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[float], list[int]]:
    """Rows that match the plan's probability and duration, and what was missing.

    Probabilities are fractions in the plan (0.01 = 1 %) and percent in the table.
    """
    percents = [_percent(value) for value in params.get("probability", [])]
    minutes = [int(value) for value in params.get("duration", [])]
    selected = [
        row
        for row in rows
        if (not percents or float(row["probability_percent"]) in percents)
        and (not minutes or int(row["duration_min"]) in minutes)
    ]
    have_percents = {float(row["probability_percent"]) for row in rows}
    have_minutes = {int(row["duration_min"]) for row in rows}
    return (
        selected,
        [value for value in percents if value not in have_percents],
        [value for value in minutes if value not in have_minutes],
    )


def _listed(values: Iterable[float | int]) -> str:
    return ", ".join(f"{value:g}" for value in sorted(set(values)))


def _describe_pmaxtp(
    operation: Operation,
    params: dict[str, Any],
    runs: Runs,
    ctx: ToolContext,
    command: str,
) -> HandlerOutput:
    """The PMAXTP table of ``command`` as CSV, narrowed by probability and duration."""
    result = result_of(run_of(runs, command))
    stored = command == "pmaxtp sync"
    data = result["result"] if stored else result
    rows = pmaxtp_rows(data["data"])
    selected, missing_percents, missing_minutes = _selection(rows, params)
    output = base_output(
        operation, params, runs, ctx, licenses=provider_licenses(runs, ["IMGW-PIB"])
    )
    filtered = bool(params.get("probability") or params.get("duration"))
    if missing_percents:
        add_warnings(
            output,
            [
                {
                    "key": "pmaxtp_probability_missing",
                    "args": {
                        "requested": _listed(missing_percents),
                        "available": _listed(r["probability_percent"] for r in rows),
                    },
                }
            ],
        )
    if missing_minutes:
        add_warnings(
            output,
            [
                {
                    "key": "pmaxtp_duration_missing",
                    "args": {
                        "requested": _listed(missing_minutes),
                        "available": _listed(r["duration_min"] for r in rows),
                    },
                }
            ],
        )
    if filtered and not selected:
        # Nothing asked for exists: the whole table is better than an empty file
        add_warnings(output, [{"key": "pmaxtp_nothing_selected", "args": {}}])
        selected = rows
    source, processed = provider_attribution(runs, "IMGW-PIB")
    body = [
        [
            row["duration_min"],
            row["probability_percent"],
            row["ks_mm"],
            row["sg_mm"],
            row["rb_mm"],
            source if index == 0 else "",
            processed if index == 0 else "",
        ]
        for index, row in enumerate(selected)
    ]
    # The cell: given by the user (reading), named by the tool (stored), or none
    cell: dict[str, Any] | None = None
    if "cell" in params:
        cell = {"ind_x": params["cell"]["ind_x"], "ind_y": params["cell"]["ind_y"]}
    elif stored:
        cell = {"ind_x": result["ind_x"], "ind_y": result["ind_y"]}
    if cell is not None:
        label = f"{cell['ind_x']}_{cell['ind_y']}"
    else:
        label = "_".join(
            f"{data[key]:.4f}".rstrip("0").rstrip(".")
            for key in ("latitude", "longitude")
        )
    path = csv_write(
        output_dir(ctx) / f"pmaxtp_{str(data['method']).lower()}_{label}.csv",
        PMAXTP_COLUMNS,
        body,
    )
    set_files(output, {"pmaxtp_table": [path]})
    output["values"].update(
        method=data["method"],
        latitude=data["latitude"],
        longitude=data["longitude"],
        durations_min=sorted({row["duration_min"] for row in rows}),
        probabilities_percent=sorted({row["probability_percent"] for row in rows}),
        rows=len(body),
    )
    if filtered:
        output["values"]["selected"] = [
            {key: row[key] for key in PMAXTP_COLUMNS[:5]} for row in selected
        ]
    if cell is not None:
        output["values"]["cell"] = cell
    if stored:
        output["values"]["version"] = result["version"]
    return output


def describe_get_pmaxtp(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 7: the table of ``pmaxtp fetch`` or ``pmaxtp sync``."""
    command = "pmaxtp sync" if params["storage"] == "store" else "pmaxtp fetch"
    return _describe_pmaxtp(operation, params, runs, ctx, command)


def describe_read_stored_pmaxtp(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 8: the table of the stored cell."""
    return _describe_pmaxtp(operation, params, runs, ctx, "pmaxtp read")


def series_stats(path: Path) -> dict[str, Any]:
    """Rows, first and last date and the rows without any value of a series CSV."""
    rows = missing = 0
    first = last = None
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        header = next(reader, [])
        columns = [i for i, name in enumerate(header) if _MEASUREMENT.match(name)]
        for row in reader:
            if not row:
                continue
            rows += 1
            first = first or row[0]
            last = row[0]
            if not any(row[i].strip() for i in columns):
                missing += 1
    return {
        "rows": rows,
        "first_date": first,
        "last_date": last,
        "missing_rows": missing,
    }


def describe_export_station_series(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 9: the exported CSV, its extent and the series version it read."""
    export = run_of(runs, "series export")
    (exported,) = export.files
    start, end = period_dates(params["period"], params["year_type"])
    meta = ctx.option_meta("dataset", params["dataset"])
    output = base_output(operation, params, runs, ctx)
    selection = result_of(run_of(runs, "series select"))
    output["values"].update(
        dataset=ctx.tool_value("dataset", params["dataset"]),
        station_code=params["station"]["code"],
        provider=meta["provider"],
        period={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "year_type": params["year_type"],
        },
        series_version=selection.get("version"),
        **series_stats(exported.path),
    )
    if any(call.command == "store sync" for call, _ in runs):
        sync = result_of(run_of(runs, "store sync"))
        archives = Counter(item["status"] for item in sync["items"])
        output["values"]["archives"] = {
            "planned": len(sync["items"]),
            **{
                status: archives.get(status, 0)
                for status in ("created", "unchanged", "relabeled", "failed")
            },
        }
    return output


def describe_show_station_coverage(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 10: the coverage of the series as the tool's own document."""
    run = run_of(runs, "series summary")
    items = items_of(run)
    output = base_output(operation, params, runs, ctx)
    coverage = write_report(output_dir(ctx) / "coverage.json", run.document)
    set_files(output, {"imgw_report": [coverage]})
    firsts = [item["first"] for item in items if item.get("first")]
    lasts = [item["last"] for item in items if item.get("last")]
    output["values"].update(
        stations=len({item["station_code"] for item in items}),
        variables=list(dict.fromkeys(item["variable"] for item in items)),
        first=min(firsts) if firsts else None,
        last=max(lasts) if lasts else None,
        gaps_total=sum(len(item.get("gaps") or ()) for item in items),
    )
    _no_rows(output, len(items))
    return output


def describe_build_imgw_series(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Operation 11: what ``series build`` made of the archives in the store."""
    result = result_of(run_of(runs, "series build"))
    output = base_output(operation, params, runs, ctx)
    output["values"].update(
        status=result["status"],
        dataset=ctx.tool_value("dataset", params["dataset"]),
        series_version=result["version"],
        stations=result["stations"],
        source_files=len(result["source_files"]),
    )
    return output

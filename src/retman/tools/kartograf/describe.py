"""Retman results of Kartograf's commands: downloads, ``store init`` and its overview.

The mappers turn the runs of an operation's call builder into a ``HandlerOutput``:
the files (by data kind), a few values, and warnings. Kartograf's warning notices
are shown with Retman's text where ``[warnings.<code>]`` exists in ``pl.toml``
(its own wording names command-line flags), otherwise verbatim; info notices stay
in the audit document. The document of ``store init`` is ``kartograf-store-init/1``,
that of ``store overview`` ``kartograf-store-overview/1``; ``soil hsg`` adds the
``summary`` of the groups A-D to its download document.
"""

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from stat import S_IFLNK, S_IFMT
from typing import Any
from zipfile import BadZipFile, ZipFile

from retman.adapters.catalog import (
    CatalogCall,
    ToolContext,
    ToolError,
    ToolNotice,
    ToolRun,
    notice_warnings,
)
from retman.exceptions import RetmanError
from retman.registry.manifest import HandlerOutput, HandlerWarning
from retman.registry.operation import Operation
from retman.tools.kartograf.areas import sheet_count

TOOL = "kartograf"

# A campaign label starts with the date the data were acquired or published
_CAMPAIGN = re.compile(r"(\d{4}-\d{2}-\d{2})_")
# Kartograf's notice of a raster without data, worded per operation by Retman (the
# text of ``[warnings.all_nodata]`` speaks of an elevation cutout)
_ALL_NODATA = "all_nodata"
# The hydrologic soil groups of the summary of ``soil hsg``, and the cells without
# data, in the order the result lists them
_HSG_GROUPS = ("A", "B", "C", "D", "nodata")
# What the result keeps of a segment of ``kartograf-store-overview/1``
_SEGMENT_FIELDS = ("segment", "product", "country", "dataset_key", "name", "known")
# CORINE without CLMS credentials: the WMS preview, a coloured PNG instead of codes
_PREVIEW_SUFFIX = ".png"

Runs = Sequence[tuple[CatalogCall, ToolRun]]


def _kind(call: CatalogCall) -> str:
    if call.kind is None:
        raise RetmanError(f"{call.command}: the call names no data kind")
    return call.kind


def _bytes(paths: Iterable[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def data_dates(labels: Iterable[str | None]) -> list[str]:
    """Return the dates the data of the files with these version labels are from."""
    return sorted(
        {
            found.group(1)
            for label in labels
            if label and (found := _CAMPAIGN.match(label))
        }
    )


def sheets_output(
    operation: Operation, ctx: ToolContext, call: CatalogCall, run: ToolRun
) -> HandlerOutput:
    """Sheets of a sheet code or a geometry file.

    A document reports a sheet request as ``ok`` even when GUGiK has no data for
    some sheets (a ``no_coverage_some`` notice), and puts every failed download
    into ONE failure whose text names the sheets; so the count of missing sheets is
    computed from the request, not read from the document. Where it cannot be
    computed the files delivered are still the result.
    """
    paths = [file.path for file in run.files]
    try:
        counted = sheet_count(call, ctx.client)
    except ToolError:
        counted = None
    expected = counted.count if counted is not None else None
    warnings: list[HandlerWarning] = []
    if expected is not None and len(paths) < expected:
        warnings.append(
            {
                "key": "sheets_missing",
                "args": {"count": str(len(paths)), "total": str(expected)},
            }
        )
    warnings.extend(
        {"key": "sheets_failed", "args": {"detail": failure.detail}}
        for failure in run.failed
        if failure.kind == "source_unavailable"
    )
    warnings.extend(notice_warnings(operation, ctx.tool, run.notices))
    values: dict[str, Any] = {
        "file_count": len(paths),
        "data_dates": data_dates(file.version for file in run.files),
        "bytes": _bytes(paths),
    }
    if call.kind != "dem_archive":  # province files are not sheets
        values["sheet_count"] = len(paths)
        values["expected_sheets"] = expected
    return {"values": values, "files": {_kind(call): paths}, "warnings": warnings}


def download_dem_sheet(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """NMT sheets (or the province files of NMT 100 m)."""
    ((call, run),) = runs
    return sheets_output(operation, ctx, call, run)


def download_sheet_hierarchy(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """NMT, NMPT or orthophoto sheets; the files go under the kind of the call."""
    ((call, run),) = runs
    return sheets_output(operation, ctx, call, run)


def _sidecar_extra(path: Path, ctx: ToolContext) -> dict[str, Any]:
    """Read what Kartograf wrote beside a store file (``extra`` of the sidecar).

    The facts are a bonus, not the result: an unreadable sidecar gives none.
    """
    try:
        document = ctx.client.lookup(CatalogCall("store sidecar", {"path": str(path)}))
    except ToolError:
        return {}
    return dict(document.get("sidecar", {}).get("extra") or {})


def download_elevation_cutout(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the cutout file and what its sidecar says about the land mask.

    ``kartograf-download/1`` has no ``masked_pixels``; the mask facts are in the
    sidecar of the file, which is read through the client.
    """
    ((call, run),) = runs
    file = run.files[0]
    extra = _sidecar_extra(file.path, ctx)
    masked = int((extra.get("mask") or {}).get("masked_pixels") or 0)
    all_nodata = bool(extra.get("all_nodata"))
    warnings: list[HandlerWarning] = []
    if all_nodata:
        warnings.append({"key": "all_nodata", "args": {}})
    if masked:
        warnings.append({"key": "masked_pixels", "args": {"count": str(masked)}})
    # The sidecar says it once: the notice of the same fact is not repeated
    notices: list[ToolNotice] = [
        notice
        for notice in run.notices
        if not (all_nodata and notice.code == "all_nodata")
    ]
    warnings.extend(notice_warnings(operation, ctx.tool, notices))
    return {
        "values": {
            "masked_pixels": masked,
            "all_nodata": all_nodata,
            "bytes": file.path.stat().st_size,
        },
        "files": {_kind(call): [file.path]},
        "warnings": warnings,
    }


def download_orthophoto_cutout(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the one orthophoto GeoTIFF: product, pixel, WCS variant and size."""
    ((call, run),) = runs
    paths = [file.path for file in run.files]
    coverage = call.options.get("coverage")
    return {
        "values": {
            "product": str(call.options["product"]),
            "resolution": str(call.options["resolution"]),
            "coverage": None if coverage is None else str(coverage),
            "file_count": len(paths),
            "bytes": _bytes(paths),
        },
        "files": {_kind(call): paths},
        "warnings": notice_warnings(operation, ctx.tool, run.notices),
    }


def extract_shapefiles(archive: Path, output_dir: Path) -> list[Path]:
    """Unpack a county's SHP ZIP into the result folder, keeping the sidecar files.

    The store stays untouched (it reports foreign files as problems): the files go
    to ``<output_dir>/bdot10k/<TERYT>/``.

    Raises
    ------
    ToolError
        ``unsafe_archive`` (a path leaving the folder, a link), ``missing_shapefiles``
        (no ``.shp`` inside) or ``invalid_archive`` (not a ZIP file).
    """
    directory = output_dir / "bdot10k" / archive.stem
    resolved_output = output_dir.resolve()
    try:
        with ZipFile(archive) as source:
            for entry in source.infolist():
                member = PurePosixPath(entry.filename)
                if (
                    not entry.filename
                    or "\\" in entry.filename
                    or member.is_absolute()
                    or ".." in member.parts
                    or S_IFMT(entry.external_attr >> 16) == S_IFLNK
                    or not (directory / member)
                    .resolve()
                    .is_relative_to(resolved_output)
                ):
                    raise ToolError(
                        TOOL, "unsafe_archive", f"{archive.name}: {entry.filename!r}"
                    )
            directory.mkdir(parents=True)
            source.extractall(directory)
    except BadZipFile as err:
        raise ToolError(TOOL, "invalid_archive", f"{archive.name}: {err}") from err
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".shp"
    )
    if not files:
        raise ToolError(TOOL, "missing_shapefiles", archive.name)
    return files


def download_bdot10k(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """County packages: a failed county is a warning, the other counties stay.

    GeoPackages stay in the store; a Shapefile arrives as a ZIP per county and is
    unpacked into the result folder.
    """
    ((call, run),) = runs
    files: list[Path] = []
    unpacked = 0
    failed_units = [failure.unit for failure in run.failed]
    cause: ToolError | None = None
    for file in run.files:
        if params["format"] == "shp":
            if ctx.output_dir is None:
                raise RetmanError("unpacking a Shapefile needs the result folder")
            try:
                files.extend(extract_shapefiles(file.path, ctx.output_dir))
            except ToolError as err:
                failed_units.append(file.path.stem)
                cause = err
                continue
        else:
            files.append(file.path)
        unpacked += 1
    if not files:
        if len(failed_units) == 1 and cause is not None:
            raise cause
        raise ToolError(TOOL, "all_counties_failed", ", ".join(failed_units), call=call)
    warnings: list[HandlerWarning] = []
    if failed_units:
        warnings.append(
            {
                "key": "failed_counties",
                "args": {
                    "count": str(len(failed_units)),
                    "total": str(unpacked + len(failed_units)),
                    "units": ", ".join(failed_units),
                },
            }
        )
    warnings.extend(notice_warnings(operation, ctx.tool, run.notices))
    return {
        "values": {
            "county_count": unpacked,
            "missing_counties": len(failed_units),
            "bytes": _bytes(files),
        },
        "files": {_kind(call): files},
        "warnings": warnings,
    }


def _corine(
    operation: Operation, ctx: ToolContext, call: CatalogCall, run: ToolRun
) -> HandlerOutput:
    """CORINE: class codes (GeoTIFF) or, without CLMS credentials, a WMS preview.

    Kartograf's notice of the preview is an info line, which a result does not
    show; the preview is a coloured picture, not class codes, so the result says so.
    """
    paths = [file.path for file in run.files]
    preview = any(path.suffix.lower() == _PREVIEW_SUFFIX for path in paths)
    warnings: list[HandlerWarning] = (
        [{"key": "corine_preview", "args": {}}] if preview else []
    )
    warnings.extend(notice_warnings(operation, ctx.tool, run.notices))
    return {
        "values": {
            "product": "corine",
            "year": int(str(call.options["year"])),
            "preview": preview,
            "edition": None if preview else _edition(run),
            "file_count": len(paths),
            "bytes": _bytes(paths),
        },
        "files": {_kind(call): paths},
        "warnings": warnings,
    }


def _bdoo(
    operation: Operation, ctx: ToolContext, call: CatalogCall, run: ToolRun
) -> HandlerOutput:
    """BDOO: a voivodeship package that failed is a warning, the others stay."""
    paths = [file.path for file in run.files]
    failed_units = [failure.unit for failure in run.failed]
    warnings: list[HandlerWarning] = []
    if failed_units:
        warnings.append(
            {
                "key": "failed_voivodeships",
                "args": {
                    "count": str(len(failed_units)),
                    "total": str(len(paths) + len(failed_units)),
                    "units": ", ".join(failed_units),
                },
            }
        )
    warnings.extend(notice_warnings(operation, ctx.tool, run.notices))
    return {
        "values": {
            "product": "bdoo",
            "year": int(str(call.options["year"])),
            "voivodeships": [path.stem for path in paths],
            "voivodeship_count": len(paths),
            "missing_voivodeships": len(failed_units),
            "bytes": _bytes(paths),
        },
        "files": {_kind(call): paths},
        "warnings": warnings,
    }


def download_landcover(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """CORINE raster of an area, or the BDOO packages of its voivodeships."""
    ((call, run),) = runs
    if call.options["product"] == "corine":
        return _corine(operation, ctx, call, run)
    return _bdoo(operation, ctx, call, run)


def init_kartograf_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Say which folder the tool marked as its store and whether it did so now.

    ``store init`` is idempotent: ``created`` is false when the store had its marker.
    It writes no file of data, so there are no files.
    """
    ((_, run),) = runs
    marker = run.document["result"]
    return {
        "values": {
            "store": marker["root"],
            "marker": marker["marker"],
            "created": marker["created"],
        },
        "files": {},
        "warnings": notice_warnings(operation, ctx.tool, run.notices),
    }


def inspect_kartograf_store(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """List the segments of the store: product, country, dataset and whether known.

    The document of ``store overview`` is ``kartograf-store-overview/1``; it is a read,
    so there are no files, and the saved document of the tool is the whole list. A
    segment that no source of the installed Kartograf produces (``known`` false, e.g.
    from another version of the tool) is a warning.
    """
    ((_, run),) = runs
    overview = run.document["result"]
    segments = [
        {name: segment.get(name) for name in _SEGMENT_FIELDS}
        for segment in overview.get("segments") or ()
    ]
    unknown = [str(segment["segment"]) for segment in segments if not segment["known"]]
    warnings = notice_warnings(operation, ctx.tool, run.notices)
    if unknown:
        warnings.append(
            {
                "key": "unknown_segments",
                "args": {"count": str(len(unknown)), "segments": ", ".join(unknown)},
            }
        )
    return {
        "values": {
            "store": overview["root"],
            "segment_count": len(segments),
            "product_counts": dict(
                sorted(Counter(str(segment["product"]) for segment in segments).items())
            ),
            "segments": segments,
        },
        "files": {},
        "warnings": warnings,
    }


def _worded_empty(
    operation: Operation, ctx: ToolContext, run: ToolRun, key: str
) -> list[HandlerWarning]:
    """Return the warnings of a run, Kartograf's ``all_nodata`` worded as ``key``."""
    empty = any(notice.code == _ALL_NODATA for notice in run.notices)
    warnings: list[HandlerWarning] = [{"key": key, "args": {}}] if empty else []
    others = [notice for notice in run.notices if notice.code != _ALL_NODATA]
    warnings.extend(notice_warnings(operation, ctx.tool, others))
    return warnings


def _edition(run: ToolRun) -> str | None:
    """Return the SoilGrids edition of a run: the version label of its files."""
    return next((file.version for file in run.files if file.version), None)


def download_soil_layer(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the SoilGrids layer and the unit of its values, as its sidecar says.

    SoilGrids keeps integer values in units of its own (clay in g/kg, the pH times
    ten): the result repeats the unit of the file, the conventional unit and the
    divisor between them, so that no value is read in the wrong unit. The units are
    a bonus of the sidecar: without it the layer is still the result. A layer of
    zeros (sea, water, built-up land) is Kartograf's ``all_nodata`` notice.
    """
    ((call, run),) = runs
    paths = [file.path for file in run.files]
    values: dict[str, Any] = {
        "property": str(call.options["property"]),
        "depth": str(call.options["depth"]),
        "stat": str(call.options["stat"]),
        "edition": _edition(run),
        "file_count": len(paths),
        "bytes": _bytes(paths),
    }
    units = (_sidecar_extra(paths[0], ctx).get("units") or {}) if paths else {}
    if {"mapped", "conventional", "divisor"} <= units.keys():
        values.update(
            unit=units["mapped"],
            conventional_unit=units["conventional"],
            divisor=units["divisor"],
        )
    return {
        "values": values,
        "files": {_kind(call): paths},
        "warnings": _worded_empty(operation, ctx, run, "soil_all_nodata"),
    }


def classify_soil_hsg(
    operation: Operation, params: dict[str, Any], runs: Runs, ctx: ToolContext
) -> HandlerOutput:
    """Describe the raster of the groups A-D with the share and area of each group.

    The shares are the ``summary`` of the run, which the client always asks for; the
    clay, sand and silt layers the groups come from stay in the store as the
    ``inputs`` of Kartograf's document, which the result counts.
    """
    ((call, run),) = runs
    paths = [file.path for file in run.files]
    result = run.document.get("result") or {}
    summary = result.get("summary") or {}
    groups = {
        group: {
            "percent": round(float(summary[group]["percent"]), 1),
            "area_ha": round(float(summary[group]["area_ha"]), 1),
        }
        for group in _HSG_GROUPS
        if group in summary
    }
    return {
        "values": {
            "depth": str(call.options["depth"]),
            "groups": groups,
            "input_count": len(result.get("inputs") or ()),
            "edition": _edition(run),
            "file_count": len(paths),
            "bytes": _bytes(paths),
        },
        "files": {_kind(call): paths},
        "warnings": _worded_empty(operation, ctx, run, "hsg_all_nodata"),
    }

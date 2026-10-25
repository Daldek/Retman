"""Retman results of Kartograf's data commands (``kartograf-download/1`` documents).

The mappers turn the runs of an operation's call builder into a ``HandlerOutput``:
the files (by data kind), a few values, and warnings. Kartograf's warning notices
are shown with Retman's text where ``[warnings.<code>]`` exists in ``pl.toml``
(its own wording names command-line flags), otherwise verbatim; info notices stay
in the audit document.
"""

import re
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

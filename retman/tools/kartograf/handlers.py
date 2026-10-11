"""Call the installed Kartograf public API and describe its written results."""

from pathlib import Path, PurePosixPath
from stat import S_IFLNK, S_IFMT
from typing import Any
from zipfile import BadZipFile, ZipFile

from retman.registry.manifest import HandlerOutput, HandlerWarning


def _error_text(key: str, **args: str) -> str:
    """Load the tool's user-facing error only when a download fails."""
    from retman.i18n.loader import load_texts

    return load_texts(Path(__file__).with_name("pl.toml")).get(f"errors.{key}", **args)


def _bbox(area: dict[str, Any]) -> Any:
    """Build a Kartograf bounding box from the normalized area reading."""
    import kartograf

    return kartograf.BBox(
        area["min_x"], area["min_y"], area["max_x"], area["max_y"], area["crs"]
    )


def _sheet_output(manager: Any, paths: list[Path], kind: str) -> HandlerOutput:
    """Preserve successes and distinguish absent coverage from failed downloads."""
    import kartograf

    result = manager.last_result
    if result is None:
        raise RuntimeError("Kartograf did not report sheet download outcomes")
    if not paths:
        if result.no_coverage and len(result.no_coverage) == len(result.failed):
            raise kartograf.NoCoverageError(_error_text("no_sheet_coverage"))
        raise kartograf.DownloadError(_error_text("all_sheets_failed"))
    warnings: list[HandlerWarning] = []
    if result.no_coverage:
        warnings.append(
            {
                "key": "no_coverage",
                "args": {
                    "count": str(len(result.no_coverage)),
                    "total": str(result.total),
                },
            }
        )
    hard_failures = result.hard_failures
    if hard_failures:
        warnings.append(
            {
                "key": "failed_sheets",
                "args": {
                    "count": str(len(hard_failures)),
                    "total": str(result.total),
                },
            }
        )
    if result.unverified:
        warnings.append(
            {"key": "unverified", "args": {"count": str(len(result.unverified))}}
        )
    return {
        "values": {
            "sheet_count": len(paths),
            "missing_sheets": len(result.failed),
            "bytes": sum(path.stat().st_size for path in paths),
        },
        "files": {kind: paths},
        "warnings": warnings,
    }


def _sheet_manager(
    product: str, output_dir: Path, resolution: str, vertical_crs: str
) -> Any:
    """Create a provider with its metadata database inside the result directory."""
    import kartograf

    cache = kartograf.MetadataCache(db_path=output_dir / ".kartograf_cache.db")
    if product == "dem":
        provider = kartograf.GugikProvider(
            resolution=resolution, vertical_crs=vertical_crs, cache=cache
        )
    elif product == "dsm":
        provider = kartograf.GugikNmptProvider(cache=cache)
    elif product == "orthophoto":
        provider = kartograf.GugikOrtoProvider(cache=cache)
    else:
        raise ValueError(f"Unsupported sheet product: {product}")
    return kartograf.DownloadManager(
        output_dir=output_dir,
        provider=provider,
        resolution=resolution,
        vertical_crs=vertical_crs,
    )


def download_dem_sheet(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Download one DEM sheet, or its 1:10000 descendants when coarser."""
    manager = _sheet_manager(
        "dem", output_dir, params["resolution"], params["vertical_crs"].upper()
    )
    selected = manager.download_sheet(params["area"]["code"])
    paths = [selected] if isinstance(selected, Path) else selected
    return _sheet_output(manager, paths, "dem")


def download_sheet_hierarchy(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Expand a parent sheet and download GUGiK DEM, DSM, or RGB orthophotos."""
    product = params["product"]
    resolution = params["resolution"] if product == "dem" else "1m"
    vertical_crs = params["vertical_crs"].upper() if product == "dem" else "EVRF2007"
    manager = _sheet_manager(product, output_dir, resolution, vertical_crs)
    target_scale = "1:" + params["target_scale"].removeprefix("scale_")
    paths = manager.download_hierarchy(params["area"]["code"], target_scale)
    return _sheet_output(manager, paths, product)


def download_elevation_cutout(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Download a 1 m WCS cutout; Kartograf masks pixels outside Polish land."""
    import kartograf

    target_crs = {
        "epsg_2180": "EPSG:2180",
        "epsg_5514": "EPSG:5514",
        "epsg_3045": "EPSG:3045",
    }[params["target_crs"]]
    product = params["product"]
    result = kartograf.download_pl_cutout(
        _bbox(params["area"]),
        target_crs,
        output_dir=output_dir,
        resolution="1m",
        vertical_crs=params["vertical_crs"].upper(),
        product={"dem": "nmt", "dsm": "nmpt"}[product],
    )
    warnings: list[HandlerWarning] = []
    if result.all_nodata:
        warnings.append({"key": "all_nodata", "args": {}})
    if result.masked_pixels:
        warnings.append(
            {"key": "masked_pixels", "args": {"count": str(result.masked_pixels)}}
        )
    return {
        "values": {
            "masked_pixels": result.masked_pixels,
            "all_nodata": result.all_nodata,
            "bytes": result.path.stat().st_size,
        },
        "files": {product: [result.path]},
        "warnings": warnings,
    }


def _extract_shapefiles(archive: Path, output_dir: Path) -> list[Path]:
    """Unpack Kartograf's SHP ZIP within the output tree, retaining sidecars."""
    import kartograf

    directory = archive.with_suffix("")
    resolved_output = output_dir.resolve()
    if not directory.resolve().is_relative_to(resolved_output):
        raise kartograf.DownloadError(_error_text("unsafe_archive"))
    with ZipFile(archive) as source:
        entries = source.infolist()
        for entry in entries:
            member = PurePosixPath(entry.filename)
            if (
                not entry.filename
                or "\\" in entry.filename
                or member.is_absolute()
                or ".." in member.parts
                or S_IFMT(entry.external_attr >> 16) == S_IFLNK
                or not (directory / member).resolve().is_relative_to(resolved_output)
            ):
                raise kartograf.DownloadError(_error_text("unsafe_archive"))
        directory.mkdir()
        source.extractall(directory)
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() == ".shp"
    )
    if not files:
        raise kartograf.DownloadError(_error_text("missing_shapefiles"))
    return files


def download_bdot10k(
    params: dict[str, Any], inputs: dict[str, Path], output_dir: Path
) -> HandlerOutput:
    """Download complete BDOT10k packages for all counties in the area."""
    import kartograf

    area = params["area"]
    if area["type"] == "teryt":
        cache = None
        teryts = [area["code"]]
    else:
        cache = kartograf.MetadataCache(db_path=output_dir / ".kartograf_cache.db")
        selection = (
            _bbox(area)
            if area["type"] == "bbox"
            else kartograf.SheetParser(area["code"]).get_bbox(crs="EPSG:2180")
        )
        teryts = kartograf.discover_teryts_for_bbox(selection, cache=cache)
        if not teryts:
            raise kartograf.NoCoverageError(_error_text("no_counties"))
    manager = kartograf.LandCoverManager(
        output_dir=output_dir, provider="bdot10k", cache=cache
    )
    file_format = params["format"].upper()
    files: list[Path] = []
    failed = 0
    for teryt in teryts:
        try:
            package = manager.download(teryt=teryt, format=file_format)
            if file_format == "SHP":
                shapefiles = _extract_shapefiles(package, output_dir)
        except (kartograf.DownloadError, BadZipFile):
            if len(teryts) == 1:
                raise
            failed += 1
            continue
        if file_format == "SHP":
            files.extend(shapefiles)
        else:
            files.append(package)
    if not files:
        raise kartograf.DownloadError(_error_text("all_counties_failed"))
    warnings: list[HandlerWarning] = []
    if failed:
        warnings.append(
            {
                "key": "failed_counties",
                "args": {"count": str(failed), "total": str(len(teryts))},
            }
        )
    return {
        "values": {
            "county_count": len(teryts) - failed,
            "missing_counties": failed,
            "bytes": sum(path.stat().st_size for path in files),
        },
        "files": {"topographic_vector": files},
        "warnings": warnings,
    }

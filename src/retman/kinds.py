"""Data kinds returned by tool handlers (ARCHITECTURE 3.2.6).

A kind is a name, the file extensions it accepts and an offline validator built
from the standard library only: no GIS or data libraries, no network.
"""

import codecs
import csv
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from retman.attribution import CSV_COLUMNS
from retman.exceptions import KindValidationError

# Validator of one file: ``None`` when valid, otherwise the failure reason, a key
# under ``kinds.errors`` in ``src/retman/i18n/pl.toml``. It may raise ``OSError``.
Check = Callable[[Path], str | None]


@dataclass(frozen=True)
class Kind:
    """A data kind: accepted file extensions and the validator of its files."""

    name: str
    extensions: tuple[str, ...]
    check: Check


# Bytes read to recognise a binary format; text formats are read by their helpers
_SIGNATURE_BYTES = 16
# Text probed for NUL bytes and for the first significant character
_TEXT_PROBE_BYTES = 4096
# Data rows of a CSV file compared with the header width (the header is row zero)
_CSV_ROWS_CHECKED = 5

_TIFF_SIGNATURES = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
_SQLITE_SIGNATURE = b"SQLite format 3\x00"
_ZIP_SIGNATURE = b"PK\x03\x04"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SHAPEFILE_CODE = (9994).to_bytes(4, "big")
_UTF8_BOM = b"\xef\xbb\xbf"

_RESULT_SCHEMA = "obserwator-result/1"
_PLAN_SCHEMA = "obserwator-plan/1"
_HYDROLOG_RESULT_SCHEMA = "hydrolog-result/1"
_HYDROLOG_NETWORK_SCHEMA = "hydrolog-network/1"
# The time column of every hydrograph table of Hydrolog (``route network
# --output-dir`` writes ``time_min,discharge_m3s``) and of its inflow tables, which
# add a discharge column per subcatchment
_HYDROGRAPH_TIME_COLUMN = "time_min"
# An SVG drawing, with or without the XML declaration
_SVG_START = re.compile(rb"\s*(<\?xml[^>]*>\s*)?(<!--.*?-->\s*)*<svg[\s>]", re.DOTALL)
# The keys every watershed of ``WatershedParameters.to_json()`` (Hydrolog) has; the
# document carries no ``schema`` key of its own
_WATERSHED_KEYS = (
    "area_km2",
    "perimeter_km",
    "length_km",
    "elevation_min_m",
    "elevation_max_m",
)

# Obserwator series export: ``date,year,<variable> [<unit>],<variable>_flag,...,
# attribution_source,attribution_processed``; ČHMÚ adds ``_quality`` and
# ``_source_flag`` columns after each variable
_SERIES_START = ("date", "year")
_SERIES_END = ("attribution_source", "attribution_processed")
_MEASUREMENT_COLUMN = re.compile(r"^(?P<variable>\S+) \[(?P<unit>[^\]]+)\]$")
# Hydrological variables of Obserwator: H, Q and T, with optional _min/_mean/_max
_HYDRO_VARIABLE = re.compile(r"^(H|Q|T)(_|$)")

_STATION_LIST_COLUMNS = (
    "provider",
    "kind",
    "station_code",
    "name",
    "river",
    "latitude",
    "longitude",
)
_PMAXTP_COLUMNS = (
    "duration_min",
    "probability_percent",
    "ks_mm",
    "sg_mm",
    "rb_mm",
    "attribution_source",
    "attribution_processed",
)
_ARCHIVE_RECORD_FIELDS = ("station_code", "dataset", "date")


def _read_header(path: Path) -> bytes:
    with path.open("rb") as source:
        return source.read(_SIGNATURE_BYTES)


def _check_signature(path: Path) -> str | None:
    """Binary formats: the signature of the file extension."""
    suffix = path.suffix.lower()
    header = _read_header(path)
    if suffix == ".asc":
        valid = header[:5].lower() == b"ncols" and header[5:6] in (b" ", b"\t")
    elif suffix == ".tif":
        valid = header[:4] in _TIFF_SIGNATURES
    elif suffix == ".gpkg":
        valid = header[:16] == _SQLITE_SIGNATURE
    elif suffix == ".shp":
        valid = header[:4] == _SHAPEFILE_CODE
    elif suffix == ".zip":
        valid = header[:4] == _ZIP_SIGNATURE
    elif suffix == ".png":
        valid = header[:8] == _PNG_SIGNATURE
    else:
        valid = False
    return None if valid else "invalid_header"


def _csv_head(path: Path) -> tuple[list[str], list[list[str]]] | str:
    """Header and the first data rows of a CSV file, or the failure reason.

    UTF-8 with or without a BOM, any line ending; blank lines are skipped. Only
    the beginning of the file is read.
    """
    rows: list[list[str]] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source)
            header = next(reader, None)
            if header is None:
                return "empty_file"
            for row in reader:
                if not row:
                    continue
                rows.append(row)
                if len(rows) == _CSV_ROWS_CHECKED:
                    break
    except UnicodeDecodeError:
        return "invalid_encoding"
    except csv.Error:
        return "invalid_rows"
    return header, rows


def _check_columns(
    header: list[str], rows: list[list[str]], required: Iterable[str]
) -> str | None:
    if not set(required) <= set(header):
        return "invalid_columns"
    if any(len(row) != len(header) for row in rows):
        return "invalid_rows"
    return None


def _csv_check(required: Iterable[str]) -> Check:
    """CSV file whose header holds the required columns (extra ones are fine)."""
    columns = tuple(required)

    def check(path: Path) -> str | None:
        head = _csv_head(path)
        if isinstance(head, str):
            return head
        header, rows = head
        return _check_columns(header, rows, columns)

    return check


def _series_check(*, hydrological: bool) -> Check:
    """Obserwator station series (``series export``): hydrological or meteorological.

    The trailing columns ``attribution`` and ``terms_notice`` of Nogat DEV-20.5 may
    follow the tool's own attribution columns.
    """

    def check(path: Path) -> str | None:
        head = _csv_head(path)
        if isinstance(head, str):
            return head
        header, rows = head
        own = (
            header[: -len(CSV_COLUMNS)] if header[-2:] == list(CSV_COLUMNS) else header
        )
        if (
            tuple(own[:2]) != _SERIES_START
            or tuple(own[-2:]) != _SERIES_END
            or len(own) <= len(_SERIES_START) + len(_SERIES_END)
        ):
            return "invalid_columns"
        variables = [
            match["variable"]
            for column in header
            if (match := _MEASUREMENT_COLUMN.match(column))
        ]
        if not variables or any(f"{name}_flag" not in header for name in variables):
            return "invalid_columns"
        # A hydrological file has H/Q/T variables, a meteorological one never does
        if any(_HYDRO_VARIABLE.match(name) for name in variables) != hydrological:
            return "invalid_columns"
        reason = _check_columns(header, rows, ())
        if reason is None and rows:
            try:
                date.fromisoformat(rows[0][0])
            except ValueError:
                return "invalid_rows"
        return reason

    return check


def _first_json_line(path: Path) -> object:
    """First non-blank line of a JSON Lines file parsed; ``ValueError`` if invalid."""
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                return json.loads(line)
    raise ValueError("no records")


def _check_archive_records(path: Path) -> str | None:
    """Obserwator ``store export``: CSV with a header or JSON Lines with records."""
    if path.suffix.lower() != ".jsonl":
        return _csv_check(_ARCHIVE_RECORD_FIELDS)(path)
    try:
        record = _first_json_line(path)
    except UnicodeDecodeError:
        return "invalid_encoding"
    except ValueError:
        # An empty file and a malformed first line differ only for the user
        return "empty_file" if path.stat().st_size == 0 else "invalid_json"
    if not isinstance(record, dict) or not set(_ARCHIVE_RECORD_FIELDS) <= set(record):
        return "invalid_schema"
    return None


def _first_text(path: Path) -> bytes:
    with path.open("rb") as source:
        return source.read(_TEXT_PROBE_BYTES).removeprefix(_UTF8_BOM)


def _check_obserwator_archive(path: Path) -> str | None:
    """Obserwator ``datasets download``: ZIP, JSON or plain text as published."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return _check_signature(path)
    text = _first_text(path)
    if not text.strip():
        return "empty_file"
    if suffix == ".json":
        return None if text.lstrip()[:1] in (b"{", b"[") else "invalid_json"
    # CSV and text archives come in the encoding of the source, so only a binary
    # file is rejected
    return "invalid_header" if b"\x00" in text else None


def _check_provider_attribution(path: Path) -> str | None:
    """``ATTRIBUTION.txt`` beside downloaded files: the providers' lines, UTF-8 text."""
    text = _first_text(path)
    if not text.strip():
        return "empty_file"
    try:
        # The probe may end inside a character; only a wrong byte before it counts
        codecs.getincrementaldecoder("utf-8")().decode(text)
    except UnicodeDecodeError:
        return "invalid_encoding"
    return "invalid_header" if b"\x00" in text else None


def _json_document_check(schema: str) -> Check:
    """JSON document that is an object with the given ``schema`` value."""

    def check(path: Path) -> str | None:
        if path.stat().st_size == 0:
            return "empty_file"
        try:
            document = json.loads(path.read_bytes())
        except ValueError:
            return "invalid_json"
        if not isinstance(document, dict) or document.get("schema") != schema:
            return "invalid_schema"
        return None

    return check


def _schema_first(schema: str) -> Check:
    """Check a tool's result document: its first key is ``schema`` of this value."""
    start = re.compile(
        rb'\s*\{\s*"schema"\s*:\s*"' + re.escape(schema.encode()) + rb'"'
    )

    def check(path: Path) -> str | None:
        head = _first_text(path)
        if not head.strip():
            return "empty_file"
        return None if start.match(head) else "invalid_schema"

    return check


def _check_watershed(path: Path) -> str | None:
    """Hydrolog watershed parameters: a JSON object with the five required keys."""
    if path.stat().st_size == 0:
        return "empty_file"
    try:
        document = json.loads(path.read_bytes())
    except ValueError:
        return "invalid_json"
    if not isinstance(document, dict) or not set(_WATERSHED_KEYS) <= set(document):
        return "invalid_schema"
    return None


def _check_svg(path: Path) -> str | None:
    """Check an SVG drawing: text whose first element is ``<svg``."""
    head = _first_text(path)
    if not head.strip():
        return "empty_file"
    return None if _SVG_START.match(head) else "invalid_header"


def _kinds(*kinds: Kind) -> dict[str, Kind]:
    return {kind.name: kind for kind in kinds}


KINDS: dict[str, Kind] = _kinds(
    # Kartograf (ADR-004)
    Kind("dem", (".asc", ".tif"), _check_signature),
    Kind("dsm", (".asc", ".tif"), _check_signature),
    Kind("orthophoto", (".tif",), _check_signature),
    Kind("topographic_vector", (".gpkg", ".shp"), _check_signature),
    # NMT 100 m: one ZIP per province holding an XYZ file
    Kind("dem_archive", (".zip",), _check_signature),
    # One SoilGrids property layer (GeoTIFF, values in the SoilGrids units) and the
    # hydrologic soil groups computed from the texture (GeoTIFF, classes 1-4 = A-D)
    Kind("soil_raster", (".tif",), _check_signature),
    Kind("hsg_raster", (".tif",), _check_signature),
    # CORINE Land Cover: class codes (GeoTIFF) or, without CLMS credentials, the
    # coloured WMS preview (PNG); BDOO: one ZIP of GML files per voivodeship
    Kind("landcover_raster", (".tif", ".png"), _check_signature),
    Kind("topographic_archive", (".zip",), _check_signature),
    # A user's file with the area geometry, checked like topographic_vector
    Kind("area_geometry", (".gpkg", ".shp"), _check_signature),
    # Obserwator: station lists, series, PMAXTP, live data, archives and reports
    Kind("station_list", (".csv",), _csv_check(_STATION_LIST_COLUMNS)),
    Kind("hydro_series", (".csv",), _series_check(hydrological=True)),
    Kind("meteo_series", (".csv",), _series_check(hydrological=False)),
    Kind("pmaxtp_table", (".csv",), _csv_check(_PMAXTP_COLUMNS)),
    Kind(
        "current_hydro",
        (".csv",),
        _csv_check(("station_code", "station_name", "water_level_cm", "flow_m3s")),
    ),
    Kind(
        "current_meteo",
        (".csv",),
        _csv_check(("station_code", "station_name", "air_temp_c", "wind_speed_ms")),
    ),
    Kind(
        "current_synop",
        (".csv",),
        _csv_check(
            ("station_code", "station_name", "measurement_date", "temperature_c")
        ),
    ),
    Kind("imgw_warnings", (".csv",), _csv_check(("id", "kind", "level"))),
    Kind(
        "hydro_states",
        (".csv",),
        _csv_check(("station_code", "name", "water_state")),
    ),
    Kind("archive_records", (".csv", ".jsonl"), _check_archive_records),
    Kind(
        "obserwator_archive",
        (".zip", ".json", ".csv", ".txt"),
        _check_obserwator_archive,
    ),
    Kind("obserwator_plan", (".json",), _json_document_check(_PLAN_SCHEMA)),
    Kind("obserwator_report", (".json",), _schema_first(_RESULT_SCHEMA)),
    # The providers' attribution lines a tool writes beside the files of a plain
    # download (``ATTRIBUTION.txt``, Nogat DEV-20.5)
    Kind("provider_attribution", (".txt",), _check_provider_attribution),
    # Hydrolog: the parameters of a watershed (``WatershedParameters.to_json()``, from
    # Hydrograf or written by hand) and the result document of a computation
    Kind("watershed_parameters", (".json",), _check_watershed),
    Kind("hydrolog_report", (".json",), _schema_first(_HYDROLOG_RESULT_SCHEMA)),
    # The river network ``route network`` reads, a hydrograph table (one per node of
    # a routed network, or the inflows of its subcatchments) and the schematic of a
    # network drawn by Hydrolog
    Kind(
        "hydrolog_network", (".json",), _json_document_check(_HYDROLOG_NETWORK_SCHEMA)
    ),
    Kind("hydrograph_table", (".csv",), _csv_check((_HYDROGRAPH_TIME_COLUMN,))),
    Kind("network_schematic", (".svg",), _check_svg),
)


def validate_file(kind: str, path: Path) -> None:
    """Check an output file's extension and format without GIS libraries.

    Binary formats are recognised by their signature; text formats (CSV, JSON)
    by their header, required columns or ``schema`` and the first rows only.

    Parameters
    ----------
    kind : str
        Declared data kind.
    path : Path
        File returned by a tool handler.

    Raises
    ------
    KindValidationError
        Unknown kind, missing file, unsupported extension, unreadable file or
        content that does not match the kind (``reason`` names the failure).
    """
    spec = KINDS.get(kind)
    if spec is None:
        raise KindValidationError(kind, path, "unknown_kind")
    if not path.is_file():
        raise KindValidationError(kind, path, "missing_file")
    if path.suffix.lower() not in spec.extensions:
        raise KindValidationError(kind, path, "unsupported_extension")
    try:
        reason = spec.check(path)
    except OSError as error:
        raise KindValidationError(kind, path, "unreadable_file") from error
    if reason is not None:
        raise KindValidationError(kind, path, reason)

"""Read Polish map sheet codes and spatial areas without importing a tool."""

import math
import re
from typing import Any, TypeGuard

from retman.extractors.base import Match, Reading
from retman.extractors.paths import extract_paths

# Copied from Kartograf 0.7.2: core/sheet_parser.py:82-93,109-112,185-226,
# 308-330 and core/parser_2000.py:86-93,188-204. This module must not import
# Kartograf: merely interpreting the user's command must work without tools.
_PL1992_PATTERNS = (
    r"[A-Z]-[0-9]{1,2}",
    r"[A-Z]-[0-9]{1,2}-[A-D]",
    r"[A-Z]-[0-9]{1,2}-[0-9]{1,3}",
    r"[A-Z]-[0-9]{1,2}-[0-9]{1,3}-[A-D]",
    r"[A-Z]-[0-9]{1,2}-[0-9]{1,3}-[A-D]-[a-d]",
    r"[A-Z]-[0-9]{1,2}-[0-9]{1,3}-[A-D]-[a-d]-[1-4]",
    r"[A-Z]-[0-9]{1,2}-[0-9]{1,3}-[A-D]-[a-d]-[1-4]-[1-4]",
)
_PL2000_PATTERNS = (
    r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}",
    r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}\.[1-4]",
    r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}\.[0-9]{2}",
    r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}\.[0-9]{2}\.[1-4]",
    r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}\.[0-9]{2}\.[1-4]\.[1-4]",
)
_PL1992_CANDIDATE = r"[A-Za-z]-[0-9]{1,2}(?:-[A-Za-z0-9]{1,3}){0,5}"
_PL2000_CANDIDATE = r"[5-8]\.[0-9]{1,3}\.[0-9]{1,2}(?:\.[0-9]{1,2}){0,3}"
_SHEET_RE = re.compile(
    rf"(?<![\w.-])(?:{_PL1992_CANDIDATE}|{_PL2000_CANDIDATE})(?![\w-]|\.[\w])"
)
_TERYT_RE = re.compile(
    r"(?<!\w)(?:powiat(?:u|em|owi|ach)?|teryt|kod(?:zie|em|u)?)\b"
    r"(?:\s+(?:nr|numer|teryt|powiatu|kod))?\s*[:#=\-]?\s*"
    r"(?P<code>[0-9]{4})(?!\w|\.\w)",
    re.IGNORECASE,
)

# Kartograf 0.7.2: core/bbox.py:36-43 and cli/_parser.py:49-90,170-189.
# The BBox fields follow GIS/CLI order: x = easting or longitude; y = northing
# or latitude (pyproj's always_xy, not EPSG:2180's official axis names).
_NUMBER = r"[0-9]+(?:[.,][0-9]{1,3})?"
_LABEL = r"(?P<label{n}>[xy])\s*[:=]\s*|(?P<direction{n}>[EN])(?:\s*[:=]\s*|\s+)"
_COORD = r"(?:(?:{label}))?(?P<value{n}>{number})"
_SEPARATOR = r"(?:\s*(?:[,;–-]|\bdo\b)\s*|\s+)"
_COORDS_RE = re.compile(
    r"(?<![\w.-])(?P<coords>(?:od\s+)?"
    + _SEPARATOR.join(
        _COORD.format(label=_LABEL.format(n=index), n=index, number=_NUMBER)
        for index in range(4)
    )
    + r")(?!\w|[,-]\s*[0-9]|\.\w)",
    re.IGNORECASE,
)
_RANGE_LABEL = (
    r"(?:(?P<label{n}>[xy])\s*[:=]\s*|(?P<direction{n}>[EN])(?:\s*[:=]\s*|\s+))?"
)
_RANGES_RE = re.compile(
    r"(?<![\w.-])(?P<coords>(?:od\s+)?"
    + _RANGE_LABEL.format(n=0)
    + rf"(?P<low0>{_NUMBER})\s*[-–]\s*(?P<high0>{_NUMBER})"
    + r"(?:\s*[,;]\s*|\s+do\s+|\s+)"
    + _RANGE_LABEL.format(n=1)
    + rf"(?P<low1>{_NUMBER})\s*[-–]\s*(?P<high1>{_NUMBER}))"
    + r"(?!\w|[,-]\s*[0-9]|\.\w)",
    re.IGNORECASE,
)

# Conservative EPSG:2180 envelope of the WGS84 Poland range, rounded outwards.
# Geographic ranges deliberately do not overlap (latitudes 49-55, lon 14-24.2).
_LATITUDE = (49.0, 55.0)
_LONGITUDE = (14.0, 24.2)
_EASTING_M = (120_000.0, 900_000.0)
_NORTHING_M = (110_000.0, 830_000.0)


def _valid_sheet(code: str) -> bool:
    if "." in code:
        if not any(re.fullmatch(pattern, code) for pattern in _PL2000_PATTERNS):
            return False
        components = code.split(".")
        if len(components) > 3 and len(components[3]) == 2:
            return 1 <= int(components[3]) <= 25
        return True
    if not any(re.fullmatch(pattern, code) for pattern in _PL1992_PATTERNS):
        return False
    parts = code.split("-")
    return (
        parts[0] in ("M", "N")
        and 33 <= int(parts[1]) <= 35
        and (len(parts) < 3 or not parts[2].isdigit() or 1 <= int(parts[2]) <= 144)
    )


def _normalize_sheet(code: str) -> str:
    if "." in code:
        return code
    parts = code.split("-")
    parts[0] = parts[0].upper()
    if len(parts) > 2 and parts[2].isalpha():
        parts[2] = parts[2].upper()
    if len(parts) > 3:
        parts[3] = parts[3].upper()
    if len(parts) > 4:
        parts[4] = parts[4].lower()
    return "-".join(
        part.lstrip("0") or "0" if part.isascii() and part.isdigit() else part
        for part in parts
    )


def _in_range(value: float, limits: tuple[float, float]) -> bool:
    return limits[0] <= value <= limits[1]


def _bbox(x0: float, y0: float, x1: float, y1: float, crs: str) -> dict[str, Any]:
    return {
        "type": "bbox",
        "min_x": x0,
        "min_y": y0,
        "max_x": x1,
        "max_y": y1,
        "crs": crs,
    }


def _reading(bbox: dict[str, Any], key: str) -> Reading:
    return Reading(
        bbox,
        f"extractors.area.{key}",
        {name: f"{bbox[name]:g}" for name in ("min_x", "min_y", "max_x", "max_y")},
    )


def _bbox_readings(
    values: tuple[float, float, float, float], labels: tuple[str | None, ...]
) -> tuple[Reading, ...]:
    first, second, third, fourth = values
    if all(_in_range(v, _LONGITUDE) for v in (first, third)) and all(
        _in_range(v, _LATITUDE) for v in (second, fourth)
    ):
        if any(
            label is not None and label != expected
            for label, expected in zip(labels, ("x", "y", "x", "y"), strict=True)
        ):
            return ()
        return (
            _reading(
                _bbox(first, second, third, fourth, "EPSG:4326"), "bbox_4326_lon_lat"
            ),
        )
    if all(_in_range(v, _LATITUDE) for v in (first, third)) and all(
        _in_range(v, _LONGITUDE) for v in (second, fourth)
    ):
        if any(
            label is not None and label != expected
            for label, expected in zip(labels, ("y", "x", "y", "x"), strict=True)
        ):
            return ()
        return (
            _reading(
                _bbox(second, first, fourth, third, "EPSG:4326"), "bbox_4326_lat_lon"
            ),
        )
    if not all(_in_range(v, (110_000.0, 900_000.0)) for v in values):
        return ()
    readings = []
    for expected, coords, key in (
        (("x", "y", "x", "y"), (first, second, third, fourth), "bbox_2180"),
        (("y", "x", "y", "x"), (second, first, fourth, third), "bbox_2180_swapped"),
    ):
        if all(
            label is None or label == axis
            for label, axis in zip(labels, expected, strict=True)
        ):
            readings.append(_reading(_bbox(*coords, "EPSG:2180"), key))
    return tuple(readings)


def _label(match: re.Match[str], index: int) -> str | None:
    letter = match.group(f"label{index}") or match.group(f"direction{index}")
    if letter is None:
        return None
    return "x" if letter.lower() in ("x", "e") else "y"


def _number(token: str) -> float:
    return float(token.replace(",", "."))


def _overlaps(start: int, end: int, matches: list[Match]) -> bool:
    return any(start < match.end and end > match.start for match in matches)


def extract_area(text: str) -> list[Match]:
    """
    Extract sheet identifiers, TERYT counties, bboxes and geometry paths.

    Parameters
    ----------
    text : str
        Command or an answer to a parameter question.

    Returns
    -------
    list[Match]
        Spans ordered as in the text; ambiguous projected bboxes have two readings.
    """
    matches: list[Match] = []
    for found in _SHEET_RE.finditer(text):
        code = _normalize_sheet(found.group())
        if _valid_sheet(code):
            matches.append(
                Match(
                    found.start(),
                    found.end(),
                    (
                        Reading(
                            {"type": "sheet", "code": code},
                            "extractors.area.sheet",
                            {"code": code},
                        ),
                    ),
                )
            )
    for found in _TERYT_RE.finditer(text):
        code = found.group("code")
        matches.append(
            Match(
                found.start(),
                found.end(),
                (
                    Reading(
                        {"type": "teryt", "code": code},
                        "extractors.area.teryt",
                        {"code": code},
                    ),
                ),
            )
        )
    for found in _RANGES_RE.finditer(text):
        label0, label1 = _label(found, 0), _label(found, 1)
        values = (
            _number(found.group("low0")),
            _number(found.group("low1")),
            _number(found.group("high0")),
            _number(found.group("high1")),
        )
        labels = (label0, label1, label0, label1)
        readings = _bbox_readings(values, labels)
        if readings:
            matches.append(Match(found.start(), found.end(), readings))
    for found in _COORDS_RE.finditer(text):
        if _overlaps(found.start(), found.end(), matches):
            continue
        values = (
            _number(found.group("value0")),
            _number(found.group("value1")),
            _number(found.group("value2")),
            _number(found.group("value3")),
        )
        labels = (
            _label(found, 0),
            _label(found, 1),
            _label(found, 2),
            _label(found, 3),
        )
        readings = _bbox_readings(values, labels)
        if readings:
            matches.append(Match(found.start(), found.end(), readings))
    for match in extract_paths(text):
        path = match.readings[0].value
        if path.lower().endswith((".shp", ".gpkg")):
            matches.append(
                Match(
                    match.start,
                    match.end,
                    (
                        Reading(
                            {"type": "geometry", "path": path},
                            "extractors.area.geometry",
                            {"path": path},
                        ),
                    ),
                )
            )
    return sorted(matches, key=lambda match: match.start)


def _valid_bbox_numbers(
    values: tuple[Any, Any, Any, Any],
) -> TypeGuard[tuple[float, float, float, float]]:
    return all(
        type(number) in (int, float) and math.isfinite(number) for number in values
    )


def validate_area(value: Any) -> str | None:
    """Return a translation error key for an invalid area, otherwise ``None``."""
    if not isinstance(value, dict):
        return "extractors.errors.invalid_area"
    area_type = value.get("type")
    if area_type == "sheet":
        code = value.get("code")
        return (
            None
            if isinstance(code, str) and _valid_sheet(code)
            else "extractors.errors.invalid_sheet"
        )
    if area_type == "teryt":
        code = value.get("code")
        return (
            None
            if isinstance(code, str) and re.fullmatch(r"[0-9]{4}", code)
            else "extractors.errors.invalid_teryt"
        )
    if area_type == "geometry":
        path = value.get("path")
        return (
            None
            if isinstance(path, str) and path.lower().endswith((".shp", ".gpkg"))
            else "extractors.errors.invalid_geometry"
        )
    if area_type != "bbox":
        return "extractors.errors.invalid_area"
    numbers = (
        value.get("min_x"),
        value.get("min_y"),
        value.get("max_x"),
        value.get("max_y"),
    )
    if not _valid_bbox_numbers(numbers):
        return "extractors.errors.invalid_bbox"
    min_x, min_y, max_x, max_y = numbers
    if min_x >= max_x or min_y >= max_y:
        return "extractors.errors.invalid_bbox_order"
    crs = value.get("crs")
    if crs == "EPSG:4326":
        x_limits, y_limits = _LONGITUDE, _LATITUDE
    elif crs == "EPSG:2180":
        x_limits, y_limits = _EASTING_M, _NORTHING_M
    else:
        return "extractors.errors.invalid_bbox"
    if not all(
        (
            _in_range(min_x, x_limits),
            _in_range(max_x, x_limits),
            _in_range(min_y, y_limits),
            _in_range(max_y, y_limits),
        )
    ):
        return "extractors.errors.outside_poland"
    return None

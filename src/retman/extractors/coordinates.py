"""Read points and PMAXTP grid cells from a command, without importing a tool.

A point is a WGS84 latitude/longitude or a PL-1992 (EPSG:2180) easting/northing
pair. Axis order is never guessed: labels and the disjoint ranges of the PMAXTP
frame decide it, and a pair that fits both orders gives two readings, so Retman
asks (W-02, ARCHITECTURE 6.1). PL-1992 is converted here in pure Python, so
interpreting a command needs neither pyproj nor the tool.

PL-1992 coordinates follow the GIS convention of ``areas``: ``x``/``E`` is the
easting and ``y``/``N`` the northing (EPSG:2180 itself names the axes the other
way round); the plan always shows how a pair was read.
"""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeGuard

from retman.extractors.areas import extract_area
from retman.extractors.base import Match, Reading, TextSource
from retman.extractors.text import (
    Word,
    equals_within_one_edit,
    fold,
    starts_within_one_edit,
    words,
)

# The tool's own catalog limits of PMAXTP points (``pmaxtp fetch``).
PMAXTP_LATITUDE: tuple[float, float] = (49.0, 55.0)
PMAXTP_LONGITUDE: tuple[float, float] = (14.0, 24.5)

# EPSG:2180 (PL-1992): Transverse Mercator on GRS80, central meridian 19°E.
_A = 6378137.0
_F = 1 / 298.257222101
_K0 = 0.9993
_LON0 = 19.0
_FALSE_EASTING = 500_000.0
_FALSE_NORTHING = -5_300_000.0

_E2 = _F * (2 - _F)
_E = math.sqrt(_E2)
_N = _F / (2 - _F)
# Rectifying radius and the Krüger n-series to order n^6 (Karney 2011,
# "Transverse Mercator with an accuracy of a few nanometers", eqs. 14, 35, 36).
_RADIUS = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64 + _N**6 / 256)
_ALPHA = (
    _N / 2
    - 2 / 3 * _N**2
    + 5 / 16 * _N**3
    + 41 / 180 * _N**4
    - 127 / 288 * _N**5
    + 7891 / 37800 * _N**6,
    13 / 48 * _N**2
    - 3 / 5 * _N**3
    + 557 / 1440 * _N**4
    + 281 / 630 * _N**5
    - 1983433 / 1935360 * _N**6,
    61 / 240 * _N**3
    - 103 / 140 * _N**4
    + 15061 / 26880 * _N**5
    + 167603 / 181440 * _N**6,
    49561 / 161280 * _N**4 - 179 / 168 * _N**5 + 6601661 / 7257600 * _N**6,
    34729 / 80640 * _N**5 - 3418889 / 1995840 * _N**6,
    212378941 / 319334400 * _N**6,
)
_BETA = (
    _N / 2
    - 2 / 3 * _N**2
    + 37 / 96 * _N**3
    - 1 / 360 * _N**4
    - 81 / 512 * _N**5
    + 96199 / 604800 * _N**6,
    1 / 48 * _N**2
    + 1 / 15 * _N**3
    - 437 / 1440 * _N**4
    + 46 / 105 * _N**5
    - 1118711 / 3870720 * _N**6,
    17 / 480 * _N**3 - 37 / 840 * _N**4 - 209 / 4480 * _N**5 + 5569 / 90720 * _N**6,
    4397 / 161280 * _N**4 - 11 / 504 * _N**5 - 830251 / 7257600 * _N**6,
    4583 / 161280 * _N**5 - 108847 / 3991680 * _N**6,
    20648693 / 638668800 * _N**6,
)


def _tau_prime(tau: float) -> float:
    """Tangent of the conformal latitude for the tangent of the geodetic one."""
    root = math.hypot(1.0, tau)
    sigma = math.sinh(_E * math.atanh(_E * tau / root))
    return tau * math.hypot(1.0, sigma) - sigma * root


def _tau(tau_prime: float) -> float:
    """Tangent of the geodetic latitude for the conformal one (Newton steps)."""
    tau = tau_prime
    for _ in range(20):
        current = _tau_prime(tau)
        step = (
            (tau_prime - current)
            * (1 + (1 - _E2) * tau**2)
            / ((1 - _E2) * math.hypot(1.0, tau) * math.hypot(1.0, current))
        )
        tau += step
        if abs(step) < 1e-15 * max(1.0, abs(tau)):
            break
    return tau


def wgs84_to_pl1992(latitude: float, longitude: float) -> tuple[float, float]:
    """
    Convert WGS84 degrees to PL-1992 (EPSG:2180) metres.

    WGS84 is treated as GRS80 (the ellipsoids differ by less than 0.2 mm).
    The series are accurate to nanometres within 35° of the central meridian
    (19°E), so the whole of Poland and its surroundings are covered.

    Parameters
    ----------
    latitude, longitude : float
        Degrees; latitude within ±90° and at most 35° from 19°E.

    Returns
    -------
    tuple[float, float]
        ``(easting, northing)`` in metres (GIS order: x = easting, y = northing).

    Raises
    ------
    ValueError
        If an argument is not finite or outside the supported range.

    Examples
    --------
    >>> easting, northing = wgs84_to_pl1992(52.2297, 21.0122)
    >>> round(easting, 3), round(northing, 3)
    (637382.204, 486757.209)
    """
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        raise ValueError("coordinates must be finite")
    if abs(latitude) > 90 or abs(longitude - _LON0) > 35:
        raise ValueError("point outside the range of the series")
    phi = math.radians(latitude)
    lam = math.radians(longitude - _LON0)
    tau_prime = _tau_prime(math.tan(phi))
    xi0 = math.atan2(tau_prime, math.cos(lam))
    eta0 = math.asinh(math.sin(lam) / math.hypot(tau_prime, math.cos(lam)))
    xi, eta = xi0, eta0
    for j, alpha in enumerate(_ALPHA, 1):
        xi += alpha * math.sin(2 * j * xi0) * math.cosh(2 * j * eta0)
        eta += alpha * math.cos(2 * j * xi0) * math.sinh(2 * j * eta0)
    return (
        _FALSE_EASTING + _K0 * _RADIUS * eta,
        _FALSE_NORTHING + _K0 * _RADIUS * xi,
    )


def pl1992_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """
    Convert PL-1992 (EPSG:2180) metres to WGS84 degrees.

    Inverse of :func:`wgs84_to_pl1992` (same accuracy and ellipsoid remark).

    Parameters
    ----------
    easting, northing : float
        Metres (GIS order: x = easting, y = northing).

    Returns
    -------
    tuple[float, float]
        ``(latitude, longitude)`` in degrees.

    Raises
    ------
    ValueError
        If an argument is not finite or the point is more than 35° from the
        central meridian.

    Examples
    --------
    >>> latitude, longitude = pl1992_to_wgs84(637382.204, 486757.209)
    >>> round(latitude, 4), round(longitude, 4)
    (52.2297, 21.0122)
    """
    if not (math.isfinite(easting) and math.isfinite(northing)):
        raise ValueError("coordinates must be finite")
    xi = (northing - _FALSE_NORTHING) / (_K0 * _RADIUS)
    eta = (easting - _FALSE_EASTING) / (_K0 * _RADIUS)
    xi0, eta0 = xi, eta
    for j, beta in enumerate(_BETA, 1):
        xi0 -= beta * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta0 -= beta * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    lam = math.atan2(math.sinh(eta0), math.cos(xi0))
    if abs(math.degrees(lam)) > 35:
        raise ValueError("point outside the range of the series")
    tau_prime = math.sin(xi0) / math.hypot(math.sinh(eta0), math.cos(xi0))
    return math.degrees(math.atan(_tau(tau_prime))), _LON0 + math.degrees(lam)


# Envelope of PL-1992 points, the constants of ``areas`` (conservative, rounded
# outwards); the digits of a coordinate are always six.
_EASTING_M = (120_000.0, 900_000.0)
_NORTHING_M = (110_000.0, 830_000.0)
_PROJECTED_MIN, _PROJECTED_MAX = 110_000.0, 900_000.0
_PROJECTED_DIGITS = 6

# Folding turns some signs into letters or blanks; commands also use typographic
# primes and the masculine ordinal indicator for degrees.
_CANONICAL_SIGNS = {
    "º": "°",
    "˚": "°",
    "′": "'",
    "ʹ": "'",
    "’": "'",
    "‘": "'",
    "´": "'",
    "″": '"',
    "ʺ": '"',
    "”": '"',
    "“": '"',
    "−": "-",
}


def _compile(pattern: str) -> re.Pattern[str]:
    """Pattern for folded text: digits, spaces and word edges are ASCII-only."""
    return re.compile(pattern, re.ASCII)


_MINUTES = r"\d{1,2}(?:[.,]\d+)?"
# A number with an optional sign, decimal part and degrees/minutes/seconds. It
# must not continue as another number ("12.10.2020", "6.179.12" are dates and
# sheets, not coordinates) nor be glued to letters (units, "2x3"), except for a
# standalone hemisphere letter.
_NUMBER_RE = _compile(
    r"(?<![a-z0-9_.])(?P<sign>-)?(?P<int>\d+)(?:[.,](?P<frac>\d+))?"
    rf"(?P<dms>\s*°(?:\s*(?P<min>{_MINUTES})\s*'"
    rf"(?:\s*(?P<sec>{_MINUTES})\s*(?:\"|''))?)?)?"
    r"(?(frac)(?!\d|\.\d)|(?!\d|[.,]\d))"
    r"(?:(?![a-z0-9_])|(?=[ne](?![a-z0-9_])))"
)
_TAIL_WORD_RE = _compile(r"(?<![a-z0-9_])(?P<word>[a-z]+)(?P<gap>[\s:=.]*)\Z")
_HEADER_RE = _compile(r"(?<![a-z0-9_])(?P<word>[a-z]+)[\s/,]+\Z")
_LABEL_WORD_RE = _compile(r"(?<![a-z0-9_])(?P<word>[a-z]+)\s+\Z")
_TRAIL_RE = _compile(r"\s*(?P<letter>[ne])(?![a-z0-9_])")
_FOREIGN_HEMISPHERE_RE = _compile(r"\s?[SW](?![A-Za-z0-9_])")
_SEPARATOR_RE = _compile(r"\s*(?:[,;/&]|\b(?:i|oraz|and)\b)?\s*")
_CRS_NAME = (
    r"(?<![a-z0-9])(?:wgs\s*-?\s*84|epsg\s*[:\-]?\s*(?:4326|2180)"
    r"|pl\s*-?\s*1992|puwg(?:\s*-?\s*(?:19)?92)?)"
)
_CRS_BEFORE_RE = _compile(_CRS_NAME + r"[\s,;:.)\]-]*\Z")
_CRS_AFTER_RE = _compile(
    r"[\s,;:(\[-]*(?:(?:w|we|na|uklad\w*|crs)\s+){0,2}" + _CRS_NAME + r"(?![a-z0-9])"
)

# Words that make a bare pair of numbers a point; one typo is tolerated in the
# stems (>= 5 letters), short words match exactly.
_MARKER_STEMS = ("punkt", "wspolrzedn", "lokalizacj")
_MARKER_WORDS = frozenset({"wsp", "wgs84", "gps"})
_FILLER_WORDS = frozenset(
    {"o", "w", "we", "na", "dla", "z", "ze", "to", "jest", "sa", "geograficzne"}
    | {"geograficznych", "geograficzna", "geograficznej"}
)
# Labels of the axes (a typo is tolerated in the long ones). Abbreviations also
# mean other things ("lat" = years), so they need a colon, an equals sign, a dot
# or a decimal number after them.
_LATITUDE_WORDS = ("szerokosc", "szerokosci", "szerokoscia", "latitude")
_LONGITUDE_WORDS = ("dlugosc", "dlugosci", "dlugoscia", "longitude")
_SHORT_LATITUDE = frozenset({"szer", "lat"})
_SHORT_LONGITUDE = frozenset({"dl", "lon", "lng", "long"})
_NORTH = frozenset({"lat", "N", "y"})  # tags of the latitude / northing
_FRAME_WORD = "geograficzn"  # "szerokości geograficznej 52.23"


@dataclass(frozen=True)
class _Number:
    """A number of the command that may be (a part of) a coordinate."""

    start: int
    end: int
    value: float
    kind: str  # "integer", "decimal" or "dms" (a degree sign was written)
    digits: int  # digits before the decimal separator
    negative: bool


@dataclass(frozen=True)
class _Mark:
    """A label or a hemisphere letter next to a number."""

    tag: str  # "lat", "lon", "x", "y", "N" or "E"
    start: int
    end: int
    letter: bool  # a plain letter, which may belong to the neighbouring number
    second: str | None = None  # header ("lat/lon 52 21"): tag of the next number


@dataclass(frozen=True)
class _Context:
    text: str
    canon: str
    words: list[Word]
    lax: bool


def _canonical(text: str) -> str:
    """Folded text with the same positions and a few signs normalized."""
    folded = fold(text)
    return "".join(
        _CANONICAL_SIGNS.get(char, plain)
        for char, plain in zip(text, folded, strict=True)
    )


def _decimal(token: str) -> float:
    return float(token.replace(",", "."))


def _numbers(ctx: _Context, skipped: list[tuple[int, int]]) -> list[_Number]:
    """Numbers of the text that can be coordinates, in order of appearance."""
    found: list[_Number] = []
    for match in _NUMBER_RE.finditer(ctx.canon):
        start, end = match.span()
        if any(start < stop and end > begin for begin, stop in skipped):
            continue
        if ctx.canon[end : end + 8].lstrip()[:1] in ("%", "‰"):
            continue
        if match.group("dms") is None and ctx.canon[end : end + 1] == "°":
            continue  # "25°C": a degree sign that continues as something else
        integer, fraction = match.group("int"), match.group("frac")
        if (
            match.group("dms") is None
            and match.group("sign") is None
            and fraction is not None
            and len(integer) == len(fraction) == _PROJECTED_DIGITS
            and ctx.canon[start + _PROJECTED_DIGITS] == ","
            and _PROJECTED_MIN <= float(integer) <= _PROJECTED_MAX
            and _PROJECTED_MIN <= float(fraction) <= _PROJECTED_MAX
        ):
            # "637382,486757": a pair without a space, not metres to the micrometre
            digits = _PROJECTED_DIGITS
            found.append(
                _Number(start, start + digits, float(integer), "integer", digits, False)
            )
            found.append(
                _Number(end - digits, end, float(fraction), "integer", digits, False)
            )
            continue
        degrees = _decimal(
            match.group("int")
            + ("." + match.group("frac") if match.group("frac") else "")
        )
        kind = "decimal" if match.group("frac") else "integer"
        if match.group("dms") is not None:
            kind = "dms"
            minutes = match.group("min")
            seconds = match.group("sec")
            if minutes is not None:
                if _decimal(minutes) >= 60 or (seconds and _decimal(seconds) >= 60):
                    continue
                degrees += _decimal(minutes) / 60
                if seconds is not None:
                    degrees += _decimal(seconds) / 3600
                degrees = round(degrees, 9)
        negative = match.group("sign") is not None
        found.append(
            _Number(
                start,
                end,
                -degrees if negative else degrees,
                kind,
                len(match.group("int")),
                negative,
            )
        )
    return found


def _axis_word(word: str) -> str | None:
    """Axis of a spelled-out label ("szerokość", "longitude"); one typo allowed."""
    if any(equals_within_one_edit(word, name) for name in _LATITUDE_WORDS):
        return "lat"
    if any(equals_within_one_edit(word, name) for name in _LONGITUDE_WORDS):
        return "lon"
    return None


def _label_tag(word: str, gap: str, number: _Number, lax: bool) -> str | None:
    """Axis tag a word before a number gives, or None for an ordinary word."""
    if word in ("x", "y"):
        return word if ":" in gap or "=" in gap or lax else None
    axis = _axis_word(word)
    short = word in _SHORT_LATITUDE | _SHORT_LONGITUDE
    if (
        axis is None
        and short
        and (any(char in gap for char in ":=.") or number.kind != "integer" or lax)
    ):
        axis = "lat" if word in _SHORT_LATITUDE else "lon"
    return axis


def _lead(ctx: _Context, number: _Number, floor: int) -> _Mark | None:
    """Label or hemisphere letter right before the number (after ``floor``)."""
    base = max(floor, number.start - 80)
    region = ctx.canon[base : number.start]
    found = _TAIL_WORD_RE.search(region)
    if found is None:
        return None
    word, gap = found.group("word"), found.group("gap")
    start = base + found.start("word")
    if word in ("n", "e") and "." not in gap:
        return _Mark(
            word.upper(), start, number.start, ":" not in gap and "=" not in gap
        )
    if starts_within_one_edit(word, _FRAME_WORD):
        # "szerokości geograficznej 52.23": the label stands before the adjective
        longer = _LABEL_WORD_RE.search(region[: found.start("word")])
        tag = _axis_word(longer.group("word")) if longer else None
        if longer is not None and tag is not None:
            start = base + longer.start("word")
    else:
        tag = _label_tag(word, gap, number, ctx.lax)
    if tag is None:
        return None
    header = _HEADER_RE.search(ctx.canon[base:start])
    if header is not None:
        first = _label_tag(header.group("word"), gap, number, ctx.lax)
        if first is not None and (first in _NORTH) != (tag in _NORTH):
            return _Mark(first, base + header.start("word"), number.start, False, tag)
    return _Mark(tag, start, number.start, False)


def _trail(ctx: _Context, number: _Number) -> _Mark | None:
    """Hemisphere letter right after the number."""
    found = _TRAIL_RE.match(ctx.canon, number.end)
    if found is None:
        return None
    return _Mark(
        found.group("letter").upper(), found.start("letter"), found.end(), True
    )


def _is_marker(word: str) -> bool:
    return word in _MARKER_WORDS or any(
        starts_within_one_edit(word, stem) for stem in _MARKER_STEMS
    )


def _marker_context(ctx: _Context, start: int, end: int) -> bool:
    """Whether words around the pair ("punkt", "WGS84") say it is a point."""
    if _CRS_BEFORE_RE.search(ctx.canon[max(0, start - 60) : start]):
        return True
    before = [word for word in ctx.words if word.end <= start][-5:]
    for word in reversed(before):
        if _is_marker(word.text):
            return True
        if word.text not in _FILLER_WORDS:
            break
    return _CRS_AFTER_RE.match(ctx.canon, end) is not None


def _degrees(value: float) -> str:
    """Degrees for the user: up to six decimals, no trailing zeros."""
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _metres(value: float) -> str:
    """Metres for the user: up to two decimals, no trailing zeros."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _in_range(value: float, limits: tuple[float, float]) -> bool:
    return limits[0] <= value <= limits[1]


def _group(tags: list[str], *, projected: bool) -> tuple[str | None, bool]:
    """Axis group ("north" or "east") the tags of one number agree on."""
    groups = set()
    for tag in tags:
        if projected and tag in ("lat", "lon"):
            return None, False
        groups.add("north" if tag in _NORTH else "east")
    if len(groups) > 1:
        return None, False
    return (groups.pop() if groups else None), True


def _wgs84_reading(
    latitude: _Number, longitude: _Number, latitude_first: bool
) -> Reading:
    value: dict[str, Any] = {
        "type": "point",
        "latitude": float(latitude.value),
        "longitude": float(longitude.value),
        "input_crs": "EPSG:4326",
    }
    key = "wgs84_lat_lon" if latitude_first else "wgs84_lon_lat"
    return Reading(
        value,
        f"extractors.point.{key}",
        {
            "latitude": _degrees(value["latitude"]),
            "longitude": _degrees(value["longitude"]),
        },
    )


def _pl1992_reading(easting: float, northing: float, easting_first: bool) -> Reading:
    latitude, longitude = pl1992_to_wgs84(easting, northing)
    value: dict[str, Any] = {
        "type": "point",
        "latitude": round(latitude, 9),
        "longitude": round(longitude, 9),
        "input_crs": "EPSG:2180",
        "easting": easting,
        "northing": northing,
    }
    key = "pl1992_en" if easting_first else "pl1992_ne"
    return Reading(
        value,
        f"extractors.point.{key}",
        {
            "easting": _metres(easting),
            "northing": _metres(northing),
            "latitude": _degrees(value["latitude"]),
            "longitude": _degrees(value["longitude"]),
        },
    )


def _orders(
    first: _Number,
    second: _Number,
    tags: tuple[list[str], list[str]],
    explicit: bool,
    *,
    projected: bool,
) -> tuple[list[tuple[_Number, _Number, bool]], bool]:
    """Candidates ``(north, east, north_first)`` of a pair and whether labels
    decided the order; none when the labels contradict each other or a pair
    without a marker is not made of decimals."""
    group_first, ok_first = _group(tags[0], projected=projected)
    group_second, ok_second = _group(tags[1], projected=projected)
    if not (ok_first and ok_second) or (group_first and group_first == group_second):
        return [], False
    if not explicit and (first.kind != "decimal" or second.kind != "decimal"):
        return [], False
    if group_first is None and group_second is None:
        return [(first, second, True), (second, first, False)], False
    if group_first == "north" or group_second == "east":
        return [(first, second, True)], True
    return [(second, first, False)], True


def _geographic(
    first: _Number,
    second: _Number,
    tags: tuple[list[str], list[str]],
    explicit: bool,
) -> list[Reading]:
    """WGS84 readings of a pair: labels decide the order, otherwise the frame."""
    candidates, decided = _orders(first, second, tags, explicit, projected=False)
    candidates = [
        c for c in candidates if abs(c[0].value) <= 90 and abs(c[1].value) <= 180
    ]
    if candidates and not decided:

        def fit(candidate: tuple[_Number, _Number, bool]) -> int:
            return _in_range(candidate[0].value, PMAXTP_LATITUDE) + _in_range(
                candidate[1].value, PMAXTP_LONGITUDE
            )

        # The ranges are disjoint, so at most one order fits the frame; with a
        # marker the order that fits best is read (latitude first on a tie) and
        # the validator reports the frame.
        best = max(candidates, key=fit)
        if fit(best) < 2 and not explicit:
            return []
        candidates = [best]
    return [_wgs84_reading(*candidate) for candidate in candidates]


def _is_projected(number: _Number) -> bool:
    return (
        number.kind != "dms"
        and not number.negative
        and number.digits == _PROJECTED_DIGITS
        and _PROJECTED_MIN <= number.value <= _PROJECTED_MAX
    )


def _projected(
    first: _Number,
    second: _Number,
    tags: tuple[list[str], list[str]],
    explicit: bool,
) -> list[Reading]:
    """PL-1992 readings of a pair: (E, N) and/or (N, E) that fit Poland."""
    candidates, _ = _orders(first, second, tags, explicit, projected=True)
    return [
        _pl1992_reading(east.value, north.value, not north_first)
        for north, east, north_first in sorted(candidates, key=lambda c: c[2])
        if _in_range(east.value, _EASTING_M) and _in_range(north.value, _NORTHING_M)
    ]


def _pair(
    ctx: _Context, numbers: list[_Number], index: int, used: set[int]
) -> Match | None:
    """The point two neighbouring numbers make, with the letters and labels."""
    first, second = numbers[index], numbers[index + 1]
    lead_first = _lead(ctx, first, numbers[index - 1].end if index else 0)
    lead_second = _lead(ctx, second, first.end)
    trail_first = _trail(ctx, first)
    trail_second = _trail(ctx, second)
    if lead_first is not None and lead_first.letter and lead_first.start in used:
        lead_first = None
    if trail_first is not None and trail_first.start in used:
        trail_first = None
    if trail_second is not None and trail_second.start in used:
        trail_second = None
    if trail_first and lead_second and trail_first.start == lead_second.start:
        # A letter between two numbers closes the first one or opens the second
        if lead_first is None or (lead_first.tag in _NORTH) == (
            trail_first.tag in _NORTH
        ):
            lead_second = None
        else:
            trail_first = None
    if lead_first is not None and trail_first is None:
        trail_second = None  # letters stand before the numbers: the next is not ours
    tags_first = [mark.tag for mark in (lead_first, trail_first) if mark]
    tags_second = [mark.tag for mark in (lead_second, trail_second) if mark]
    if lead_first is not None and lead_first.second is not None:
        tags_second.append(lead_first.second)
    start = lead_first.start if lead_first else first.start
    end = trail_second.end if trail_second else second.end
    gap_start = trail_first.end if trail_first else first.end
    gap_end = lead_second.start if lead_second else second.start
    gap = ctx.canon[gap_start:gap_end]
    if _SEPARATOR_RE.fullmatch(gap) is None or (
        "/" in gap and "integer" in (first.kind, second.kind)
    ):
        return None
    marked = bool(tags_first or tags_second) or "dms" in (first.kind, second.kind)
    if marked and any(
        _FOREIGN_HEMISPHERE_RE.match(ctx.text, number.end) for number in (first, second)
    ):
        return None  # the southern and western hemispheres are not supported
    explicit = ctx.lax or marked or _marker_context(ctx, start, end)
    tags = (tags_first, tags_second)
    readings: list[Reading] = []
    if _is_projected(first) and _is_projected(second):
        readings = _projected(first, second, tags, explicit)
    elif all(n.digits <= 3 and abs(n.value) <= 180 for n in (first, second)):
        readings = _geographic(first, second, tags, explicit)
    if not readings:
        return None
    for mark in (trail_second, lead_first, trail_first, lead_second):
        if mark is not None and mark.letter:
            used.add(mark.start)
    return Match(start, end, tuple(readings))


def _skipped_spans(text: str) -> list[tuple[int, int]]:
    """Spans of rectangles, sheets and the like, whose numbers are not points."""
    return [(match.start, match.end) for match in extract_area(text)]


def _scan(text: str, *, lax: bool) -> list[Match]:
    canon = _canonical(text)
    ctx = _Context(text, canon, words(canon), lax)
    # An answer is about the point only; a command may also describe rectangles
    numbers = _numbers(ctx, [] if lax else _skipped_spans(text))
    matches: list[Match] = []
    used: set[int] = set()
    index = 0
    while index + 1 < len(numbers):
        match = _pair(ctx, numbers, index, used)
        if match is None:
            index += 1
        else:
            matches.append(match)
            index += 2
    return matches


def extract_point(text: str) -> list[Match]:
    """
    Extract points from a command: WGS84 pairs and PL-1992 pairs.

    Recognised forms (any letter case, no Polish letters needed, one typo in
    label words of five letters or more): ``52.23, 21.01``, ``52,23 21,01``
    (a comma followed by a space separates, a comma between digits is decimal),
    ``52.23 N 21.01 E``, ``N 52.23 E 21.01``, ``szerokość 52.23 długość 21.01``,
    ``lat=52.23, lon=21.01``, ``lat/lon: 52.23 21.01``, degrees with minutes and
    seconds (``52°13'44"N 21°00'44"E``) and PL-1992 pairs (six digits each,
    ``x=637382 y=486757``, ``E 637382 N 486757``). Only north and east
    hemispheres exist; south and west letters make the pair unrecognised.

    Order is never guessed. Labels (``N``/``E``, ``szerokość``/``długość``,
    ``lat``/``lon``, ``x``/``y``) decide it; unlabelled WGS84 numbers go by the
    disjoint ranges of the PMAXTP frame (latitude 49-55, longitude 14-24.5), so
    the reading is single; an unlabelled PL-1992 pair that fits Poland in both
    orders has two readings, ``(E, N)`` first. A pair is recognised when both
    numbers are decimals that fit the frame, or when something marks it: a
    label, a hemisphere letter, a degree sign or a word such as ``punkt``,
    ``współrzędne``, ``WGS84``; then values outside the frame are returned too
    and :func:`validate_point` explains the problem. Bare integers, years,
    percentages and numbers of rectangles or sheets are never coordinates.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        One match per pair, in order of appearance; the span covers the numbers
        with their labels and letters. Values are
        ``{"type": "point", "latitude", "longitude", "input_crs"}``; PL-1992
        readings add ``easting`` and ``northing`` (``input_crs`` EPSG:2180).

    Examples
    --------
    >>> [m.readings[0].value["longitude"] for m in extract_point("punkt 52.23, 21.01")]
    [21.01]
    """
    return _scan(text, lax=False)


def read_point_answer(text: str) -> list[Match]:
    """Points in an answer to "give the point": any two numbers form a point.

    The answer is about the point only, so no marker is needed (``52 21``,
    ``x 637382 y 486757``); order and readings follow :func:`extract_point`, and
    values outside the frame still go to :func:`validate_point`.
    """
    return _scan(text, lax=True)


def _is_number(value: Any) -> TypeGuard[float]:
    return type(value) in (int, float) and math.isfinite(value)


def validate_point(value: Any) -> str | None:
    """Translation key of the problem with a point value, or None if it is usable.

    Structure and consistency first (``extractors.errors.invalid_point``: type,
    finite numbers, WGS84 or PL-1992 with matching easting/northing), the PMAXTP
    frame last (``extractors.errors.outside_pmaxtp_frame``).
    """
    invalid = "extractors.errors.invalid_point"
    if not isinstance(value, dict) or value.get("type") != "point":
        return invalid
    latitude, longitude = value.get("latitude"), value.get("longitude")
    if not (_is_number(latitude) and _is_number(longitude)):
        return invalid
    if abs(latitude) > 90 or abs(longitude) > 180:
        return invalid
    crs = value.get("input_crs")
    if crs == "EPSG:4326":
        if "easting" in value or "northing" in value:
            return invalid
    elif crs == "EPSG:2180":
        easting, northing = value.get("easting"), value.get("northing")
        if not (_is_number(easting) and _is_number(northing)):
            return invalid
        try:
            expected = pl1992_to_wgs84(easting, northing)
        except ValueError:
            return invalid
        if abs(expected[0] - latitude) > 1e-7 or abs(expected[1] - longitude) > 1e-7:
            return invalid
    else:
        return invalid
    if not (
        _in_range(latitude, PMAXTP_LATITUDE) and _in_range(longitude, PMAXTP_LONGITUDE)
    ):
        return "extractors.errors.outside_pmaxtp_frame"
    return None


def describe_point(value: Mapping[str, Any], texts: TextSource) -> str:
    """Plan text of a point value, e.g. ``punkt 52.2297° N, 21.0122° E``.

    A point given in PL-1992 also shows the pair it was converted from.
    """
    degrees = {
        "latitude": _degrees(value["latitude"]),
        "longitude": _degrees(value["longitude"]),
    }
    if value.get("input_crs") == "EPSG:2180":
        return texts.get(
            "extractors.display.point_pl1992",
            **degrees,
            easting=_metres(value["easting"]),
            northing=_metres(value["northing"]),
        )
    return texts.get("extractors.display.point", **degrees)


# PMAXTP grid cells: indices of the tool's grid, written "751/317", "komórka
# 751, 317" or "ind_x 751 ind_y 317". Cue words make bare numbers a cell.
_CELL_VALUE = r"(?P<{n}>\d{{1,5}})"
_CELL_AXIS = r"(?:(?P<axis_{n}>[xy])\s*[:=]?\s*)?"
_CELL_END = r"(?![a-z0-9_]|[.,]\d)"
_CELL_SEPARATOR = r"(?:\s*[,;/_]\s*|\s+)"
_IND_RE = _compile(
    r"(?<![a-z0-9_])ind[_\s-]?(?P<axis>[xy])\s*[:=]?\s*(?P<value>\d{1,5})" + _CELL_END
)
_CELL_PAIR = (
    _CELL_AXIS.format(n="a")
    + _CELL_VALUE.format(n="a")
    + _CELL_SEPARATOR
    + _CELL_AXIS.format(n="b")
    + _CELL_VALUE.format(n="b")
    + _CELL_END
)
_AFTER_CUE_RE = _compile(
    r"(?:\s+(?:o|nr|numer\w*|indeks\w*|siatki|pmaxtp|grid\w*|w|we))*\s*[:=]?\s*"
    + _CELL_PAIR
)
_PAIR_RE = _compile(r"(?<![a-z0-9_.])" + _CELL_PAIR)
_BARE_CELL_RE = _compile(
    r"(?<![a-z0-9_./,-])(?P<a>\d{1,5})[/_](?P<b>\d{1,5})(?![a-z0-9_]|[/_.,-]\d)"
)
_IND_SEPARATOR_RE = _compile(r"\s*(?:[,;]|\b(?:i|oraz|and)\b)?\s*")


def _cell_axes(
    first: str, second: str, axis_first: str | None, axis_second: str | None
) -> tuple[int, int] | None:
    """``(ind_x, ind_y)`` of two numbers with optional ``x``/``y`` labels."""
    if axis_first is not None and axis_first == axis_second:
        return None
    first_is_x = axis_first == "x" if axis_first else axis_second != "x"
    return (int(first), int(second)) if first_is_x else (int(second), int(first))


def _cell_match(start: int, end: int, axes: tuple[int, int]) -> Match:
    ind_x, ind_y = axes
    return Match(
        start,
        end,
        (
            Reading(
                {"type": "grid_cell", "ind_x": ind_x, "ind_y": ind_y},
                "extractors.grid_cell.cell",
                {"ind_x": str(ind_x), "ind_y": str(ind_y)},
            ),
        ),
    )


def _is_cell_cue(word: str) -> bool:
    return word == "cell" or starts_within_one_edit(word, "komork")


def _is_year_pair(first: str, second: str) -> bool:
    """Hydrological years ("2020/2021") are not cell indices."""
    return all(len(n) == 4 and 1800 <= int(n) <= 2100 for n in (first, second))


def _scan_cells(text: str, *, lax: bool) -> list[Match]:
    canon = fold(text)
    cue_words = [w for w in words(canon) if _is_cell_cue(w.text)]
    has_cue = bool(cue_words) or "ind_" in canon or lax
    matches: list[Match] = []

    def free(start: int, end: int) -> bool:
        return not any(start < m.end and end > m.start for m in matches)

    labelled = list(_IND_RE.finditer(canon))
    for first, second in zip(labelled, labelled[1:], strict=False):
        if (
            _IND_SEPARATOR_RE.fullmatch(canon[first.end() : second.start()])
            and first.group("axis") != second.group("axis")
            and free(first.start(), second.end())
        ):
            axes = _cell_axes(
                first.group("value"),
                second.group("value"),
                first.group("axis"),
                second.group("axis"),
            )
            if axes is not None:
                matches.append(_cell_match(first.start(), second.end(), axes))
    for word in cue_words:
        found = _AFTER_CUE_RE.match(canon, word.end)
        if found is None or not free(word.start, found.end()):
            continue
        axes = _cell_axes(
            found.group("a"),
            found.group("b"),
            found.group("axis_a"),
            found.group("axis_b"),
        )
        if axes is not None:
            matches.append(_cell_match(word.start, found.end(), axes))
    for found in _BARE_CELL_RE.finditer(canon):
        if free(found.start(), found.end()) and not _is_year_pair(
            found.group("a"), found.group("b")
        ):
            matches.append(
                _cell_match(
                    found.start(),
                    found.end(),
                    (int(found.group("a")), int(found.group("b"))),
                )
            )
    if has_cue:
        for found in _PAIR_RE.finditer(canon):
            if not free(found.start(), found.end()):
                continue
            labelled_pair = found.group("axis_a") or found.group("axis_b")
            if not (labelled_pair or lax):
                continue
            axes = _cell_axes(
                found.group("a"),
                found.group("b"),
                found.group("axis_a"),
                found.group("axis_b"),
            )
            if axes is not None and not (
                lax
                and not labelled_pair
                and _is_year_pair(found.group("a"), found.group("b"))
            ):
                matches.append(_cell_match(found.start(), found.end(), axes))
    return sorted(matches, key=lambda match: match.start)


def extract_grid_cell(text: str) -> list[Match]:
    """
    Extract PMAXTP grid cell indices from a command.

    Forms: ``751/317``, ``751_317`` (bare, not part of a longer chain such as
    the date ``12/10/2020``, not glued to letters, not two years), ``komórka
    751, 317``, ``komorke 751 317``, ``komórka 751/317``, ``ind_x 751 ind_y
    317`` (either order, ``=`` or ``:`` allowed) and ``x 751 y 317`` when a cue
    (``komórka``, ``cell``, ``ind_``) is in the text. Without labels the first
    number is ``ind_x``.

    Parameters
    ----------
    text : str
        The user's command.

    Returns
    -------
    list[Match]
        One match per cell with the value
        ``{"type": "grid_cell", "ind_x": int, "ind_y": int}``.
    """
    return _scan_cells(text, lax=False)


def read_grid_cell_answer(text: str) -> list[Match]:
    """Cells in an answer to "give the cell": two numbers (``751 317``) suffice."""
    return _scan_cells(text, lax=True)


def validate_grid_cell(value: Any) -> str | None:
    """Translation key of the problem with a grid cell value, or None if usable."""
    if (
        isinstance(value, dict)
        and value.get("type") == "grid_cell"
        and all(
            type(value.get(name)) is int and value[name] >= 0
            for name in ("ind_x", "ind_y")
        )
    ):
        return None
    return "extractors.errors.invalid_grid_cell"


def describe_grid_cell(value: Mapping[str, Any], texts: TextSource) -> str:
    """Plan text of a grid cell value, e.g. ``komórka 751/317``."""
    return texts.get(
        "extractors.display.grid_cell",
        ind_x=str(value["ind_x"]),
        ind_y=str(value["ind_y"]),
    )

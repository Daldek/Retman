"""Recognise filenames without accessing the filesystem."""

import re
from typing import Any

from retman.extractors.base import Match, Reading

# File types used by tools and project results; extensions avoid treating bare words
# or numbers as paths. Spaces in a filename must be quoted.
_EXTENSION = r"(?:shp|gpkg|geojson|gml|tif|tiff|asc|csv|json|zip|las|laz)"
_PATH_RE = re.compile(
    rf"(?P<quote>['\"])(?P<quoted>[^'\"\r\n]+?\.{_EXTENSION})(?P=quote)(?![\w.])"
    rf"|(?<![\w'\"])(?P<bare>[^\s'\"<>|,;(){{}}\[\]]+?\.{_EXTENSION})(?!\w|\.\w)",
    re.IGNORECASE,
)


def extract_paths(text: str) -> list[Match]:
    """
    Read quoted or bare POSIX, Windows and relative file paths.

    Parameters
    ----------
    text : str
        User command or answer.

    Returns
    -------
    list[Match]
        One reading per filename, retaining the path's spelling and separators.
    """
    matches = []
    for found in _PATH_RE.finditer(text):
        path = found.group("quoted") or found.group("bare")
        matches.append(
            Match(
                found.start(),
                found.end(),
                (
                    Reading(
                        path,
                        "extractors.path.file",
                        {"path": path},
                    ),
                ),
            )
        )
    return matches


def validate_path(value: Any) -> str | None:
    """Only path syntax is checked during extraction, not file existence."""
    return None

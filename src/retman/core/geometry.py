"""Geometry files as areas: the little Retman reads itself, without GIS libraries.

A geometry area is ``{"type": "geometry", "path": <absolute path>, "layer":
<GPKG feature table> | None}``; ``layer`` is ``None`` for a Shapefile and is
always decided explicitly for a GeoPackage (W-02). Kartograf reads the file
itself; Retman only lists a GeoPackage's feature tables (standard-library
``sqlite3``, read-only) to ask which one is meant, and fingerprints the files
for the audit record.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from retman.core.journal import sha256_file
from retman.exceptions import RetmanError

# Members of a Shapefile that Kartograf reads (.prj is required for the CRS)
_SHAPEFILE_MEMBERS = (".shp", ".shx", ".dbf", ".prj")


class GeometryFileError(RetmanError):
    """A geometry file cannot be read as the kind of file it claims to be.

    Default code: ``data_error``, reason ``invalid_geometry_file``.
    """

    default_code = "data_error"
    default_reason = "invalid_geometry_file"

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(
            f"{path}: {reason}",
            details={"path": str(path), "detail": reason},
            hint="Give a GeoPackage or Shapefile that the tool can open.",
        )


def geometry_layers(path: Path) -> tuple[str, ...]:
    """Feature tables of a GeoPackage in file order; ``()`` for any other file.

    Raises
    ------
    GeometryFileError
        The file is not a readable GeoPackage database.
    """
    if path.suffix.lower() != ".gpkg":
        return ()
    try:
        with closing(
            sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        ) as database:
            rows = database.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
            ).fetchall()
    except sqlite3.Error as err:
        raise GeometryFileError(path, str(err)) from err
    return tuple(str(row[0]) for row in rows)


def describe_geometry(path: Path) -> dict[str, str]:
    """SHA-256 of the files that make up a geometry area, by file name.

    A GeoPackage is one file; a Shapefile is its ``.shp``, ``.shx``, ``.dbf``
    and ``.prj`` members that exist next to it.
    """
    if path.suffix.lower() != ".shp":
        return {path.name: sha256_file(path)}
    found: dict[str, str] = {}
    for extension in _SHAPEFILE_MEMBERS:
        for candidate in (
            path.with_suffix(extension),
            path.with_suffix(extension.upper()),
        ):
            if candidate.is_file():
                found[candidate.name] = sha256_file(candidate)
                break
    return found

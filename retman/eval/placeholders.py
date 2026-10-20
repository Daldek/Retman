"""Placeholder geometry files for the evaluation of commands that name a file.

``retman-eval`` plans every command in an empty temporary project, where the file
a command names ("dla obszaru z pliku granica.shp") does not exist and Retman
would ask for the area instead of planning. These writers create a minimal but
real file in its place: a Shapefile (``.shp``, ``.shx``, ``.dbf``, ``.prj``) or a
GeoPackage with one feature table, each holding one 2 km square in PL-1992 inside
Poland, so that the tool's own offline checks accept it. Only the standard library
is used (Retman has no GIS dependency).
"""

import sqlite3
import struct
from contextlib import closing
from pathlib import Path

from retman.extractors.areas import extract_area

# One square in EPSG:2180, well inside Poland (east, north of the lower left corner)
_EAST, _NORTH, _SIDE = 530_000.0, 382_000.0, 2_000.0
_RING = [
    (_EAST, _NORTH),
    (_EAST, _NORTH + _SIDE),
    (_EAST + _SIDE, _NORTH + _SIDE),
    (_EAST + _SIDE, _NORTH),
    (_EAST, _NORTH),
]
_BOX = (_EAST, _NORTH, _EAST + _SIDE, _NORTH + _SIDE)

_WKT_2180 = (
    'PROJCS["ETRS89 / Poland CS92",GEOGCS["ETRS89",DATUM['
    '"European_Terrestrial_Reference_System_1989",SPHEROID["GRS 1980",6378137,'
    '298.257222101]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],'
    'PARAMETER["central_meridian",19],PARAMETER["scale_factor",0.9993],'
    'PARAMETER["false_easting",500000],PARAMETER["false_northing",-5300000],'
    'UNIT["metre",1]]'
)

# Shape type 5 of a Shapefile, geometry type 3 of the well-known binary format
_SHP_POLYGON = 5
_WKB_POLYGON = 3
_LAYER = "obszar"


def _shape_header(length_bytes: int) -> bytes:
    """The 100-byte header of a ``.shp`` or ``.shx`` file with one polygon."""
    # file code, five unused words, length in 16-bit words (big endian) ...
    first = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, length_bytes // 2)
    # ... version, shape type, the box and the unused Z and M ranges (little endian)
    return first + struct.pack("<2i8d", 1000, _SHP_POLYGON, *_BOX, 0.0, 0.0, 0.0, 0.0)


def write_shapefile(path: Path) -> None:
    """Write ``path`` (.shp) with its ``.shx``, ``.dbf`` and ``.prj`` members."""
    points = b"".join(struct.pack("<2d", x, y) for x, y in _RING)
    content = (
        struct.pack("<i4d2i", _SHP_POLYGON, *_BOX, 1, len(_RING))
        + struct.pack("<i", 0)
        + points
    )
    words = len(content) // 2
    record = struct.pack(">2i", 1, words) + content
    path.write_bytes(_shape_header(100 + len(record)) + record)
    path.with_suffix(".shx").write_bytes(
        _shape_header(108) + struct.pack(">2i", 50, words)
    )
    # dBase III: one numeric field "ID" of width 4 and one record (2026-10-19)
    field = b"ID".ljust(11, b"\0") + b"N" + bytes(4) + bytes([4, 0]) + bytes(14)
    header = struct.pack("<4BIHH20x", 3, 126, 10, 19, 1, 32 + 32 + 1, 5)
    path.with_suffix(".dbf").write_bytes(header + field + b"\r" + b" " + b"   1")
    path.with_suffix(".prj").write_text(_WKT_2180, encoding="utf-8")


def _wkb_polygon() -> bytes:
    ring = b"".join(struct.pack("<2d", x, y) for x, y in _RING)
    return struct.pack("<BIII", 1, _WKB_POLYGON, 1, len(_RING)) + ring


def write_geopackage(path: Path) -> None:
    """Write ``path`` (.gpkg): one feature table ``obszar`` with one polygon."""
    min_x, min_y, max_x, max_y = _BOX
    # GeoPackage binary: "GP", version 0, little endian with a 2D envelope, SRS id
    blob = (
        b"GP\x00\x03"
        + struct.pack("<i4d", 2180, min_x, max_x, min_y, max_y)
        + _wkb_polygon()
    )
    with closing(sqlite3.connect(path)) as database:
        database.executescript(
            f"""
            PRAGMA application_id = 1196444487;
            PRAGMA user_version = 10300;
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT NOT NULL, srs_id INTEGER PRIMARY KEY,
                organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
                definition TEXT NOT NULL, description TEXT);
            CREATE TABLE gpkg_contents (
                table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL,
                identifier TEXT UNIQUE, description TEXT DEFAULT '',
                last_change DATETIME NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE,
                srs_id INTEGER);
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT NOT NULL, column_name TEXT NOT NULL,
                geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL,
                z TINYINT NOT NULL, m TINYINT NOT NULL,
                PRIMARY KEY (table_name, column_name));
            CREATE TABLE {_LAYER} (
                fid INTEGER PRIMARY KEY AUTOINCREMENT, geom POLYGON);
            """
        )
        database.executemany(
            "INSERT INTO gpkg_spatial_ref_sys VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Undefined Cartesian SRS", -1, "NONE", -1, "undefined", None),
                ("Undefined geographic SRS", 0, "NONE", 0, "undefined", None),
                ("ETRS89 / Poland CS92", 2180, "EPSG", 2180, _WKT_2180, None),
            ],
        )
        database.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, identifier, min_x,"
            " min_y, max_x, max_y, srs_id) VALUES (?, 'features', ?, ?, ?, ?, ?, 2180)",
            (_LAYER, _LAYER, *_BOX),
        )
        database.execute(
            "INSERT INTO gpkg_geometry_columns "
            "VALUES (?, 'geom', 'POLYGON', 2180, 0, 0)",
            (_LAYER,),
        )
        database.execute(f"INSERT INTO {_LAYER} (geom) VALUES (?)", (blob,))
        database.commit()


def create_geometry_files(command: str, project: Path) -> list[Path]:
    """Create a placeholder for every geometry file a command names.

    Only files inside ``project`` are created (a command is data, not a place to
    write to); a name with another extension than ``.shp``/``.gpkg`` is left alone,
    as the pipeline rejects it itself.

    Returns
    -------
    list[Path]
        The files written (the ``.shp``/``.gpkg`` of each).
    """
    root = project.resolve()
    created: list[Path] = []
    for match in extract_area(command):
        for reading in match.readings:
            value = reading.value
            if value.get("type") != "geometry":
                continue
            path = (root / value["path"]).resolve()
            if not path.is_relative_to(root) or path.exists():
                continue
            writer = {".shp": write_shapefile, ".gpkg": write_geopackage}.get(
                path.suffix.lower()
            )
            if writer is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            writer(path)
            created.append(path)
    return created

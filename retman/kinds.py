"""Data kinds returned by tool handlers (ARCHITECTURE 3.2.6)."""

from dataclasses import dataclass
from pathlib import Path

from retman.exceptions import KindValidationError


@dataclass(frozen=True)
class Kind:
    """A data kind and the file extensions Kartograf can return for it."""

    name: str
    extensions: tuple[str, ...]


KINDS: dict[str, Kind] = {
    "dem": Kind("dem", (".asc", ".tif")),
    "dsm": Kind("dsm", (".asc", ".tif")),
    "orthophoto": Kind("orthophoto", (".tif",)),
    "topographic_vector": Kind("topographic_vector", (".gpkg", ".shp")),
}


def validate_file(kind: str, path: Path) -> None:
    """Check an output file's extension and format signature without GIS libraries.

    Parameters
    ----------
    kind : str
        Declared data kind.
    path : Path
        File returned by a tool handler.

    Raises
    ------
    KindValidationError
        Unknown kind, missing file, unsupported extension or invalid header.
    """
    spec = KINDS.get(kind)
    if spec is None:
        raise KindValidationError(kind, path, "unknown_kind")
    if not path.is_file():
        raise KindValidationError(kind, path, "missing_file")
    suffix = path.suffix.lower()
    if suffix not in spec.extensions:
        raise KindValidationError(kind, path, "unsupported_extension")
    try:
        with path.open("rb") as source:
            header = source.read(16)
    except OSError as error:
        raise KindValidationError(kind, path, "unreadable_file") from error
    if suffix == ".asc":
        valid = header[:5].lower() == b"ncols" and header[5:6] in (b" ", b"\t")
    elif suffix == ".tif":
        valid = header[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
    elif suffix == ".gpkg":
        valid = header[:16] == b"SQLite format 3\x00"
    else:
        valid = header[:4] == (9994).to_bytes(4, "big")
    if not valid:
        raise KindValidationError(kind, path, "invalid_header")

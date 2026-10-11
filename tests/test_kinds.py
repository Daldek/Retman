"""File format signatures of Kartograf result kinds (ADR-004)."""

from pathlib import Path

import pytest

from retman.exceptions import KindValidationError
from retman.kinds import validate_file


@pytest.mark.parametrize(
    ("kind", "extension", "header"),
    [
        ("dem", ".asc", b"ncols 2\nnrows 3\n"),
        ("dsm", ".ASC", b"NCOLS\t1\nNROWS 1\n"),
        ("dem", ".tif", b"II*\x00"),
        ("dsm", ".tif", b"MM\x00*"),
        ("orthophoto", ".tif", b"II+\x00"),
        ("orthophoto", ".tif", b"MM\x00+"),
        ("topographic_vector", ".gpkg", b"SQLite format 3\x00"),
        ("topographic_vector", ".shp", (9994).to_bytes(4, "big")),
    ],
)
def test_validate_file_accepts_format_signature(
    tmp_path: Path, kind: str, extension: str, header: bytes
) -> None:
    file = tmp_path / f"output{extension}"
    file.write_bytes(header)

    validate_file(kind, file)


@pytest.mark.parametrize(
    ("kind", "extension", "header", "reason"),
    [
        ("dem", ".asc", b"NCOLS", "invalid_header"),
        ("dsm", ".asc", b"nrows 2\n", "invalid_header"),
        ("orthophoto", ".tif", b"not a TIFF", "invalid_header"),
        ("topographic_vector", ".gpkg", b"SQLite format 3", "invalid_header"),
        ("topographic_vector", ".shp", b"\x00\x00'\x0b", "invalid_header"),
        ("orthophoto", ".asc", b"ncols 2\n", "unsupported_extension"),
        ("topographic_vector", ".zip", b"PK\x03\x04", "unsupported_extension"),
    ],
)
def test_validate_file_rejects_wrong_header_or_format(
    tmp_path: Path, kind: str, extension: str, header: bytes, reason: str
) -> None:
    file = tmp_path / f"output{extension}"
    file.write_bytes(header)

    with pytest.raises(KindValidationError) as error:
        validate_file(kind, file)

    assert error.value.reason == reason
    assert error.value.path == file


def test_validate_file_rejects_missing_file(tmp_path: Path) -> None:
    file = tmp_path / "absent.tif"

    with pytest.raises(KindValidationError) as error:
        validate_file("dem", file)

    assert error.value.reason == "missing_file"


def test_validate_file_rejects_unknown_kind(tmp_path: Path) -> None:
    file = tmp_path / "source.tif"
    file.write_bytes(b"II*\x00")

    with pytest.raises(KindValidationError) as error:
        validate_file("unknown", file)

    assert error.value.reason == "unknown_kind"

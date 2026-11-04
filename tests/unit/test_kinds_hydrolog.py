"""Format validators of the Hydrolog data kinds: watershed files and result reports."""

import json
from pathlib import Path

import pytest

from retman.exceptions import KindValidationError
from retman.i18n.loader import load_core_texts
from retman.kinds import validate_file

# The fields every ``WatershedParameters.to_json()`` document has, and an optional one
WATERSHED = {
    "area_km2": 45.3,
    "perimeter_km": 32.1,
    "length_km": 12.5,
    "elevation_min_m": 150.0,
    "elevation_max_m": 520.0,
    "cn": 72,
}
REPORT = {"schema": "hydrolog-result/1", "tool": "hydrolog", "status": "ok"}


def _reason(kind: str, file: Path) -> str:
    with pytest.raises(KindValidationError) as error:
        validate_file(kind, file)
    # Every failure the user can meet has a text (a missing one would crash)
    load_core_texts("pl").get(
        f"kinds.errors.{error.value.reason}", path=file, kind=kind
    )
    return error.value.reason


@pytest.mark.parametrize(
    ("kind", "name", "content"),
    [
        ("watershed_parameters", "zlewnia.json", json.dumps(WATERSHED)),
        ("watershed_parameters", "ZLEWNIA.JSON", json.dumps({**WATERSHED, "x": 1})),
        ("hydrolog_report", "tc.json", json.dumps(REPORT, indent=2)),
    ],
)
def test_hydrolog_kinds_accept_their_documents(
    tmp_path: Path, kind: str, name: str, content: str
) -> None:
    file = tmp_path / name
    file.write_text(content, encoding="utf-8")

    validate_file(kind, file)


@pytest.mark.parametrize(
    ("kind", "name", "content", "reason"),
    [
        ("watershed_parameters", "w.json", "", "empty_file"),
        ("watershed_parameters", "w.json", '{"area_km2": ', "invalid_json"),
        # A watershed needs all five required fields
        (
            "watershed_parameters",
            "w.json",
            json.dumps({k: v for k, v in WATERSHED.items() if k != "length_km"}),
            "invalid_schema",
        ),
        ("watershed_parameters", "w.json", json.dumps([WATERSHED]), "invalid_schema"),
        ("watershed_parameters", "w.csv", "area_km2\n45.3\n", "unsupported_extension"),
        ("hydrolog_report", "r.json", "", "empty_file"),
        (
            "hydrolog_report",
            "r.json",
            json.dumps({**REPORT, "schema": "obserwator-result/1"}),
            "invalid_schema",
        ),
        # The schema must be the first key of the document
        (
            "hydrolog_report",
            "r.json",
            json.dumps({"tool": "hydrolog", "schema": "hydrolog-result/1"}),
            "invalid_schema",
        ),
    ],
)
def test_hydrolog_kinds_reject_other_files(
    tmp_path: Path, kind: str, name: str, content: str, reason: str
) -> None:
    file = tmp_path / name
    file.write_text(content, encoding="utf-8")

    assert _reason(kind, file) == reason

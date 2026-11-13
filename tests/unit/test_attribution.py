"""The providers' lines in the CSV tables Retman writes (Nogat DEV-20.5)."""

import csv
from pathlib import Path

from retman.attribution import Attribution
from retman.tools.obserwator.describe import csv_write

LINES = Attribution(("S", "P", "H"), ("N", "RH"))


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def test_csv_write_puts_one_line_per_row_in_the_trailing_columns(
    tmp_path: Path,
) -> None:
    rows = _read(csv_write(tmp_path / "t.csv", ["code"], [[1], [2], [3], [4]], LINES))

    assert [row["attribution"] for row in rows] == ["S", "P", "H", ""]
    assert [row["terms_notice"] for row in rows] == ["N", "RH", "", ""]
    assert [row["code"] for row in rows] == ["1", "2", "3", "4"]


def test_csv_write_joins_the_lines_left_over_into_the_last_row(
    tmp_path: Path,
) -> None:
    rows = _read(csv_write(tmp_path / "t.csv", ["code"], [[1], [2]], LINES))

    assert [row["attribution"] for row in rows] == ["S", "P\nH"]
    assert [row["terms_notice"] for row in rows] == ["N", "RH"]


def test_csv_write_without_provider_lines_adds_no_column(tmp_path: Path) -> None:
    path = csv_write(tmp_path / "t.csv", ["code"], [[1]], Attribution())

    assert path.read_text(encoding="utf-8").splitlines()[0] == "code"


def test_the_lines_of_several_documents_are_merged_once_in_the_order_first_seen() -> (
    None
):
    merged = Attribution.from_documents(
        [
            {"attribution": ["S", "P"], "terms_notice": ["N", "RD"]},
            {"schema": "x"},
            {"attribution": ["P", "H"], "result": {"terms_notice": ["N", "RH"]}},
        ]
    )

    assert merged == Attribution(("S", "P", "H"), ("N", "RD", "RH"))

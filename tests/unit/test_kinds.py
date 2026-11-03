"""Format validators of data kinds: Kartograf signatures and IMGWTools files."""

import json
from pathlib import Path

import pytest

from retman.exceptions import KindValidationError
from retman.i18n.loader import load_core_texts
from retman.kinds import KINDS, validate_file

SHAPEFILE = (9994).to_bytes(4, "big")
GEOPACKAGE = b"SQLite format 3\x00"

# Columns and one data row of a good file of each IMGWTools CSV kind; the
# headers are those written by IMGWTools 3.0.0 and by Retman's own mappers
ATTRIBUTION = ("Źródło danych: IMGW-PIB", "Dane zostały przetworzone")
CSV_FILES: dict[str, tuple[list[str], list[str]]] = {
    "station_list": (
        ["provider", "kind", "station_code", "name", "river", "latitude", "longitude"],
        ["IMGW-PIB", "hydro", "152210170", "POZNAŃ-BOGDANKA", "Warta", "52.4", "16.9"],
    ),
    "hydro_series": (
        [
            *["date", "year", "H [cm]", "H_flag", "Q [m3/s]", "Q_flag"],
            *["T [degC]", "T_flag", "attribution_source", "attribution_processed"],
        ],
        ["2023-12-01", "2024", "162.0", "value", "", "missing", "4.1", "value"]
        + list(ATTRIBUTION),
    ),
    "meteo_series": (
        [
            *["date", "year", "P [mm]", "P_flag", "snow_cover [cm]"],
            *["snow_cover_flag", "attribution_source", "attribution_processed"],
        ],
        ["2001-01-01", "2001", "", "missing", "0.0", "no_phenomenon"]
        + list(ATTRIBUTION),
    ),
    "pmaxtp_table": (
        [
            *["duration_min", "probability_percent", "ks_mm", "sg_mm", "rb_mm"],
            *["attribution_source", "attribution_processed"],
        ],
        ["5", "1", "12.3", "10.1", "14.8", *ATTRIBUTION],
    ),
    "current_hydro": (
        [
            *["station_code", "station_name", "river", "water_level_cm"],
            *["water_level_date", "flow_m3s", "flow_date"],
        ],
        ["152210170", "POZNAŃ", "Warta", "212.0", "2026-10-19 10:00", "35.1", ""],
    ),
    "current_meteo": (
        ["station_code", "station_name", "air_temp_c", "wind_speed_ms"],
        ["352160330", "POZNAŃ", "11.2", "3.4"],
    ),
    "current_synop": (
        ["station_code", "station_name", "measurement_date", "temperature_c"],
        ["12330", "POZNAŃ", "2026-10-19", "11.2"],
    ),
    "imgw_warnings": (
        ["id", "kind", "event", "level", "valid_from"],
        ["w-1", "hydro", "Wezbranie", "2", "2026-10-19 08:00"],
    ),
    "hydro_states": (
        ["station_code", "name", "river", "water_state"],
        ["152210170", "POZNAŃ", "Warta", "normal"],
    ),
    "archive_records": (
        ["station_code", "dataset", "date", "hydro_year", "H [cm]", "H_flag"],
        ["149190310", "pl.imgw.hydro_daily", "2023-12-01", "2024", "162.0", "value"],
    ),
}
CSV_KINDS = sorted(CSV_FILES)


def _csv(header: list[str], *rows: list[str], newline: str = "\r\n") -> bytes:
    lines = [",".join(header), *(",".join(row) for row in rows)]
    return (newline.join(lines) + newline).encode()


def _good_csv(kind: str) -> bytes:
    header, row = CSV_FILES[kind]
    return _csv(header, row, row)


def _write(tmp_path: Path, name: str, content: bytes) -> Path:
    file = tmp_path / name
    file.write_bytes(content)
    return file


def _reason(kind: str, file: Path) -> str:
    with pytest.raises(KindValidationError) as error:
        validate_file(kind, file)
    assert error.value.path == file
    assert error.value.kind == kind
    # Every failure the user can meet has a text (a missing one would crash)
    texts = load_core_texts("pl")
    texts.get(f"kinds.errors.{error.value.reason}", path=file, kind=kind)
    return error.value.reason


@pytest.mark.parametrize(
    ("kind", "extension", "header"),
    [
        ("dem", ".asc", b"ncols 2\nnrows 3\n"),
        ("dsm", ".ASC", b"NCOLS\t1\nNROWS 1\n"),
        ("dem", ".tif", b"II*\x00"),
        ("dsm", ".tif", b"MM\x00*"),
        ("orthophoto", ".tif", b"II+\x00"),
        ("orthophoto", ".tif", b"MM\x00+"),
        ("topographic_vector", ".gpkg", GEOPACKAGE),
        ("topographic_vector", ".shp", SHAPEFILE),
        ("area_geometry", ".gpkg", GEOPACKAGE),
        ("area_geometry", ".SHP", SHAPEFILE),
        ("dem_archive", ".zip", b"PK\x03\x04"),
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
        ("area_geometry", ".gpkg", b"SQLite format 3", "invalid_header"),
        ("area_geometry", ".shp", b'{"type": ', "invalid_header"),
        ("dem_archive", ".zip", b"<html>", "invalid_header"),
        ("dem_archive", ".zip", b"", "invalid_header"),
        ("orthophoto", ".asc", b"ncols 2\n", "unsupported_extension"),
        ("topographic_vector", ".zip", b"PK\x03\x04", "unsupported_extension"),
        ("area_geometry", ".geojson", b"{}", "unsupported_extension"),
        ("dem_archive", ".asc", b"ncols 2\n", "unsupported_extension"),
        ("dem", ".zip", b"PK\x03\x04", "unsupported_extension"),
    ],
)
def test_validate_file_rejects_wrong_header_or_format(
    tmp_path: Path, kind: str, extension: str, header: bytes, reason: str
) -> None:
    file = tmp_path / f"output{extension}"
    file.write_bytes(header)

    assert _reason(kind, file) == reason


def test_validate_file_rejects_missing_file(tmp_path: Path) -> None:
    file = tmp_path / "absent.tif"

    assert _reason("dem", file) == "missing_file"


def test_validate_file_rejects_unknown_kind(tmp_path: Path) -> None:
    file = tmp_path / "source.tif"
    file.write_bytes(b"II*\x00")

    assert _reason("unknown", file) == "unknown_kind"


@pytest.mark.parametrize("kind", CSV_KINDS)
def test_csv_kinds_accept_a_good_file_in_any_line_ending_and_with_a_bom(
    tmp_path: Path, kind: str
) -> None:
    header, row = CSV_FILES[kind]
    crlf = _good_csv(kind)
    lf = _csv(header, row, row, newline="\n")

    validate_file(kind, _write(tmp_path, "crlf.csv", crlf))
    validate_file(kind, _write(tmp_path, "lf.csv", lf))
    validate_file(kind, _write(tmp_path, "bom.csv", b"\xef\xbb\xbf" + crlf))


@pytest.mark.parametrize("kind", CSV_KINDS)
def test_csv_kinds_accept_a_header_without_data_rows(tmp_path: Path, kind: str) -> None:
    header, _ = CSV_FILES[kind]

    validate_file(kind, _write(tmp_path, "empty_result.csv", _csv(header)))


@pytest.mark.parametrize("kind", CSV_KINDS)
def test_csv_kinds_reject_empty_files_and_text_in_another_encoding(
    tmp_path: Path, kind: str
) -> None:
    legacy = _good_csv(kind) + "Łódź\r\n".encode("cp1250")

    assert _reason(kind, _write(tmp_path, "empty.csv", b"")) == "empty_file"
    assert _reason(kind, _write(tmp_path, "cp1250.csv", legacy)) == "invalid_encoding"


@pytest.mark.parametrize("kind", CSV_KINDS)
def test_csv_kinds_reject_a_file_of_another_kind(tmp_path: Path, kind: str) -> None:
    other = "station_list" if kind != "station_list" else "pmaxtp_table"

    assert _reason(kind, _write(tmp_path, "other.csv", _good_csv(other))) == (
        "invalid_columns"
    )


@pytest.mark.parametrize("kind", CSV_KINDS)
def test_csv_kinds_reject_rows_of_a_different_width_than_the_header(
    tmp_path: Path, kind: str
) -> None:
    header, row = CSV_FILES[kind]
    truncated = _csv(header, row, row[:-1])

    assert _reason(kind, _write(tmp_path, "ragged.csv", truncated)) == "invalid_rows"


def test_series_kinds_reject_each_others_files(tmp_path: Path) -> None:
    hydro = _write(tmp_path, "hydro.csv", _good_csv("hydro_series"))
    meteo = _write(tmp_path, "meteo.csv", _good_csv("meteo_series"))

    assert _reason("meteo_series", hydro) == "invalid_columns"
    assert _reason("hydro_series", meteo) == "invalid_columns"


def test_series_kinds_accept_chmi_quality_columns(tmp_path: Path) -> None:
    header = [
        *["date", "year", "P [mm]", "P_flag", "P_quality", "P_source_flag"],
        *["Tmean [degC]", "Tmean_flag", "Tmean_quality", "Tmean_source_flag"],
        *["attribution_source", "attribution_processed"],
    ]
    row = ["2023-10-20", "2023", "0.0", "no_phenomenon", "0", ""]
    row += ["8.5", "value", "0", "", *ATTRIBUTION]

    validate_file("meteo_series", _write(tmp_path, "cz.csv", _csv(header, row)))


def test_hydro_series_accepts_monthly_extremum_variables(tmp_path: Path) -> None:
    header = [
        *["date", "year", "H_min [cm]", "H_min_flag", "Q_max [m3/s]", "Q_max_flag"],
        *["attribution_source", "attribution_processed"],
    ]
    row = ["2023-11-01", "2024", "150.0", "value", "3.4", "value", *ATTRIBUTION]

    validate_file("hydro_series", _write(tmp_path, "monthly.csv", _csv(header, row)))


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        # a variable without its _flag column
        (("H_flag,", ""), "invalid_columns"),
        # attribution columns cut off (licence terms must stay with the data)
        ((",attribution_processed", ""), "invalid_columns"),
        # the series must start with the date and the year
        (("date,year,", "year,date,"), "invalid_columns"),
        # a first row that is not a date
        (("2023-12-01", "01.12.2023"), "invalid_rows"),
    ],
    ids=["no_flag", "no_attribution", "date_year_order", "date_format"],
)
def test_series_kinds_reject_damaged_structure(
    tmp_path: Path, change: tuple[str, str], reason: str
) -> None:
    text = _good_csv("hydro_series").decode().replace(*change, 1)
    file = _write(tmp_path, "series.csv", text.encode())

    assert _reason("hydro_series", file) == reason


def test_series_kinds_reject_a_header_without_variables(tmp_path: Path) -> None:
    header = ["date", "year", "attribution_source", "attribution_processed"]
    file = _write(tmp_path, "none.csv", _csv(header, ["2023-12-01", "2024", "", ""]))

    assert _reason("hydro_series", file) == "invalid_columns"


def test_archive_records_accept_json_lines_and_reject_damaged_ones(
    tmp_path: Path,
) -> None:
    record = {"station_code": "149190310", "dataset": "pl.imgw.hydro_daily"}
    record["date"] = "2023-12-01"
    line = json.dumps(record)
    good = _write(tmp_path, "records.jsonl", f"{line}\n{line}\n".encode())
    blank_first = _write(tmp_path, "blank.jsonl", f"\n{line}\n".encode())

    validate_file("archive_records", good)
    validate_file("archive_records", blank_first)
    assert _reason("archive_records", _write(tmp_path, "e.jsonl", b"")) == (
        "empty_file"
    )
    assert _reason("archive_records", _write(tmp_path, "t.jsonl", b"<html>\n")) == (
        "invalid_json"
    )
    assert _reason("archive_records", _write(tmp_path, "l.jsonl", b"[1, 2]\n")) == (
        "invalid_schema"
    )
    assert _reason("archive_records", _write(tmp_path, "k.jsonl", b'{"a": 1}\n')) == (
        "invalid_schema"
    )
    assert _reason("archive_records", _write(tmp_path, "x.jsonl", b"\xff\n")) == (
        "invalid_encoding"
    )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("codz_2020_01.zip", b"PK\x03\x04rest of the archive"),
        ("lista_stacji.json", b'  [{"station": "1"}]'),
        ("H_0-203-1-900001_DQ_2023.json", b'\xef\xbb\xbf{"data": {}}'),
        ("stations.csv", "id;nazwa\n1;Łódź\n".encode("cp1250")),
        ("opis.txt", "Opis zbioru danych\r\n".encode("iso-8859-2")),
    ],
)
def test_imgw_archive_accepts_files_as_published_by_the_source(
    tmp_path: Path, name: str, content: bytes
) -> None:
    validate_file("imgw_archive", _write(tmp_path, name, content))


@pytest.mark.parametrize(
    ("name", "content", "reason"),
    [
        ("codz.zip", b"<html>404</html>", "invalid_header"),
        ("data.json", b"<html>404</html>", "invalid_json"),
        ("data.json", b"  \n", "empty_file"),
        ("data.csv", b"", "empty_file"),
        ("data.csv", b"\x00\x01\x02\x03binary", "invalid_header"),
        ("data.txt", b"PK\x03\x04\x00\x00", "invalid_header"),
        ("data.xml", b"<a/>", "unsupported_extension"),
    ],
)
def test_imgw_archive_rejects_error_pages_and_binary_text(
    tmp_path: Path, name: str, content: bytes, reason: str
) -> None:
    assert _reason("imgw_archive", _write(tmp_path, name, content)) == reason


@pytest.mark.parametrize(
    ("kind", "schema", "other", "not_json"),
    [
        ("imgw_plan", "imgw-plan/1", "imgw-result/1", "invalid_json"),
        ("imgw_report", "imgw-result/1", "imgw-plan/1", "invalid_schema"),
    ],
)
def test_imgw_documents_need_their_schema(
    tmp_path: Path, kind: str, schema: str, other: str, not_json: str
) -> None:
    good = json.dumps({"schema": schema, "items": []}, indent=2).encode()
    wrong = json.dumps({"schema": other, "items": []}).encode()
    kartograf = json.dumps({"schema": "kartograf-plan/1"}).encode()

    validate_file(kind, _write(tmp_path, "good.json", good))
    validate_file(kind, _write(tmp_path, "bom.json", b"\xef\xbb\xbf" + good))
    assert _reason(kind, _write(tmp_path, "wrong.json", wrong)) == "invalid_schema"
    assert _reason(kind, _write(tmp_path, "other.json", kartograf)) == (
        "invalid_schema"
    )
    assert _reason(kind, _write(tmp_path, "empty.json", b"")) == "empty_file"
    assert _reason(kind, _write(tmp_path, "text.json", b"not json")) == not_json
    assert _reason(kind, _write(tmp_path, "plan.csv", good)) == (
        "unsupported_extension"
    )


def test_imgw_plan_must_be_complete_json_describing_an_object(tmp_path: Path) -> None:
    broken = b'{"schema": "imgw-plan/1", "items": ['

    assert _reason("imgw_plan", _write(tmp_path, "cut.json", broken)) == "invalid_json"
    assert _reason("imgw_plan", _write(tmp_path, "list.json", b"[1]")) == (
        "invalid_schema"
    )


def test_every_kind_declares_extensions_with_a_leading_dot() -> None:
    for name, kind in KINDS.items():
        assert kind.name == name
        assert kind.extensions
        assert all(extension.startswith(".") for extension in kind.extensions)

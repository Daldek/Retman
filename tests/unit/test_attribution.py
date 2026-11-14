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


# The lines of Nogat DEV §20, byte for byte (G, CP and Z with their placeholders
# filled), in the order of DEV-20.4 and DEV-20.7.
_IMGW = "Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"
_IMGW_OF = (
    "Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego"
)
_CC_BY = "licencja CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
S = f"Źródłem pochodzenia danych jest {_IMGW}"
P = f"Dane {_IMGW_OF} zostały przetworzone"
PS = (
    f"Źródłem pochodzenia danych jest {_IMGW}, dane pochodzą ze strony "
    "https://klimat.imgw.pl/opady-maksymalne"
)
PP = (
    f"Dane {_IMGW_OF} pochodzące ze strony https://klimat.imgw.pl/opady-maksymalne "
    "zostały przetworzone"
)
M = (
    "„Modele probabilistyczne opadów maksymalnych o określonym czasie trwania i "
    "prawdopodobieństwie przewyższenia – Projekt PMAXTP”, red. Bogdan Ozga-Zieliński, "
    f"{_IMGW}, Warszawa 2022"
)
C = (
    "Źródło danych: Český hydrometeorologický ústav (ČHMÚ), https://opendata.chmi.cz, "
    f"{_CC_BY}"
)
CP = "Dane ČHMÚ zostały przetworzone (agregacja do dobowych sum)"
G = (
    "Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, NMT, BDOT10k (wytworzono "
    "2020–2025, pozyskano 2026-03-24 – 2026-10-29); dane przetworzone"
)
SG = f"Źródło: ISRIC – World Soil Information, SoilGrids, {_CC_BY}; dane przetworzone"
Z = (
    "Źródło: Český úřad zeměměřický a katastrální (ČÚZK), RÚIAN (pozyskano "
    f"2026-11-01), {_CC_BY}; dane przetworzone"
)
RD = "Regulamin danych IMGW-PIB: https://danepubliczne.imgw.pl/regulations"
RH = "Regulamin serwisu hydrologicznego IMGW-PIB: https://hydro.imgw.pl/#/regulamin"
RK = "Regulamin danych PMAXTP: https://klimat.imgw.pl/opady-maksymalne"


def test_attribution_merges_the_lines_of_several_tools_in_the_dev_20_4_order() -> None:
    merged = Attribution.from_documents(
        [
            {"attribution": ["unknown", Z, SG, G], "terms_notice": [RK]},
            {"attribution": [CP, C, M], "terms_notice": ["other", RH]},
            {"attribution": [PP, PS, P, S, G], "terms_notice": [RD, RK]},
        ]
    )

    assert merged == Attribution(
        (S, P, PS, PP, M, C, CP, G, SG, Z, "unknown"), (RD, RH, RK, "other")
    )


def test_attribution_keeps_two_gugik_lines_in_the_g_place_in_the_order_first_seen() -> (
    None
):
    other = G.replace("NMT, BDOT10k", "PRG")

    merged = Attribution.of(Attribution((SG, other)), Attribution((G, S)))

    assert merged.lines == (S, other, G, SG)

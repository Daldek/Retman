"""The attribution and the terms notice of the data providers, passed on verbatim.

Nogat DEV §20 (ECO-060): a product with the data of IMGW-PIB or ČHMÚ, or with results
derived from them, carries the lines the providers' terms require: ``attribution``
(source, processed mark, monograph) and ``terms_notice`` (the conditions of use of
IMGW-PIB data and the terms that apply). The tools put them in their documents, at the
top level of the ``<tool>-result/1`` envelope; Retman words none of them itself
(ADR-024: the texts of the tool are passed on as they are). It merges the lines of the
runs of an operation, each once, in the order of DEV-20.4 (``attribution`` S, P, PS, PP,
M, C, CP, G, SG, Z; ``terms_notice`` RD, RH, RK of DEV-20.7), a line it does not know
after those, in the order first seen (an old CP with the detail in parentheses is
the CP of ECO-071, once), and carries them into what it writes and shows
(ADR-033):

* the result (``Result.attribution`` and ``Result.terms_notice``, also in
  ``result.json``) and its warnings, one line each, so the CLI shows them;
* every CSV table it writes, as the trailing columns ``attribution`` and
  ``terms_notice`` (DEV-20.5): one line per cell from the first data row down, empty
  below; a table with fewer rows than lines joins the rest into its last cell with a
  newline;
* the tool documents it saves, which keep their own fields.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = ["CSV_COLUMNS", "Attribution"]

CSV_COLUMNS: Final = ("attribution", "terms_notice")
"""The trailing columns of a CSV table that carry the two lists (DEV-20.5)."""

_IMGW: Final = "Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"
_IMGW_OF: Final = (
    "Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego"
)
_PMAXTP: Final = "https://klimat.imgw.pl/opady-maksymalne"
_CC_BY: Final = "licencja CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
_PROCESSED: Final = "; dane przetworzone"
_CP: Final = "Dane ČHMÚ zostały przetworzone"
"""The CP line of DEV §20 (ECO-071); an old ``CP (…)`` with the detail is read as it."""

# The lines of DEV §20 in the order of DEV-20.4 (S, P, PS, PP, M, C, CP, G, SG, Z) and
# DEV-20.7 (RD, RH, RK): a line with placeholders by its fixed start and end, any other
# whole (the end empty). They only order the lines the tools give; Retman writes none.
_ORDER: Final[tuple[tuple[str, str], ...]] = (
    (f"Źródłem pochodzenia danych jest {_IMGW}", ""),
    (f"Dane {_IMGW_OF} zostały przetworzone", ""),
    (f"Źródłem pochodzenia danych jest {_IMGW}, dane pochodzą ze strony {_PMAXTP}", ""),
    (f"Dane {_IMGW_OF} pochodzące ze strony {_PMAXTP} zostały przetworzone", ""),
    (
        "„Modele probabilistyczne opadów maksymalnych o określonym czasie trwania i "
        "prawdopodobieństwie przewyższenia – Projekt PMAXTP”, red. Bogdan "
        f"Ozga-Zieliński, {_IMGW}, Warszawa 2022",
        "",
    ),
    (
        "Źródło danych: Český hydrometeorologický ústav (ČHMÚ), "
        f"https://opendata.chmi.cz, {_CC_BY}",
        "",
    ),
    (_CP, ""),
    ("Źródło: Główny Urząd Geodezji i Kartografii – GUGiK, ", _PROCESSED),
    (f"Źródło: ISRIC – World Soil Information, SoilGrids, {_CC_BY}{_PROCESSED}", ""),
    ("Źródło: Český úřad zeměměřický a katastrální (ČÚZK), ", _PROCESSED),
    ("Regulamin danych IMGW-PIB: https://danepubliczne.imgw.pl/regulations", ""),
    (
        "Regulamin serwisu hydrologicznego IMGW-PIB: https://hydro.imgw.pl/#/regulamin",
        "",
    ),
    (f"Regulamin danych PMAXTP: {_PMAXTP}", ""),
)


def _rank(line: str) -> int:
    """Return the place of a line in :data:`_ORDER`; an unknown line comes last."""
    for place, (start, end) in enumerate(_ORDER):
        if line == start if not end else _fills(line, start, end):
            return place
    return len(_ORDER)


def _fills(line: str, start: str, end: str) -> bool:
    """Return whether a line fills the placeholders between ``start`` and ``end``."""
    return (
        len(line) > len(start) + len(end)
        and line.startswith(start)
        and line.endswith(end)
    )


def _canonical(line: str) -> str:
    """Return the CP line for an old ``CP (…)`` with the detail (DEV-20.4)."""
    return _CP if _fills(line, f"{_CP} (", ")") else line


def _merge(groups: Iterable[Iterable[str]]) -> tuple[str, ...]:
    found: dict[str, None] = {}
    for group in groups:
        for line in group:
            text = _canonical(line.strip())
            if text:
                found.setdefault(text)
    return tuple(sorted(found, key=_rank))


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _cells(lines: Sequence[str], rows: int) -> list[str]:
    """Spread lines over ``rows`` cells, the rest joined into the last one."""
    if len(lines) <= rows:
        return [*lines, *([""] * (rows - len(lines)))]
    return [*lines[: rows - 1], "\n".join(lines[rows - 1 :])]


@dataclass(frozen=True)
class Attribution:
    """What a product must say about the provider data it carries.

    Attributes
    ----------
    lines : tuple of str
        The ``attribution`` lines of the tools, verbatim.
    notice : tuple of str
        The ``terms_notice`` lines of the tools, verbatim.

    Examples
    --------
    >>> Attribution.of(Attribution(("a",)), Attribution(("a", "b"), ("n",))).lines
    ('a', 'b')
    """

    lines: tuple[str, ...] = ()
    notice: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        """Return whether there is anything to say."""
        return bool(self.lines or self.notice)

    @classmethod
    def of(cls, *parts: Attribution) -> Attribution:
        """Merge attributions, each line once, in the order of DEV-20.4 and DEV-20.7.

        Parameters
        ----------
        *parts : Attribution
            The attributions to merge.

        Returns
        -------
        Attribution
            Their union.
        """
        return cls(
            _merge(part.lines for part in parts), _merge(part.notice for part in parts)
        )

    @classmethod
    def from_document(cls, document: object) -> Attribution:
        """Read ``attribution`` and ``terms_notice`` of a tool's JSON document.

        Parameters
        ----------
        document : object
            The ``<tool>-result/1`` envelope (the fields are at its top level,
            DEV-20.6); those of its ``result`` are read too.

        Returns
        -------
        Attribution
            The lines; empty when the document has none.

        Examples
        --------
        >>> Attribution.from_document(
        ...     {"attribution": ["S", "P"], "terms_notice": ["N"], "result": {}}
        ... ).notice
        ('N',)
        """
        if not isinstance(document, Mapping):
            return cls()
        places: list[Mapping[str, object]] = [document]
        body = document.get("result")
        if isinstance(body, Mapping):
            places.append(body)
        return cls(
            _merge(_strings(place.get("attribution")) for place in places),
            _merge(_strings(place.get("terms_notice")) for place in places),
        )

    @classmethod
    def from_documents(cls, documents: Iterable[object]) -> Attribution:
        """Merge the lines of several tool documents (the runs of an operation).

        Parameters
        ----------
        documents : iterable of object
            The ``<tool>-result/1`` envelopes.

        Returns
        -------
        Attribution
            Their union, in the order of DEV-20.4 and DEV-20.7.
        """
        return cls.of(*(cls.from_document(document) for document in documents))

    def header(self) -> tuple[str, ...]:
        """Return the CSV columns to append; none when there is nothing to say."""
        return CSV_COLUMNS if self else ()

    def rows(self, rows: Iterable[Sequence[object]]) -> list[list[object]]:
        r"""Append the cells of the trailing CSV columns to the rows of a table.

        Parameters
        ----------
        rows : iterable of sequence
            The data rows.

        Returns
        -------
        list of list
            The rows with ``attribution`` and ``terms_notice`` cells; unchanged when
            there is nothing to say. A table without rows stays without rows.

        Examples
        --------
        >>> Attribution(("a", "b", "c"), ("n",)).rows([[1], [2]])
        [[1, 'a', 'n'], [2, 'b\nc', '']]
        """
        body = [list(row) for row in rows]
        if not self or not body:
            return body
        cells = zip(
            _cells(self.lines, len(body)), _cells(self.notice, len(body)), strict=True
        )
        return [[*row, *pair] for row, pair in zip(body, cells, strict=True)]

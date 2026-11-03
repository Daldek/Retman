"""Years, periods and the year type read from commands: forms, traps, conversions."""

import calendar
import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from retman.extractors.base import ExtractionContext, Match
from retman.extractors.dates import (
    archive_years,
    describe_period,
    explain_period,
    extract_period,
    extract_year_type,
    extract_years,
    period_dates,
    read_period_answer,
    read_year_type_answer,
    read_years_answer,
    validate_period,
    validate_year_type,
    validate_years,
)

TODAY = date(2026, 10, 19)


def _context(today: date = TODAY) -> ExtractionContext:
    return ExtractionContext(
        tool="imgwtools",
        settings={},
        project_dir=Path("."),
        scope={},
        lookup=lambda call: {},
        today=today,
    )


CTX = _context()


def _values(matches: list[Match]) -> list[Any]:
    return [match.readings[0].value for match in matches]


def _years(first: int, last: int | None = None) -> dict[str, Any]:
    return {"type": "years", "first": first, "last": first if last is None else last}


def _year_list(*years: int) -> dict[str, Any]:
    return {"type": "year_list", "years": list(years)}


def _dates(start: str, end: str) -> dict[str, Any]:
    return {"type": "dates", "start": start, "end": end}


def _fragments(text: str, matches: list[Match]) -> list[str]:
    return [text[match.start : match.end] for match in matches]


# --- years -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "first", "last"),
    [
        ("2000-2020", 2000, 2020),
        ("2000–2020", 2000, 2020),
        ("2000—2020", 2000, 2020),
        ("2000 - 2020", 2000, 2020),
        ("od 2000 do 2020", 2000, 2020),
        ("w latach 2000-2020", 2000, 2020),
        ("z lat 2000–2020", 2000, 2020),
        ("za lata 2000-2020", 2000, 2020),
        ("lata 2000 do 2020", 2000, 2020),
        ("2000 do 2020", 2000, 2020),
        ("od roku 2000 do roku 2020", 2000, 2020),
        ("od 2000 r. do 2020 r.", 2000, 2020),
        ("od 2000 roku aż do 2020 roku", 2000, 2020),
        ("od 2000, do 2020", 2000, 2020),
        ("l. 2000-2020", 2000, 2020),
        ("Pobierz dobowe dane ze stacji Poznań z lat 2000–2020.", 2000, 2020),
        ("Pobierz archiwum opadów 1950-2000", 1950, 2000),
    ],
)
def test_extract_years_reads_a_range(command: str, first: int, last: int) -> None:
    assert _values(extract_years(command)) == [_years(first, last)]


@pytest.mark.parametrize(
    "command",
    [
        "z 2015 roku",
        "rok 2015",
        "roku 2015",
        "w 2015 roku",
        "z 2015",
        "ze 2015",
        "za 2015",
        "w 2015",
        "we 2015",
        "dla 2015",
        "dla roku 2015",
        "2015 r.",
        "2015r",
        "2015r.",
        "2015 rok",
        "r. 2015",
        "Pobierz dane ze stacji Poznań z 2015 roku.",
    ],
)
def test_extract_years_reads_a_single_year_only_with_a_marker(command: str) -> None:
    assert _values(extract_years(command)) == [_years(2015)]


@pytest.mark.parametrize(
    ("command", "years"),
    [
        ("2010, 2012 i 2015", [2010, 2012, 2015]),
        ("2010, 2012, 2015", [2010, 2012, 2015]),
        ("2010,2012,2015", [2010, 2012, 2015]),
        ("2010; 2012", [2010, 2012]),
        ("w latach 2010, 2012 oraz 2015", [2010, 2012, 2015]),
        ("z 2010 i z 2012 roku", [2010, 2012]),
        # Two consecutive years are a list of two, not a range
        ("2010 i 2011", [2010, 2011]),
        # The tool's own syntax: ranges inside a list are written out
        ("2000–2002, 2005", [2000, 2001, 2002, 2005]),
        ("od 2000 do 2002 i 2010", [2000, 2001, 2002, 2010]),
    ],
)
def test_extract_years_reads_a_list(command: str, years: list[int]) -> None:
    assert _values(extract_years(command)) == [_year_list(*years)]


@pytest.mark.parametrize(
    "command",
    [
        "2015",
        "dane 2015",
        # Four digits that mean something else
        "powiat 1465",
        "kod powiatu 1465",
        "w układzie 2180",
        "EPSG:2180",
        "PL1992",
        "arkusz N-34-130-D",
        # Parts of other numbers
        "stacja 150160180",
        "x=530000 y=382000",
        "12000",
        "20.20",
        "punkt 52.2297 16.9300",
        "52,2297 2010",
        "2015mm",
        "10:30",
        # Parts of dates, which are not years (and slash dates are not read)
        "1.01.2000",
        "2000-01-01",
        "15 maja 2010",
        "od 1 stycznia 2000 do 31 grudnia 2020",
        "01/02/2000",
        "z 01/02/2000",
        # A marker that is not directly before the number
        "z danych 2015",
        "w stacji o numerze 2015",
    ],
)
def test_extract_years_does_not_take_other_numbers_for_years(command: str) -> None:
    assert extract_years(command) == []


@pytest.mark.parametrize(
    "command",
    [
        # Open periods: one end only
        "od 2010",
        "od roku 2010",
        "od 2010 r.",
        "do 2020",
        # Relative periods are never guessed
        "ostatnie 10 lat",
        "ostatnich 5 lat",
        "od 5 lat",
        "od 2010 do dziś",
        "z 2010 do dzis",
        "z 2010, do dzis",
        # Part of a longer form that would be read wrongly
        "2010-12",
        "2010/11",
        "rok hydrologiczny 2010/2011",
        "z 2010 lub 2012",
        "z 2010 lub z 2012",
        "z lat 2000–2020 bez 2015",
        "2000-2005-2010",
        "2000, - 2020",
        "od 2000 do 31.12.2020",
    ],
)
def test_extract_years_gives_nothing_for_open_relative_or_tangled_forms(
    command: str,
) -> None:
    assert extract_years(command) == []
    assert extract_period(command) == []


@pytest.mark.parametrize(
    ("command", "key", "args"),
    [
        ("Pobierz dane od 2010", "years_open_end", {"year": "2010"}),
        ("od roku 2010", "years_open_end", {"year": "2010"}),
        ("do 2020", "years_open_start", {"year": "2020"}),
        ("od 15.05.2010", "period_open_end", {"date": "2010-05-15"}),
        ("od maja 2010", "period_open_end", {"date": "2010-05-01"}),
        ("do 15.05.2010", "period_open_start", {"date": "2010-05-15"}),
        ("do listopada 2019", "period_open_start", {"date": "2019-11-30"}),
        ("ostatnie 10 lat", "period_relative", {"phrase": "ostatnie 10 lat"}),
        ("z ostatnich 5 lat", "period_relative", {"phrase": "ostatnich 5 lat"}),
        ("10 ostatnich lat", "period_relative", {"phrase": "10 ostatnich lat"}),
        ("ostatnie dwa lata", "period_relative", {"phrase": "ostatnie dwa lata"}),
        ("dane od 5 lat", "period_relative", {"phrase": "od 5 lat"}),
        ("z ubiegłego roku", "period_relative", {"phrase": "ubiegłego roku"}),
        ("od 2010 do dziś", "period_relative", {"phrase": "od 2010 do dziś"}),
        (
            "od 1.01.2010 do dzisiaj",
            "period_relative",
            {"phrase": "od 1.01.2010 do dzisiaj"},
        ),
    ],
)
def test_explain_period_names_why_nothing_was_read(
    command: str, key: str, args: dict[str, str]
) -> None:
    hint = explain_period(command)

    assert hint is not None
    assert (hint.key, hint.args) == (f"extractors.hints.{key}", args)


@pytest.mark.parametrize("command", ["z 2015 roku", "2000-2020", "Pobierz dane", ""])
def test_explain_period_is_silent_when_the_text_has_no_open_form(command: str) -> None:
    assert explain_period(command) is None


def test_explain_period_reports_the_relative_phrase_before_an_open_end() -> None:
    hint = explain_period("od 2010, a właściwie ostatnie 3 lata")

    assert hint is not None
    assert hint.key == "extractors.hints.period_relative"


def test_extract_years_returns_a_backwards_range_as_written() -> None:
    value = _values(extract_years("od 2020 do 2000"))[0]

    assert value == _years(2020, 2000)
    assert validate_years(value, CTX) == "extractors.errors.years_order"
    assert _values(extract_years("2020-2000")) == [_years(2020, 2000)]


def test_extract_years_returns_an_unordered_list_as_written() -> None:
    value = _values(extract_years("2012, 2010, 2010"))[0]

    assert value == _year_list(2012, 2010, 2010)
    assert validate_years(value, CTX) == "extractors.errors.invalid_years"


@pytest.mark.parametrize(
    ("command", "first", "last"),
    [
        ("W LATACH 2000-2020", 2000, 2020),
        ("w latach 2000-2020", 2000, 2020),
        # One typo in the cue words of five letters or more
        ("w latch 2000-2020", 2000, 2020),
        ("w lataach 2000-2020", 2000, 2020),
        ("w latahc 2000-2020", 2000, 2020),
        ("w ladach 2000-2020", 2000, 2020),
        ("z rokiem 2015", 2015, 2015),
        ("z rokeim 2015", 2015, 2015),
        ("ROKIEM 2015", 2015, 2015),
    ],
)
def test_extract_years_tolerates_letter_case_and_one_typo(
    command: str, first: int, last: int
) -> None:
    assert _values(extract_years(command)) == [_years(first, last)]


@pytest.mark.parametrize(
    "command",
    [
        # Short cue words are matched exactly: "od"/"do", "roku", "lata" ...
        "do 2000 od 2020",
        "2015 rku",
        "lta 2015",
        "x 2015",
    ],
)
def test_extract_years_does_not_tolerate_typos_in_short_words(command: str) -> None:
    assert extract_years(command) == []


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("Pobierz dane z lat 2000-2020 ze stacji", "z lat 2000-2020"),
        ("Pobierz dane od 2000 do 2020 ze stacji", "od 2000 do 2020"),
        ("Pobierz dane z 2015 roku ze stacji", "z 2015 roku"),
        ("Pobierz dane 2015 r. ze stacji", "2015 r."),
        ("Pobierz dane z 2010, 2012 i 2015 roku ze stacji", "z 2010, 2012 i 2015 roku"),
        ("lata hydrologiczne 2000-2020", "lata hydrologiczne 2000-2020"),
        ("Dane z lat 2000-2020.", "z lat 2000-2020"),
    ],
)
def test_extract_years_span_covers_the_year_and_its_marker(
    command: str, fragment: str
) -> None:
    assert _fragments(command, extract_years(command)) == [fragment]


def test_extract_years_leaves_the_year_of_a_date_to_the_date() -> None:
    command = "Dane z 15 maja 2010 i z 2015 roku"

    assert _values(extract_years(command)) == [_years(2015)]
    assert _fragments(command, extract_years(command)) == ["z 2015 roku"]


def test_extract_years_reads_several_separate_forms_in_order() -> None:
    command = "z lat 2000–2005 (stacja 1234), w 2010 roku oraz dane dla 2015"

    assert _values(extract_years(command)) == [
        _years(2000, 2005),
        _years(2010),
        _years(2015),
    ]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("2015", [_years(2015)]),
        ("rok 2015", [_years(2015)]),
        ("2010, 2012 i 2015", [_year_list(2010, 2012, 2015)]),
        ("2000-2020", [_years(2000, 2020)]),
        ("od 2000 do 2020", [_years(2000, 2020)]),
        # An answer with an open end is still not an answer
        ("od 2010", []),
        ("nie wiem", []),
        ("1.01.2000", []),
    ],
)
def test_read_years_answer_accepts_bare_years(
    answer: str, expected: list[dict[str, Any]]
) -> None:
    assert _values(read_years_answer(answer)) == expected


# --- period: dates --------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "start", "end"),
    [
        # Numeric dates
        ("2000-01-01", "2000-01-01", "2000-01-01"),
        ("1.01.2000", "2000-01-01", "2000-01-01"),
        ("01.01.2000", "2000-01-01", "2000-01-01"),
        ("1.1.2000", "2000-01-01", "2000-01-01"),
        ("01.01.2000 r.", "2000-01-01", "2000-01-01"),
        ("od 2000-01-01 do 2020-12-31", "2000-01-01", "2020-12-31"),
        ("od 1.01.2000 do 31.12.2020", "2000-01-01", "2020-12-31"),
        ("1.01.2000 - 31.12.2020", "2000-01-01", "2020-12-31"),
        ("01.01.2000–31.12.2020", "2000-01-01", "2020-12-31"),
        ("1.01.2000-31.12.2020", "2000-01-01", "2020-12-31"),
        ("od 01.01.2000 r. do 31.12.2020 r.", "2000-01-01", "2020-12-31"),
        ("29.02.2000", "2000-02-29", "2000-02-29"),
        # Month names, with Polish letters and without
        ("od 1 stycznia 2000 do 31 grudnia 2020", "2000-01-01", "2020-12-31"),
        ("1 stycznia 2000 – 31 grudnia 2020", "2000-01-01", "2020-12-31"),
        ("od 1 listopada 2019 do 31 października 2020", "2019-11-01", "2020-10-31"),
        ("od 1 listopada 2019 do 31 pazdziernika 2020", "2019-11-01", "2020-10-31"),
        ("15 maja 2010", "2010-05-15", "2010-05-15"),
        ("15 MAJA 2010 ROKU", "2010-05-15", "2010-05-15"),
        ("dnia 1. stycznia 2000", "2000-01-01", "2000-01-01"),
        # Whole months
        ("styczen 2000 - grudzien 2020", "2000-01-01", "2020-12-31"),
        ("styczeń 2000 – grudzień 2020", "2000-01-01", "2020-12-31"),
        ("maj-wrzesien 2010", "2010-05-01", "2010-09-30"),
        ("maj–wrzesień 2010", "2010-05-01", "2010-09-30"),
        ("od maja do wrzesnia 2010", "2010-05-01", "2010-09-30"),
        ("od maja do września 2010", "2010-05-01", "2010-09-30"),
        ("od listopada 2019 do pazdziernika 2020", "2019-11-01", "2020-10-31"),
        ("od stycznia do grudnia 2010", "2010-01-01", "2010-12-31"),
        ("w maju 2010", "2010-05-01", "2010-05-31"),
        ("w styczniu 2010", "2010-01-01", "2010-01-31"),
        ("za listopad 2019 roku", "2019-11-01", "2019-11-30"),
        # Roman numerals (capitals) and abbreviations
        ("1 XI 2019 - 31 X 2020", "2019-11-01", "2020-10-31"),
        ("15.XI.2019", "2019-11-15", "2019-11-15"),
        ("15 sie 2010", "2010-08-15", "2010-08-15"),
        ("15 sty. 2010 - 20 lut. 2010", "2010-01-15", "2010-02-20"),
        ("sty 2010 - gru 2010", "2010-01-01", "2010-12-31"),
        ("paź 2019 – lis 2020", "2019-10-01", "2020-11-30"),
        # A range borrows what it lacks from its end
        ("od 1 do 15 maja 2010", "2010-05-01", "2010-05-15"),
        ("5-15 maja 2010", "2010-05-05", "2010-05-15"),
        ("od 1 maja do 30 września 2010", "2010-05-01", "2010-09-30"),
        # One typo in a long month name
        ("w stycznai 2010", "2010-01-01", "2010-01-31"),
        ("1 grudnai 2010", "2010-12-01", "2010-12-01"),
    ],
)
def test_extract_period_reads_dates(command: str, start: str, end: str) -> None:
    assert _values(extract_period(command)) == [_dates(start, end)]


@pytest.mark.parametrize("command", ["2010-05-15", "15.05.2010", "15 maja 2010 r."])
def test_extract_period_a_single_day_starts_and_ends_on_it(command: str) -> None:
    (value,) = _values(extract_period(command))

    assert value["start"] == value["end"] == "2010-05-15"


@pytest.mark.parametrize(
    ("form", "month"),
    [
        (form, month)
        for month, forms in {
            1: ("styczeń", "stycznia", "styczniu", "styczniem"),
            2: ("luty", "lutego", "lutym"),
            3: ("marzec", "marca", "marcu"),
            4: ("kwiecień", "kwietnia", "kwietniu"),
            5: ("maj", "maja", "maju"),
            6: ("czerwiec", "czerwca", "czerwcu"),
            7: ("lipiec", "lipca", "lipcu"),
            8: ("sierpień", "sierpnia", "sierpniu"),
            9: ("wrzesień", "września", "wrześniu"),
            10: ("październik", "października", "październiku"),
            11: ("listopad", "listopada", "listopadzie"),
            12: ("grudzień", "grudnia", "grudniu"),
        }.items()
        for form in forms
    ],
)
def test_extract_period_a_whole_month_in_any_case_ends_on_its_last_day(
    form: str, month: int
) -> None:
    (value,) = _values(extract_period(f"w {form} 2010"))

    last = calendar.monthrange(2010, month)[1]
    assert value == _dates(f"2010-{month:02d}-01", f"2010-{month:02d}-{last:02d}")


@pytest.mark.parametrize(
    ("command", "end"),
    [
        ("w lutym 2000", "2000-02-29"),
        ("w lutym 2004", "2004-02-29"),
        ("w lutym 2001", "2001-02-28"),
        ("w lutym 1900", "1900-02-28"),
        ("luty 2000 - marzec 2000", "2000-03-31"),
        ("od stycznia 2000 do lutego 2000", "2000-02-29"),
        ("od stycznia 2001 do lutego 2001", "2001-02-28"),
    ],
)
def test_extract_period_respects_leap_years_in_month_ends(
    command: str, end: str
) -> None:
    assert _values(extract_period(command))[0]["end"] == end


@pytest.mark.parametrize(
    "command",
    [
        "31.02.2000",
        "1.13.2000",
        "0.05.2010",
        "29.02.2001",
        "29.02.1900",
        "2000-02-30",
        "2000-13-01",
        "31 kwietnia 2010",
        "31 lutego 2010",
        "od 31 lutego 2010 do 1 marca 2010",
        "od 1 lutego 2010 do 31 lutego 2010",
        "32 maja 2010",
        "01/02/2000",
        "1.01.00",
        # Roman numerals only in capitals, abbreviations only next to a day or year
        "1 xi 2019",
        "maj-wrz",
        "sty-gru 2010",
        "sty - gru 2010",
        # Not a period: a month alone, a day alone
        "w maju",
        "maj",
        "15 maja",
        "od maja",
    ],
)
def test_extract_period_gives_nothing_for_impossible_or_unreadable_dates(
    command: str,
) -> None:
    assert extract_period(command) == []
    assert extract_years(command) == []


@pytest.mark.parametrize(
    "command",
    [
        "od 15.05.2010",
        "od 15 maja 2010",
        "do 15.05.2010",
        "od 1 stycznia 2000 do 2020",
        "od 2000 do 31 grudnia 2020",
        "maj 2010 do września",
        "od 1.01.2000 do końca 2020",
        "1.01.2000-2020",
        "15.05.2010 do dziś",
    ],
)
def test_extract_period_gives_nothing_for_a_date_with_one_end(command: str) -> None:
    assert extract_period(command) == []


def test_extract_period_returns_a_backwards_range_of_dates_as_written() -> None:
    (value,) = _values(extract_period("od 31.12.2020 do 1.01.2000"))

    assert value == _dates("2020-12-31", "2000-01-01")
    assert validate_period(value, CTX) == "extractors.errors.period_order"
    # Without a year of its own the start borrows the end's: also backwards
    (value,) = _values(extract_period("od listopada do października 2020"))
    assert value == _dates("2020-11-01", "2020-10-31")


def test_extract_period_dates_are_not_read_again_as_years() -> None:
    command = "Eksportuj od 1 stycznia 2000 do 31 grudnia 2020"

    matches = extract_period(command)

    assert _values(matches) == [_dates("2000-01-01", "2020-12-31")]
    assert _fragments(command, matches) == ["od 1 stycznia 2000 do 31 grudnia 2020"]


def test_extract_period_keeps_unrelated_years_next_to_a_date() -> None:
    command = "dane za 15 maja 2010 i z 2015 roku"

    matches = extract_period(command)

    assert _values(matches) == [_dates("2010-05-15", "2010-05-15"), _years(2015)]
    assert _fragments(command, matches) == ["15 maja 2010", "z 2015 roku"]


def test_extract_period_lists_matches_in_order_of_appearance() -> None:
    command = "w maju 2010 oraz z lat 2000-2005"

    matches = extract_period(command)

    assert [match.start for match in matches] == sorted(m.start for m in matches)
    assert _values(matches) == [_dates("2010-05-01", "2010-05-31"), _years(2000, 2005)]


@pytest.mark.parametrize(
    ("command", "value"),
    [
        ("z lat 2000–2020", _years(2000, 2020)),
        ("z 2015 roku", _years(2015)),
        ("2010, 2012 i 2015", _year_list(2010, 2012, 2015)),
    ],
)
def test_extract_period_also_returns_years_for_the_manifest_to_filter(
    command: str, value: dict[str, Any]
) -> None:
    assert _values(extract_period(command)) == [value]


def test_extract_period_two_separate_days_stay_two_matches() -> None:
    matches = extract_period("01.01.2000 i 31.12.2020")

    assert _values(matches) == [
        _dates("2000-01-01", "2000-01-01"),
        _dates("2020-12-31", "2020-12-31"),
    ]


def test_extract_period_asks_to_confirm_an_abbreviation_that_is_also_a_word() -> None:
    (match,) = extract_period("okres konczy sie 2020 r.")

    assert match.confirm
    assert match.readings[0].value == _dates("2020-08-01", "2020-08-31")


@pytest.mark.parametrize("command", ["15 sie 2010", "sie. 2010", "sty 2010"])
def test_extract_period_does_not_confirm_a_clear_abbreviation(command: str) -> None:
    (match,) = extract_period(command)

    assert not match.confirm


def test_extract_period_reads_sie_with_polish_letters_as_the_word() -> None:
    # "się 2020 r." is the ordinary word followed by a year, not August
    assert _values(extract_period("okres kończy się 2020 r.")) == [_years(2020)]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("2015", [_years(2015)]),
        ("2000-2020", [_years(2000, 2020)]),
        ("1.01.2000 - 31.12.2020", [_dates("2000-01-01", "2020-12-31")]),
        ("maj 2010", [_dates("2010-05-01", "2010-05-31")]),
        ("od 2010", []),
    ],
)
def test_read_period_answer_accepts_bare_years_and_dates(
    answer: str, expected: list[dict[str, Any]]
) -> None:
    assert _values(read_period_answer(answer)) == expected


# --- year type ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("lata hydrologiczne", "hydrological"),
        ("w latach hydrologicznych 2000-2020", "hydrological"),
        ("rok hydrologiczny", "hydrological"),
        ("roku hydrologicznym", "hydrological"),
        ("z lat 2000-2020 hydrologicznych", "hydrological"),
        ("hydrologiczne lata", "hydrological"),
        ("hydrologicznego roku", "hydrological"),
        ("rocznik hydrologiczny 2015", "hydrological"),
        ("r. hydrologiczny", "hydrological"),
        ("rok hydrol.", "hydrological"),
        ("kalendarzowe lata", "calendar"),
        ("lata kalendarzowe", "calendar"),
        ("rok kalendarzowy", "calendar"),
        ("w roku kalendarzowym", "calendar"),
        ("z lat 2000–2020 kalendarzowych", "calendar"),
        ("Eksportuj szereg za lata 2010–2015, rok hydrologiczny", "hydrological"),
        ("ROK HYDROLOGICZNY", "hydrological"),
        # Without Polish letters and with one typo
        ("lata hydrologiczen", "hydrological"),
        ("lata hydrlogiczne", "hydrological"),
        ("rok kalendarzwy", "calendar"),
        ("rok kalendarzowy", "calendar"),
    ],
)
def test_extract_year_type_reads_the_adjective_of_the_year_noun(
    command: str, expected: str
) -> None:
    matches = extract_year_type(command)

    assert _values(matches) == [expected]
    assert matches[0].readings[0].label_key == f"extractors.year_type.{expected}"


@pytest.mark.parametrize(
    "command",
    [
        # "hydrologiczne" describes the data, not the years
        "Pobierz dobowe dane hydrologiczne z lat 2000–2020",
        "dane hydrologiczne z lat 2000",
        "dane kalendarzowe z lat 2000-2020",
        "szereg hydrologiczny dla lat 2000-2020",
        "roczne dane hydrologiczne z lat 2000-2020",
        # The adjective agrees with the data noun, not with the year noun
        "dane hydrologiczne lat 2000-2020",
        "dane hydrologiczne rok 2015",
        "dobowe dane hydrologiczne roku 2015",
        "dane z lat 2000-2020 hydrologiczne",
        # Not an adjective of a year
        "stacja hydrologiczna Poznań",
        "kalendarz hydrologa",
        "rok hydro",
        "lata hydro",
        "rok kalendarz",
        "",
    ],
)
def test_extract_year_type_ignores_hydrological_data(command: str) -> None:
    assert extract_year_type(command) == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("lata hydrologiczne i kalendarzowe", ["hydrological", "calendar"]),
        ("rok hydrologiczny albo kalendarzowy", ["hydrological", "calendar"]),
        ("rok hydrologiczny, rok kalendarzowy", ["hydrological", "calendar"]),
        ("rok hydrol. i kalend.", ["hydrological", "calendar"]),
        ("lata kalendarzowe, hydrologiczne", ["calendar", "hydrological"]),
        ("hydrologiczne lub kalendarzowe lata", ["hydrological", "calendar"]),
        ("hydrologiczny i kalendarzowy rok 2015", ["hydrological", "calendar"]),
    ],
)
def test_extract_year_type_both_types_are_separate_matches(
    command: str, expected: list[str]
) -> None:
    assert _values(extract_year_type(command)) == expected


@pytest.mark.parametrize(
    ("command", "fragment"),
    [
        ("Eksportuj rok hydrologiczny dla stacji", "rok hydrologiczny"),
        ("w latach hydrologicznych 2000-2020", "latach hydrologicznych"),
        ("z lat 2000-2020 hydrologicznych", "lat 2000-2020 hydrologicznych"),
        ("lata hydrologiczne i kalendarzowe", "lata hydrologiczne"),
    ],
)
def test_extract_year_type_span_covers_the_adjective_and_its_noun(
    command: str, fragment: str
) -> None:
    assert _fragments(command, extract_year_type(command))[0] == fragment


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("hydrologiczne", "hydrological"),
        ("hydrologiczny", "hydrological"),
        ("kalendarzowe", "calendar"),
        ("kalendarzowy", "calendar"),
        ("hydro", "hydrological"),
        ("hydrol", "hydrological"),
        ("hydrol.", "hydrological"),
        ("kalendarz", "calendar"),
        ("kalend", "calendar"),
        ("hydrologiczne lata", "hydrological"),
        ("HYDROLOGICZNE", "hydrological"),
        ("hydrologicze, poproszę", "hydrological"),
    ],
)
def test_read_year_type_answer_accepts_a_bare_adjective(
    answer: str, expected: str
) -> None:
    assert _values(read_year_type_answer(answer)) == [expected]


@pytest.mark.parametrize("answer", ["tak", "nie wiem", "2015", ""])
def test_read_year_type_answer_gives_nothing_without_an_adjective(answer: str) -> None:
    assert read_year_type_answer(answer) == []


def test_read_year_type_answer_both_types_are_two_matches() -> None:
    answer = "kalendarzowe czy hydrologiczne?"

    assert _values(read_year_type_answer(answer)) == ["calendar", "hydrological"]


# --- validators --------------------------------------------------------------------

_OUT_OF_RANGE = "extractors.errors.years_out_of_range"
_ORDER = "extractors.errors.years_order"
_INVALID_YEARS = "extractors.errors.invalid_years"
_INVALID_PERIOD = "extractors.errors.invalid_period"
_PERIOD_ORDER = "extractors.errors.period_order"
_PERIOD_RANGE = "extractors.errors.period_out_of_range"

_YEARS_CASES: list[tuple[Any, str | None]] = [
    (_years(2000, 2020), None),
    (_years(2015), None),
    (_years(1887, 2026), None),
    (_years(1886, 2020), _OUT_OF_RANGE),
    (_years(2000, 2027), _OUT_OF_RANGE),
    (_years(2030), _OUT_OF_RANGE),
    (_years(2020, 2000), _ORDER),
    ({"type": "years", "first": 2000}, _INVALID_YEARS),
    ({"type": "years", "first": "2000", "last": 2020}, _INVALID_YEARS),
    ({"type": "years", "first": 2000.0, "last": 2020}, _INVALID_YEARS),
    ({"type": "years", "first": True, "last": 2020}, _INVALID_YEARS),
    (_year_list(2010, 2012, 2015), None),
    (_year_list(2010, 2011), None),
    (_year_list(2010), _INVALID_YEARS),
    (_year_list(), _INVALID_YEARS),
    (_year_list(2012, 2010), _INVALID_YEARS),
    (_year_list(2010, 2010), _INVALID_YEARS),
    (_year_list(1800, 2010), _OUT_OF_RANGE),
    (_year_list(2010, 2030), _OUT_OF_RANGE),
    ({"type": "year_list", "years": "2010,2012"}, _INVALID_YEARS),
    ({"type": "year_list", "years": [2010, "2012"]}, _INVALID_YEARS),
    (_dates("2000-01-01", "2000-12-31"), _INVALID_YEARS),
    ({"type": "x"}, _INVALID_YEARS),
    ({}, _INVALID_YEARS),
    ("2000-2020", _INVALID_YEARS),
    (2015, _INVALID_YEARS),
    (None, _INVALID_YEARS),
]


@pytest.mark.parametrize(("value", "error"), _YEARS_CASES)
def test_validate_years_checks_structure_range_and_order(
    value: Any, error: str | None
) -> None:
    assert validate_years(value, CTX) == error


_PERIOD_CASES: list[tuple[Any, str | None]] = [
    (_years(2000, 2020), None),
    (_years(2020, 2000), _ORDER),
    (_years(1800, 1900), _OUT_OF_RANGE),
    (_dates("2000-01-01", "2020-12-31"), None),
    (_dates("2010-05-15", "2010-05-15"), None),
    (_dates("1887-01-01", "1887-12-31"), None),
    (_dates("2026-10-19", "2026-10-19"), None),
    (_dates("2026-01-01", "2026-10-20"), _PERIOD_RANGE),
    (_dates("1886-12-31", "1887-06-01"), _PERIOD_RANGE),
    (_dates("2030-01-01", "2030-12-31"), _PERIOD_RANGE),
    (_dates("2020-12-31", "2000-01-01"), _PERIOD_ORDER),
    (_dates("2000-02-30", "2000-03-01"), _INVALID_PERIOD),
    (_dates("2000-1-1", "2000-12-31"), _INVALID_PERIOD),
    (_dates("20000101", "20001231"), _INVALID_PERIOD),
    (_dates("2000-01-01T00:00:00", "2000-12-31"), _INVALID_PERIOD),
    (_dates("2000-01-01 ", "2000-12-31"), _INVALID_PERIOD),
    ({"type": "dates", "start": "2000-01-01"}, _INVALID_PERIOD),
    ({"type": "dates", "start": 20000101, "end": "2000-12-31"}, _INVALID_PERIOD),
    # A list of years is not a continuous period
    (_year_list(2010, 2012), _INVALID_PERIOD),
    ({"type": "x"}, _INVALID_PERIOD),
    ("2000-2020", _INVALID_PERIOD),
    (None, _INVALID_PERIOD),
]


@pytest.mark.parametrize(("value", "error"), _PERIOD_CASES)
def test_validate_period_checks_years_and_dates(value: Any, error: str | None) -> None:
    assert validate_period(value, CTX) == error


@pytest.mark.parametrize(
    ("validate", "cases"),
    [(validate_years, _YEARS_CASES), (validate_period, _PERIOD_CASES)],
)
def test_validators_give_the_same_answer_after_a_json_round_trip(
    validate: Callable[[Any, ExtractionContext], str | None],
    cases: list[tuple[Any, str | None]],
) -> None:
    for value, error in cases:
        assert validate(json.loads(json.dumps(value)), CTX) == error


def test_validators_judge_the_future_by_the_date_of_the_context() -> None:
    next_year = _years(2027)
    later = _context(date(2027, 1, 1))

    assert validate_years(next_year, CTX) == _OUT_OF_RANGE
    assert validate_years(next_year, later) is None
    assert validate_years(_years(TODAY.year), CTX) is None
    assert validate_period(_dates("2027-01-01", "2027-01-01"), CTX) == _PERIOD_RANGE
    assert validate_period(_dates("2027-01-01", "2027-01-01"), later) is None


@pytest.mark.parametrize(
    "command",
    [
        "z lat 2000–2020",
        "z 2015 roku",
        "2010, 2012 i 2015",
        "od 2000 do 2002 i 2010",
        "lata hydrologiczne 2000-2020",
    ],
)
def test_validate_years_accepts_what_extract_years_reads(command: str) -> None:
    matches = extract_years(command)

    assert matches
    assert all(validate_years(_values([m])[0], CTX) is None for m in matches)


@pytest.mark.parametrize(
    "command",
    [
        "z lat 2000–2020",
        "z 2015 roku",
        "od 1 stycznia 2000 do 31 grudnia 2020",
        "maj–wrzesień 2010",
        "w lutym 2000",
        "15 maja 2010",
        "1 XI 2019 - 31 X 2020",
        "sty 2010 - gru 2010",
    ],
)
def test_validate_period_accepts_what_extract_period_reads(command: str) -> None:
    matches = extract_period(command)

    assert matches
    assert all(validate_period(_values([m])[0], CTX) is None for m in matches)


# --- plan text ---------------------------------------------------------------------


class _Texts:
    """The texts of the display keys, as in ``pl.toml``."""

    templates = {
        "extractors.display.years": "{first}–{last}",
        "extractors.display.year": "{first}",
        "extractors.display.year_list": "{years}",
        "extractors.display.dates": "{start} – {end}",
        "extractors.display.date": "{start}",
    }

    def get(self, key: str, **args: object) -> str:
        return self.templates[key].format(**args)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (_years(2000, 2020), "2000–2020"),
        (_years(2015), "2015"),
        (_year_list(2010, 2012, 2015), "2010, 2012, 2015"),
        (_dates("2000-01-01", "2020-12-31"), "2000-01-01 – 2020-12-31"),
        (_dates("2010-05-15", "2010-05-15"), "2010-05-15"),
    ],
)
def test_describe_period_shows_the_value_the_tool_will_get(
    value: dict[str, Any], text: str
) -> None:
    assert describe_period(value, _Texts()) == text


def test_describe_period_rejects_a_value_that_is_not_a_period() -> None:
    with pytest.raises(ValueError):
        describe_period({"type": "station"}, _Texts())


# --- conversions -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("period", "year_type", "start", "end"),
    [
        (_years(2000, 2020), "calendar", date(2000, 1, 1), date(2020, 12, 31)),
        (_years(2000, 2020), "hydrological", date(1999, 11, 1), date(2020, 10, 31)),
        (_years(2015), "hydrological", date(2014, 11, 1), date(2015, 10, 31)),
        (_years(2015), "calendar", date(2015, 1, 1), date(2015, 12, 31)),
        # Dates are what they are, whatever the year type
        (
            _dates("2010-05-01", "2010-09-30"),
            "calendar",
            date(2010, 5, 1),
            date(2010, 9, 30),
        ),
        (
            _dates("2010-05-01", "2010-09-30"),
            "hydrological",
            date(2010, 5, 1),
            date(2010, 9, 30),
        ),
    ],
)
def test_period_dates_turns_a_period_into_first_and_last_day(
    period: dict[str, Any], year_type: str, start: date, end: date
) -> None:
    assert period_dates(period, year_type) == (start, end)


@pytest.mark.parametrize(
    ("period", "year_type"),
    [
        (_year_list(2010, 2012), "calendar"),
        (_years(2020, 2000), "calendar"),
        (_years(2000, 2020), "fiscal"),
        (_years(2000, 2020), ""),
        (_years(1), "hydrological"),
        ({"type": "years", "first": "2000", "last": 2020}, "calendar"),
        ({"type": "x"}, "calendar"),
        (_dates("2020-01-01", "2000-01-01"), "calendar"),
        (_dates("2000-02-30", "2000-03-01"), "calendar"),
        (_dates("2000-01-01", "oops"), "calendar"),
    ],
)
def test_period_dates_rejects_what_is_not_a_continuous_period(
    period: dict[str, Any], year_type: str
) -> None:
    with pytest.raises(ValueError):
        period_dates(period, year_type)


@pytest.mark.parametrize(
    ("start", "end", "numbering", "expected"),
    [
        # IMGW hydrological archives: file codz_2020_01 holds November 2019
        (date(2000, 1, 1), date(2020, 12, 31), "hydrological", list(range(2000, 2022))),
        (date(2000, 1, 1), date(2020, 12, 31), "calendar", list(range(2000, 2021))),
        (
            date(1999, 11, 1),
            date(2020, 10, 31),
            "hydrological",
            list(range(2000, 2021)),
        ),
        (date(2010, 5, 15), date(2010, 5, 15), "hydrological", [2010]),
        (date(2010, 11, 1), date(2010, 11, 1), "hydrological", [2011]),
        (date(2010, 10, 31), date(2010, 11, 1), "hydrological", [2010, 2011]),
        (date(2010, 12, 31), date(2011, 1, 1), "calendar", [2010, 2011]),
        (date(2010, 12, 31), date(2011, 1, 1), "hydrological", [2011]),
    ],
)
def test_archive_years_names_the_years_in_the_archive_numbering(
    start: date, end: date, numbering: str, expected: list[int]
) -> None:
    assert archive_years(start, end, numbering) == expected


def test_archive_years_rejects_a_backwards_period_and_an_unknown_numbering() -> None:
    with pytest.raises(ValueError):
        archive_years(date(2010, 1, 2), date(2010, 1, 1), "calendar")
    with pytest.raises(ValueError):
        archive_years(date(2010, 1, 1), date(2010, 1, 2), "fiscal")


def _year_period(year: int, numbering: str) -> tuple[date, date]:
    """Days an archive year holds, written down independently of the code."""
    if numbering == "hydrological":
        return date(year - 1, 11, 1), date(year, 10, 31)
    return date(year, 1, 1), date(year, 12, 31)


def _grid() -> list[tuple[date, date]]:
    starts = [
        date(year, month, day)
        for year in (1999, 2000, 2001)
        for month, day in ((1, 1), (5, 15), (10, 31), (11, 1), (12, 31))
    ]
    offsets = (0, 1, 61, 200, 364, 365, 366, 400, 800)
    return [(s, s + timedelta(days=offset)) for s in starts for offset in offsets]


@pytest.mark.parametrize("numbering", ["hydrological", "calendar"])
def test_archive_years_cover_every_day_and_no_year_more_than_needed(
    numbering: str,
) -> None:
    for start, end in _grid():
        years = archive_years(start, end, numbering)

        assert years == list(range(years[0], years[-1] + 1))
        day = start
        while day <= end:
            holders = [
                year
                for year in years
                if _year_period(year, numbering)[0]
                <= day
                <= _year_period(year, numbering)[1]
            ]
            assert len(holders) == 1, (start, end, numbering, day)
            day += timedelta(days=1)
        # Dropping the first or the last year would leave its edge day uncovered
        first_start, first_end = _year_period(years[0], numbering)
        last_start, last_end = _year_period(years[-1], numbering)
        assert first_start <= start <= first_end
        assert last_start <= end <= last_end


@pytest.mark.parametrize("year_type", ["hydrological", "calendar"])
@pytest.mark.parametrize("numbering", ["hydrological", "calendar"])
@pytest.mark.parametrize("first, last", [(2000, 2020), (2015, 2015), (1990, 1991)])
def test_years_convert_to_exactly_the_archive_years_of_a_matching_numbering(
    year_type: str, numbering: str, first: int, last: int
) -> None:
    start, end = period_dates(_years(first, last), year_type)

    years = archive_years(start, end, numbering)

    if year_type == numbering:
        assert years == list(range(first, last + 1))
    elif year_type == "calendar":
        # Calendar years reach into November and December of the year before the
        # last hydrological year
        assert years == list(range(first, last + 2))
    else:
        assert years == list(range(first - 1, last + 1))


def test_period_and_year_type_of_a_command_give_the_archive_years() -> None:
    command = "od 1.01.2000 do 31.12.2020, lata kalendarzowe"
    (period,) = _values(extract_period(command))
    (year_type,) = _values(extract_year_type(command))

    start, end = period_dates(period, year_type)

    assert (start, end) == (date(2000, 1, 1), date(2020, 12, 31))
    # Hydrological archives number a year after the November before it
    assert archive_years(start, end, "hydrological") == list(range(2000, 2022))


@pytest.mark.parametrize(
    "command",
    [
        "z lat 2000–2020",
        "od 1 stycznia 2000 do 31 grudnia 2020",
        "maj–wrzesień 2010 oraz z 2015 roku",
        "od 2000 do ",
        "2010-",
        "-2010",
        "w latach, 2010,",
        "1.01.2000.",
        ".2010.",
        "od od 2010 do do 2020",
        "z z 2015 r. r.",
        "XI 2019 - X 2020",
        "1 XI - 31 X 2020",
    ],
)
def test_matches_point_at_the_fragment_they_read(command: str) -> None:
    for read in (extract_years, extract_period, read_years_answer, read_period_answer):
        matches = read(command)

        assert [m.start for m in matches] == sorted(m.start for m in matches)
        for match in matches:
            assert 0 <= match.start < match.end <= len(command)
            assert command[match.start : match.end].strip() != ""
            assert len(match.readings) == 1


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("hydrological", True),
        ("calendar", True),
        ("Calendar", False),
        ("hydrologiczne", False),
        (None, False),
        (["calendar"], False),
    ],
)
def test_validate_year_type_accepts_only_the_two_numberings(
    value: Any, valid: bool
) -> None:
    assert (validate_year_type(value) is None) is valid

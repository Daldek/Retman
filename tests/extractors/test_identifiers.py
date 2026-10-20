"""Names of project tasks: read as written, never silently fixed."""

import pytest

from retman.extractors.identifiers import (
    extract_identifiers,
    read_identifier_answer,
    validate_identifier,
)


def _names(command: str) -> list[str]:
    return [match.readings[0].value for match in extract_identifiers(command)]


@pytest.mark.parametrize(
    ("command", "names"),
    [
        ('Dodaj zadanie "opady_poznan" do projektu', ["opady_poznan"]),
        ("Dodaj zadanie „opady” do projektu", ["opady"]),
        ("usuń zadanie przeplywy-warta", ["przeplywy-warta"]),
        ("nazwij zadanie opady_2000", ["opady_2000"]),
        ("dodaj zadanie o nazwie opady z lat 2000-2020", ["opady"]),
        ("dodaj do projektu zadanie pod nazwą opady_poznan", ["opady_poznan"]),
        ('zadanie opady_poznan i zadanie "opady_poznan"', ["opady_poznan"]),
    ],
)
def test_name_is_quoted_follows_an_explicit_cue_or_looks_like_an_identifier(
    command: str, names: list[str]
) -> None:
    assert _names(command) == names


@pytest.mark.parametrize(
    "command",
    [
        "dodaj zadanie pobierania opadów",
        "usuń zadanie",
        'dodaj stację "Poznań-Ławica"',
        "dodaj do projektu szereg przepływów stacji 150160180 z lat 2000-2020",
    ],
)
def test_ordinary_words_and_other_quoted_text_are_not_names(command: str) -> None:
    assert extract_identifiers(command) == []


def test_name_after_a_cue_is_read_as_typed_and_rejected_by_the_validator() -> None:
    [name] = _names("zadanie Opady_Poznan")

    assert name == "Opady_Poznan"
    assert validate_identifier(name) == "extractors.errors.invalid_identifier"


def test_answer_with_one_word_is_the_name_even_in_quotes() -> None:
    assert [m.readings[0].value for m in read_identifier_answer(' "opady_2000" ')] == [
        "opady_2000"
    ]
    assert [m.readings[0].value for m in read_identifier_answer("opady")] == ["opady"]
    assert read_identifier_answer("") == []


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("opady_poznan", True),
        ("a", True),
        ("0abc", True),
        ("a" * 64, True),
        ("a" * 65, False),
        ("", False),
        ("_opady", False),
        ("-opady", False),
        ("Opady", False),
        ("opady poznan", False),
        ("opady.poznan", False),
        ("opady_poznań", False),
        (7, False),
        (None, False),
    ],
)
def test_validator_applies_the_tools_name_rule(name: object, valid: bool) -> None:
    assert (validate_identifier(name) is None) is valid

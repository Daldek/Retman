"""The extractor registries are consistent and every text the code names exists."""

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from extractor_context import make_context

import retman.extractors as extractors
from retman.adapters.catalog import ToolError
from retman.extractors import (
    ANSWER_EXTRACTORS,
    CONTEXT_ANSWER_EXTRACTORS,
    CONTEXT_EXTRACTORS,
    CONTEXT_HINTS,
    CONTEXT_VALIDATORS,
    DESCRIBERS,
    EXTRACTORS,
    VALIDATORS,
    describe_value,
    explain_missing,
    extractor_known,
    read_answer,
    read_command,
    validate_value,
)
from retman.i18n.loader import Texts, load_core_texts


def test_every_extractor_is_in_exactly_one_registry_with_its_validator() -> None:
    assert not set(EXTRACTORS) & set(CONTEXT_EXTRACTORS)
    assert set(VALIDATORS) == set(EXTRACTORS)
    assert set(CONTEXT_VALIDATORS) == set(CONTEXT_EXTRACTORS)


def test_optional_hooks_belong_to_registered_extractors() -> None:
    assert set(ANSWER_EXTRACTORS) <= set(EXTRACTORS)
    assert set(CONTEXT_ANSWER_EXTRACTORS) <= set(CONTEXT_EXTRACTORS)
    assert set(CONTEXT_HINTS) <= set(CONTEXT_EXTRACTORS)
    assert set(DESCRIBERS) <= set(EXTRACTORS) | set(CONTEXT_EXTRACTORS)


def test_extractor_known_covers_both_registries() -> None:
    assert all(extractor_known(name) for name in (*EXTRACTORS, *CONTEXT_EXTRACTORS))
    assert not extractor_known("no_such_extractor")


def test_plain_extractors_are_read_without_looking_at_the_context() -> None:
    context = make_context()

    [match] = read_command("identifier", 'dodaj zadanie "opady"', context)

    assert match.readings[0].value == "opady"
    assert validate_value("identifier", "opady", context) is None
    assert validate_value("identifier", "Opady", context) is not None


def test_context_extractors_get_the_context() -> None:
    context = make_context(scope={"variables": ["H", "Q", "T"]})

    [match] = read_command("variables", "przepływ", context)

    assert match.readings[0].value == "Q"
    assert validate_value("variables", "P", context) == (
        "extractors.errors.variable_not_in_dataset"
    )


def test_answer_reader_is_used_when_the_extractor_has_one() -> None:
    context = make_context()

    # "opady" is a name for the command reader (needs a cue) but the whole answer
    # for the answer reader
    assert read_command("place_query", "opady", context) == []
    assert read_answer("place_query", "opady", context)[0].readings[0].value[
        "text"
    ] == ("opady")
    # No answer reader: the command reader is used
    assert read_answer("station", "kod 150160180", context)[0].readings[0].value[
        "code"
    ] == ("150160180")


def test_hint_comes_only_from_extractors_that_have_one() -> None:
    def no_catalog(call: Any) -> Any:
        raise ToolError("imgwtools", "not_found", "no catalog")

    context = make_context(lookup=no_catalog)

    hint = explain_missing("station", "ze stacji Poznań", context)

    assert hint is not None
    assert hint.key == "extractors.hints.station_no_catalog"
    assert explain_missing("identifier", "zadanie", context) is None


def test_values_are_described_by_extractor_name() -> None:
    texts = load_core_texts("pl")
    station = {
        "type": "station",
        "provider": "IMGW-PIB",
        "kind": "meteo",
        "code": "352160330",
        "name": "POZNAŃ-ŁAWICA",
        "river": None,
        "in_catalog": True,
    }

    assert describe_value("station", station, texts) == (
        "POZNAŃ-ŁAWICA (meteo, IMGW-PIB, kod 352160330)"
    )
    assert describe_value("area", {"type": "sheet", "code": "N-34"}, texts) is None
    assert describe_value("identifier", "opady", texts) is None


def _string_constants(path: Path) -> Iterator[str]:
    """String literals of a module; docstrings and pieces of f-strings excluded."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                skipped.add(id(first.value))
        if isinstance(node, ast.JoinedStr):
            skipped.update(id(part) for part in node.values)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skipped
        ):
            yield node.value


def _text_exists(texts: Texts, literal: str) -> bool:
    """A key exists; a key ending in ``_`` is the start of keys built at run time."""
    if not literal.endswith("_"):
        return texts.has(literal)
    parent, _, stem = literal.rpartition(".")
    return texts.has(parent) and any(
        name.startswith(stem) for name in texts.table(parent)
    )


def test_every_translation_key_the_extractors_name_exists_in_the_core_texts() -> None:
    texts = load_core_texts("pl")
    key = re.compile(r"extractors(\.[a-z0-9_]+)+")
    missing = sorted(
        {
            f"{path.name}: {literal}"
            for path in Path(extractors.__file__).parent.glob("*.py")
            for literal in _string_constants(path)
            if key.fullmatch(literal) and not _text_exists(texts, literal)
        }
    )

    assert missing == []

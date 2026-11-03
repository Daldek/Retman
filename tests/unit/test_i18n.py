"""The translation files: the same keys and placeholders in every language."""

import string
import tomllib
from importlib import resources
from typing import Any

import pytest

from retman.catalog import data_commands
from retman.catalog.describe import describe_command
from retman.i18n.loader import (
    MessageTexts,
    Texts,
    load_core_texts,
    localize,
    machine_messages,
)

PACKAGES = {
    "core": "retman.i18n",
    "kartograf": "retman.tools.kartograf",
    "imgwtools": "retman.tools.imgwtools",
}


def _load(package: str, language: str) -> dict[str, Any]:
    text = resources.files(package).joinpath(f"{language}.toml").read_text("utf-8")
    return tomllib.loads(text)


def _flat(node: dict[str, Any], prefix: str = "") -> dict[str, str | list[str]]:
    flat: dict[str, str | list[str]] = {}
    for key, value in node.items():
        if isinstance(value, dict):
            flat.update(_flat(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def _fields(text: str) -> set[str]:
    """The names of the placeholders of a text."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


@pytest.mark.parametrize("name", PACKAGES)
def test_english_has_the_keys_and_the_placeholders_of_polish(name: str) -> None:
    package = PACKAGES[name]
    polish = _flat(_load(package, "pl"))
    english = _flat(_load(package, "en"))
    if name == "core":
        # the English catalog texts are the declarations of the commands (AGI-9.1)
        polish = {k: v for k, v in polish.items() if not k.startswith("catalog.")}

    assert sorted(english) == sorted(polish)
    for key, polish_text in polish.items():
        english_text = english[key]
        if isinstance(polish_text, list):
            assert isinstance(english_text, list) and len(english_text) == len(
                polish_text
            ), key
        else:
            assert isinstance(english_text, str), key
            assert _fields(english_text) == _fields(polish_text), key


def test_the_answer_words_of_a_language_are_distinct_and_lower_case() -> None:
    for language in ("pl", "en"):
        texts = load_core_texts(language)
        words = [
            word
            for key in ("yes", "no", "change", "check", "cancel", "end")
            for word in texts.lines(f"answers.{key}")
        ]

        assert len(words) == len(set(words)), language
        assert all(word == word.lower() for word in words), language


def test_every_command_is_described_in_english_from_its_declaration() -> None:
    english = load_core_texts("en")

    for command in data_commands():
        lines = "\n".join(describe_command(command, english))

        assert command.summary in lines, command.name
        for option in command.options:
            assert option.description in lines, (command.name, option.name)


def test_a_float_takes_the_decimal_mark_of_the_language_only_when_it_is_formatted() -> (
    None
):
    data = {"p": {"fixed": "{x:.2f}", "plain": "{x}"}}
    polish = Texts(data, "test", "pl")
    english = Texts(data, "test", "en")

    assert polish.get("p.fixed", x=0.5) == "0,50"
    assert english.get("p.fixed", x=0.5) == "0.50"
    assert polish.get("p.plain", x=0.5) == "0.5"
    assert polish.decimal(1234.5, ".1f") == "1234,5"
    assert english.decimal(2, ".12g") == "2"


def test_a_message_is_written_again_from_the_texts_of_another_language() -> None:
    english = MessageTexts(
        {"a": {"outer": "Plan {n}: {inner}", "inner": "{x:.1f} metres"}}, "en", "en"
    )
    polish = Texts(
        {"a": {"outer": "Plan nr {n}: {inner}", "inner": "{x:.1f} metra"}},
        "pl",
        "pl",
    )

    message = english.get("a.outer", n=3, inner=english.get("a.inner", x=0.5))

    assert str(message) == "Plan 3: 0.5 metres"
    assert localize(message, polish) == "Plan nr 3: 0,5 metra"
    assert localize("plain text", polish) == "plain text"


def test_the_machine_messages_are_the_english_texts() -> None:
    message = machine_messages().get("doctor.section_tools")

    assert message == load_core_texts("en").get("doctor.section_tools")
    assert localize(message, load_core_texts("pl")) == "Narzędzia"

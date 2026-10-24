"""Contract tests of the CLI against the catalog and the library (AGI-1.2, AGI-3)."""

import argparse
import io
import json
from pathlib import Path
from typing import Any

import pytest
from error_documents import last_line_document

import retman
from retman import cli
from retman.catalog import Command, data_commands
from retman.cli.parser import PRESENTATION, build_parser
from retman.i18n.loader import load_core_texts

COMMANDS = data_commands()
IDS = [command.name for command in COMMANDS]
PARSER = build_parser(load_core_texts("pl"))


def _verb_parsers() -> dict[str, argparse.ArgumentParser]:
    groups = next(
        action
        for action in PARSER._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    verbs: dict[str, argparse.ArgumentParser] = {}
    for group, group_parser in groups.choices.items():
        (verb_action,) = (
            action
            for action in group_parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        for verb, verb_parser in verb_action.choices.items():
            verbs[f"{group} {verb}"] = verb_parser
    return verbs


VERBS = _verb_parsers()


def _flags(parser: argparse.ArgumentParser) -> set[str]:
    return {
        flag
        for action in parser._actions
        for flag in action.option_strings
        if flag.startswith("--") and flag != "--help"
    }


def _run(argv: list[str], **kwargs: Any) -> tuple[int, str, str]:
    import contextlib

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv, **kwargs)
    return code, out.getvalue(), err.getvalue()


class TestParser:
    """The parser is generated from the catalog (AGI-1.1, AGI-3.1)."""

    def test_every_command_has_a_verb_parser_and_nothing_else_has(self) -> None:
        assert set(VERBS) == set(IDS)

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_the_flags_are_the_options_and_the_presentation_options(
        self, command: Command
    ) -> None:
        expected = {option.flag for option in command.options} | {
            "--json",
            "--lang",
            "--verbose",
            "--quiet",
        }

        assert _flags(VERBS[command.name]) == expected

    def test_every_flag_is_the_kebab_case_of_an_option_name(self) -> None:
        for command in COMMANDS:
            for option in command.options:
                assert option.flag == "--" + option.name.replace("_", "-")
                assert "_" not in option.flag

    def test_the_presentation_options_are_the_same_on_every_verb(self) -> None:
        assert set(PRESENTATION) == {"as_json", "lang", "verbose", "quiet"}
        for parser in VERBS.values():
            assert {"--json", "--lang", "--verbose", "--quiet"} <= _flags(parser)

    def test_the_short_form_o_belongs_to_no_option(self) -> None:
        """AGI-3.4 keeps ``-o`` for ``--output-dir``; Retman has no such option."""
        for parser in VERBS.values():
            shorts = {
                flag
                for action in parser._actions
                for flag in action.option_strings
                if not flag.startswith("--")
            }
            assert shorts <= {"-h"}


class TestHelp:
    """``--help`` says what the command does, lists the values and gives examples."""

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_help_starts_with_the_summary_and_ends_with_examples(
        self, command: Command, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as stopped:
            cli.main([command.group, command.verb, "--help", "--lang", "en"])

        text = capsys.readouterr().out
        assert stopped.value.code == 0
        lines = [line for line in text.splitlines() if line.strip()]
        assert lines[0].startswith("usage: retman " + command.name)
        summary = next(
            line for line in lines[1:] if not line.startswith((" ", "usage"))
        )
        assert summary.endswith(".")
        assert lines[-2].startswith("Przykłady:") or lines[-2].startswith("Examples:")
        assert lines[-1].strip().startswith("retman " + command.name)

    def test_help_lists_each_value_of_a_choice_with_its_meaning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            cli.main(["commands", "guide", "--help"])

        text = " ".join(capsys.readouterr().out.split())
        for value in ("agents", "llms", "agents-md-block"):
            assert f"{value}:" in text

    def test_the_groups_are_listed_with_a_line_each(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            cli.main(["--help"])

        text = capsys.readouterr().out
        for command in COMMANDS:
            assert f"    {command.group} " in text

    def test_version_prints_the_package_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as stopped:
            cli.main(["--version"])

        assert stopped.value.code == 0
        assert capsys.readouterr().out == f"retman {retman.__version__}\n"

    def test_no_output_carries_colour_codes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The CLI never colours its output (AGI-3.6)."""
        with pytest.raises(SystemExit):
            cli.main(["--help"])
        code, out, _ = _run(["commands", "schema", "--command", "plan run"])

        assert code == 0
        assert "\x1b[" not in capsys.readouterr().out + out


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A folder with a settings file: the commands that read it run offline."""
    monkeypatch.chdir(tmp_path)
    assert cli.main(["config", "init", "--config", "nogat.toml"]) == 0
    return tmp_path


OFFLINE: list[tuple[str, dict[str, object]]] = [
    ("commands list", {}),
    ("commands list", {"limit": 3}),
    ("commands schema", {"command": "plan run"}),
    ("commands schema", {"limit": 2}),
    ("commands guide", {"format": "llms"}),
    ("results list", {"config": "nogat.toml"}),
    ("journal show", {"config": "nogat.toml", "limit": 5}),
    ("config show", {"config": "nogat.toml"}),
]


class TestStreams:
    """``--json`` prints one document and nothing else; an error ends on stderr."""

    @pytest.mark.parametrize(("name", "options"), OFFLINE)
    def test_json_is_the_envelope_alone_and_equals_the_library_result(
        self, name: str, options: dict[str, object], project: Path
    ) -> None:
        command = next(c for c in COMMANDS if c.name == name)
        argv = [*name.split(" "), "--json"]
        for key, value in options.items():
            argv += [command.option(key).flag, str(value)]

        code, out, err = _run(argv)

        assert (code, err) == (0, "")
        assert out.count("\n") == 1
        printed = json.loads(out)
        assert printed == retman.run_command(name, **options).to_dict()

    @pytest.mark.parametrize(("name", "options"), OFFLINE[:3])
    def test_without_json_the_text_is_for_people_and_not_a_document(
        self, name: str, options: dict[str, object], project: Path
    ) -> None:
        command = next(c for c in COMMANDS if c.name == name)
        argv = [*name.split(" ")]
        for key, value in options.items():
            argv += [command.option(key).flag, str(value)]

        code, out, err = _run(argv)

        assert (code, err) == (0, "")
        assert not out.lstrip().startswith("{")

    @pytest.mark.parametrize("as_json", [False, True])
    def test_an_error_prints_nothing_on_stdout_and_ends_on_the_document(
        self, as_json: bool
    ) -> None:
        argv = ["commands", "schema", "--command", "no such command"]

        code, out, err = _run([*argv, "--json"] if as_json else argv)

        document = last_line_document(err)
        assert out == ""
        assert code == document["exit_code"] == 3
        assert document["code"] == "not_found"
        assert document["command"] == "commands schema"

    def test_the_error_document_is_english_in_both_languages(self) -> None:
        polish = last_line_document(_run(["commands", "schema", "--command", "x"])[2])
        english = last_line_document(
            _run(["commands", "schema", "--command", "x", "--lang", "en"])[2]
        )

        assert polish["message"] == english["message"]
        assert polish["hint"] == english["hint"]

    def test_a_flag_the_command_does_not_have_is_a_validation_error(self) -> None:
        code, out, err = _run(["commands", "list", "--output", "x"])

        document = last_line_document(err)
        assert (code, out) == (2, "")
        assert document["code"] == "validation_error"

    def test_a_value_of_the_wrong_type_is_a_validation_error_naming_the_option(
        self,
    ) -> None:
        code, _, err = _run(["commands", "list", "--limit", "many"])

        assert code == 2
        assert last_line_document(err)["code"] == "validation_error"

    def test_an_unknown_choice_names_the_allowed_values(self) -> None:
        code, _, err = _run(["commands", "guide", "--format", "html"])

        document = last_line_document(err)
        assert code == 2
        assert document["code"] == "validation_error"
        assert "agents" in str(document["details"]) + document["message"]


class TestLanguage:
    """Human text follows ``--lang``; machine documents do not (AGI-9.2)."""

    def test_the_options_texts_of_the_catalog_document_do_not_depend_on_lang(
        self,
    ) -> None:
        polish = json.loads(
            _run(["commands", "schema", "--command", "plan run", "--json"])[1]
        )
        english = json.loads(
            _run(
                [
                    "commands",
                    "schema",
                    "--command",
                    "plan run",
                    "--json",
                    "--lang",
                    "en",
                ]
            )[1]
        )

        assert polish == english
        assert polish["result"]["commands"][0]["summary"].startswith("Plan ")

    def test_the_text_view_of_a_command_is_polish_by_default(self) -> None:
        _, out, _ = _run(["commands", "list"])

        assert "Zaplanuj operację" in out

    def test_an_unknown_language_is_refused_by_the_parser(self) -> None:
        code, _, err = _run(["commands", "list", "--lang", "de"])

        assert code == 2
        assert last_line_document(err)["code"] == "validation_error"

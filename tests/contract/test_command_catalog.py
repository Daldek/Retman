"""Contract tests of the command catalog (AGI-1.1, AGI-2, AGI-3.4, AGI-4.1, DEV-19)."""

import importlib
import inspect
import os
import shlex
import tomllib
from collections.abc import Iterator, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from nogat_schemas import validator

import retman.operations
from retman._errors import CODES
from retman.catalog import Command, Option, data_commands, execute, validate_command
from retman.catalog.document import catalog_document
from retman.cli.parser import PRESENTATION, build_parser, options_of
from retman.exceptions import InvalidValueError
from retman.i18n.loader import load_core_texts

COMMANDS = data_commands()
IDS = [command.name for command in COMMANDS]
REGISTRY_CODES = {entry.code for entry in CODES}
TEXTS = load_core_texts("pl")
NOT_A_VERB = {"the", "a", "an", "this", "that", "retman", "it"}
# The names that AGI-3.4 shares between the tools, with the type they must have here
SHARED_TYPES = {
    "check": "boolean",
    "yes": "boolean",
    "force": "boolean",
    "limit": "integer",
    "cursor": "string",
    "output": "path",
}


def _function(command: Command) -> Any:
    module_name, _, attribute = command.function.rpartition(".")
    return getattr(importlib.import_module(module_name), attribute)


def _options() -> Iterator[tuple[Command, Option]]:
    for command in COMMANDS:
        for option in command.options:
            yield command, option


class TestDeclarations:
    """Rules that every declaration of the catalog obeys."""

    def test_names_and_operation_ids_are_unique(self) -> None:
        assert len(set(IDS)) == len(IDS)
        operation_ids = [command.operation_id for command in COMMANDS]
        assert len(set(operation_ids)) == len(operation_ids)

    def test_every_group_and_verb_is_one_lowercase_word(self) -> None:
        for command in COMMANDS:
            assert command.name == f"{command.group} {command.verb}"
            assert command.group.isalpha() and command.group.islower()
            assert command.verb.isalpha() and command.verb.islower()

    def test_a_group_is_one_run_of_consecutive_commands(self) -> None:
        groups = [command.group for command in COMMANDS]

        runs = [g for index, g in enumerate(groups) if g != groups[index - 1]]
        assert len(runs) == len(set(runs))

    def test_a_summary_is_one_sentence_that_starts_with_a_verb(self) -> None:
        for command in COMMANDS:
            first = command.summary.split(" ", 1)[0]
            assert first[0].isupper() and first.lower() not in NOT_A_VERB
            assert command.summary.endswith(".")
            assert len(command.summary) <= 100

    def test_a_description_says_when_not_to_use_the_command(self) -> None:
        for command in COMMANDS:
            assert "not for" in command.description.lower(), command.name

    def test_effects_agree_with_the_check_option(self) -> None:
        """A command that writes plans its effects with ``--check`` (AGI-1.3)."""
        for command in COMMANDS:
            assert command.check == (not command.effects.read_only), command.name
            if command.check:
                option = command.option("check")
                assert (option.type, option.required, option.default) == (
                    "boolean",
                    False,
                    None,
                )

    def test_a_read_only_command_has_no_output_path(self) -> None:
        for command in COMMANDS:
            if command.effects.read_only:
                assert not any(option.writes for option in command.options)

    def test_every_command_with_options_can_fail_validation(self) -> None:
        for command in COMMANDS:
            if command.options:
                assert "validation_error" in command.errors, command.name

    def test_every_command_that_reads_the_settings_file_can_miss_it(self) -> None:
        for command in COMMANDS:
            if any(option.name == "config" for option in command.options):
                assert "not_found" in command.errors, command.name

    def test_declared_errors_are_codes_of_the_registry(self) -> None:
        for command in COMMANDS:
            assert set(command.errors) <= REGISTRY_CODES

    def test_the_shared_option_names_keep_their_meaning(self) -> None:
        for command, option in _options():
            expected = SHARED_TYPES.get(option.name)
            if expected is not None:
                assert option.type == expected, (command.name, option.name)
            if option.name == "output":
                assert option.path_role == "output"
            if option.name == "limit":
                assert option.minimum == 1

    def test_an_option_never_takes_the_name_of_a_presentation_option(self) -> None:
        reserved = {"json", "lang", "verbose", "quiet", "help", "version", "as_json"}
        assert set(PRESENTATION) <= reserved
        for command, option in _options():
            assert option.name not in reserved, (command.name, option.name)

    def test_one_of_groups_have_at_least_two_members(self) -> None:
        for command in COMMANDS:
            groups: dict[str, list[str]] = {}
            for option in command.options:
                if option.one_of is not None:
                    groups.setdefault(option.one_of, []).append(option.name)
            assert all(len(members) > 1 for members in groups.values())


class TestFunctions:
    """Each command is one public function of ``retman.operations`` (AGI-7.2)."""

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_the_function_is_exported_under_the_name_of_the_command(
        self, command: Command
    ) -> None:
        name = f"{command.group}_{command.verb}".replace("-", "_")

        assert command.function == f"retman.operations.{name}"
        assert _function(command) is getattr(retman.operations, name)
        assert name in retman.operations.__all__

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_the_options_are_keyword_only_parameters_of_the_function(
        self, command: Command
    ) -> None:
        parameters = inspect.signature(_function(command)).parameters
        names = {option.name for option in command.options}

        assert all(p.kind is p.KEYWORD_ONLY for p in parameters.values())
        assert names <= set(parameters)
        # what is no option is an injection of the caller and has a default
        for name in set(parameters) - names:
            assert parameters[name].default is not inspect.Parameter.empty, name

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_required_and_default_agree_with_the_function(
        self, command: Command
    ) -> None:
        parameters = inspect.signature(_function(command)).parameters
        for option in command.options:
            parameter = parameters[option.name]
            assert option.required == (parameter.default is parameter.empty)
            if option.default is not None:
                assert parameter.default == option.default, option.name

    def test_the_package_exports_exactly_the_operations_of_the_catalog(self) -> None:
        exported = {
            name
            for name in retman.operations.__all__
            if not name.startswith(("check_", "plan_document", "targets_"))
        }
        functions = {c.function.rpartition(".")[2] for c in COMMANDS}

        assert functions <= exported


class TestTexts:
    """The catalog is English; every text has a Polish counterpart (AGI-9.1)."""

    def test_every_command_option_rule_and_choice_has_a_polish_text(self) -> None:
        entries = catalog_document(COMMANDS)["commands"]

        for command, entry in zip(COMMANDS, entries, strict=True):
            polish = entry["i18n"]["pl"]
            assert polish["summary"] and polish["description"]
            assert len(polish["rules"]) == len(command.rules)
            for option in entry["options"]:
                assert option["i18n"]["pl"]["description"]

    def test_the_polish_texts_name_no_command_or_option_that_does_not_exist(
        self,
    ) -> None:
        tables = tomllib.loads(
            resources.files("retman.i18n").joinpath("pl.toml").read_text("utf-8")
        )["catalog"]

        assert set(tables) == {command.operation_id for command in COMMANDS}
        for command in COMMANDS:
            assert set(tables[command.operation_id]["options"]) == {
                option.name for option in command.options
            }

    def test_the_english_texts_are_not_polish(self) -> None:
        polish_letters = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
        for command, option in _options():
            assert not polish_letters & set(option.description), (
                command.name,
                option.name,
            )
        for command in COMMANDS:
            assert not polish_letters & set(command.summary + command.description)


class TestDocument:
    """The document ``retman-commands/1`` of the whole catalog (AGI-2.4)."""

    def test_it_obeys_the_nogat_schema(self) -> None:
        document = catalog_document(COMMANDS)

        errors = list(validator("commands-1").iter_errors(document))

        assert [error.message for error in errors] == []

    def test_a_command_with_a_check_mode_names_itself_as_its_plan(self) -> None:
        entries = catalog_document(COMMANDS)["commands"]

        for command, entry in zip(COMMANDS, entries, strict=True):
            assert entry["check"] == (command.name if command.check else None)

    def test_an_output_path_carries_its_role(self) -> None:
        entries = catalog_document(COMMANDS)["commands"]

        roles = {
            (entry["name"], option["name"]): option["path_role"]
            for entry in entries
            for option in entry["options"]
            if "path_role" in option
        }

        assert roles[("eval run", "output")] == "output"
        assert roles[("plan run", "config")] == "input"
        assert roles[("config init", "config")] == "output"


class TestExamples:
    """Each example is a valid call, and the command line of it parses back."""

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_the_examples_are_valid_calls(self, command: Command) -> None:
        for example in command.examples:
            assert set(validate_command(command, example)) >= set(example)

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_the_command_line_of_an_example_parses_to_the_same_options(
        self, command: Command
    ) -> None:
        parser = build_parser(TEXTS)
        for example in command.examples:
            words = shlex.split(command.command_line(example))
            assert words[:3] == ["retman", command.group, command.verb]

            parsed = options_of(command, parser.parse_args(words[1:]))

            wanted = {
                option.name: option.normalize(example[option.name])
                for option in command.options
                if option.name in example
                and not (option.type == "boolean" and example[option.name] is False)
            }
            assert {
                name: command.option(name).normalize(value)
                for name, value in parsed.items()
            } == wanted

    def test_a_list_option_is_given_by_repeating_its_flag(self) -> None:
        command = next(c for c in COMMANDS if c.name == "scaffold check")

        line = command.command_line({"tool": ["kartograf", "imgwtools"]})

        assert line == "retman scaffold check --tool kartograf --tool imgwtools"


def _contains(actual: object, excerpt: object) -> list[str]:
    """List how ``excerpt`` is not contained in ``actual`` (empty when it is)."""
    if isinstance(excerpt, Mapping):
        if not isinstance(actual, Mapping):
            return [f"{actual!r} is no object"]
        problems: list[str] = []
        for key, wanted in excerpt.items():
            if key not in actual:
                problems.append(f"{key!r} is missing")
            else:
                problems += [f"{key}: {p}" for p in _contains(actual[key], wanted)]
        return problems
    if isinstance(excerpt, list):
        if not isinstance(actual, list) or len(actual) < len(excerpt):
            return [f"{actual!r} is no list of {len(excerpt)} items"]
        return [
            f"[{i}] {problem}"
            for i, wanted in enumerate(excerpt)
            for problem in _contains(actual[i], wanted)
        ]
    return [] if actual == excerpt else [f"{actual!r} != {excerpt!r}"]


class TestExampleResults:
    """The excerpt of each example result that can be produced offline is true."""

    def test_the_helper_finds_what_is_missing(self) -> None:
        assert _contains({"a": [1, {"b": 2}], "c": 3}, {"a": [1, {"b": 2}]}) == []
        assert _contains({"a": 1}, {"a": 2}) == ["a: 1 != 2"]
        assert _contains({}, {"a": 1}) == ["'a' is missing"]
        assert _contains({"a": []}, {"a": [1]})

    @pytest.fixture
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """A folder with a settings file and a result, as the examples assume."""
        monkeypatch.chdir(tmp_path)
        execute("config init", {"config": "nogat.toml"})
        result = tmp_path / "retman-output" / "001_download_dem_sheet"
        result.mkdir(parents=True)
        (result / "result.json").write_text(
            '{"number": 1, "operation": "download_dem_sheet", "ok": true,'
            ' "summary": "ok", "timing": {"end": "2026-01-01T00:00:00+00:00"}}',
            encoding="utf-8",
        )
        (tmp_path / "retman-output" / "journal.jsonl").write_text(
            '{"time": "2026-01-01T00:00:00+00:00", "event": "command", '
            '"command": "x"}\n',
            encoding="utf-8",
        )
        return tmp_path

    OFFLINE = (
        "config show",
        "config init",
        "results list",
        "journal show",
        "commands list",
        "commands schema",
        "commands guide",
    )

    @pytest.mark.parametrize("name", OFFLINE)
    def test_the_result_contains_the_excerpt(
        self, name: str, project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        command = next(c for c in COMMANDS if c.name == name)
        if name == "config init":
            (project / "nogat.toml").unlink()
        for example, excerpt in zip(
            command.examples, command.example_results, strict=True
        ):
            result = execute(command, example, {"project_dir": project}).to_dict()

            assert _contains(result["result"], excerpt) == []

    def test_the_other_examples_are_covered_elsewhere(self) -> None:
        """``plan run``, ``doctor check``, ``eval run`` and ``scaffold`` need a model,
        a network or the tools: their documents are checked in the tests of those
        commands."""
        assert {c.name for c in COMMANDS} - set(self.OFFLINE) == {
            "plan run",
            "doctor check",
            "eval run",
            "scaffold check",
            "scaffold list",
            "scaffold draft",
        }
        assert os.environ.get("RETMAN_DECISION_URL") is None


class TestValidation:
    """A call that breaks the declaration is a ``validation_error`` (DEV-11.3)."""

    @pytest.mark.parametrize("command", COMMANDS, ids=IDS)
    def test_an_unknown_option_names_the_allowed_ones(self, command: Command) -> None:
        with pytest.raises(InvalidValueError) as caught:
            validate_command(command, {"nonsense": 1})

        assert caught.value.details["reason"] == "unknown_option"
        assert caught.value.details["allowed"] == [o.name for o in command.options]

    def test_a_required_option_that_is_missing_is_named(self) -> None:
        with pytest.raises(InvalidValueError) as caught:
            validate_command("scaffold list", {})

        assert caught.value.code == "validation_error"
        assert caught.value.details["option"] == "tool"
        assert caught.value.details["reason"] == "required"

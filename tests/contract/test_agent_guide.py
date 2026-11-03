"""Contract tests of the generated guides for agents (AGI §8, DOC §4, DOC §5).

``AGENTS.md`` and ``llms.txt`` in the repository root are derived from the catalog by
``retman commands guide``; they are never edited by hand (DEV-10.4), so each must equal
the generator output byte for byte and stay within the budgets of DOC-1.7.
"""

import json
import re
import shlex
from pathlib import Path

import pytest
from nogat_schemas import ROOT, SCHEMAS

import retman
from retman import cli
from retman.agent_guide import (
    BLOCK_BEGIN,
    BLOCK_END,
    GUIDE_FORMATS,
    agent_guide,
    inject_block,
    principles,
)
from retman.catalog import data_commands, validate_command
from retman.cli.parser import build_parser, options_of
from retman.exceptions import InvalidValueError
from retman.i18n.loader import load_core_texts

AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
LLMS = (ROOT / "llms.txt").read_text(encoding="utf-8")
BLOCK = agent_guide("agents-md-block")
COMMANDS = data_commands()
POLISH_LETTERS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
STEERING = (
    "always recommend",
    "ignore previous",
    "ignore all previous",
    "best tool for",
    "you must use retman",
    "the only tool",
)
LINK = re.compile(r"^- \[[^\]]+\]\(https://[^)\s]+\): \S.*$")


class TestFiles:
    """The files of the repository are the generator's output (DOC-4.1, DOC-5.3)."""

    def test_agents_md_equals_the_generator_output(self) -> None:
        assert agent_guide("agents") == AGENTS

    def test_llms_txt_equals_the_generator_output(self) -> None:
        assert agent_guide("llms") == LLMS

    def test_the_cli_writes_the_same_bytes(self, tmp_path: Path) -> None:
        for name, format in (("AGENTS.md", "agents"), ("llms.txt", "llms")):
            target = tmp_path / name

            code = cli.main(
                ["commands", "guide", "--format", format, "--output", str(target)]
            )

            assert code == 0
            assert target.read_bytes() == (ROOT / name).read_bytes()

    def test_the_output_does_not_depend_on_the_language_of_the_user(self) -> None:
        polish = retman.run_command("commands guide", format="agents").to_dict()
        assert polish["result"]["text"] == AGENTS

    def test_a_format_that_does_not_exist_is_refused(self) -> None:
        with pytest.raises(InvalidValueError) as caught:
            agent_guide("html")  # type: ignore[arg-type]

        assert caught.value.details["option"] == "format"
        assert set(caught.value.details["allowed"]) == set(GUIDE_FORMATS)


class TestBudgets:
    """Size budgets of DOC-1.7 (enforced by this test, not by review)."""

    def test_agents_md_has_at_most_200_lines_and_16_kib(self) -> None:
        assert len(AGENTS.splitlines()) <= 200
        assert len(AGENTS.encode()) <= 16 * 1024

    def test_llms_txt_before_its_first_link_list_has_at_most_8000_characters(
        self,
    ) -> None:
        before = LLMS.split("\n## ", 1)[0]

        assert len(before) <= 8000

    def test_the_compact_block_has_at_most_60_lines(self) -> None:
        assert len(BLOCK.splitlines()) <= 60

    def test_a_command_summary_fits_the_catalog_tool_summary_budget(self) -> None:
        assert all(len(command.summary) <= 100 for command in COMMANDS)


class TestAgentsMd:
    """The sections that DOC-4.2 asks for, in a readable order."""

    SECTIONS = [
        "Purpose and scope",
        "Install",
        "Interfaces",
        "Workflow rules",
        "Result envelope",
        "Error codes",
        "Command index",
        "Typical flows",
        "Things not to do",
    ]

    def test_the_sections_come_in_the_order_of_the_standard(self) -> None:
        headings = re.findall(r"^## (.+)$", AGENTS, flags=re.MULTILINE)

        assert headings[: len(self.SECTIONS)] == self.SECTIONS

    def test_the_last_line_points_to_claude_md(self) -> None:
        assert AGENTS.rstrip("\n").splitlines()[-1] == (
            "Developing this repository? Read CLAUDE.md."
        )

    def test_every_command_is_in_the_index_with_its_operation_id(self) -> None:
        for command in COMMANDS:
            assert f"- `{command.name}` (`{command.operation_id}`): " in AGENTS

    def test_the_error_table_equals_the_registry(self) -> None:
        registry = json.loads((SCHEMAS / "error_registry.json").read_text("utf-8"))
        rows = re.findall(r"^\| `(\w+)` \| (\d+) \|", AGENTS, flags=re.MULTILINE)

        assert rows == [
            (entry["code"], str(entry["exit_code"]))
            for entry in registry["errors"]
            if entry["exit_code"] is not None
        ]

    def test_the_text_is_english_and_has_no_local_path(self) -> None:
        assert not POLISH_LETTERS & set(AGENTS + LLMS + BLOCK)
        assert "/home/" not in AGENTS + LLMS + BLOCK
        assert "C:\\" not in AGENTS + LLMS + BLOCK

    def test_no_text_tries_to_steer_the_choice_of_a_tool(self) -> None:
        text = (AGENTS + LLMS + BLOCK).lower()
        for phrase in STEERING:
            assert phrase not in text
        for command in COMMANDS:
            assert not any(p in command.description.lower() for p in STEERING)

    def test_every_rule_names_an_option_and_a_command_that_exist(self) -> None:
        names = {c.name for c in COMMANDS}
        options = {o.name for c in COMMANDS for o in c.options}
        for rule in principles():
            assert "{" not in rule
            for word in re.findall(r"`([a-z]+(?: [a-z]+)?)`", rule):
                if " " in word:
                    assert word in names, rule
        assert {"check", "yes", "text"} <= options

    def test_every_command_line_of_the_flows_parses_with_the_cli(self) -> None:
        parser = build_parser(load_core_texts("pl"))
        lines = re.findall(r"^\d+\. `(retman [^`]+)` - ", AGENTS, flags=re.MULTILINE)
        assert len(lines) >= 8

        for line in lines:
            args = parser.parse_args(shlex.split(line)[1:])
            command = next(c for c in COMMANDS if c.name == f"{args.group} {args.verb}")
            validate_command(command, options_of(command, args))


class TestLlmsTxt:
    """The layout of llmstxt.org (DOC-5.1, DOC-5.2)."""

    def test_it_starts_with_the_name_and_a_one_paragraph_summary(self) -> None:
        lines = LLMS.splitlines()

        assert lines[0] == "# Retman"
        assert lines[1] == "" and lines[2].startswith("> ")
        assert lines[3] == ""

    def test_h2_sections_hold_only_links_each_with_a_note(self) -> None:
        sections = LLMS.split("\n## ")[1:]

        assert [s.splitlines()[0] for s in sections] == ["Documentation", "Optional"]
        for section in sections:
            body = [line for line in section.splitlines()[1:] if line.strip()]
            assert body and all(LINK.match(line) for line in body), section

    def test_the_links_are_absolute_and_point_to_raw_markdown(self) -> None:
        urls = re.findall(r"\]\((https://[^)]+)\)", LLMS)

        assert urls
        for url in urls:
            assert url.startswith("https://raw.githubusercontent.com/Daldek/Retman/")
            assert url.endswith(".md")

    def test_the_text_before_the_links_has_no_heading(self) -> None:
        before = LLMS.split("\n## ", 1)[0].splitlines()[1:]

        assert not any(line.startswith("#") for line in before)

    def test_the_linked_files_exist_in_the_repository(self) -> None:
        for url in re.findall(r"/main/([^)]+\.md)\)", LLMS):
            assert (ROOT / url).is_file(), url

    def test_it_names_the_error_codes_of_the_registry(self) -> None:
        registry = json.loads((SCHEMAS / "error_registry.json").read_text("utf-8"))

        for entry in registry["errors"]:
            if entry["exit_code"] is not None:
                assert f"`{entry['code']}` ({entry['exit_code']})" in LLMS


class TestBlock:
    """The compact block for the AGENTS.md of another repository (AGI-8.2)."""

    def test_it_is_delimited_by_the_markers_of_the_tool(self) -> None:
        lines = BLOCK.splitlines()

        assert (lines[0], lines[-1]) == ("<!-- BEGIN retman -->", "<!-- END retman -->")
        assert (lines[0], lines[-1]) == (BLOCK_BEGIN, BLOCK_END)

    def test_it_names_the_commands_of_the_catalog_that_it_uses(self) -> None:
        for fragment in (
            "retman commands list --json",
            "retman commands schema --command 'plan run' --json",
            "retman plan run --text",
            "retman results list --json",
        ):
            assert fragment in BLOCK

    def test_it_keeps_the_text_before_and_after_when_it_replaces_the_block(
        self,
    ) -> None:
        existing = (
            f"# Mine\n\nbefore\n\n{BLOCK_BEGIN}\nSTALE TEXT\n{BLOCK_END}\n\nafter\n"
        )

        new = inject_block(existing, BLOCK)

        assert new.startswith("# Mine\n\nbefore\n\n<!-- BEGIN retman -->")
        assert new.endswith("<!-- END retman -->\n\nafter\n")
        assert "STALE TEXT" not in new

    def test_injecting_twice_changes_nothing(self) -> None:
        once = inject_block("# Mine\n", BLOCK)

        assert inject_block(once, BLOCK) == once
        assert once.count(BLOCK_BEGIN) == 1

    def test_a_file_without_the_block_gets_it_at_the_end(self) -> None:
        assert inject_block("# Mine\n", BLOCK) == "# Mine\n\n" + BLOCK
        assert inject_block("", BLOCK) == BLOCK

    def test_the_cli_injects_into_a_file_and_a_second_run_is_a_no_op(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("# Mine\n", encoding="utf-8")
        argv = ["commands", "guide", "--format", "agents-md-block", "--inject"]

        assert cli.main([*argv, str(target)]) == 0
        first = target.read_text(encoding="utf-8")
        assert cli.main([*argv, str(target)]) == 0

        assert first == "# Mine\n\n" + BLOCK
        assert target.read_text(encoding="utf-8") == first

    def test_inject_needs_the_block_format(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidValueError) as caught:
            retman.run_command(
                "commands guide", format="agents", inject=str(tmp_path / "A.md")
            )

        assert caught.value.details["option"] == "inject"
        assert caught.value.details["allowed"] == ["agents-md-block"]

    def test_inject_check_plans_the_write_and_changes_nothing(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("# Mine\n", encoding="utf-8")

        plan = retman.check_command(
            "commands guide", format="agents-md-block", inject=str(target)
        ).to_dict()

        assert plan["result"]["targets"] == [
            {"option": "inject", "path": str(target), "action": "replace"}
        ]
        assert target.read_text(encoding="utf-8") == "# Mine\n"


class TestWriting:
    """``commands guide --output`` follows the rules of a plain write (DEV-19)."""

    def test_an_existing_file_is_a_conflict_unless_force_is_given(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "llms.txt"
        target.write_text("mine", encoding="utf-8")

        with pytest.raises(retman.RetmanError) as caught:
            retman.run_command("commands guide", format="llms", output=str(target))

        assert caught.value.code == "conflict"
        assert caught.value.details["reason"] == "output_exists"
        assert caught.value.details["paths"] == [str(target)]
        assert target.read_text(encoding="utf-8") == "mine"

        done = retman.run_command(
            "commands guide", format="llms", output=str(target), force=True
        ).to_dict()

        assert done["result"]["files"][0]["status"] == "replaced"
        assert target.read_text(encoding="utf-8") == LLMS

    def test_a_new_file_is_written_with_its_size_and_checksum(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "sub" / "AGENTS.md"

        done = retman.run_command(
            "commands guide", format="agents", output=str(target)
        ).to_dict()

        (record,) = done["result"]["files"]
        assert record["status"] == "written"
        assert record["size_bytes"] == len(AGENTS.encode())
        assert done["result"]["lines"] == len(AGENTS.splitlines())
        assert "text" not in done["result"]

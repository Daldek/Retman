"""Executable examples of the README (DOC-2.6) and the facts it states.

``README.md`` holds fenced code blocks; this module runs them, so an example that
stops working fails the gate. A block is one test, named ``README.md:L42`` after the
line of its opening fence, and runs in a fresh working directory with a settings file
that does not exist yet, so a block that plans starts with ``retman config init``.
The model server is the one thing that is replaced: the decision backend is a
``FakeDecisionBackend`` with the choices that the examples need, and the tools Retman
adapts run for real, offline.

The info string, the text after the opening backticks, selects what happens:

``bash``
    Executed. A line that starts with ``retman `` runs in-process as
    ``retman.cli.main(shlex.split(line)[1:])`` and must exit with 0. Empty and
    comment lines are skipped, a trailing ``\\`` continues the line, and a trailing
    ``# comment`` is dropped. There are no pipes, redirections or variables. Lines
    that do not start with ``retman `` are ignored; a block without any is not a test.
``python``
    Executed with ``exec`` in a fresh namespace.
``json``
    Not executed; it must parse as JSON.
``json output``
    The output of the block it directly follows (a ``bash`` or ``python`` block that
    runs). That block runs again and its stdout, which must be one JSON document, has
    to contain this one. For ``bash`` it is the stdout of the last ``retman`` command
    (give it ``--json``); for ``python`` the whole stdout. The match is a recursive
    subset: object keys may be left out, scalars are equal, the string ``"..."`` as a
    value matches anything, lists have the same length unless the last element is
    ``"..."``.
``toml``
    Must parse. A block that holds the table ``[retman.decision]`` replaces the
    decision tables of the settings that ``retman config init`` writes and must load
    as settings.

Any other info string (``sh``, ``text``, ``console``...) is not executed.
"""

import json
import math
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import retman.core.pipeline as pipeline
from retman.backends.base import Decision
from retman.catalog import data_commands
from retman.cli.main import main
from retman.config import init_config, load_config
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
WILDCARD = "..."
FENCE = re.compile(r"^(?P<indent>\s*)(?P<ticks>`{3,})(?P<info>[^`]*)$")

# What the model server decides in the examples: the category, the operation and the
# options of the Kartograf DEM that the commands name
CHOICES: dict[str, str | Decision] = {
    "spatial_data": "spatial_data",
    "download_dem_sheet": "download_dem_sheet",
    "1m": "1m",
    "evrf2007": "evrf2007",
}

# DOC-2.1: the sections of a README in their order; the section of an interface that
# the project lacks is omitted (there is no MCP server)
SECTIONS = [
    "When to use",
    "When not to use",
    "Install",
    "Quick start",
    "Capabilities",
    "For AI agents",
    "MCP server",
    "Related tools",
    "Errors and exit codes",
    "Data and licensing",
    "Documentation",
    "Development",
    "Status, licence, author",
]
REQUIRED = set(SECTIONS) - {"MCP server"}


@dataclass(frozen=True)
class Block:
    """A fenced code block of a document."""

    line: int
    info: str
    code: str
    previous: "Block | None"

    @property
    def name(self) -> str:
        """Test id: the document and the line of the opening fence."""
        return f"README.md:L{self.line}"


def closes(line: str, ticks: str) -> bool:
    """Whether ``line`` closes a fence opened with ``ticks``."""
    text = line.strip()
    return len(text) >= len(ticks) and set(text) == {"`"}


def parse_blocks(text: str) -> list[Block]:
    """Return the fenced blocks of ``text`` in order; ``previous`` links them."""
    lines = text.splitlines()
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        opening = FENCE.match(lines[index])
        if opening is None:
            index += 1
            continue
        start = index
        body: list[str] = []
        index += 1
        while index < len(lines) and not closes(lines[index], opening["ticks"]):
            body.append(lines[index].removeprefix(opening["indent"]))
            index += 1
        if index == len(lines):
            raise ValueError(f"README.md:L{start + 1}: the code fence is not closed")
        index += 1
        info = " ".join(opening["info"].split())
        previous = blocks[-1] if blocks else None
        blocks.append(Block(start + 1, info, "\n".join(body) + "\n", previous))
    return blocks


def commands_of(code: str) -> list[str]:
    """The ``retman`` command lines of a ``bash`` block, continuations joined."""
    commands: list[str] = []
    line = ""
    for raw in code.splitlines():
        text = raw.strip()
        if not line and (not text or text.startswith("#")):
            continue
        if text.endswith("\\"):
            line += text[:-1].strip() + " "
            continue
        line = (line + text).strip()
        if line.startswith("retman "):
            commands.append(line)
        line = ""
    return commands


def runs(block: Block) -> bool:
    """Whether the block is executed: ``python``, or ``bash`` with a command."""
    return block.info == "python" or (
        block.info == "bash" and bool(commands_of(block.code))
    )


def collect() -> list[Any]:
    """One test parameter per block that is executed or checked."""
    blocks = parse_blocks(README.read_text(encoding="utf-8"))
    return [
        pytest.param(block, id=block.name)
        for block in blocks
        if runs(block) or block.info in ("json", "json output", "toml")
    ]


def run_line(block: Block, line: str, capsys: pytest.CaptureFixture[str]) -> str:
    """Run one ``retman`` line in-process; return its stdout."""
    words = shlex.split(line, comments=True)
    capsys.readouterr()
    status = main(words[1:])
    captured = capsys.readouterr()
    if status != 0:
        pytest.fail(f"{block.name}: `{line}` exited with {status}\n{captured.err}")
    return captured.out


def execute(block: Block, capsys: pytest.CaptureFixture[str]) -> str:
    """Run a block; return the stdout that a ``json output`` block shows."""
    if block.info == "python":
        capsys.readouterr()
        namespace: dict[str, Any] = {"__name__": "__documentation__"}
        exec(compile(block.code, block.name, "exec"), namespace)
        return capsys.readouterr().out
    output = ""
    for line in commands_of(block.code):
        output = run_line(block, line, capsys)
    return output


def mismatches(expected: Any, actual: Any, path: str = "$") -> list[str]:
    """Where ``expected`` is not contained in ``actual`` (rules: module docstring)."""
    if isinstance(expected, str) and expected == WILDCARD:
        return []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected an object, found {actual!r}"]
        problems: list[str] = []
        for key, value in expected.items():
            if key in actual:
                problems += mismatches(value, actual[key], f"{path}.{key}")
            else:
                problems.append(f"{path}.{key}: missing")
        return problems
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected a list, found {actual!r}"]
        open_ended = bool(expected) and expected[-1] == WILDCARD
        shown = expected[:-1] if open_ended else expected
        if len(actual) < len(shown) or (not open_ended and len(actual) > len(shown)):
            more = "or more " if open_ended else ""
            return [f"{path}: expected {len(shown)} {more}items, found {len(actual)}"]
        return [
            problem
            for index, value in enumerate(shown)
            for problem in mismatches(value, actual[index], f"{path}[{index}]")
        ]
    return (
        []
        if same_scalar(expected, actual)
        else [f"{path}: expected {expected!r}, found {actual!r}"]
    )


def same_scalar(expected: Any, actual: Any) -> bool:
    """Equality of JSON scalars: ``True`` is not ``1``; floats to a relative 1e-9."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        if isinstance(expected, int) and isinstance(actual, int):
            return expected == actual
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-12)
    return bool(expected == actual)


def check_json(block: Block) -> None:
    """A ``json`` block parses."""
    try:
        json.loads(block.code)
    except ValueError as error:
        pytest.fail(f"{block.name} is not valid JSON: {error}")


def check_output(block: Block, capsys: pytest.CaptureFixture[str]) -> None:
    """A ``json output`` block is contained in the stdout of the block before it."""
    source = block.previous
    if source is None or not runs(source):
        pytest.fail(
            f"{block.name}: `json output` must directly follow a block that runs"
        )
    try:
        expected = json.loads(block.code)
    except ValueError as error:
        pytest.fail(
            f"{block.name} is not valid JSON ('...' is a value, not a line): {error}"
        )
    output = execute(source, capsys)
    try:
        actual = json.loads(output)
    except ValueError:
        pytest.fail(
            f"{block.name}: the stdout of {source.name} is not one JSON document "
            f"(use --json, print only JSON): {output[:200]!r}"
        )
    problems = mismatches(expected, actual)
    assert not problems, f"{block.name} differs from the output of {source.name}:\n" + (
        "\n".join(problems)
    )


def check_toml(block: Block, tmp_path: Path) -> None:
    """A ``toml`` block parses; decision tables also load as the settings of Retman."""
    try:
        data = tomllib.loads(block.code)
    except tomllib.TOMLDecodeError as error:
        pytest.fail(f"{block.name} is not valid TOML: {error}")
    if "decision" not in data.get("retman", {}):
        return
    written = init_config(tmp_path / "written.toml")
    text = written.read_text(encoding="utf-8")
    start, end = text.index("[retman.decision]"), text.index("[retman.text]")
    written.write_text(text[:start] + block.code + "\n" + text[end:], encoding="utf-8")
    load_config(written)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh working directory without settings, and the model server replaced."""
    monkeypatch.setenv("NOGAT_CONFIG", str(tmp_path / "nogat.toml"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        pipeline,
        "build_decision_backend",
        lambda config, texts: FakeDecisionBackend(CHOICES),
    )
    return tmp_path


@pytest.mark.parametrize("block", collect())
def test_documented_example_works(
    block: Block, workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if block.info == "json":
        check_json(block)
    elif block.info == "json output":
        check_output(block, capsys)
    elif block.info == "toml":
        check_toml(block, workdir)
    else:
        execute(block, capsys)


def test_output_match_is_a_subset_with_wildcards() -> None:
    actual = {"a": 1, "b": {"c": [1, 2, 3], "d": 0.30000000000000004}, "e": None}
    shown = {"a": 1, "b": {"c": [1, "..."], "d": 0.3}, "e": None}
    assert mismatches(shown, actual) == []
    assert mismatches({"a": "...", "b": {"c": [1, 2, 3]}}, actual) == []
    wrong = [{"a": 2}, {"x": 1}, {"b": {"c": [1, 2]}}, {"b": {"c": [1, 2, 4]}}]
    wrong += [{"b": {"c": []}}, {"e": 0}, {"a": True}, {"b": {"d": 0.31}}]
    for document in wrong:
        assert mismatches(document, actual), document


def test_fences_and_commands_are_found_in_a_document() -> None:
    text = (
        "intro\n```bash\nretman commands list\n```\n\n- item\n\n"
        "  ````text\n  ```\n  ````\n  ```json output\n  {}\n  ```\n"
    )
    blocks = parse_blocks(text)
    assert [(block.line, block.info) for block in blocks] == [
        (2, "bash"),
        (8, "text"),
        (11, "json output"),
    ]
    assert blocks[1].code == "```\n"
    assert blocks[2].previous is blocks[1]
    code = (
        "uv tool install x\n# note\nretman plan run \\\n  --text 'x' --check\n\n"
        "retman commands list\n"
    )
    assert commands_of(code) == [
        "retman plan run --text 'x' --check",
        "retman commands list",
    ]


def section(text: str, heading: str) -> str:
    """The text of the ``## heading`` section, up to the next ``## `` heading."""
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : None if end < 0 else end]


def test_the_readme_keeps_its_budget_and_the_order_of_its_sections() -> None:
    text = README.read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
    summary = text.split("\n\n")[1]

    assert len(text.splitlines()) <= 400
    assert text.startswith("# Retman: ")
    assert not summary.startswith(("#", "!", "["))
    assert len(summary) <= 400
    assert set(headings) >= REQUIRED
    assert [SECTIONS.index(heading) for heading in headings] == sorted(
        SECTIONS.index(heading) for heading in headings
    )


def test_the_readme_links_are_absolute() -> None:
    """Relative links do not resolve on PyPI or for an agent (DOC-1.4)."""
    text = README.read_text(encoding="utf-8")
    targets = re.findall(r"\]\(([^)\s]+)\)", text)

    assert targets
    assert [t for t in targets if not t.startswith("https://")] == []
    agents = section(text, "For AI agents")
    for name in ("llms.txt", "AGENTS.md"):
        assert (
            f"](https://raw.githubusercontent.com/Daldek/Retman/main/{name})" in agents
        )


def table_rows(text: str) -> list[list[str]]:
    """The backticked cells of every row of the Markdown tables in ``text``."""
    lines = [line for line in text.splitlines() if line.startswith("|")]
    return [re.findall(r"`([^`]+)`", line) for line in lines]


def test_the_capabilities_table_lists_every_command_of_the_catalog() -> None:
    capabilities = section(README.read_text(encoding="utf-8"), "Capabilities")
    rows = [row[:2] for row in table_rows(capabilities) if len(row) >= 2]

    listed = [(cli.removeprefix("retman "), fn) for cli, fn in rows if " " in cli]
    expected = [(c.name, c.function) for c in data_commands()]
    assert listed == expected


def test_the_capabilities_table_counts_the_operations_of_the_registry() -> None:
    pytest.importorskip("kartograf")
    pytest.importorskip("imgwtools")
    capabilities = section(README.read_text(encoding="utf-8"), "Capabilities")
    cells = [line.split("|") for line in capabilities.splitlines() if line[:1] == "|"]
    listed = {
        ids[0]: int(row[-3])
        for row in cells
        if (ids := re.findall(r"`([a-z_]+)`", row[2])) and row[-3].strip().isdigit()
    }

    operations = load_operations("pl").values()
    counted: dict[str, int] = {}
    for operation in operations:
        counted[operation.category] = counted.get(operation.category, 0) + 1
    assert listed == counted
    assert f"{len(operations)} operations in {len(counted)} categories" in capabilities

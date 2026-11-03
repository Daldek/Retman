"""Guide for AI agents generated from the command catalog (AGI §8).

:func:`agent_guide` renders ``AGENTS.md`` (``format="agents"``), ``llms.txt``
(``format="llms"``) and the compact block for the ``AGENTS.md`` of a consumer
repository (``format="agents-md-block"``), always in English (AGI-9.2), from the
hand-written templates in ``src/retman/_data/agents`` (``<format>.md``). Every marker
``<!-- retman:<block> -->`` of a template is replaced by a block generated from the
command catalog (:func:`retman.catalog.data_commands`), the error registry
(:data:`retman.exceptions.ERROR_CODES`) and the data of this module: the principles
(:func:`principles`) and the typical flows, whose steps are catalog commands rendered
as CLI lines. A marker that fills a whole line takes a block of any number of lines, a
marker inside a line a one-line block; an unknown block or a block used twice is a
program error (``ValueError``).

The flows are checked while they are rendered: every step names an existing command
and gives valid options (:func:`retman.catalog.validate_command`), so a renamed option
or command stops the generator instead of leaving a stale example in the guide. The
principles name options and commands through ``{opt:...}`` and ``{cmd:...}``
placeholders that are checked against the catalog in the same way.

The output depends only on the installed package (no dates, no version, no local
paths), so ``AGENTS.md`` and ``llms.txt`` in the repository root are derived files that
the tests compare byte for byte with the generator. Regenerate them after any change
of the catalog, the error registry, the templates or this module::

    retman commands guide --format agents --output AGENTS.md --force
    retman commands guide --format llms --output llms.txt --force
"""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Final, Literal, cast

from retman.catalog import Command, data_commands, get_command, validate_command
from retman.exceptions import ERROR_CODES

__all__ = [
    "BLOCK_BEGIN",
    "BLOCK_END",
    "GUIDE_FORMATS",
    "GuideFormat",
    "agent_guide",
    "inject_block",
    "principles",
]

GuideFormat = Literal["agents", "llms", "agents-md-block"]
GUIDE_FORMATS: Final[tuple[str, ...]] = ("agents", "llms", "agents-md-block")
"""Formats of :func:`agent_guide` (AGI-3.8)."""
BLOCK_BEGIN: Final = "<!-- BEGIN retman -->"
BLOCK_END: Final = "<!-- END retman -->"
"""Markers that delimit the block of ``agents-md-block`` (AGI-8.2)."""

_MARKER: Final = re.compile(r"<!--\s*retman:(?P<name>[^\s>]*)\s*-->")
_PLACEHOLDER: Final = re.compile(r"\{(?P<kind>opt|cmd):(?P<name>[^{}]+)\}")
_TEMPLATES: Final = ("_data", "agents")

# --- texts
# -----------------------------------------------------------------------------

# Titles of the command groups. A group of the catalog without a title here shows its
# bare name; a test requires a title for every group.
_GROUP_TITLES: Final[Mapping[str, str]] = {
    "plan": "From a Polish command to a plan and a result",
    "config": "Settings",
    "doctor": "Diagnosis",
    "results": "Results of the project folder",
    "journal": "Journal of the project folder",
    "commands": "The command catalog and this guide",
    "eval": "Quality of the model",
    "scaffold": "Descriptions of the tools (for developers)",
}
# The rules of AGENTS.md and of the block. ``{opt:name}`` and ``{cmd:name}`` are
# checked against the catalog and replaced by the bare name.
_PRINCIPLES: Final[tuple[str, ...]] = (
    "**Discover, do not guess:** `{cmd:commands list}` lists the commands, "
    "`{cmd:commands schema}` (option `{opt:command}`) gives options, effects, "
    "errors and examples.",
    "**Plan, then run:** `{cmd:plan run}` with `{opt:check}` shows what Retman "
    "understood; run it with `{opt:yes}` only after the user approved that plan "
    "(`result.confirmed` is false until then).",
    "**The text is the user's Polish sentence:** pass it as `{opt:text}`, do not "
    "translate or rewrite it. Nothing is asked without a terminal: put every missing "
    "value into the text and plan again.",
    "**Open questions are part of a plan:** `result.questions` lists them and "
    "`result.complete` is false; `{opt:yes}` with an open question is "
    "`validation_error` (reason `input_required`, `details.questions`).",
    "**Errors by code:** decide by `code`, `details.reason` and `details.option` (or "
    "the exit code), fix the argument as `hint` says and call again; never present an "
    "error as a result.",
    "**Outcomes are not errors:** `partial` (exit 10) and `failed` (exit 11) print the "
    "envelope; read `items`, a failed unit has a registry `code`.",
    "**Read `notices` and `result.run.warnings`:** licence and data-quality notes of "
    "the data providers belong with the data; pass them on.",
    "**Run Retman in the project folder:** results and the journal live there "
    "(`{cmd:results list}`, `{cmd:journal show}`); no ordinary command writes "
    "elsewhere.",
)
# What each code of the error registry means for an agent.
_ERROR_ADVICE: Final[Mapping[str, str]] = {
    "validation_error": "wrong or missing option or input: see `details.option`",
    "not_found": "unknown command, settings file, input file or result: see `hint`",
    "conflict": "file exists or plan not confirmed: another path, `force`, or `yes`",
    "source_unavailable": "model server or data service failed: run `doctor check`",
    "missing_dependency": "a tool is not installed: install it (`hint`)",
    "data_error": "malformed input or command set: see `details.path` and `reason`",
    "store_unavailable": "a tool store cannot be used: run `doctor check`",
    "io_error": "a file cannot be read or written: check `details.path`",
    "forbidden": "path or action not allowed: see `hint`",
    "calculation_error": "valid input, no result computable: change the data",
    "no_data": "the source has no data for the area or period: change the request",
    "unsupported": "the command is outside Retman's operations (`details.operations`)",
    "cancelled": "stopped by the user: nothing half done, run again",
    "terminated": "ended by SIGTERM: nothing half done, run again",
    "internal_error": "bug in Retman: report command, options, version",
}

# --- flows
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Step:
    """One step of a flow: a catalog command with its options and a note (Markdown)."""

    note: str
    command: str
    options: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class _Flow:
    """A typical task of an agent: a title, an introduction and its steps."""

    title: str
    intro: str
    steps: tuple[_Step, ...]


_TEXT: Final = "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4"
_FLOWS: Final[tuple[_Flow, ...]] = (
    _Flow(
        "Get data with a Polish command",
        "The model server must answer (`doctor check`) and the tool must be installed.",
        (
            _Step(
                "the plan: `result.operation`, `result.values` with their `source`, "
                "`result.questions` when the command leaves something open; nothing "
                "is run or written.",
                "plan run",
                {"text": _TEXT, "check": True},
            ),
            _Step(
                "runs the confirmed plan; `result.run.files` lists the files and "
                "`result.run.summary` says what was done. Only after the user "
                "approved the plan.",
                "plan run",
                {"text": _TEXT, "yes": True},
            ),
            _Step(
                "number and summary of every result in the project folder.",
                "results list",
            ),
        ),
    ),
    _Flow(
        "Find out why something does not work",
        "`doctor check` answers `partial` or `failed` when a check blocks work.",
        (
            _Step(
                "every check is a unit of `items`; a failed one has `code`, `reason` "
                "and a message with the fix.",
                "doctor check",
            ),
            _Step(
                "each setting with its value and source (option, variable, file or "
                "default); credentials are `present` or `missing`.",
                "config show",
            ),
        ),
    ),
    _Flow(
        "Set Retman up for a user",
        "Writes the `[retman]` tables into `nogat.toml`; an existing table is a "
        "`conflict`. Ask before `collect_commands`: it records the user's commands.",
        (
            _Step(
                "the plan: `result.targets[]` with the action `write` or `conflict`.",
                "config init",
                {"check": True},
            ),
            _Step("writes the tables; `result.files` names the file.", "config init"),
        ),
    ),
    _Flow(
        "Measure the model on the command set",
        "Plans every command without running anything; needs the model server.",
        (
            _Step(
                "the files that would be written, with their actions.",
                "eval run",
                {"target_error": 0.01, "output": "records.jsonl", "check": True},
            ),
            _Step(
                "the measures in `result`; a failed unit of `items` is a command that "
                "had to be refused and was planned.",
                "eval run",
                {"target_error": 0.01, "output": "records.jsonl"},
            ),
        ),
    ),
)
_EXAMPLE: Final = ("plan run", {"text": _TEXT, "check": True})
# Commands of the compact block: the discovery pair, then the commonest calls.
_BLOCK_COMMANDS: Final[tuple[tuple[str, Mapping[str, object]], ...]] = (
    ("commands list", {}),
    ("commands schema", {"command": "plan run"}),
    _EXAMPLE,
    ("plan run", {"text": _TEXT, "yes": True}),
    ("results list", {}),
)

# --- helpers
# ---------------------------------------------------------------------------


def _code(text: object) -> str:
    return f"`{text}`"


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(cell(text) for text in header) + " |",
        "|" + "---|" * len(header),
    ]
    lines += ["| " + " | ".join(cell(text) for text in row) + " |" for row in rows]
    return "\n".join(lines)


def _groups(commands: Sequence[Command]) -> dict[str, list[Command]]:
    """Group the commands by group, in catalog order."""
    grouped: dict[str, list[Command]] = {}
    for command in commands:
        grouped.setdefault(command.group, []).append(command)
    return grouped


def _group_title(group: str) -> str:
    return _GROUP_TITLES.get(group, group)


def _checked(text: str, commands: Sequence[Command]) -> str:
    """Return ``text`` with its ``{opt:...}``/``{cmd:...}`` placeholders replaced.

    Raises
    ------
    ValueError
        A placeholder names an option or a command that the catalog lacks.
    """
    options = {option.name for command in commands for option in command.options}
    names = {command.name for command in commands}

    def fill(match: re.Match[str]) -> str:
        known, kind = (
            (options, "option") if match["kind"] == "opt" else (names, "command")
        )
        if match["name"] not in known:
            raise ValueError(
                f"The guide names the {kind} {match['name']!r}, which the catalog "
                "does not have"
            )
        return match["name"]

    return _PLACEHOLDER.sub(fill, text)


# --- blocks
# ----------------------------------------------------------------------------


def principles() -> tuple[str, ...]:
    """Return the rules for an agent, shared by AGENTS.md and the compact block.

    Returns
    -------
    tuple of str
        The rules as English Markdown (one string per rule, without numbering):
        discover before calling, plan then run, the text is Polish, open questions,
        errors by code, outcomes, notices, the project folder. The options and
        commands they name exist in the catalog.
    """
    commands = data_commands()
    return tuple(_checked(rule, commands) for rule in _PRINCIPLES)


def _rules() -> str:
    return "\n".join(
        f"{number}. {rule}" for number, rule in enumerate(principles(), start=1)
    )


def _index() -> str:
    """One heading per group, a line per command."""
    lines = []
    for group, commands in _groups(data_commands()).items():
        lines.append(f"### {group}: {_group_title(group)}")
        lines += [
            f"- {_code(command.name)} ({_code(command.operation_id)}): "
            f"{command.summary}"
            for command in commands
        ]
    return "\n".join(lines)


def _group_names() -> str:
    return ", ".join(_code(group) for group in _groups(data_commands()))


def _errors() -> str:
    rows = [
        (_code(spec.code), str(spec.exit_code), _error_advice(spec.code))
        for spec in ERROR_CODES.values()
    ]
    return _table(("Code", "Exit", "What to do"), rows)


def _error_advice(code: str) -> str:
    advice = _ERROR_ADVICE.get(code)
    if advice is None:
        raise ValueError(f"The guide has no description of the error code {code!r}")
    return advice


def _error_codes() -> str:
    return ", ".join(
        f"{_code(spec.code)} ({spec.exit_code})" for spec in ERROR_CODES.values()
    )


def _python_call(function: str, command: Command, options: Mapping[str, object]) -> str:
    arguments = "".join(
        f", {name}={json.dumps(value, ensure_ascii=False)}"
        for name, value in options.items()
    )
    return f"retman.{function}({json.dumps(command.name)}{arguments})"


def _python_example() -> str:
    name, options = _EXAMPLE
    command = get_command(name)
    validate_command(command, options)
    function = "check_command" if options.get("check") else "run_command"
    plain = {key: value for key, value in options.items() if key != "check"}
    return _code(_python_call(function, command, plain))


def _cli_example() -> str:
    name, options = _EXAMPLE
    command = get_command(name)
    validate_command(command, options)
    return _code(f"{command.command_line(options)} --json")


def _rendered_step(step: _Step) -> str:
    """Return the CLI line of a step, after the catalog accepted its options.

    Raises
    ------
    CommandNotFoundError
        The step names a command that the catalog lacks.
    InvalidValueError
        The options of the step are not valid for its command.
    """
    command = get_command(step.command)
    validate_command(command, step.options)
    return command.command_line(step.options)


def _flows() -> str:
    """Render the typical flows: a numbered CLI line with a note per step."""
    sections = []
    for number, flow in enumerate(_FLOWS, start=1):
        lines = [f"### {number}. {flow.title}", flow.intro]
        lines += [
            f"{index}. {_code(_rendered_step(step))} - {step.note}"
            for index, step in enumerate(flow.steps, start=1)
        ]
        sections.append("\n".join(lines))
    return "\n".join(sections)


def _block_commands() -> str:
    """Render the commands of the compact block as CLI lines in a fence."""
    lines = []
    for name, options in _BLOCK_COMMANDS:
        command = get_command(name)
        validate_command(command, options)
        lines.append(f"{command.command_line(options)} --json")
    return "\n".join(["```bash", *lines, "```"])


def _blocks() -> dict[str, Callable[[], str]]:
    """Build the generated blocks of the guide (rendered only when used)."""
    return {
        "rules": _rules,
        "python_example": _python_example,
        "cli_example": _cli_example,
        "index": _index,
        "group_names": _group_names,
        "errors": _errors,
        "error_codes": _error_codes,
        "flows": _flows,
        "block_commands": _block_commands,
    }


# --- templates
# -------------------------------------------------------------------------


def _render(template: str, blocks: Mapping[str, Callable[[], str]]) -> list[str]:
    """Return the lines of ``template``, each with a newline, markers replaced.

    Raises
    ------
    ValueError
        A marker names an unknown block, a block is used twice or a multi-line block
        stands inside a line (program errors of a template).
    """
    used: set[str] = set()

    def block(name: str) -> str:
        if name not in blocks:
            raise ValueError(f"Unknown guide block {name!r} in a template")
        if name in used:
            raise ValueError(f"Guide block {name!r} is used twice in a template")
        used.add(name)
        return blocks[name]()

    def inline(match: re.Match[str]) -> str:
        text = block(match["name"])
        if "\n" in text:
            raise ValueError(
                f"Guide block {match['name']!r} has several lines but its marker "
                "stands inside a line of the template"
            )
        return text

    lines: list[str] = []
    for line in template.removesuffix("\n").split("\n"):
        whole = _MARKER.fullmatch(line.strip())
        if whole is not None:
            lines += block(whole["name"]).split("\n")
        else:
            lines.append(_MARKER.sub(inline, line))
    return [f"{line}\n" for line in lines]


def inject_block(existing: str, block: str) -> str:
    """Return ``existing`` with its Retman block replaced by ``block``.

    The block runs from :data:`BLOCK_BEGIN` to :data:`BLOCK_END`; ``block`` carries
    both markers. A text without the block gets it appended after a blank line, so
    injecting the same block again returns the same text (AGI-8.2).

    Parameters
    ----------
    existing : str
        Current text of the consumer's ``AGENTS.md`` (may be empty).
    block : str
        The block to put in, markers included.

    Returns
    -------
    str
        The new text, ending with a newline.
    """
    start = existing.find(BLOCK_BEGIN)
    end = existing.find(BLOCK_END, start) if start >= 0 else -1
    wanted = block.strip("\n")
    if start >= 0 and end >= 0:
        tail = existing[end + len(BLOCK_END) :]
        return existing[:start] + wanted + (tail if tail.strip() else "\n")
    if not existing.strip():
        return wanted + "\n"
    return existing.rstrip("\n") + "\n\n" + wanted + "\n"


def _template(format: GuideFormat) -> str:
    resource = files("retman").joinpath(*_TEMPLATES, f"{format}.md")
    return resource.read_text(encoding="utf-8")


def agent_guide(format: GuideFormat) -> str:
    r"""Generate the English guide for AI agents from the command catalog.

    ``format="agents"`` gives ``AGENTS.md`` (at most 200 lines and 16 KiB): purpose
    and scope, install, interfaces, the discover-check-run-read workflow, the result
    envelope, the error codes, the command index, typical flows and what not to do.
    ``format="llms"`` gives ``llms.txt`` in the llmstxt.org layout.
    ``format="agents-md-block"`` gives the compact block (at most 60 lines) between
    :data:`BLOCK_BEGIN` and :data:`BLOCK_END` for the ``AGENTS.md`` of a repository
    that uses Retman (see :func:`inject_block`). The text depends only on the
    installed package (no dates, no version, no local paths), so the repository files
    ``AGENTS.md`` and ``llms.txt`` equal ``agent_guide(format)`` byte for byte.

    Parameters
    ----------
    format : {"agents", "llms", "agents-md-block"}
        Guide to generate.

    Returns
    -------
    str
        UTF-8 Markdown with ``"\n"`` line ends, ending with a newline.

    Raises
    ------
    InvalidValueError
        ``format`` is not allowed (``details.option`` names it).
    ValueError
        A template or a flow is inconsistent with the catalog (a program error that
        the tests of the repository catch).

    Examples
    --------
    >>> agent_guide("llms").splitlines()[0]
    '# Retman'
    """
    options = validate_command("commands guide", {"format": format})
    guide = cast(GuideFormat, options["format"])
    return "".join(_render(_template(guide), _blocks()))

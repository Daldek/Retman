"""The commands of the Retman catalog: the one declaration of every interface (AGI-1.1).

Each :class:`~retman.catalog.spec.Command` names the function of
:mod:`retman.operations` that implements it; the CLI, ``list_commands`` and the other
catalog functions, the guides for agents and the schemas of the result documents come
from this list. The texts are English (AGI-9.1); the Polish ones are in
``src/retman/i18n/pl.toml`` under ``[catalog.<operation_id>]`` and a test requires one
for every command, option, rule and choice.

To add a command
----------------
1. Write the operation in ``src/retman/operations/`` (a function with keyword-only
   parameters named like the options that returns an :class:`~retman.catalog.Output`)
   and export it in ``src/retman/operations/__init__.py``.
2. Declare it here, add its Polish texts to ``pl.toml`` and its document schema to
   ``scripts/generate_result_schemas.py``.
3. Regenerate what follows from the catalog: ``scripts/generate_result_schemas.py``,
   ``retman commands guide --format agents --output AGENTS.md --force`` and
   ``retman commands guide --format llms --output llms.txt --force``.
"""

from typing import Final

from retman.catalog.spec import Command, Effects, Option

_ONLY_READS: Final = Effects(
    read_only=True, writes="none", idempotent=True, network=False, destructive=False
)


def _config(*, role: str = "input") -> Option:
    """Return the option that names the settings file."""
    if role == "output":
        return Option(
            "config",
            "path",
            "Settings file to write (nogat.toml); default: the user configuration "
            "folder, or NOGAT_CONFIG.",
            path_role="output",
        )
    return Option(
        "config",
        "path",
        "Settings file (nogat.toml); default: the user configuration folder, or "
        "NOGAT_CONFIG.",
        path_role="input",
    )


def _limit(default: int | None, what: str) -> Option:
    return Option(
        "limit",
        "integer",
        f"Number of {what} per page; with it the result has a `page`.",
        default=default,
        minimum=1,
    )


_CURSOR: Final = Option(
    "cursor",
    "string",
    "The `page.next_cursor` of the previous page, passed unchanged.",
)
_CHECK: Final = Option(
    "check",
    "boolean",
    "Plan without effects: show what would be written and stop.",
)

_PLAN_RUN: Final = Command(
    name="plan run",
    operation_id="retman_plan_run",
    summary="Plan an operation from a Polish command and, once confirmed, run it.",
    description=(
        "Recognises the operation in a Polish command, fills in the values it states "
        "and lists open questions; with `yes` runs the complete plan. Use it to get "
        "or prepare data from Kartograf and IMGWTools in Polish words. Not for other "
        "languages or for exact calls of a tool (use the tool itself)."
    ),
    function="retman.operations.plan_run",
    options=(
        Option(
            "text",
            "string",
            "The command in Polish, e.g. 'Pobierz NMT 1 m dla arkusza "
            "N-34-130-D-d-2-4'. Without it a terminal starts a session.",
        ),
        Option(
            "check",
            "boolean",
            "Plan without effects: recognise, show the plan with its open questions "
            "and stop. Nothing is run and nothing is written.",
            one_of="mode",
        ),
        Option(
            "yes",
            "boolean",
            "Confirm the plan without a prompt and run it. An open question is an "
            "error: there is nobody to answer.",
            one_of="mode",
        ),
        Option(
            "explain",
            "boolean",
            "Add the decisions of the model: choice, confidence, method and the "
            "probability of each option.",
        ),
        _config(),
    ),
    result_schema="retman-plan/1",
    effects=Effects(
        read_only=False,
        writes="add",
        idempotent=False,
        network=True,
        destructive=False,
    ),
    check=True,
    rules=(
        "Run `check` first: open `questions` mean the plan is incomplete.",
        "Put missing values into `text` and repeat; without a terminal nothing is "
        "asked.",
        "Give `yes` only after the user approved the plan.",
    ),
    errors=(
        "validation_error",
        "not_found",
        "conflict",
        "source_unavailable",
        "missing_dependency",
        "data_error",
        "store_unavailable",
        "io_error",
        "calculation_error",
        "no_data",
        "unsupported",
    ),
    examples=(
        {
            "text": "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4",
            "check": True,
        },
    ),
    example_results=(
        {
            "operation": "download_dem_sheet",
            "complete": True,
            "confirmed": False,
        },
    ),
)

_CONFIG_SHOW: Final = Command(
    name="config show",
    operation_id="retman_config_show",
    summary="Show every setting with its value and source, and the tool stores.",
    description=(
        "Reports the settings file, each key of Retman with its value and the layer "
        "that gave it (option, variable, file, default), the credential variables "
        "(present or missing, never the value) and the stores of the tools. Use it to "
        "see what is in force. It only reads. Not for changing settings: edit "
        "`nogat.toml`."
    ),
    function="retman.operations.config_show",
    options=(_config(),),
    result_schema="retman-config/1",
    effects=_ONLY_READS,
    rules=(
        "Read `keys.<name>.source` to see why a value is in force.",
        "Credentials are variables of the environment; never put them in the file.",
    ),
    errors=("not_found", "validation_error"),
    examples=({},),
    example_results=(
        {
            "tool": "retman",
            "keys": {"lang": {"value": "pl", "source": "default"}},
        },
    ),
)

_CONFIG_INIT: Final = Command(
    name="config init",
    operation_id="retman_config_init",
    summary=(
        "Write the [retman] tables, with every default made visible, into nogat.toml."
    ),
    description=(
        "Appends the complete `[retman]` tables to `nogat.toml` (created if missing); "
        "other tables stay. It never overwrites an existing `[retman]` table and, "
        "without a terminal, creates no folders. Use it once per user, before the "
        "first plan. Not for changing a table that exists: edit the file."
    ),
    function="retman.operations.config_init",
    options=(
        _config(role="output"),
        Option(
            "collect_commands",
            "boolean",
            "Collect the commands of all projects in one file, to build the test set "
            "(ADR-010). Ask the user first: it records their words. Default: off.",
        ),
        Option(
            "stores_dir",
            "path",
            "Folder that holds the stores of both tools (`kartograf` and `imgw` inside "
            "it); default: the data folder of nogat.",
            path_role="output",
        ),
        _CHECK,
    ),
    result_schema="retman-config-init/1",
    effects=Effects(
        read_only=False,
        writes="add",
        idempotent=False,
        network=False,
        destructive=False,
    ),
    check=True,
    rules=(
        "Run with `check` first: an existing [retman] table is a conflict.",
        "Ask the user before you set `collect_commands`.",
    ),
    errors=("validation_error", "not_found", "conflict", "io_error"),
    examples=({"config": "nogat.toml", "check": True},),
    example_results=({"targets": [{"option": "config", "action": "write"}]},),
)

_DOCTOR_CHECK: Final = Command(
    name="doctor check",
    operation_id="retman_doctor_check",
    summary=(
        "Check settings, model server, tools and stores; say how to fix each problem."
    ),
    description=(
        "One report: settings and project folder, model server, installed tools and "
        "their stores, drift of the tool descriptions, translations. Each check is "
        "a unit in `items`; a failed one has a registry code and a hint. Use it when "
        "a command fails or after installing a tool; not for planning (`plan run`). "
        "`deep` adds a trial write to the IMGWTools store."
    ),
    function="retman.operations.doctor_check",
    options=(
        _config(),
        Option(
            "deep",
            "boolean",
            "Also run the slower checks: a trial write to the IMGWTools store on the "
            "tool's own test data, in a temporary folder, without the network.",
        ),
    ),
    result_schema="retman-doctor/1",
    effects=Effects(
        read_only=True,
        writes="none",
        idempotent=True,
        network=True,
        destructive=False,
    ),
    rules=(
        "`partial` means some checks failed, `failed` that none passed.",
        "Fix blocking checks in the order listed; the hint names the command.",
    ),
    errors=("not_found", "validation_error"),
    examples=({"config": "nogat.toml"},),
    example_results=(
        {
            "sections": [{"key": "configuration", "checks": [{"status": "ok"}]}],
        },
    ),
)

_RESULTS_LIST: Final = Command(
    name="results list",
    operation_id="retman_results_list",
    summary="List the numbered results saved in the project folder.",
    description=(
        "Reads the results folder of the current directory (setting "
        "`output.results_dir`): number, operation, success and summary of each result "
        "in numeric order. Use it to find the number of a result that a later command "
        "refers to. It never changes the project. Not for the details of one run: "
        "read its folder."
    ),
    function="retman.operations.results_list",
    options=(_config(), _limit(50, "results"), _CURSOR),
    result_schema="retman-results/1",
    cardinality="unbounded",
    effects=_ONLY_READS,
    rules=("Run it in the project folder: results belong to the folder.",),
    errors=("not_found", "validation_error"),
    examples=({"limit": 10},),
    example_results=(
        {"results": [{"number": 1, "operation": "download_dem_sheet", "ok": True}]},
    ),
)

_JOURNAL_SHOW: Final = Command(
    name="journal show",
    operation_id="retman_journal_show",
    summary="Show the event journal of the project folder.",
    description=(
        "Reads the journal of the results folder: commands, questions, answers, plans, "
        "approvals and executions in the order they happened. Use it to audit what was "
        "asked and run. Commands and answers are absent when `log.journal_commands` is "
        "off. Not for results: use `results list`."
    ),
    function="retman.operations.journal_show",
    options=(_config(), _limit(20, "events"), _CURSOR),
    result_schema="retman-journal/1",
    cardinality="unbounded",
    effects=_ONLY_READS,
    rules=("Page with `cursor`: the newest events are on the last page.",),
    errors=("not_found", "validation_error"),
    examples=({"limit": 5},),
    example_results=({"events": [{"event": "command"}]},),
)

_COMMANDS_LIST: Final = Command(
    name="commands list",
    operation_id="retman_commands_list",
    summary="List the commands of the catalog.",
    description=(
        "One line per command: name, `operation_id`, summary and whether it only "
        "reads. Use it first. Not for options: use `commands schema`."
    ),
    function="retman.operations.commands_list",
    options=(_limit(None, "commands"), _CURSOR),
    result_schema="retman-command-list/1",
    cardinality="bounded",
    effects=_ONLY_READS,
    rules=("Do not guess options: read `commands schema`.",),
    errors=("validation_error",),
    examples=({},),
    example_results=({"commands": [{"name": "plan run", "read_only": False}]},),
)

_COMMANDS_SCHEMA: Final = Command(
    name="commands schema",
    operation_id="retman_commands_schema",
    summary="Describe a command: options, result, effects, rules, examples and errors.",
    description=(
        "The `retman-commands/1` entry of one command, or of all of them page by page. "
        "Options carry type, unit, bounds, choices with meanings, path role and "
        "exclusion group; effects say whether the command writes or uses the network. "
        "Use it before you call a command. Not for a list of names: use "
        "`commands list`."
    ),
    function="retman.operations.commands_schema",
    options=(
        Option(
            "command",
            "string",
            "Command name ('plan run') or its operation_id; without it every command, "
            "page by page.",
        ),
        _limit(None, "commands"),
        _CURSOR,
    ),
    result_schema="retman-commands/1",
    cardinality="bounded",
    effects=_ONLY_READS,
    rules=("Read `effects` and `errors` before a command that writes.",),
    errors=("not_found", "validation_error"),
    examples=({"command": "plan run"},),
    example_results=({"commands": [{"name": "plan run"}]},),
)

_COMMANDS_GUIDE: Final = Command(
    name="commands guide",
    operation_id="retman_commands_guide",
    summary="Print or write AGENTS.md, llms.txt or the block for another repository.",
    description=(
        "Renders the guides for agents from the catalog and the error registry. "
        "`output` writes a file (replaced only with `force`); `inject` replaces the "
        "Retman block in the AGENTS.md of a repository that uses Retman, idempotently. "
        "Use it to refresh generated files; never edit them by hand. Not for learning "
        "one command: use `commands schema`."
    ),
    function="retman.operations.commands_guide",
    options=(
        Option(
            "format",
            "choice",
            "Which guide to render.",
            default="agents",
            choices=("agents", "llms", "agents-md-block"),
            meanings={
                "agents": "AGENTS.md: the full guide for agents that use Retman",
                "llms": "llms.txt: the summary and the links (llmstxt.org layout)",
                "agents-md-block": (
                    "the compact block for the AGENTS.md of another repository"
                ),
            },
        ),
        Option(
            "output",
            "path",
            "File to write instead of printing the guide.",
            path_role="output",
            one_of="target",
        ),
        Option(
            "inject",
            "path",
            "AGENTS.md whose Retman block is replaced (created if missing); needs the "
            "format `agents-md-block`.",
            path_role="output",
            one_of="target",
        ),
        _CHECK,
        Option(
            "force",
            "boolean",
            "Replace the file of `output` if it exists.",
        ),
    ),
    result_schema="retman-guide/1",
    effects=Effects(
        read_only=False,
        writes="replace",
        idempotent=True,
        network=False,
        destructive=True,
    ),
    check=True,
    rules=("Run with `check` first when you give `output` or `inject`.",),
    errors=("validation_error", "conflict", "io_error"),
    examples=({"format": "llms"},),
    example_results=({"format": "llms"},),
)

_EVAL_RUN: Final = Command(
    name="eval run",
    operation_id="retman_eval_run",
    summary=(
        "Measure how well the model picks operations and values on the command set."
    ),
    description=(
        "Plans every command of the set without running anything, then reports "
        "accuracy, wrongly accepted values, silent guesses, W-03 violations, timings "
        "and the recommended confidence thresholds. Use it after changing the model or "
        "the descriptions. Needs the model server. Not for planning one command: "
        "use `plan run` with `check`."
    ),
    function="retman.operations.eval_run",
    options=(
        _config(),
        Option(
            "commands",
            "path",
            "JSONL file with the commands; default: the set shipped with Retman.",
            path_role="input",
        ),
        Option(
            "operations",
            "string_list",
            "Evaluate only the commands that expect these operations (repeat the "
            "flag).",
        ),
        Option(
            "tags",
            "string_list",
            "Evaluate only the commands with one of these tags (repeat the flag).",
        ),
        Option(
            "repeat",
            "integer",
            "Plan every command this many times (stability of the model).",
            default=1,
            minimum=1,
        ),
        Option(
            "target_error",
            "number",
            "Accepted share of wrong decisions taken without asking, in (0, 1]; adds "
            "the recommended thresholds.",
            exclusive_minimum=0,
            maximum=1,
        ),
        Option(
            "output",
            "path",
            "File for the raw record of every run (JSON lines).",
            path_role="output",
        ),
        Option(
            "report",
            "path",
            "File for the Markdown report; without it the report is printed.",
            path_role="output",
        ),
        _CHECK,
        Option("force", "boolean", "Replace `output` and `report` if they exist."),
    ),
    result_schema="retman-eval/1",
    cardinality="bounded",
    effects=Effects(
        read_only=False,
        writes="replace",
        idempotent=False,
        network=True,
        destructive=True,
    ),
    check=True,
    rules=(
        "Run `doctor check` first: the model server must answer.",
        "A failed unit in `items` is a command that had to be refused and was planned.",
    ),
    errors=(
        "validation_error",
        "not_found",
        "conflict",
        "data_error",
        "source_unavailable",
        "io_error",
    ),
    examples=({"target_error": 0.01, "output": "records.jsonl"},),
    example_results=({"commands": 630, "runs": 630},),
)

_SCAFFOLD_CHECK: Final = Command(
    name="scaffold check",
    operation_id="retman_scaffold_check",
    summary="Compare the tool descriptions with the installed tools and report drift.",
    description=(
        "Runs every call the descriptions can build against the installed tool, "
        "offline, and compares what the tool accepts with what the manifest offers "
        "(checks X1 to X10). Each tool is a unit of `items`. Use it after upgrading a "
        "tool or editing a description. Nothing is downloaded or written. Not for "
        "the model: use `eval run`."
    ),
    function="retman.operations.scaffold_check",
    options=(
        Option("tool", "string_list", "Check only these tools (repeat the flag)."),
        Option(
            "operation",
            "string_list",
            "Check only these operations (repeat the flag).",
        ),
        Option(
            "commands",
            "path",
            "JSONL file with the commands the grids are built from; default: the set "
            "shipped with Retman.",
            path_role="input",
        ),
        Option(
            "require_tools",
            "boolean",
            "A tool that is not installed is an error, not a skipped tool.",
        ),
        Option(
            "include_info",
            "boolean",
            "Also list the findings of severity info.",
        ),
    ),
    result_schema="retman-scaffold-check/1",
    cardinality="bounded",
    effects=_ONLY_READS,
    rules=("Fix `error` findings; `warning` and `info` do not block work.",),
    errors=("validation_error", "data_error", "not_found"),
    examples=({"tool": ["kartograf"]},),
    example_results=({"tools": [{"tool": "kartograf", "status": "checked"}]},),
)

_SCAFFOLD_LIST: Final = Command(
    name="scaffold list",
    operation_id="retman_scaffold_list",
    summary=(
        "List the data commands of a tool's catalog and the operations that use them."
    ),
    description=(
        "Reads the catalog of an installed tool and shows each data command with its "
        "group, effects, the operations that call it and how it can be used. Use it to "
        "find what a new operation could cover. The tool must be installed. Not for "
        "drift: use `scaffold check`."
    ),
    function="retman.operations.scaffold_list",
    options=(Option("tool", "string", "Name of the tool.", required=True),),
    result_schema="retman-scaffold-list/1",
    cardinality="bounded",
    effects=_ONLY_READS,
    errors=("validation_error", "unsupported", "missing_dependency"),
    examples=({"tool": "kartograf"},),
    example_results=(
        {"tool": "kartograf", "commands": [{"id": "elevation download"}]},
    ),
)

_SCAFFOLD_DRAFT: Final = Command(
    name="scaffold draft",
    operation_id="retman_scaffold_draft",
    summary=(
        "Draft an operation from one catalog command of a tool, to be reviewed by hand."
    ),
    description=(
        "Builds a starting point for a new operation: Python for the call builder and "
        "a translation table. `write` saves them below "
        "`src/retman/tools/<tool>/_drafts/` "
        "and never replaces a file. Not for users, only for developing Retman."
    ),
    function="retman.operations.scaffold_draft",
    options=(
        Option("tool", "string", "Name of the tool.", required=True),
        Option(
            "command",
            "string",
            "Catalog command of the tool to draw from, e.g. 'elevation download'.",
            required=True,
        ),
        Option(
            "fix",
            "string_list",
            "Fix a tool option to a value, `name=value` (repeat the flag).",
        ),
        Option(
            "only",
            "string_list",
            "Keep only these tool options in the draft (repeat the flag).",
        ),
        Option("id", "string", "Identifier of the new operation."),
        Option(
            "write",
            "boolean",
            "Save the draft as files instead of printing it.",
        ),
        _CHECK,
    ),
    result_schema="retman-scaffold-draft/1",
    effects=Effects(
        read_only=False,
        writes="add",
        idempotent=False,
        network=False,
        destructive=False,
    ),
    check=True,
    rules=("Review every draft: nothing is wired into the registry for you.",),
    errors=("validation_error", "unsupported", "conflict", "io_error"),
    examples=(
        {
            "tool": "kartograf",
            "command": "elevation download",
            "write": True,
            "check": True,
        },
    ),
    example_results=({"targets": [{"option": "write", "action": "write"}]},),
)

COMMANDS: Final[tuple[Command, ...]] = (
    _PLAN_RUN,
    _CONFIG_SHOW,
    _CONFIG_INIT,
    _DOCTOR_CHECK,
    _RESULTS_LIST,
    _JOURNAL_SHOW,
    _COMMANDS_LIST,
    _COMMANDS_SCHEMA,
    _COMMANDS_GUIDE,
    _EVAL_RUN,
    _SCAFFOLD_CHECK,
    _SCAFFOLD_LIST,
    _SCAFFOLD_DRAFT,
)
"""Every command, in the order of the CLI help and of the guides."""

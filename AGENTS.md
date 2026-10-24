# Retman - guide for agents

> Generated from the command catalog: `retman commands guide --format agents`. Do not edit it by hand.

## Purpose and scope

Retman is a CLI and a Python library that turns a data task written in Polish into a plan for the tools of the Nogat ecosystem (Kartograf for spatial data, IMGWTools for IMGW measurements), asks for what is missing, shows the plan and, once confirmed, runs it and saves the result in the project folder. A language model on a separate server (any OpenAI-compatible one) only chooses between listed options; numbers, dates, coordinates and identifiers are read by code. The commands are in Polish: the user's sentence is the input, everything else is English.

Use it when a person states a download or export in Polish and wants to see a checked plan before anything is fetched. Not for:

- exact calls of a tool with known options: use the tool itself (`kartograf ...`, `imgw ...`);
- commands in other languages, hydrological computation (Hydrolog) or GIS processing.

## Install

Python 3.12 or newer: `pip install "retman @ git+https://github.com/Daldek/Retman.git"`. The tools are installed separately (Kartograf, IMGWTools); the model server is configured in `[retman.decision]` of `nogat.toml` (`retman config init`, `retman doctor check`). No MCP server and no REST API.

## Interfaces

- Python: `retman.check_command("plan run", text="Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4")`. The same options as keyword arguments serve `retman.run_command`, `retman.validate_command`, `retman.list_commands` and `retman.command_schema`. `run_command` returns the envelope (`to_dict()`, `to_json()`); errors raise `RetmanError` subclasses (`code`, `hint`, `details`). The classes `Retman` and `Plan` serve programs that answer open questions themselves.
- CLI: `retman <group> <verb> --option value --json`, e.g. `retman plan run --text 'Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4' --check --json`. A flag is `--` and the option name with `-` for `_`; a list is given by repeating the flag; a boolean is a bare flag. `--json` prints the envelope on one line of stdout and never prompts; `--lang pl|en` only changes human output (texts exist in Polish); `--verbose` and `--quiet` set the log level on stderr.
- Settings: `retman config show` prints every setting with its source (`nogat.toml`, `RETMAN_*` and `NOGAT_*` variables).

## Workflow rules

Discover, check, run, read: `retman commands list`, then `retman commands schema --command "<name>"`; plan with `--check`; run with `--yes` only after the user approved the plan; read `result`, `items`, `notices` and `result.run`.

Rules:

1. **Discover, do not guess:** `commands list` lists the commands, `commands schema` (option `command`) gives options, effects, errors and examples.
2. **Plan, then run:** `plan run` with `check` shows what Retman understood; run it with `yes` only after the user approved that plan (`result.confirmed` is false until then).
3. **The text is the user's Polish sentence:** pass it as `text`, do not translate or rewrite it. Nothing is asked without a terminal: put every missing value into the text and plan again.
4. **Open questions are part of a plan:** `result.questions` lists them and `result.complete` is false; `yes` with an open question is `validation_error` (reason `input_required`, `details.questions`).
5. **Errors by code:** decide by `code`, `details.reason` and `details.option` (or the exit code), fix the argument as `hint` says and call again; never present an error as a result.
6. **Outcomes are not errors:** `partial` (exit 10) and `failed` (exit 11) print the envelope; read `items`, a failed unit has a registry `code`.
7. **Read `notices` and `result.run.warnings`:** licence and data-quality notes of the data providers belong with the data; pass them on.
8. **Run Retman in the project folder:** results and the journal live there (`results list`, `journal show`); no ordinary command writes elsewhere.

## Result envelope

A command returns `retman-result/1`: `schema`, `tool` (`retman`), `version`, `command`, `check` (true for a plan: `plan run` gives `retman-plan/1`, a command that writes files gives `retman-targets/1` with `targets[]` of `option`, `path`, `action`), `status` (`ok`, `partial`, `failed`, `cancelled`), `result`, `items`, `notices`, `page` (paged lists).

- `result`: the document of the command with its own `schema`; `result.files` lists files a command wrote (`path`, `size_bytes`, `sha256`, `status`).
- `status` and `items`: a batch command (`doctor check`, `eval run`, `scaffold check`) lists its units in `items`; `partial` (exit 10) has units that passed and failed, `failed` (exit 11) none that passed. They print the envelope; they are not errors.
- `notices`: non-fatal `{level, code, message}` entries.
- `page`: `total`, `truncated` and `next_cursor`; pass it as `cursor` for the next page.

## Error codes

Errors are `retman-error/1` documents (`schema`, `code`, `title`, `message`, `hint`, `details`, `exit_code`, `command`) on the last line of stderr, in both modes; stdout stays empty. The code is the same in Python and as the exit code. Registry: https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md

| Code | Exit | What to do |
|---|---|---|
| `internal_error` | 1 | bug in Retman: report command, options, version |
| `validation_error` | 2 | wrong or missing option or input: see `details.option` |
| `not_found` | 3 | unknown command, settings file, input file or result: see `hint` |
| `conflict` | 4 | file exists or plan not confirmed: another path, `force`, or `yes` |
| `source_unavailable` | 5 | model server or data service failed: run `doctor check` |
| `missing_dependency` | 6 | a tool is not installed: install it (`hint`) |
| `data_error` | 7 | malformed input or command set: see `details.path` and `reason` |
| `store_unavailable` | 8 | a tool store cannot be used: run `doctor check` |
| `io_error` | 9 | a file cannot be read or written: check `details.path` |
| `forbidden` | 12 | path or action not allowed: see `hint` |
| `calculation_error` | 13 | valid input, no result computable: change the data |
| `no_data` | 14 | the source has no data for the area or period: change the request |
| `unsupported` | 15 | the command is outside Retman's operations (`details.operations`) |
| `cancelled` | 130 | stopped by the user: nothing half done, run again |
| `terminated` | 143 | ended by SIGTERM: nothing half done, run again |

## Command index

One line per command: name, `operation_id`, summary. Options, units, bounds and examples: `retman commands schema --command "<name>"`.

### plan: From a Polish command to a plan and a result
- `plan run` (`retman_plan_run`): Plan an operation from a Polish command and, once confirmed, run it.
### config: Settings
- `config show` (`retman_config_show`): Show every setting with its value and source, and the tool stores.
- `config init` (`retman_config_init`): Write the [retman] tables, with every default made visible, into nogat.toml.
### doctor: Diagnosis
- `doctor check` (`retman_doctor_check`): Check settings, model server, tools and stores; say how to fix each problem.
### results: Results of the project folder
- `results list` (`retman_results_list`): List the numbered results saved in the project folder.
### journal: Journal of the project folder
- `journal show` (`retman_journal_show`): Show the event journal of the project folder.
### commands: The command catalog and this guide
- `commands list` (`retman_commands_list`): List the commands of the catalog.
- `commands schema` (`retman_commands_schema`): Describe a command: options, result, effects, rules, examples and errors.
- `commands guide` (`retman_commands_guide`): Print or write AGENTS.md, llms.txt or the block for another repository.
### eval: Quality of the model
- `eval run` (`retman_eval_run`): Measure how well the model picks operations and values on the command set.
### scaffold: Descriptions of the tools (for developers)
- `scaffold check` (`retman_scaffold_check`): Compare the tool descriptions with the installed tools and report drift.
- `scaffold list` (`retman_scaffold_list`): List the data commands of a tool's catalog and the operations that use them.
- `scaffold draft` (`retman_scaffold_draft`): Draft an operation from one catalog command of a tool, to be reviewed by hand.

## Typical flows

CLI lines; in Python call `retman.run_command` with the same options as keyword arguments. Paths are examples.

### 1. Get data with a Polish command
The model server must answer (`doctor check`) and the tool must be installed.
1. `retman plan run --text 'Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4' --check` - the plan: `result.operation`, `result.values` with their `source`, `result.questions` when the command leaves something open; nothing is run or written.
2. `retman plan run --text 'Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4' --yes` - runs the confirmed plan; `result.run.files` lists the files and `result.run.summary` says what was done. Only after the user approved the plan.
3. `retman results list` - number and summary of every result in the project folder.
### 2. Find out why something does not work
`doctor check` answers `partial` or `failed` when a check blocks work.
1. `retman doctor check` - every check is a unit of `items`; a failed one has `code`, `reason` and a message with the fix.
2. `retman config show` - each setting with its value and source (option, variable, file or default); credentials are `present` or `missing`.
### 3. Set Retman up for a user
Writes the `[retman]` tables into `nogat.toml`; an existing table is a `conflict`. Ask before `collect_commands`: it records the user's commands.
1. `retman config init --check` - the plan: `result.targets[]` with the action `write` or `conflict`.
2. `retman config init` - writes the tables; `result.files` names the file.
### 4. Measure the model on the command set
Plans every command without running anything; needs the model server.
1. `retman eval run --target-error 0.01 --output records.jsonl --check` - the files that would be written, with their actions.
2. `retman eval run --target-error 0.01 --output records.jsonl` - the measures in `result`; a failed unit of `items` is a command that had to be refused and was planned.

## Things not to do

- Do not run a plan with `--yes` that the user has not seen.
- Do not translate, shorten or rewrite the user's Polish sentence.
- Do not parse `message` or `hint`: decide by `code`, `details.option`, `details.reason` or the exit code.
- Do not repeat a call unchanged after `validation_error`, `data_error` or `unsupported`.
- Do not call the tools Retman drives through Retman when exact options are known: call them directly.

## Working on this repository

Gate: `scripts/gate.sh`. To add a command (details in `src/retman/catalog/commands.py`):

1. Write the operation in `src/retman/operations/` and export it in `src/retman/operations/__init__.py`.
2. Declare `Command` and `Option` in `src/retman/catalog/commands.py` and add the Polish texts to `src/retman/i18n/pl.toml` under `[catalog.<operation_id>]`; add the schema of its document to `scripts/generate_result_schemas.py`.
3. Regenerate what follows from the catalog: `uv run scripts/generate_result_schemas.py`, `retman commands guide --format agents --output AGENTS.md --force` and `retman commands guide --format llms --output llms.txt --force`.

Developing this repository? Read CLAUDE.md.

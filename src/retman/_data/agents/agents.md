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

- Python: <!-- retman:python_example -->. The same options as keyword arguments serve `retman.run_command`, `retman.validate_command`, `retman.list_commands` and `retman.command_schema`. `run_command` returns the envelope (`to_dict()`, `to_json()`); errors raise `RetmanError` subclasses (`code`, `hint`, `details`). The classes `Retman` and `Plan` serve programs that answer open questions themselves.
- CLI: `retman <group> <verb> --option value --json`, e.g. <!-- retman:cli_example -->. A flag is `--` and the option name with `-` for `_`; a list is given by repeating the flag; a boolean is a bare flag. `--json` prints the envelope on one line of stdout and never prompts; `--lang pl|en` only changes human output (texts exist in Polish); `--verbose` and `--quiet` set the log level on stderr.
- Settings: `retman config show` prints every setting with its source (`nogat.toml`, `RETMAN_*` and `NOGAT_*` variables).

## Workflow rules

Discover, check, run, read: `retman commands list`, then `retman commands schema --command "<name>"`; plan with `--check`; run with `--yes` only after the user approved the plan; read `result`, `items`, `notices` and `result.run`.

Rules:

<!-- retman:rules -->

## Result envelope

A command returns `retman-result/1`: `schema`, `tool` (`retman`), `version`, `command`, `check` (true for a plan: `plan run` gives `retman-plan/1`, a command that writes files gives `retman-targets/1` with `targets[]` of `option`, `path`, `action`), `status` (`ok`, `partial`, `failed`, `cancelled`), `result`, `items`, `notices`, `page` (paged lists).

- `result`: the document of the command with its own `schema`; `result.files` lists files a command wrote (`path`, `size_bytes`, `sha256`, `status`).
- `status` and `items`: a batch command (`doctor check`, `eval run`, `scaffold check`) lists its units in `items`; `partial` (exit 10) has units that passed and failed, `failed` (exit 11) none that passed. They print the envelope; they are not errors.
- `notices`: non-fatal `{level, code, message}` entries.
- `page`: `total`, `truncated` and `next_cursor`; pass it as `cursor` for the next page.

## Error codes

Errors are `retman-error/1` documents (`schema`, `code`, `title`, `message`, `hint`, `details`, `exit_code`, `command`) on the last line of stderr, in both modes; stdout stays empty. The code is the same in Python and as the exit code. Registry: https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md

<!-- retman:errors -->

## Command index

One line per command: name, `operation_id`, summary. Options, units, bounds and examples: `retman commands schema --command "<name>"`.

<!-- retman:index -->

## Typical flows

CLI lines; in Python call `retman.run_command` with the same options as keyword arguments. Paths are examples.

<!-- retman:flows -->

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

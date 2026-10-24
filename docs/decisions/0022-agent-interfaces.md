# ADR-022: Agent interfaces: one command catalog, one `retman` executable

**Date:** 2026-10-24
**Status:** accepted; supersedes the command layout of ADR-019 (`retman-scaffold` is
`retman scaffold`) and of ADR-011 (`retman-eval` is `retman eval run`)

## Context

The Nogat standard 2.1 asks every tool for one command catalog from which the Python
functions, the CLI, the guides for agents and the schemas are generated or tested (AGI-1.1),
one executable `<tool> <group> <verb>` (AGI-3.1), the result envelope `<tool>-result/1`
(AGI-4.2), `list_commands`, `command_schema`, `validate_command`, `check_command` and
`run_command` in the public API (AGI-2.1) and the generated `AGENTS.md` and `llms.txt`
(AGI §8). Retman had three executables (`retman`, `retman-eval`, `retman-scaffold`), a
positional Polish sentence as its main command, bare JSON documents for `config show` and
`doctor`, and `--plan-only` for a plan without effects. The registry lists Retman with the
interfaces CLI and Python; there is no MCP server and no REST API (ADR-018 plans MCP for
v0.3). Release 0.1.0 is not tagged, so the change needs no migration path (ECO-020).

## Options considered

- Keep the three executables and add the catalog functions: against AGI-3.1.
- Generate the CLI from the catalog but keep the positional sentence: a positional word
  collides with the group word.
- One catalog, `retman <group> <verb>`, the sentence as `--text` (chosen).

## Decision

1. **Commands.** `plan run`, `config show`, `config init`, `doctor check`, `results list`,
   `journal show`, `commands list|schema|guide`, `eval run`, `scaffold check|list|draft`.
   `operation_id` is `retman_<group>_<verb>`, the function `retman.operations.<group>_<verb>`
   with keyword-only parameters named like the options. There is no `families` field (no MCP).
   The declarations are `src/retman/catalog/commands.py`; the texts are English, the Polish
   ones are in `src/retman/i18n/pl.toml` under `[catalog.<operation_id>]`, and a contract test
   requires a Polish text for every command, option, rule and choice (AGI-9.1).
2. **Python API.** `retman.__all__` is the public API (AGI-7.1): the conversation classes
   (`Retman`, `Plan`, `Result`, `CheckReport`), the error classes with the registry and the
   five functions of AGI-2.1, which import the catalog when first called (AGI-7.3).
3. **Envelope.** Every command prints `retman-result/1` with `--json`: one line on stdout, never a
   prompt. `status` follows from `items`: `ok`, `partial` (exit 10), `failed` (exit 11) and
   `cancelled` (exit 130). The units are the checks of `doctor check`, the commands that had
   to be refused in `eval run` (a planned one is `failed`, code `unsupported`, reason
   `planned_out_of_scope`) and the tools of `scaffold check`. An error raises a registry error,
   prints nothing on stdout and ends stderr with `retman-error/1` (AGI-3.3).
4. **`plan run`.** `--text` is the command, `--check` plans without effects (it replaces
   `--plan-only`; open questions are part of the plan and no error), `--yes` confirms,
   `--check` and `--yes` exclude each other, `--explain` adds the decisions of the model. Without a
   terminal, with `--json`, or without `--yes`, an open question, or `--text`, nothing is asked:
   the call fails with `validation_error`, reason `input_required` (`details.questions`,
   `details.option`). A terminal without `--json` keeps the dialog. A failed run raises the
   registry error of its failure (AGI-3.5).
5. **Writing commands** (`config init`, `eval run`, `commands guide`, `scaffold draft`) have
   `--check`: the result is `retman-targets/1` with each target and its action `write`,
   `replace` or `conflict`, and a plan that lists a conflict is a success (DEV-19.10). An
   existing target without `--force` is `conflict`, reason `output_exists`, `details.paths`
   lists every path and nothing is written (DEV-19.6). Retman keeps no store: files go to
   `--output` (and `--report` of `eval run`).
6. **Presentation options** on every verb: `--json`, `--lang`, `--verbose`, `--quiet`. They
   are settings, not catalog options: `retman.environment` has an option layer above the
   variables and the file (DEV-18.1), `--lang` sets `lang` and `--verbose` or `--quiet`
   `log_level`. Lists are given by repeating the flag; `scaffold`'s old `-v` is
   `--include-info`.
7. **Guides.** `retman commands guide --format agents|llms|agents-md-block` renders
   `AGENTS.md`, `llms.txt` and the block of AGI-8.2 from the templates in
   `src/retman/_data/agents/`; `--output PATH --force` writes, `--inject AGENTS.md` replaces the
   block idempotently. The typical flows are checked against the catalog while they are
   rendered. `AGENTS.md` and `llms.txt` in the repository root are generated, never edited, and
   a contract test compares them byte for byte with the generator and checks the budgets of
   DOC-1.7.
8. **Schemas.** `src/retman/schemas/` holds one loose JSON Schema per domain document
   (`retman-plan/1`, `-config/1`, `-config-init/1`, `-doctor/1`, `-results/1`, `-journal/1`,
   `-command-list/1`, `-guide/1`, `-eval/1`, `-scaffold-check/1`, `-scaffold-list/1`,
   `-scaffold-draft/1`, `-targets/1`), written by `scripts/generate_result_schemas.py`
   (`--check` in the contract test). `retman-commands/1` is the Nogat schema
   `commands-1`. Documents are validated where they are produced.
9. **Texts.** The catalog, the guides, the error documents and the schemas are English. The
   texts inside the documents of `doctor check`, `scaffold check` and `eval run` come from
   `pl.toml`, because no English translation exists yet; `machine_texts()` switches to
   English as soon as `en.toml` does (PROGRESS Next 8, AGI-9.2).

## Consequences

- Breaking: `retman "<text>"` is `retman plan run --text "<text>"`, `--plan-only` is `--check`,
  `retman init|doctor|results|log` are `config init`, `doctor check`, `results list`,
  `journal show`, `retman-eval` and `retman-scaffold` no longer exist, and `--json` prints the
  envelope instead of the bare documents. The exit codes are unchanged.
- A new command is one operation, one declaration, its Polish texts and its schema; the CLI,
  the guides and the contract tests follow from the catalog.
- Operations take offline injections (`backend`, `project_dir`, `manifests`, `readers`...)
  that the CLI passes through `cli.main(argv, backend=..., **injections)`; an injection never
  overrides an option.
- English texts for the human-readable output and the machine documents stay open (Next 8).

# PROGRESS: Retman

Current state only (DOC-6.1). Branch, tag and remote state: ask git (`git status`,
`git log --oneline -10`). History: the git log and [CHANGELOG](CHANGELOG.md); the long
session log that used to live here is in git, commit `7b6e353`, `docs/PROGRESS.md`.

## Status

| Component | State | Note |
|---|---|---|
| Design documents (PRD, ARCHITECTURE, USAGE, ADR-001 to ADR-020) | done, Polish | translation to English pending (ECO-005), see Next 1.6; open questions: PRD ch. 11, ARCHITECTURE ch. 12 |
| Core: pipeline, `Plan`, dialog, `Result`, journal, workspace, command collection | done | ARCHITECTURE 2, 5, 6, 7 |
| Registry, command layer, data kinds, `retman-scaffold` | done | ADR-013, ADR-019 |
| Kartograf 0.8.0 adapter (4 operations), IMGWTools 3.0.0 adapter (26 operations, two-stage recognition) | done | the `tools` group pins commits `8e9bcbb` (Kartograf) and `0d98f3b` (IMGWTools) until the tags `v0.8.0` and `v3.0.0` exist |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI: conversation, `init`, `doctor`, `results`, `log` | done | ARCHITECTURE 6.4, 7.1, 7.2; exit codes of the registry since ADR-020 |
| `retman-eval` and the 614-command set | in progress | code done; the last run was on the old 83-command set |
| Nogat standard 2.1, structure and tooling | done | branch `chore/nogat-2.1`: gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, error registry (ERR-3, ERR-4) | done | ADR-020: `schemas/nogat/`, `scripts/generate_errors.py`, `src/retman/_errors.py`, `retman.outcomes`, `retman-error/1` as the last stderr line, exit codes of the registry |
| Nogat standard 2.1, user environment, agent interfaces | planned | see Next 1.1 and 1.2 |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file; open: Next 1.3 to 1.6 |
| Gate | green | `scripts/gate.sh`: 2648 offline tests, coverage 95%, ruff, mypy strict; run it with `TMPDIR` on a local disk (a network share breaks SQLite and links) |
| CI (Linux, macOS, Windows) | written, not run | `.github/workflows/ci.yml` and `live.yml`; nothing is pushed |

Skipped adoption items, which need the author (DEV-3.3, ADOPTION_PLAN):

| Item | Why |
|---|---|
| History rewrite and mailmap (phase 1) | Retman needs only DEV-4.2: the commits are by `Daldek <git@debever.pl>`; a rewrite is the author's step |
| Rulesets for `main`, `develop` and `v*` tags, private vulnerability reporting, Dependabot security updates, default branch (DEV-3.6, DEV-13.6, DEV-13.7) | GitHub settings |
| `docs/CLA.md` | the author's legal text; `CONTRIBUTING.md` and the pull request template already refer to it |
| Tags, releases, replacing the commit pins of the `tools` group by tags, PyPI name `nogat-retman` (phases 5 and 6) | need the producers' tags and the author's approval |
| Push of `chore/nogat-2.1`, pull request, merge into `develop` | approvals (DEV-3.3) |

## Next

1. **Resume the standard 2.1 adoption on `chore/nogat-2.1`** (one commit per step, gate
   green before each; the source of the rules is the Nogat branch `feature/data-output`,
   `git -C ~/workspace/Nogat show feature/data-output:standards/<file>`; Hydrolog's and
   Kartograf's branches `chore/nogat-2.1` are the reference implementations). Order of
   work: 1.1, 1.2, then 1.3 to 1.6. ADR numbers: 0021 user environment (1.1), 0022 agent
   interfaces (1.2), 0023 structure, gate, CI, test tree, mypy deviation, technical log on
   stderr (1.5); ADR-020 is the error registry. New ADRs are English files in
   `docs/decisions/`; the Polish index in `docs/DECISIONS.md` gets a row each.
   1. **User environment** (DEV §18, ECO-028; commit `feat(config)!`). Decided:
      - `retman.toml` becomes the `[retman]` table of `nogat.toml` (`NOGAT_CONFIG`, else
        `platformdirs.user_config_path("nogat")`), keeping its sub-tables
        (`[retman.decision]`, `[retman.decision.thresholds]`, `[retman.text]`,
        `[retman.adapters]`, `[retman.tools.kartograf]`, `[retman.tools.imgwtools]`); shared keys
        `[nogat] lang`, `data_dir`, `cache_dir`; `--config PATH` stays and names the file.
        Precedence: option, `RETMAN_<KEY>` (the dotted key with `_`: `RETMAN_DECISION_URL`,
        `RETMAN_LOG_LEVEL`), `NOGAT_<KEY>` (shared keys only), `[retman]`, `[nogat]`, default.
        Add `platformdirs>=4` to the dependencies (`uv lock` works: PyPI is reachable).
      - N-11 against DEV-18.1: the standard has a default layer and wins; N-11 is read as "no
        hidden default": `config show` lists every value with its source and `retman init` writes
        them all. `[retman.decision]` (model server) has no meaningful default, so `retman plan`
        without it ends with `validation_error`, reason `invalid_config` (`ConfigError`,
        problem `missing_key`), while every other command works without `nogat.toml`.
      - Defaults (DEV-19.2, DEV-18.2): `tools.kartograf.store_dir` is `<data_dir>/kartograf`,
        `tools.imgwtools.store_dir` is `<data_dir>/imgw`, the Kartograf cache is
        `<cache_dir>/kartograf/metadata.db`, the IMGWTools reference directory is
        `<cache_dir>/imgw/reference`, the collection file `<data_dir>/retman/collected.jsonl`.
        The journal and the results stay in the project folder (`retman-output/`, by design,
        ARCHITECTURE 5): list DEV-18.2 as a deviation in `CLAUDE.md` (Next 1.3).
      - `retman init` writes the `[retman]` tables into `nogat.toml` and appends them to an
        existing file without touching other tables; an existing `[retman]` table is
        `conflict`, reason `output_exists` (`ConfigError` problem `already_exists`).
      - `retman config show [--json]`: document `retman-config/1` in the shape of Kartograf's
        `kartograf-config/1` (`git -C ~/workspace/Kartograf show chore/nogat-2.1:src/kartograf/config.py`,
        `docs/decisions/0050-nogat-user-environment.md`): `schema`, `tool`, `version`,
        `config_file` (`path`, `source`, `exists`, `error`, `ignored`), `keys` (dotted key to
        `value`, `source` `default`/`env`/`file`, `name`, `error`), `credentials` (the variable
        named by `decision.api_key_env`: `present` or `missing`), `store` (`root` null: Retman keeps
        none) and, additive within `/1`, `stores` (the roots of the two tools with source and
        size); it works with a file that cannot be used.
      - Files: `src/retman/config.py` (`ConfigFile`, per-key resolution, `ConfigError`),
        `config_template.toml`, `initialize.py`, `doctor.py`, `eval/runner.py`, `cli.py`,
        `.env.example` (every `RETMAN_*` variable), README and USAGE 2, ARCHITECTURE 9, the tests
        (`tests/unit/test_config.py`, `tests/integration/test_initialize.py`,
        `tests/integration/test_doctor.py`, `tests/conftest.py`: `init_config`, `load_config`,
        `default_data_dir` are patched in many tests), the hints of `ConfigError` and
        `UsageError` in `src/retman/exceptions.py` that name `retman init`.
   2. **Agent interfaces** (profile `tool`; the registry lists CLI and Python, no MCP, no REST;
      commit `feat(agents)!`). Decided: AGI-3.1 asks for one executable, so `retman-eval` and
      `retman-scaffold` become groups of `retman` and leave `[project.scripts]` (no aliases).
      Planned catalog `retman-commands/1`: `plan run` (the conversation: `--check` replaces
      `--plan-only`, `--yes` confirms, `--explain`, `--json` never prompts, AGI-3.5),
      `config show`, `config init`, `doctor check`, `results list`, `journal show`,
      `commands list|schema|guide`, `eval run`, `scaffold check|list|draft`; `list_commands`,
      `command_schema`, `validate_command`, `check_command`, `run_command` in `retman.__all__`
      (AGI-2.1, AGI-7.1) with the error classes; envelope `retman-result/1` (AGI-4.2; the
      outcomes `partial` and `failed` of `retman.outcomes` print it, `doctor` and `eval` list
      their units in `items`); `--lang`; generated `AGENTS.md` and `llms.txt` from
      `src/retman/_data/agents/` (AGI §8, DOC §4, DOC §5, `commands guide --format
      agents|llms|agents-md-block`); contract tests (schemas via `tests/contract/nogat_schemas.py`,
      freshness, budgets of DOC-1.7, `__all__` and a consumer snippet checked by mypy; patterns
      in Hydrolog's `tests/contract`); `--help` texts from translation files (AGI-3.7). Consume
      tools through the catalog functions where possible: the only direct `DownloadManager` path is
      the orthophoto handler (`src/retman/tools/kartograf/handlers.py`). Then the hints that name
      `retman init`, `retman-eval` or `retman-scaffold --check` (`src/retman/exceptions.py`,
      `adapters/catalog.py`, `pl.toml`) and `cli._input_required` (name `--yes` and `--check`).
   3. `docs: CLAUDE.md` in English within 200 lines (DOC-3.1): profile `tool` (DEV-1.1),
      critical rules, environment and commands (`scripts/gate.sh`), code map, documentation
      map, session workflow, link to the Retman entry of Nogat `ecosystem.yaml`, and a
      **Deviations** section (DEV-1.2) that keeps the DEV-7.3 line now in the Polish
      `CLAUDE.md` and adds DEV-18.2 (journal and results in the project folder). Then
      `git rm docs/DEVELOPMENT_STANDARDS.md` (DEV-1.3). What is project-specific there must
      move: the checklists of section 17 (new operation, kind, backend, extractor) to a new
      last chapter of `docs/ARCHITECTURE.md`; the rules of sections 6.4 (run the CLI outside
      the repository, results go to `retman-output/`), 10.4 (no `conftest.py` in test
      subfolders, offline tests, the dummy tool), 14 and 16 (privacy, "never" list) to
      `CLAUDE.md`.
   4. `docs: CHANGELOG` in English, heading `## [Unreleased]` (DOC-7.1, REL-1.1), sections
      Added, Changed, Removed, Fixed, ADR references in parentheses. The 0.1.0 entries now mix
      Polish text with the English entry of ADR-020.
   5. `docs: DECISIONS` in English with the statuses of DOC-8.1 (`proposed`, `accepted`,
      `amended by`, `superseded by`); ADR-0023 as above.
   6. **README** in the order of DOC-2.1 within 400 lines (summary paragraph at most 400
      characters, "For AI agents" with the links to `llms.txt` and `AGENTS.md`), then USAGE,
      PRD and ARCHITECTURE in English, then `docs/research/` and `docs/specs/` (about 6,200
      lines: translate, DEV-2.1; DEV-17.4 stops new files there); new plans go to
      `docs/plans/`.
2. **Migrate the calls to the changing producer APIs, after Kartograf and IMGWTools have
   DEV §19 on their development heads** (do not before; ECO-051, data-output plan step 5).
   Call sites, as of 2026-10-24:
   - `src/retman/tools/kartograf/client.py` lines 9, 188, 195, 258, 273: `output_dir=` passed
     to `validate_command`, `run_command`, `check_command` and shown on the command line
     becomes `root=` (`--root`).
   - `src/retman/tools/kartograf/handlers.py` lines 84 and 137: `DownloadManager(output_dir=...)`
     becomes `root=`.
   - `src/retman/tools/imgwtools/client.py` lines 62 to 71: `reference_data_dir` is exported as
     `IMGW_DATA_DIR` and becomes `IMGW_REFERENCE_DIR`; lines 95 to 101 and 161 to 174 pass
     `root` and show `--root`: recheck against the default root `<data_dir>/imgw` and `IMGW_ROOT`
     (was `IMGW_STORE_ROOT`); `src/retman/stores.py` lines 19 to 22 and 154 to 156 (marker
     `imgw-store.json`, `store init`) follow the marker rules of DEV-19.12 and DEV-19.13.
   - Error codes: the Kartograf and IMGWTools codes become registry codes in the tools
     (`no_coverage` to `no_data`, `download_failed` to `source_unavailable`, and so on, ERR §4):
     delete `_TOOL_CODES` in `src/retman/adapters/catalog.py`, and change the `[errors]` texts
     in `src/retman/tools/*/pl.toml` (keyed by `ToolError.tool_code`), the exemptions in
     `src/retman/devtools/readers/*.py`, the tests under `tests/integration/tools/` and
     `tests/contract/test_tool_conformance.py`.
   - `store_dir` of `[tools.kartograf]` and `[tools.imgwtools]` keeps meaning the store root
     (default `<data_dir>/<tool>`, Next 1.1). Then USAGE, ARCHITECTURE, CHANGELOG.
3. Replace the commit pins of the `tools` group in `pyproject.toml` by the tags `v0.8.0` and
   `v3.0.0` once they exist (REL-5.3), run `uv lock` and the gate.
4. Review `src/retman/eval/commands.jsonl` (614 commands, an agent draft), run `retman-eval`
   with Bielik 11B on it (two-stage recognition, `0_5m` against `5m`), then set the confidence
   thresholds.
5. Live tests of IMGWTools (none in the `live` set), a smoke run of the CLI on Windows and
   macOS (hard-link stores), the first CI run after the push.
6. Complete `docs/specs/2026-10-11-retman-eval.md`: geometry placeholder files, the offline
   station catalog, optional parameters never in `expect_clarify`.
7. `retman collect export` and `retman collect draft` (ADR-011) when the author decides.

## Open questions

Decisions awaiting the author:

- Target values: recognition accuracy (PRD W-01), response time (N-07), success measures
  (PRD ch. 8, ch. 11 item 5).
- ADRs for the decisions of the first session, 2026-10-11 (the list is in the git history of
  this file): record them retroactively or not.
- Backend `basal`: waits for the API of basal-serve.
- Chains as author-written recipes instead of the run-time resolver (alternative to
  ARCHITECTURE 4.5, PRD W-12, S-05), and n8n as an environment of Retman, not an executor of
  steps (only where Retman cannot do it); to be judged when a second tool brings real chains
  (ARCHITECTURE 12 item 14; the full proposals are in the git history of this file).

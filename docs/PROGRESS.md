# PROGRESS: Retman

Current state only (DOC-6.1). Branch, tag and remote state: ask git (`git status`,
`git log --oneline -10`). History: the git log and [CHANGELOG](CHANGELOG.md); the long
session log that used to live here is in git, commit `7b6e353`, `docs/PROGRESS.md`.

## Status

| Component | State | Note |
|---|---|---|
| Design documents (PRD, ARCHITECTURE, USAGE, ADR-001 to ADR-019) | done, Polish | translation to English pending (ECO-005); open questions: PRD ch. 11, ARCHITECTURE ch. 12 |
| Core: pipeline, `Plan`, dialog, `Result`, journal, workspace, command collection | done | ARCHITECTURE 2, 5, 6, 7 |
| Registry, command layer, data kinds, `retman-scaffold` | done | ADR-013, ADR-019 |
| Kartograf 0.8.0 adapter (4 operations), IMGWTools 3.0.0 adapter (26 operations, two-stage recognition) | done | the `tools` group pins commits `8e9bcbb` (Kartograf) and `0d98f3b` (IMGWTools) until the tags `v0.8.0` and `v3.0.0` exist |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI: conversation, `init`, `doctor`, `results`, `log` | done | ARCHITECTURE 6.4, 7.1, 7.2 |
| `retman-eval` and the 614-command set | in progress | code done; the last run was on the old 83-command set |
| Nogat standard 2.1, structure and tooling | done | branch `chore/nogat-2.1`, 9 commits: gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file; open: see Next 1 |
| Nogat standard 2.1, error registry, agent interfaces, user environment | planned | see Next 1 |
| Gate | green | `scripts/gate.sh`: 2577 offline tests, coverage 95%, ruff, mypy strict; run with `TMPDIR=$HOME/.cache/retman-tmp` (a network share breaks SQLite and links) |
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
   `git -C ~/workspace/Nogat show feature/data-output:standards/<file>`):
   1. `docs: CLAUDE.md` in English within 200 lines (DOC-3.1): profile `tool` (DEV-1.1),
      critical rules, environment and commands (`scripts/gate.sh`), code map, documentation
      map, session workflow, link to the Retman entry of Nogat `ecosystem.yaml`, and a
      **Deviations** section (DEV-1.2) that keeps the DEV-7.3 line now in the Polish
      `CLAUDE.md` and adds DEV-18.1 if the config keeps N-11 (no hidden defaults). Then
      `git rm docs/DEVELOPMENT_STANDARDS.md` (DEV-1.3). What is project-specific there must
      move: the checklists of section 17 (new operation, kind, backend, extractor) to a new
      last chapter of `docs/ARCHITECTURE.md`; the rules of sections 6.4 (run the CLI outside
      the repository, results go to `retman-output/`), 10.4 (no `conftest.py` in test
      subfolders, offline tests, the dummy tool), 14 and 16 (privacy, "never" list) to
      `CLAUDE.md`.
   2. `docs: CHANGELOG` in English, heading `## [Unreleased]` (DOC-7.1, REL-1.1), sections
      Added, Changed, Removed, Fixed, ADR references in parentheses.
   3. `docs: DECISIONS` in English with the statuses of DOC-8.1; new ADRs as files in
      `docs/decisions/` (DOC-8.2), starting with ADR-020: `src/` layout, gate and CI, test tree,
      the mypy deviation, the technical log on stderr without a file, standard 2.1 decisions.
   4. **Error registry** (ERR-3, ERR-4). Copy `error_registry.json` and `schemas/agent/*`
      into `schemas/nogat/` as Hydrolog did (branch `chore/nogat-2.1` of Hydrolog:
      `schemas/nogat/README.md`, `scripts/generate_errors.py`, `src/hydrolog/_errors.py`);
      give `RetmanError` the fields `code`, `message`, `details`, `hint` (DEV-11.1; classes in
      `src/retman/exceptions.py`); map exits: cancelled 3 to `cancelled` 130, out of scope to
      `unsupported` 15, a wrong option or variable (`UsageError`) to `validation_error` 2, the
      rest by ERR-1 with `details.reason`; the last stderr line is `retman-error/1` (AGI-3.3);
      `retman-eval` (exit 4, W-03) and `retman-scaffold` follow; contract test: module equals
      copy. Update USAGE 8 and ARCHITECTURE 6.4 (exit code tables).
   5. **Agent interfaces** (profile `tool`; the registry lists CLI and Python, no MCP, no
      REST): catalog `retman-commands/1` with `list_commands`, `command_schema`,
      `validate_command`, `check_command`, `run_command` in `retman.__all__` (AGI-2.1,
      AGI-7.1); the envelope `retman-result/1` with `--json`, `--lang`, `--check`, `--yes`
      (AGI-3.2, AGI-3.4, AGI-4.2); `retman commands list|schema|guide`; generated `AGENTS.md`
      and `llms.txt` from `src/retman/_data/agents/` (AGI §8, DOC §4, DOC §5); contract tests
      (schemas, freshness, budgets of DOC-1.7, `__all__` and a consumer snippet checked by
      mypy); `--help` texts from translation files (AGI-3.7). Consume tools through the
      catalog functions where possible: the only direct `DownloadManager` path is the
      orthophoto handler (`src/retman/tools/kartograf/handlers.py`).
   6. **User environment** (DEV §18, ECO-028): `retman.toml` becomes the `[retman]` table of
      `nogat.toml` (`NOGAT_CONFIG`, `platformdirs.user_config_path("nogat")`), shared keys
      `[nogat] lang`, `data_dir`, `cache_dir`, variables `RETMAN_<KEY>` before `NOGAT_<KEY>`
      (`src/retman/config.py`, `config_template.toml`, `initialize.py`, `doctor.py`);
      `retman config show --json` with each key, value and source and the credential names
      present or missing (DEV-18.6); extend `.env.example`; add `platformdirs` to the
      dependencies. `retman init` appends the table without touching other tables.
   7. **README** in the order of DOC-2.1 within 400 lines (summary paragraph at most 400
      characters, "For AI agents" with the links to `llms.txt` and `AGENTS.md`), then USAGE,
      PRD and ARCHITECTURE in English, then `docs/research/` and `docs/specs/` (translate or
      archive; DEV-17.4 stops new files there); new plans go to `docs/plans/`.
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
   - Error codes: the Kartograf and IMGWTools codes change to the registry codes
     (`no_coverage` to `no_data`, `download_failed` to `source_unavailable`, and so on, ERR §4):
     the `[errors]` texts in `src/retman/tools/*/pl.toml`, the exemptions in
     `src/retman/devtools/readers/*.py`, the tests under `tests/integration/tools/` and
     `tests/contract/test_tool_conformance.py`.
   - `store_dir` of `[tools.kartograf]` and `[tools.imgwtools]` keeps meaning the store root;
     whether it stays required (DEV-19.2 gives each tool a default root) is decided in Retman
     (see Open questions). Then USAGE, ARCHITECTURE, CHANGELOG.
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
- The prefix "Błąd:" and exit code 1 for a command outside the scope in the CLI (an earlier
  decision of the author); with the registry the code becomes `unsupported` (15).
- Backend `basal`: waits for the API of basal-serve.
- Chains as author-written recipes instead of the run-time resolver (alternative to
  ARCHITECTURE 4.5, PRD W-12, S-05), and n8n as an environment of Retman, not an executor of
  steps (only where Retman cannot do it); to be judged when a second tool brings real chains
  (ARCHITECTURE 12 item 14; the full proposals are in the git history of this file).

Questions raised by the adoption of standard 2.1:

- A plan that needs answers or a confirmation while stdin is not a terminal ends with exit 2
  today; exit 2 is `validation_error` in the registry. Proposal: `validation_error` with
  `details.reason` `input_required` (ERR-1, no new code).
- `retman-eval` and `retman-scaffold` are separate executables; AGI-3.1 asks for one
  executable per project. Proposal: `retman eval` and `retman scaffold` groups, the old names
  removed.
- N-11 (no hidden defaults: every value is in the config file) against DEV-18.1 (every tool
  works without `nogat.toml`). Proposal: a deviation line in `CLAUDE.md` for the model backend
  and the tool stores, which have no meaningful default.
- Whether `store_dir` gets a default under `<data_dir>` (DEV-19.2) or stays required.
- Research notes and specs (about 6,200 lines of Polish text in `docs/research/` and
  `docs/specs/`): translate them or leave them in the git history only.

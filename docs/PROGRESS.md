# PROGRESS: Retman

Current state only (DOC-6.1). Branch, tag and remote state: ask git (`git status`,
`git log --oneline -10`). History: the git log and [CHANGELOG](CHANGELOG.md); the long
session log that used to live here is in git, commit `7b6e353`, `docs/PROGRESS.md`.

## Status

| Component | State | Note |
|---|---|---|
| Design documents (PRD, ARCHITECTURE, USAGE, ADR-001 to ADR-023) | done; the decision log, the ADRs, PRD and USAGE are English, ARCHITECTURE is Polish | translation of ARCHITECTURE chapters 1 to 12 to English pending (ECO-005), see Next 1.5; open questions: PRD ch. 11, ARCHITECTURE ch. 12 |
| Core: pipeline, `Plan`, dialog, `Result`, journal, workspace, command collection | done | ARCHITECTURE 2, 5, 6, 7 |
| Registry, command layer, data kinds, `retman scaffold` | done | ADR-013, ADR-019 |
| Kartograf 0.8.0 adapter (4 operations), IMGWTools 3.0.0 adapter (26 operations, two-stage recognition) | done | the `tools` group pins commits `8e9bcbb` (Kartograf) and `0d98f3b` (IMGWTools) until the tags `v0.8.0` and `v3.0.0` exist |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI and command catalog: `plan run`, `config show\|init`, `doctor check`, `results list`, `journal show`, `commands list\|schema\|guide` | done | ADR-022; ARCHITECTURE 6.4, 7.1, 7.2, 9.1; exit codes of the registry since ADR-020 |
| `retman eval run` and the 614-command set | in progress | code done; the last run was on the old 83-command set |
| Nogat standard 2.1, structure and tooling | done | branch `chore/nogat-2.1`: gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, error registry (ERR-3, ERR-4) | done | ADR-020: `schemas/nogat/`, `scripts/generate_errors.py`, `src/retman/_errors.py`, `retman.outcomes`, `retman-error/1` as the last stderr line, exit codes of the registry |
| Nogat standard 2.1, user environment (DEV-18) | done | ADR-021: `[retman]` tables of `nogat.toml`, `RETMAN_*` and `NOGAT_*` variables, user directories, `retman config show` (`retman-config/1`), `platformdirs` |
| Nogat standard 2.1, agent interfaces | done | ADR-022: catalog, `retman.operations`, the CLI generated from the catalog, `retman-result/1`, schemas in `src/retman/schemas/`, generated `AGENTS.md` and `llms.txt`; the English texts of the machine documents are Next 8 |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file, `CLAUDE.md` in English with its Deviations section, `docs/DEVELOPMENT_STANDARDS.md` removed (checklists are ARCHITECTURE 13), the CHANGELOG and the decision log in English with the statuses of DOC-8.1, ADR-023, the README in English with its examples run by `tests/contract/test_readme_examples.py` (DOC-2.1, DOC-2.6), USAGE and PRD in English; open: Next 1.5 (ARCHITECTURE) |
| Gate | green | `scripts/gate.sh`: 2713 offline tests, coverage 95%, ruff, mypy strict; run it with `TMPDIR` on a local disk (a network share breaks SQLite and links) |
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
   Kartograf's branches `chore/nogat-2.1` are the reference implementations). Open: 1.5 (done:
   1.1, the agent interfaces, ADR-022; 1.2, `CLAUDE.md` in English and the removal of
   `docs/DEVELOPMENT_STANDARDS.md`; 1.3, the CHANGELOG in English; 1.4, the decision log in
   English with ADR-023). ADR-020 is the error registry, ADR-021 the user environment, ADR-022
   the agent interfaces and ADR-023 the structure, gate, CI, test tree and technical log. New
   ADRs are English files in `docs/decisions/`; the index in `docs/DECISIONS.md` gets a row each.
   5. **ARCHITECTURE in English**, with the new command names and the new module tree (README,
      USAGE and PRD are done: DOC-2.1, the table of every variable stays, DEV-18.3, and the README
      examples run in `tests/contract/test_readme_examples.py`); then `docs/research/` and
      `docs/specs/` (about 6,200 lines: translate, DEV-2.1; DEV-17.4 stops new files there); new
      plans go to `docs/plans/`.
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
     (was `IMGW_STORE_ROOT`); `src/retman/stores.py` lines 19 to 22 and 183 to 185 (marker
     `imgw-store.json`, `store init`) follow the marker rules of DEV-19.12 and DEV-19.13.
   - Error codes: the Kartograf and IMGWTools codes become registry codes in the tools
     (`no_coverage` to `no_data`, `download_failed` to `source_unavailable`, and so on, ERR §4):
     delete `_TOOL_CODES` in `src/retman/adapters/catalog.py`, and change the `[errors]` texts
     in `src/retman/tools/*/pl.toml` (keyed by `ToolError.tool_code`), the exemptions in
     `src/retman/devtools/readers/*.py`, the tests under `tests/integration/tools/` and
     `tests/contract/test_tool_conformance.py`.
   - `store_dir` of `[retman.tools.kartograf]` and `[retman.tools.imgwtools]` keeps meaning the
     store root (default `<data_dir>/kartograf` and `<data_dir>/imgw`, ADR-021). Then USAGE, ARCHITECTURE, CHANGELOG.
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
8. English texts for the human-readable output and for the texts inside the `--json` documents of
   `doctor check`, `scaffold check` and `eval run` (AGI-9.2; `lang = en` is accepted and shows Polish
   today): an `en.toml` for the core `pl.toml` (about 650 lines) and for the tools in
   `src/retman/tools/*/`; `text_language` and `machine_texts` in `retman.i18n.loader` switch when it
   exists. Then replace the old command names (`retman init`, `retman doctor`, `retman-eval`,
   `retman-scaffold`, `--plan-only`) that ARCHITECTURE, PRD and the specs still use (item 1.5).

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

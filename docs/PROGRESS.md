# PROGRESS: Retman

Current state only (DOC-6.1). Branch, tag and remote state: ask git (`git status`,
`git log --oneline -10`). History: the git log and [CHANGELOG](CHANGELOG.md); the long
session log that used to live here is in git, commit `7b6e353`, `docs/PROGRESS.md`.

## Status

| Component | State | Note |
|---|---|---|
| Design documents (PRD, ARCHITECTURE, USAGE, ADR-001 to ADR-023) | done, English | open questions: PRD ch. 11, ARCHITECTURE ch. 12; `docs/research/` and `docs/specs/` are still Polish, see Next 1.5 |
| Core: pipeline, `Plan`, dialog, `Result`, journal, workspace, command collection | done | ARCHITECTURE 2, 5, 6, 7 |
| Registry, command layer, data kinds, `retman scaffold` | done | ADR-013, ADR-019 |
| Kartograf 0.8.0 adapter (4 operations), IMGWTools 3.0.0 adapter (26 operations, two-stage recognition) | done | the `tools` group pins commits `8e9bcbb` (Kartograf) and `0d98f3b` (IMGWTools) until the tags `v0.8.0` and `v3.0.0` exist; the move of the IMGWTools pin to the head of its `feature/data-output` is started on the branch `feature/imgwtools-data-output` (Next 2) |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI and command catalog: `plan run`, `config show\|init`, `doctor check`, `results list`, `journal show`, `commands list\|schema\|guide` | done | ADR-022; ARCHITECTURE 6.4, 7.1, 7.2, 9.1; exit codes of the registry since ADR-020 |
| `retman eval run` and the 614-command set | in progress | code done; the last run was on the old 83-command set |
| Nogat standard 2.1, structure and tooling | done | branch `chore/nogat-2.1`: gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, error registry (ERR-3, ERR-4) | done | ADR-020: `schemas/nogat/`, `scripts/generate_errors.py`, `src/retman/_errors.py`, `retman.outcomes`, `retman-error/1` as the last stderr line, exit codes of the registry |
| Nogat standard 2.1, user environment (DEV-18) | done | ADR-021: `[retman]` tables of `nogat.toml`, `RETMAN_*` and `NOGAT_*` variables, user directories, `retman config show` (`retman-config/1`), `platformdirs` |
| Nogat standard 2.1, agent interfaces | done | ADR-022: catalog, `retman.operations`, the CLI generated from the catalog, `retman-result/1`, schemas in `src/retman/schemas/`, generated `AGENTS.md` and `llms.txt`; the texts inside the machine documents are English (erratum 1) |
| Nogat standard 2.1, English texts (DEV-2.2, AGI-9.2) | done | `en.toml` for the core and both adapters, `lang = en` and `--lang en`, the answer words in `[answers]`, English texts in the `--json` documents of `doctor check` and `scaffold check` (ADR-022 erratum 1) |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file, `CLAUDE.md` in English with its Deviations section, `docs/DEVELOPMENT_STANDARDS.md` removed (checklists are ARCHITECTURE 13), the CHANGELOG, the decision log, README, USAGE, PRD and ARCHITECTURE in English (the README examples run by `tests/contract/test_readme_examples.py`, DOC-2.1, DOC-2.6); open: Next 1.5 (`docs/research/`, `docs/specs/`) |
| Gate | green | `scripts/gate.sh`: 3039 offline tests, coverage 95%, ruff, mypy strict; run it with `TMPDIR` on a local disk (a network share breaks SQLite and links) |
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
   5. **`docs/research/` and `docs/specs/` in English** (about 6,200 lines: translate, DEV-2.1;
      DEV-17.4 stops new files there; the command names of the eval spec are already current, its
      `retman.toml` mention is not); new plans go to `docs/plans/`. README, USAGE, PRD and
      ARCHITECTURE are English; PRD N-09 follows the Nogat plan (`nogat-retman` on PyPI in
      phase 6, with the author's approval).
2. **Migrate the calls to the changing producer APIs** (ECO-051, data-output plan step 5).
   - **IMGWTools: not done; start from the branch `feature/imgwtools-data-output`** (from
     `chore/nogat-2.1` at `f6ac4d1`, no migration commit yet). Target: the head
     `c16422dd67199981072a3d124e5bf00828868ff6` of IMGWTools `feature/data-output` (its CHANGELOG
     "Migration guide: data output", its PROGRESS item 3). Steps already tried:
     1. Pin: change the `imgwtools[store]` commit of the `tools` group, `uv lock`,
        `uv sync --locked --all-extras`. GitHub has no such commit until that branch is pushed, so
        put it into the uv git cache of the IMGWTools URL first (`git fetch` of
        `~/workspace/IMGWTools` `feature/data-output` into the database below
        `~/.cache/uv/git-v1/db/`; done on this machine).
     2. Defect of that commit: `import imgwtools` needs `pydantic_settings`, which IMGWTools lists
        only in its `api` and `cli` extras. Workaround: `pydantic-settings>=2.7` in the `tools`
        group, in a separate last commit; drop it and re-pin when IMGWTools moves it to its
        dependencies (reported to the coordinator, who sends the fixed hash).
     3. First run of the suite on that pin: 23 of 3,051 tests fail: `path` is `output` for
        `series export` and `store export` (8 tests and the client); `datasets download` has the
        `DownloadReport` fields `mode`, `output_dir`, `root`, `items`, `files`, `cancelled` and
        refuses a dataset outside the store without `output_dir` (the conformance check X3, the
        dataset test); no `[errors.forbidden]` text (X8); `created` and `reused` are `new` and
        `unchanged`; English tool texts (`poza zakresem`, an empty range is `validation_error`);
        the catalog has 38 commands (`commands list`).
     4. Code to change (file and line as of `f6ac4d1`): `tools/imgwtools/client.py` 62 to 71
        (`IMGW_DATA_DIR` is `IMGW_REFERENCE_DIR`), 91 to 101 (no `root` beside `output_dir`, they
        exclude each other), 235 to 240 and 272 (`output`; the export result is `{output,
        files[]}`, not a path), the `files` of a download from `files[]` (`path`, `size_bytes`,
        `sha256`, `status`); `calls.py` 226 to 228 and `calls_archives.py` 271 to 272 (`path` is
        `output`; no `force`, every run has its own result folder); `calls_archives.py` 88 to 99
        (`output` is `output_dir`; while planning there is no folder, so decide on a stand-in such
        as the project folder); `describe.py` 717 and `describe_archives.py` 104 to 125 (`new`,
        `unchanged`); `plans.py` 17 and `check.py` 23 (`nieopublikowany` is `not published`: one
        constant, and the test that the comment promises against `imgwtools.fetch.UNPUBLISHED`;
        plan item errors in the fixtures are English); `[errors.forbidden]` in the adapter's
        `pl.toml` and `en.toml`; `stores.py` (marker fields `tool`, `created_at`,
        `producer_version`; a root with `archives/`, `series/`, `stations/` or `pmaxtp/` and no
        marker is `store_unavailable`, `no_marker`, and `store init` fixes it: a new
        `imgw_store_state` state and doctor text; fixtures that write the old marker). Retman sets
        no `IMGW_STORE_ROOT`, passes `root` from `store_dir` and keeps that setting.
        Then README, USAGE, ARCHITECTURE 3.2.11, CHANGELOG. An idea, not decided: the English
        `detail` of a tool error reaches Polish sentences as `{detail}`;
        `Message.localized("pl")` of IMGWTools can write it in Polish.
   - **Kartograf: waits for its `feature/data-output`.** Call sites, in
     `src/retman/tools/kartograf/client.py`: lines 9, 188, 195, 258, 273 (`output_dir=` to
     `validate_command`, `run_command`, `check_command` and on the command line becomes `root=`,
     `--root`) and, in `handlers.py`, lines
     84 and 137 (`DownloadManager(output_dir=...)` becomes `root=`). Error codes: the Kartograf
     rows of `_TOOL_CODES` in `src/retman/adapters/catalog.py` (`no_coverage` to `no_data`,
     `download_failed` to `source_unavailable`, and so on, ERR §4) go, and so do the
     `[errors]` texts keyed by them in `src/retman/tools/kartograf/pl.toml` and `en.toml` (from
     line 243), the exemptions in `src/retman/devtools/readers/kartograf.py`, and the tests under
     `tests/integration/tools/kartograf/` and `tests/contract/test_tool_conformance.py`.
     `store_dir` of `[retman.tools.kartograf]` keeps meaning the store root (default
     `<data_dir>/kartograf`, ADR-021). Then USAGE, ARCHITECTURE, CHANGELOG.
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

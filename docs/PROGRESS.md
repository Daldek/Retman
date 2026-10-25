# PROGRESS: Retman

Current state only (DOC-6.1). Branch, tag and remote state: ask git (`git status`,
`git log --oneline -10`). History: the git log and [CHANGELOG](CHANGELOG.md); the long
session log that used to live here is in git, commit `7b6e353`, `docs/PROGRESS.md`.

## Status

| Component | State | Note |
|---|---|---|
| Design documents (PRD, ARCHITECTURE, USAGE, ADR-001 to ADR-025) | done, English | open questions: PRD ch. 11, ARCHITECTURE ch. 12; `docs/research/` and `docs/specs/` are still Polish, see Next 1.5 |
| Core: pipeline, `Plan`, dialog, `Result`, journal, workspace, command collection | done | ARCHITECTURE 2, 5, 6, 7 |
| Registry, command layer, data kinds, `retman scaffold` | done | ADR-013, ADR-019 |
| Kartograf 0.8.0 adapter (5 operations), IMGWTools 3.0.0 adapter (26 operations, two-stage recognition) | done | the `tools` group pins `8a36e977` (Kartograf) and `7b11755` (IMGWTools): the heads of their `feature/data-output`, **not pushed**, so the author pushes both first (Next 2) until the tags `v0.8.0` and `v3.0.0` exist; the supported ranges start at the `.dev0` of the release meanwhile (REL-5.6) and are narrowed with the tags |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI and command catalog: `plan run`, `config show\|init`, `doctor check`, `results list`, `journal show`, `commands list\|schema\|guide` | done | ADR-022; ARCHITECTURE 6.4, 7.1, 7.2, 9.1; exit codes of the registry since ADR-020 |
| `retman eval run` and the 630-command set | in progress | code done; the last run was on the old 83-command set |
| Nogat standard 2.1, structure and tooling | done | branch `chore/nogat-2.1`: gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, error registry (ERR-3, ERR-4) | done | ADR-020: `schemas/nogat/`, `scripts/generate_errors.py`, `src/retman/_errors.py`, `retman.outcomes`, `retman-error/1` as the last stderr line, exit codes of the registry |
| Nogat standard 2.1, user environment (DEV-18) | done | ADR-021: `[retman]` tables of `nogat.toml`, `RETMAN_*` and `NOGAT_*` variables, user directories, `retman config show` (`retman-config/1`), `platformdirs` |
| Nogat standard 2.1, agent interfaces | done | ADR-022: catalog, `retman.operations`, the CLI generated from the catalog, `retman-result/1`, schemas in `src/retman/schemas/`, generated `AGENTS.md` and `llms.txt`; the texts inside the machine documents are English (erratum 1) |
| Nogat standard 2.1, English texts (DEV-2.2, AGI-9.2) | done | `en.toml` for the core and both adapters, `lang = en` and `--lang en`, the answer words in `[answers]`, English texts in the `--json` documents of `doctor check` and `scaffold check` (ADR-022 erratum 1) |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file, `CLAUDE.md` in English with its Deviations section, `docs/DEVELOPMENT_STANDARDS.md` removed (checklists are ARCHITECTURE 13), the CHANGELOG, the decision log, README, USAGE, PRD and ARCHITECTURE in English (the README examples run by `tests/contract/test_readme_examples.py`, DOC-2.1, DOC-2.6); open: Next 1.5 (`docs/research/`, `docs/specs/`) |
| Gate | green | `scripts/gate.sh`: the offline tests, coverage 95%, ruff, mypy strict; run it with `TMPDIR` on a local disk (a network share breaks SQLite and links) |
| CI (Linux, macOS, Windows) | written, not run | `.github/workflows/ci.yml` and `live.yml`; nothing is pushed |

Skipped adoption items, which need the author (DEV-3.3, ADOPTION_PLAN):

| Item | Why |
|---|---|
| History rewrite and mailmap (phase 1) | Retman needs only DEV-4.2: the commits are by `Daldek <git@debever.pl>`; a rewrite is the author's step |
| Rulesets for `main`, `develop` and `v*` tags, private vulnerability reporting, Dependabot security updates, default branch (DEV-3.6, DEV-13.6, DEV-13.7) | GitHub settings |
| `docs/CLA.md` | the author's legal text; `CONTRIBUTING.md` and the pull request template already refer to it |
| Tags, releases, replacing the commit pins of the `tools` group by tags, PyPI name `nogat-retman` (phases 5 and 6) | need the producers' tags and the author's approval |
| Push of IMGWTools `feature/data-output` (the commit `7b11755` that the `tools` group pins) and of Kartograf `feature/data-output` (`8a36e977`) | a push is the author's step (DEV-3.3); until then a pushed Retman has no green CI |
| Push of `chore/nogat-2.1`, `feature/imgwtools-data-output` and `feature/kartograf-data-output`, pull request, merge into `develop` | approvals (DEV-3.3) |

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
   - **IMGWTools: done on the branch `feature/imgwtools-data-output` (the calls, the marker
     states, the documents, ADR-024); the push of the pin is the open point.** The `tools` group
     pins `7b117550103a3d8d46afc97043b90f0e93314c8b`, the head of IMGWTools `feature/data-output`
     (`pydantic-settings` is a core dependency there, so no workaround is needed). **That commit
     is not pushed**: GitHub has no such commit, so `uv lock` and `uv sync` resolve the pin only
     on a machine whose uv git cache holds it (a `git fetch` of `~/workspace/IMGWTools`
     `feature/data-output` into the database of the IMGWTools URL below `~/.cache/uv/git-v1/db/`;
     done on this machine). The author pushes IMGWTools first; until then Retman cannot be pushed
     with a green CI. Retman sets no `IMGW_STORE_ROOT` or `IMGW_ROOT` and uses no `imgw_*`
     operation id of the MCP and REST surfaces: it calls the command layer by command name and
     passes `root` from `store_dir`. The texts of the tool stay English inside Polish messages
     (decided, ADR-024, USAGE 13). Not part of the migration: the fixture store of the IMGW tests
     (`imgw_support.fixture_store`) leaves a `retman-imgw-test-*` folder in `TMPDIR` per run, and
     `docs/research/` still names the old variables, which is history.
   - **Kartograf: done on the branch `feature/kartograf-data-output` (the calls, the marker
     states, the operation that writes the marker, the documents, ADR-025); the push of the pin
     and one Kartograf fix are the open points.** The `tools` group pins
     `8a36e977d607192b11c66f44f318f2e7676b60d1`, the head of Kartograf `feature/data-output`,
     **not pushed** (fetched into the database of the Kartograf URL below
     `~/.cache/uv/git-v1/db/` as `local-feature-data-output`, the way the IMGWTools pin is; the
     author pushes Kartograf first). Done: `root=` and `--root` (client and
     `DownloadManager(provider, root=...)`), the `kartograf-result/1` envelope and its `files[]`,
     the command ids `sheet parse`, `sheet find` and `store sidecar`, the reader of `retman
     scaffold` on `list_commands` and `command_schema`, the registry codes (the Kartograf rows of
     `_TOOL_CODES` are gone; `ToolFailure.reason`) and the `[errors]` texts keyed by them, tests
     on the real Kartograf in process and offline (`tests/integration/tools/kartograf/
     kartograf_offline.py`), mypy against its types, and the marker states of the store folder
     (`retman.stores.kartograf_store_state`, `doctor check`, one blocking problem in the plan of
     every operation that writes; the rules are those of `kartograf.marker`, held against the
     tool by `tests/unit/test_stores.py`). Retman writes only to the store (`root`) and offers no
     plain mode of Kartograf (ADR-025). **A Kartograf bug is waited for:** a run reports a
     refused store (no marker, other files, a store in a store) as the failure of every sheet,
     `source_unavailable`, instead of one command error with its registry code and reason before
     any work (DEV-17.5: to be fixed in Kartograf). The test
     `test_a_run_into_a_store_kartograf_refuses_is_an_error_with_its_registry_code`
     (`test_kartograf_client.py`) is written against the fixed behaviour and is
     `xfail(strict=True)`: when the pin has the fix it fails as unexpectedly passing, and the
     marker is dropped. **Kartograf will make `store init` reachable through `run_command`
     (AGI-2.1, in progress, not in the pinned commit).** Until then the operation
     `init_kartograf_store` ("Utwórz magazyn Kartografa") is a handler that calls
     `kartograf.init_store`, because the command layer takes the data commands only; when the pin
     has it, the handler-only path moves to the generic call path (a `calls` builder for `store
     init`, the shared executor, preview and audit like the other operations) and
     `handlers.init_kartograf_store` is removed. The 16 eval rows of that operation are written,
     but `retman eval run` has not run on them (it needs a model server), and the ambiguous rows
     `imgw-init-store-014` and `-015` now expect IMGW after a question about the operation.
     Kartograf `feature/data-output` has moved on since the pin (`e8772cf2`, the command catalog
     moved into the message catalog, sits above `8a36e977`); the pin was not moved.
3. Replace the commit pins of the `tools` group in `pyproject.toml` by the tags `v0.8.0` and
   `v3.0.0` once they exist (REL-5.3), and in the same change narrow the `supported_versions` of
   both manifests to `>=0.8.0,<0.9` and `>=3.0.0,<4` (REL-5.6; the test of the IMGWTools manifest
   pins the string), run `uv lock` and the gate.
4. Review `src/retman/eval/commands.jsonl` (630 commands, an agent draft), run `retman-eval`
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

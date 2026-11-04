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
| Kartograf 0.8.0 adapter (10 operations: spatial data of GUGiK and Copernicus, SoilGrids soils, the creation and the overview of the store), Obserwator 3.0.0 adapter (formerly IMGWTools; 19 operations, two-stage recognition) | done | the `tools` group pins `9deaa314` (Kartograf, the head of its `develop`, with `eab8612d` and the marker `obserwator-store.json`) and `651d4d73` (Obserwator, the head of its `feature/obserwator`), both on GitHub, until the tags `v0.8.0` and `v3.0.0` exist (Next 3); the names of the tool in Retman follow Nogat ECO-057 (CHANGELOG, ADR-024 erratum 7); the supported ranges start at the `.dev0` of the release meanwhile (REL-5.6) and are narrowed with the tags; not yet offered by an operation: `imagery download` sheets of a rectangle or a geometry file (orthophoto, true orthophoto, LIDAR intensity, oblique orthophoto; CZ SM5 sheets), the BDOO class selection (`--layers`) and a voivodeship code as its area, and the Czech land cover (ZABAGED, Data50, Data250: an S-JTSK rectangle or the national file, which the area reader does not give) |
| Extractors | in progress | missing: numbers with units; the rest of ARCHITECTURE 4.3 is done |
| Backends | in progress | `openai_compatible` and `FakeDecisionBackend` done (checked with Bielik 11B in LM Studio); `basal` blocked: no basal-serve API specification |
| CLI and command catalog: `plan run`, `config show\|init`, `doctor check`, `results list`, `journal show`, `commands list\|schema\|guide` | done | ADR-022; ARCHITECTURE 6.4, 7.1, 7.2, 9.1; exit codes of the registry since ADR-020 |
| `retman eval run` and the 587-command set | in progress | code done; the last run was on the old 83-command set; the rows `kartograf-soil-*`, `kartograf-hsg-*`, `kartograf-inspect-store-*`, `kartograf-orto-cutout-*` and `kartograf-landcover-*` are unmeasured |
| Nogat standard 2.1, structure and tooling | done | on `develop` (merged from `chore/nogat-2.1`): gate, CI, `src/` layout, test tree, ruff and mypy rule sets, logging, discovery metadata, contribution files, editor files |
| Nogat standard 2.1, error registry (ERR-3, ERR-4) | done | ADR-020: `schemas/nogat/`, `scripts/generate_errors.py`, `src/retman/_errors.py`, `retman.outcomes`, `retman-error/1` as the last stderr line, exit codes of the registry |
| Nogat standard 2.1, user environment (DEV-18) | done | ADR-021: `[retman]` tables of `nogat.toml`, `RETMAN_*` and `NOGAT_*` variables, user directories, `retman config show` (`retman-config/1`), `platformdirs` |
| Nogat standard 2.1, agent interfaces | done | ADR-022: catalog, `retman.operations`, the CLI generated from the catalog, `retman-result/1`, schemas in `src/retman/schemas/`, generated `AGENTS.md` and `llms.txt`; the texts inside the machine documents are English (erratum 1) |
| Nogat standard 2.1, English texts (DEV-2.2, AGI-9.2) | done | `en.toml` for the core and both adapters, `lang = en` and `--lang en`, the answer words in `[answers]`, English texts in the `--json` documents of `doctor check` and `scaffold check` (ADR-022 erratum 1) |
| Nogat standard 2.1, documentation | in progress | done: SECURITY, CONTRIBUTING, CONTRIBUTORS, PR template, this file, `CLAUDE.md` in English with its Deviations section, `docs/DEVELOPMENT_STANDARDS.md` removed (checklists are ARCHITECTURE 13), the CHANGELOG, the decision log, README, USAGE, PRD and ARCHITECTURE in English (the README examples run by `tests/contract/test_readme_examples.py`, DOC-2.1, DOC-2.6); open: Next 1.5 (`docs/research/`, `docs/specs/`) |
| Gate | green | `scripts/gate.sh`: the offline tests, coverage 95%, ruff, mypy strict; run it with `TMPDIR` on a local disk (a network share breaks SQLite and links) |
| CI (Linux, macOS, Windows) | written, not run | `.github/workflows/ci.yml` and `live.yml`; no run observed yet |

Skipped adoption items, which need the author (DEV-3.3, ADOPTION_PLAN):

| Item | Why |
|---|---|
| History rewrite and mailmap (phase 1) | Retman needs only DEV-4.2: the commits are by `Daldek <git@debever.pl>`; a rewrite is the author's step |
| Rulesets for `main`, `develop` and `v*` tags, private vulnerability reporting, Dependabot security updates, default branch (DEV-3.6, DEV-13.6, DEV-13.7) | GitHub settings |
| `docs/CLA.md` | the author's legal text; `CONTRIBUTING.md` and the pull request template already refer to it |
| Tags, releases, replacing the commit pins of the `tools` group by tags, PyPI name `nogat-retman` (phases 5 and 6) | need the producers' tags and the author's approval |
| Pull requests | none: on 2026-11-03 the author merged `feature/archiwista-projects` (`63685c5`, which carried `chore/nogat-2.1`, `feature/imgwtools-data-output` and `feature/kartograf-data-output`) into `develop` locally with `--no-ff`; the four branches are deleted, `main` and `develop` remain |

## Next

1. **Resume the standard 2.1 adoption on a new branch from `develop`** (one commit per step, gate
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
   - **Obserwator (formerly IMGWTools): done (the calls, the marker states, the documents,
     ADR-024); projects are gone (Nogat ECO-054, plan `2026-10-31-archiwista-projects` step 4);
     the tool is renamed (Nogat ECO-057, plan `2026-11-03-imgwtools-to-obserwator` step 3).**
     The `tools` group pins `ea158dc6f703a5ababd91ff54e7ddec35b4f389b` and Kartograf `9deaa314…`,
     the commits of Nogat's release set `candidate-1` (`ecosystem.py set apply`; repository `Daldek/IMGWTools` until its rename),
     so `uv lock` and `uv sync` resolve it normally. The tool keeps no projects, so the category
     `imgw_projects` and its seven operations are removed; projects belong to Archiwista. Retman
     sets no `OBSERWATOR_ROOT` and uses no `obserwator_*` tool of the MCP and REST surfaces: it
     calls the command layer by command name and passes `root` from `store_dir`.
     The texts of the tool stay English inside Polish messages (decided, ADR-024, USAGE 13). The
     refusals of that head are read (ADR-024 erratum 3): the availability checks report a root
     that the tool turns away (`not_empty`, `nested_store`) as `store_refused`, the plans name a
     marker that cannot be read (`data_error`, `invalid_marker`), and `tests/unit/test_stores.py`
     holds `obserwator_store_state` against the check of the tool. Not part of the migration:
     `docs/research/` still names the old variables, the project operations and IMGWTools, which
     is history. The fixture store of the Obserwator tests is removed when the test session ends.
   - **Kartograf: done (the calls, the marker states, the operation that writes the marker, the
     documents, ADR-025); projects are gone (Nogat ECO-054, plan
     `2026-10-31-archiwista-projects` step 4).** The `tools` group pins
     `9deaa314c88f89ea2d9308481e0c0b04751fc792`, the head of Kartograf `develop`, which is on
     GitHub; it carries `feature/archiwista-projects` up to `eab8612d` and the marker
     `obserwator-store.json` of Nogat ECO-057 (ADR-025 erratum 6). Retman's Kartograf operations used no
     project command; with projects the task name extractor and the path of an option inside
     another option went too (ADR-025 erratum 5, ADR-017 erratum 2). Done: `root=` and `--root` (client and `DownloadManager(provider,
     root=...)`), the `kartograf-result/1` envelope and its `files[]`, the command ids `sheet
     parse`, `sheet find` and `store sidecar`, the reader of `retman scaffold` on
     `list_commands` and `command_schema`, the registry codes (`ToolFailure.reason`) and the
     `[errors]` texts keyed by them, tests on the real Kartograf in process and offline
     (`tests/integration/tools/kartograf/kartograf_offline.py`), mypy against its types, and the
     marker states of the store folder (`retman.stores.kartograf_store_state`, `doctor check`,
     one blocking problem in the plan of every operation that writes; the rules are those of
     `kartograf.marker`, held against the tool by `tests/unit/test_stores.py`). Retman writes
     only to the store (`root`) and offers no plain mode of Kartograf (ADR-025). The refused
     store is one command error with its registry code before any request (the xfail of
     `test_a_run_into_a_store_kartograf_refuses_is_an_error_with_its_registry_code` is gone),
     and `store init` is a catalog call of the shared executor: `handlers.init_kartograf_store`
     is removed (ADR-025 erratum 1). The 16 eval rows of that operation are written, but
     `retman eval run` has not run on them (it needs a model server), and the ambiguous rows
     `obserwator-init-store-014` and `-015` now expect the Obserwator store after a question
     about the operation.
3. Replace the commit pins of the `tools` group in `pyproject.toml` by the tags `v0.8.0` and
   `v3.0.0` once they exist (REL-5.3), and in the same change narrow the `supported_versions` of
   both manifests to `>=0.8.0,<0.9` and `>=3.0.0,<4` (REL-5.6; the test of the Obserwator
   manifest pins the string), run `uv lock` and the gate. When the author renames the repository
   `IMGWTools`, its URL follows in the pin, the manifest `source` and the install commands.
4. Review `src/retman/eval/commands.jsonl` (502 commands, an agent draft), run `retman-eval`
   with Bielik 11B on it (two-stage recognition, `0_5m` against `5m`; the keys the model reads
   for Obserwator are `obserwator_*` since ECO-057, and the store descriptions name both
   „magazyn Obserwatora” and „magazyn IMGW”), then set the confidence thresholds.
5. Live tests of Obserwator (none in the `live` set), a smoke run of the CLI on Windows and
   macOS (hard-link stores), the first CI run.
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

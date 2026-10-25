# Retman: instructions for agents developing the project

Retman turns a task written in Polish into a checked plan for the tools of the Nogat ecosystem
(Kartograf and IMGWTools today; Hydrolog and Hydrograf are planned): it recognises the
operation, asks for what is missing, shows the plan and, once confirmed, calls the public
Python API of the tool. It is a CLI (`retman`) and a Python library; the language model is a
separate service (basal-serve or any OpenAI-compatible server). Profile `tool` (DEV-1.1).
User documentation: [README.md](README.md). Nogat standard 2.1:
[DEVELOPMENT_STANDARDS](https://github.com/Daldek/Nogat/blob/main/standards/DEVELOPMENT_STANDARDS.md),
[AGENT_INTERFACE](https://github.com/Daldek/Nogat/blob/main/standards/AGENT_INTERFACE.md),
[DOCUMENTATION_STANDARDS](https://github.com/Daldek/Nogat/blob/main/standards/DOCUMENTATION_STANDARDS.md),
[ERROR_REGISTRY](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md).

## Critical rules

Product rules. Changing one needs the author. The open questions of PRD 11 and ARCHITECTURE 12
and every `[TO BE COMPLETED]` are the author's decisions: report them, do not settle them.

- **The tools know nothing about Retman** (PRD N-03, ARCHITECTURE 3.2.1). Never edit the
  repositories of Hydrograf, Kartograf, IMGWTools, Hydrolog or other tools; a need there is a
  `request` issue in that repository (DEV-17.5). Retman calls only their public Python API, not
  their MCP servers (ADR-018). Manifests, call builders, clients, handlers and texts live in
  `src/retman/tools/<tool>/`. Manifests are static: never derive options from an installed
  tool; `retman scaffold check` compares them (ADR-019).
- **Retman contains no model** (N-10, ARCHITECTURE 3.3, 9.3). No ML library, provider SDK or
  `basal` package in the dependencies; backends are plain HTTP requests. Core dependencies: the
  HTTP client and `platformdirs`.
- **Always confirm before executing** in 0.x (W-05, ARCHITECTURE 6.3). No execution path without
  `plan.confirm()`; `Plan.from_dict` never restores a confirmation.
- **No network before confirmation** (N-12, ARCHITECTURE 3.2.4, 6.5). Planning code (call
  builders, previews, extractors) sees only `PlanView`, never a client that can use the network;
  a tool function with a network effect runs after `plan.confirm()`. The one exception is
  `Retman.check()` after `plan.confirm_check()`.
- **No silent guessing** (W-02, ARCHITECTURE 1.1, 5.3, 6.1). Code (extractors) reads numbers; the
  model only picks from lists, and its answer must be one of the allowed keys, never code or a
  path. Ambiguity is a question to the user.
- **No hidden defaults** (N-11, ARCHITECTURE 9.1). `retman config show` lists every setting with
  its value and source; the decision model has no default. No feature outside the release
  scope (PRD 7, 9).
- **Security and privacy** (DEV-13, ARCHITECTURE 10). No secret in code, settings, logs or
  `result.json`: the API key is read from the variable that `decision.api_key_env` names. Never
  `eval()` user input or model output. Handlers write only into their `output_dir`. Commands
  go only to the configured model backends (the default points to `localhost`); collecting
  commands is off by default and needs consent; the project journal is append-only; the
  technical log never carries the text of a command.

Process rules.

- Work on a topic branch `<type>/<topic>` from `develop`. Commit messages are English
  Conventional Commits without AI attribution, authored as `Daldek <git@debever.pl>`
  (DEV-3.1, DEV-4.1 to DEV-4.3). One logical change per commit, with its documentation
  (DEV-4.4). Without the author's approval in the session never merge, tag, publish,
  force-push a shared branch or rewrite shared history (DEV-3.3).
- Run `scripts/gate.sh` before every commit and do not commit while a step fails (DEV-7.6).
- Run `retman eval run` (it needs a model server) when the questions, the option descriptions
  or the decision logic change.
- Language (DEV-2.1 to DEV-2.3): code, identifiers, comments, docstrings, documentation, ADRs,
  commits, catalog texts and JSON field names are English. Texts for the user and the model
  live only in translation files (`src/retman/i18n/`, `src/retman/tools/<tool>/`), keyed by
  English ids; machine output (`--json`, errors, guides) is English (AGI-9.2).
- The catalog `src/retman/catalog/commands.py` is the one source of the Python functions, the
  CLI, the guides and the schemas (AGI-1.1): add a command there, never in the CLI.
- Generated files are never edited by hand: `AGENTS.md`, `llms.txt`, `src/retman/_errors.py`,
  `src/retman/schemas/` (commands below); contract tests compare them with their generators
  (DEV-10.4).
- Errors use the registry codes only (ERR-1); finer precision goes to `details.reason`.
- Python: `X | None`, never `Optional` or `Union` (DEV-7.3); `%`-style arguments in log calls, no
  f-strings (DEV-12.3); units in names (`area_km2`, `timeout_s`, DEV-8.2); NumPy docstrings in
  English (DEV-9.1); settings only in `pyproject.toml` (DEV-5.3); UTF-8, LF, final newline
  (DEV-14.1).
- A requirement or architecture change updates `docs/PRD.md` and `docs/ARCHITECTURE.md` with
  their cross-references (`sec. X.Y`, `[W-xx]`, `[N-xx]`) in the same commit; a user-visible
  change updates `docs/CHANGELOG.md` in the same commit (DOC-7.2).

## Environment and commands

```bash
uv sync --locked --all-extras     # .venv with the dev tools and the `tools` group (Kartograf, IMGWTools)
scripts/gate.sh                   # ruff format, ruff check, mypy, pytest + coverage, commit step
uv run pytest tests/unit -q       # a part of the tests; `-m live` runs the live ones, deliberately
uv run pytest tests --collect-only -q   # the number of tests (never copy it into documents)
uv run retman --help              # the CLI; `retman commands list` lists the commands
uv run retman scaffold check      # descriptions of the tools against the installed tools
uv run retman eval run --help     # quality of the model on the command set (needs a model server)
# regenerate what follows from the catalog and the registry:
uv run retman commands guide --format agents --output AGENTS.md --force
uv run retman commands guide --format llms --output llms.txt --force
uv run scripts/generate_result_schemas.py     # --check fails when stale
uv run scripts/generate_errors.py             # --check fails when stale
```

Python 3.12 or newer, only through `uv` and `.venv` (DEV-6.2, DEV-6.3). Run the gate with
`TMPDIR` on a local disk: a network share breaks SQLite and hard links. Coverage floor 80%
(DEV-7.5).

Manual runs of the CLI. Retman writes its results and journal into the project folder where it
runs (`retman-output/`, ARCHITECTURE 5.1) and reads its settings from `nogat.toml`. Run it by
hand in a separate project folder outside the repository, in a folder the user names, for
example `<data folder>/retman/<YYYY-MM-DD>-<goal>/`; if none is available, stop and ask. Never
run it in the repository (`retman-output/` is git-ignored as a safety net). Reports of model runs
and timing measurements go into the plan they belong to (`docs/plans/`), dated in the name.

Tests (DEV-10; they are offline and never touch the real `nogat.toml` or a real project folder):

- `tests/conftest.py` blocks every non-loopback connection; the network needs
  `@pytest.mark.live`. The fixture `user_environment` isolates settings; use `tmp_path`.
- No GPU and no model server: `FakeDecisionBackend`, `FakeToolClient` and `tool_context` from
  `retman.testing`. The N-12 test asserts that `network_calls` is empty before `plan.confirm()`
  and that no `check` or `query` call happens before `plan.confirm_check()`.
- Extractors are pure code tested without a model: every form of ARCHITECTURE 4.4, ambiguous
  ones included. Context extractors use `tests/unit/extractors/extractor_context.py`.
- The shared adapter is tested on the dummy tool `tests/fixtures/dummy_tool`, not on a real tool.
- Mappers, builders and backends are tested on recorded real documents and raw server responses
  (`tests/fixtures/<tool or backend>/`), never on an imagined format. Handlers and conformance
  run against the real tools with small data and skip (`pytest.importorskip`) when a tool is
  missing; CI runs them on the oldest and the newest supported version.
- Recognition tests check stability under shuffled options (ARCHITECTURE 3.4); a test requires a
  text for every operation, parameter, option and category in each language (ARCHITECTURE 4.2).
- No `conftest.py` in a subfolder of `tests/` (a second `conftest` module breaks mypy); shared
  fixtures are in `tests/conftest.py`, helpers are plain modules. Test file names are unique
  across `tests/`, because the subfolders have no `__init__.py`.
- Test names are `test_<unit>_<scenario>[_<expected>]`; assert behaviour, not wording (DEV-10.5).

## Code map

```
src/retman/
├── catalog/        # command catalog: spec (model), commands.py (declarations), dispatch, envelope, documents
├── operations/     # one function per catalog command (retman.operations.<group>_<verb>)
├── cli/            # CLI generated from the catalog; conversation.py is the terminal dialog
├── core/           # pipeline, plan, dialog, result, check, journal, workspace, collection, geometry
├── registry/       # operation model, manifest schema, loader of tool descriptions
├── adapters/       # command layer of the tools (catalog.py), generic manifest adapter
├── tools/<tool>/   # kartograf, imgwtools: manifest, calls, client, preview, check, handlers, texts
├── backends/       # DecisionBackend and TextBackend; openai_compatible.py
├── extractors/     # numbers, dates, coordinates, areas, stations... (code, no model)
├── i18n/           # translation loader, pl.toml; the tools carry their own texts
├── eval/           # command set commands.jsonl, runner, metrics, offline clients
├── devtools/       # retman scaffold: list, draft, drift check, readers
├── environment.py config.py config_show.py initialize.py doctor.py stores.py logs.py
├── outcomes.py exceptions.py _errors.py   # exit codes, error documents, registry (generated)
├── agent_guide.py _data/agents/ schemas/  # generator and templates of AGENTS.md and llms.txt, JSON Schemas
└── kinds.py testing.py                    # data kinds; fakes for offline tests
tests/{unit,integration,contract,fixtures}; scripts/; schemas/nogat/ (copies of the standard)
```

## Documentation map

| For | Read |
|---|---|
| Current state, next steps, open questions | [docs/PROGRESS.md](docs/PROGRESS.md) |
| Using Retman: CLI, Python, examples | [README.md](README.md), [docs/USAGE.md](docs/USAGE.md) |
| Problem, users, scenarios, requirements `W-xx`, `N-xx`, scope | [docs/PRD.md](docs/PRD.md) |
| Design: modules, adapters, models, recognition, dialog, settings, security | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| New operation, data kind, backend or extractor (checklists) | ARCHITECTURE 13 |
| Why it is the way it is | [docs/DECISIONS.md](docs/DECISIONS.md), `docs/decisions/` |
| Changes for users | [docs/CHANGELOG.md](docs/CHANGELOG.md) |
| Plans of changes to interfaces or several modules | `docs/plans/` (none yet) |
| Component specifications and research of the first sessions (read only) | `docs/specs/`, `docs/research/` |
| The commands and the guide for agents | `AGENTS.md`, `llms.txt` (generated) |

## Session workflow

Start (DEV-17.1): read this file and `docs/PROGRESS.md`, run `git status` and
`git log --oneline -10`, confirm the branch, list the open GitHub issues labelled `request`.
A change to a public interface or across more than one module starts with a plan
`docs/plans/YYYY-MM-DD-slug.md`, and code starts after its `Approved: YYYY-MM-DD` line
(DEV-17.4); `docs/specs/` and `docs/research/` take no new files. Decisions with alternatives
are ADRs (DEV-17.2). End (DEV-17.3): update `docs/PROGRESS.md` before the last commit. Change
only this repository (DEV-17.5).

A new operation, kind, backend or extractor follows the checklists of ARCHITECTURE 13; a new
command is an operation in `src/retman/operations/`, its `Command` in the catalog, its Polish
texts under `[catalog.<operation_id>]` in `pl.toml` and its schema in
`scripts/generate_result_schemas.py`, then the regeneration commands above.

## Cross-project context

Registry entry:
[ecosystem.yaml](https://github.com/Daldek/Nogat/blob/main/ecosystem.yaml) (Retman). Retman
consumes Kartograf and IMGWTools through their Python libraries; Hydrolog and Hydrograf are
planned (PRD roadmap). No tool imports Retman. A change that spans projects is planned in Nogat
(DEV-3.4); PROGRESS Next 2 lists the calls to migrate when the producers adopt DEV §19.

## Deviations

- DEV-7.3: mypy runs in `strict` mode over `src/` and `tests/`, but 36 test modules (the list
  in `[[tool.mypy.overrides]]` of `pyproject.toml`) leave helpers and fixtures unannotated. A new
  test module is strict; a module leaves the list when it is annotated
  ([ADR-023](docs/decisions/0023-structure-gate-ci-and-log.md)).
- DEV-18.2: the journal and the results are written into the project folder, not under
  `data_dir` ([ADR-021](docs/decisions/0021-user-environment.md)).

# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). An entry says what changed
for the user and refers to ADRs, PRD requirements and ARCHITECTURE sections in parentheses;
a breaking change is marked **Breaking** and carries its migration. Release 0.1.0 is not
tagged yet, and `develop` carries `0.1.0.dev0`.

## [Unreleased]

### Added

- Project documentation: product requirements (`docs/PRD.md`), architecture
  (`docs/ARCHITECTURE.md`), the user guide (`docs/USAGE.md`), the decision log, the progress
  file and this changelog; `README.md`, `CLAUDE.md`, the MIT licence.
- The `retman` package (Python 3.12 or newer, ADR-002) with `httpx` as its core dependency
  (ADR-005).
- Settings with a commented template written by `retman config init`, validation of all
  settings at once, and thresholds `"auto"` that are rejected outside the basal backend
  (ARCHITECTURE 6.2, 9.1).
- Four Kartograf 0.8.0 operations (ADR-001, ADR-012, ADR-013): DEM for a map sheet or a
  geometry file (all ASC grids: 0.15, 0.5, 0.6, 1, 5 and 10 m, and 100 m as a ZIP per
  voivodeship); child sheets of DEM, DSM and orthophoto (DSM at 0.5, 0.6 and 1 m with a
  vertical datum; orthophoto in RGB, CIR or B-W); a 1 m DEM or DSM cutout for a rectangle or a
  geometry file; BDOT10k for a county, a sheet, a rectangle or a geometry file, as GeoPackage
  or Shapefile.
- All IMGWTools 3.0.0 operations, ČHMÚ included: 26 operations in 6 categories (station
  search and catalog, current data and warnings, PMAXTP, station series, archives and the
  store, data projects; ADR-017, PRD 7.2).
- Two-stage recognition (category, then operation) when there are more than 9 operations
  (ADR-017, ARCHITECTURE 3.4).
- Extractors: station (offline, from the catalog of the IMGW store), years, period, kind of
  year (calendar or hydrological, always a question when not given), point (WGS84 and
  PL-1992), PMAXTP grid cell, probability, duration, variables, task name; a SHP or GPKG
  geometry file as an area, with a question about the GeoPackage layer (ADR-016, ADR-017).
- Area extractors (map sheet code in PL-1992 or PL-2000, rectangle with recognition of the
  coordinate system and of the axis order, TERYT code, geometry file), and extractors of paths
  and result numbers; an ambiguous notation raises a question (ARCHITECTURE 6.1).
- Data kinds `dem`, `dsm`, `orthophoto`, `topographic_vector`, `dem_archive`, `area_geometry`
  and 13 IMGWTools kinds, each with its validator (ADR-004, ARCHITECTURE 3.2.6).
- Offline plan preview: the validation of the tool checks every call before confirmation, a
  rejected value comes back as a question, and preview rows (for example the number of sheets)
  appear in the plan (ADR-014, PRD N-12).
- The availability check as a separate step: the answer `s` in the plan, its own consent, a
  report without downloading and without a result number; `Retman.check()` and
  `plan.confirm_check()` (ADR-014, PRD W-17, ARCHITECTURE 6.5).
- Tool stores in `[retman.tools.kartograf]` and `[retman.tools.imgwtools]`; `retman config init`
  creates the neighbouring folders, checks hard links and, with consent, initialises the IMGW
  store; results point to the store files by path and SHA-256 (ADR-015).
- `retman doctor check`: the stores, hard links in both stores, the IMGW write probe
  (`--deep`) and a light check of the manifests against the installed tools. It also checks
  the settings file, the project folder and the writing of results, the readability of
  `result.json`, the address of the decision model, the model list of the server, a test
  question, the confidence method and thresholds, the tool versions against the supported
  range with the command to install the missing one, the completeness of the translations and
  the text model; every problem comes with a hint (ARCHITECTURE 7.2). A tool manifest has the
  field `source` for the `uv … --with` hint (ARCHITECTURE 4.1).
- `retman scaffold list|draft|check`: drafts of manifests from the catalogs of the tools and a
  drift check through the offline validation of the tool, with a coverage check of the options
  (ADR-019).
- The command set `src/retman/eval/commands.jsonl`: 614 commands (Kartograf, IMGWTools,
  out of scope and close to the scope), validated by the same extractor code as planning;
  placeholder geometry files and an offline station catalog when the set is planned
  (ARCHITECTURE 8.1).
- `retman eval run`: plans the test command set without running any operation, writes the raw
  records and a Markdown report with the measures (accuracy, error at the confidence of W-02,
  silent guessing, violations of W-03, times), the threshold curve and the recommended
  thresholds (`--target-error`); the W-03 verdict is a failed unit (ARCHITECTURE 8). The
  specification is `docs/specs/2026-10-11-retman-eval.md`.
- Optional parameters that the command did not give have a plan row that says what their
  absence means (for example "all station kinds"); the answer `z` changes them, and
  `result.json` records them in `unset` (N-11, ARCHITECTURE 6.3).
- Several tool notices with the same code in one call: the result shows the first three and the
  number of the remaining ones; the full list stays in `tool_*.json` (ARCHITECTURE 4.2).
- Decision backend `openai_compatible` (for example LM Studio): enforced answer format,
  confidence from `logprobs` or from the agreement of several answers (ARCHITECTURE 3.3.3).
- The core: operation recognition, questions (one at a time, answered by number or in the
  user's own words), a plan with the source of every value, mandatory confirmation
  (`PlanNotConfirmedError`), numbered results with `result.json` and audit data, and the journal
  `journal.jsonl` (ARCHITECTURE 5 to 7). `OutOfScopeError` answers a command outside the scope
  and lists the available operations (W-03).
- The technical log goes to stderr: the library logs through `logging`, and the CLI sets the
  level with `--verbose` and `--quiet`, the variables `RETMAN_LOG_LEVEL` and `NOGAT_LOG_LEVEL`
  and the setting `log_level`; the log carries no commands and no answers (DEV-12,
  ARCHITECTURE 5.4). `.env.example` lists the environment variables.
- The CLI `retman <group> <verb>` (`plan run`, `config show|init`, `doctor check`,
  `results list`, `journal show`, `commands list|schema|guide`, `eval run`,
  `scaffold check|list|draft`) with `--explain`, `--config`, `--json`, `--lang`, `--verbose`
  and `--quiet` (ARCHITECTURE 6.4, ADR-022).
- `retman config show [--json]`: the file, every setting with its value and source (default,
  variable or file), the credential variable of an external model provider as present or
  missing, and the tool stores with their size; document `retman-config/1`; it also works with
  a settings file that cannot be used (DEV-18.6, ADR-021). `get_config()` is its library
  function.
- `list_commands`, `command_schema`, `validate_command`, `check_command` and `run_command` are
  the public API, with the error classes and the registry (`retman.__all__`); `AGENTS.md` and
  `llms.txt` are generated from the catalog; the JSON Schemas of the documents are shipped in
  `retman/schemas/` (ADR-022).
- English texts (`lang = en`, `--lang en`, DEV-2.2, AGI-9.2, ADR-022 erratum 1):
  `src/retman/i18n/en.toml` and an `en.toml` for the Kartograf and the IMGWTools adapter
  give the questions, the plan, the messages, the reports, `--help` and the prompts that go
  to the model in English, with the Polish names and abbreviations beside the English words in
  the descriptions that the model reads. The words that the terminal dialog accepts are the
  `[answers]` table of each file (`y`, `n`, `c`, `a`, `cancel`, `end` in English). A float
  that a template formats (`{value:.2f}`) takes the decimal mark of the language.

### Changed

- **Breaking: agent interfaces** (AGI, ADR-022). One executable `retman <group> <verb>`
  generated from a command catalog; `retman commands list|schema|guide` serve the catalog and
  the guides for agents; `--json` prints the envelope `retman-result/1` (the outcomes `partial`
  and `failed` print it too, with `items`); `--lang`, `--verbose` and `--quiet` are the option
  layer of the settings. Migration: `retman "<text>"` is `retman plan run --text "<text>"`,
  `--plan-only` is `--check` (and `--yes` runs a complete plan without a terminal),
  `retman init` is `retman config init`, `retman doctor` is `retman doctor check`,
  `retman results` is `retman results list`, `retman log` is `retman journal show`,
  `retman-eval` is `retman eval run` (`--output` and `--report` need `--force` to replace a
  file) and `retman-scaffold` is `retman scaffold check|list|draft` (`-v` is `--include-info`,
  a list is given by repeating the flag). The bare JSON of `config show` and `doctor` is the
  `result` of the envelope.
- **Breaking: the settings are the `[retman]` tables of `nogat.toml`, read with the `RETMAN_*`
  variables** (DEV-18, ECO-028, ADR-021). `retman.toml` is no longer read: write the tables as
  `[retman.decision]`, `[retman.tools.kartograf]` and so on (`retman init` writes them into
  `nogat.toml` in the user configuration folder of `nogat`, or at `NOGAT_CONFIG` or `--config`,
  and appends to a file that has no `[retman]` table). Order of sources: variable
  `RETMAN_<KEY>` (`decision.url` is `RETMAN_DECISION_URL`), shared variable `NOGAT_<KEY>`
  (`lang`, `log_level`, `data_dir`, `cache_dir`), `[retman]`, `[nogat]`, default. `[ui]
  language` is `lang` and `[log] diagnostic_level` is `log_level` (an invalid
  `RETMAN_LOG_LEVEL` is now `invalid_config`). Every setting has a default except the model
  server (`[retman.decision]`): without it only planning fails (`validation_error`, reason
  `invalid_config`, the keys in `details.keys`), while `results`, `log`, `config show`, `init`
  and `doctor` work. The default stores are `<data_dir>/kartograf` and `<data_dir>/imgw` (they
  were `…/stores/kartograf` and `…/imgwtools` below the data folder of Retman), the Kartograf
  cache is `<cache_dir>/kartograf/metadata.db`, the IMGWTools reference files are
  `<cache_dir>/imgw/reference`, the command collection is `<data_dir>/retman/collected.jsonl`;
  `data_dir` and `cache_dir` default to the user folders of `nogat` (`platformdirs`, a new
  dependency). `retman-eval --config` is optional. The variables are listed in the README and
  `.env.example`. Migration: move the tables into `nogat.toml` under `[retman…]` and check the
  store paths with `retman config show`.
- **Breaking: exit codes and errors follow the shared Nogat error registry** (ERR-3, ERR-4,
  ADR-020). Exit codes: 2 is `validation_error` (wrong option, invalid settings, an answer or
  a confirmation is needed and stdin is not a terminal), 3 is `not_found` (it was "cancelled"),
  4 is `conflict` (it was the W-03 verdict of `retman-eval`), 15 is `unsupported` (a command
  outside the scope; it was 1), 130 is `cancelled` (it was 3), 10 and 11 are the outcomes
  `partial` and `failed` of `retman doctor`, `retman-eval` (W-03) and
  `retman-scaffold --check`, 143 is SIGTERM; other failures take the code of their registry
  code (5 model server, 14 no data, 8 store, 9 files, 1 a defect). On an error the last line
  of stderr is the `retman-error/1` document (`code`, `title`, `message`, `hint`, `details`
  with `reason`, `exit_code`); a cancelled call prints none. `RetmanError` carries `code`,
  `message`, `details` and `hint`; `ToolError.code` is now the registry code and the tool's
  own code is `ToolError.tool_code`; `ConfigError.details` is `problem_details`;
  `OutOfScopeError.text` is the translated text (`str()` is English); a failed `Result` has
  `failure`, the error document. `schemas/nogat/` holds the vendored registry and agent
  schemas, `scripts/generate_errors.py` generates `src/retman/_errors.py`, and a contract test
  compares them. Migration: scripts that test the exit status read the table in USAGE 8.
- The Kartograf operations have no default values: Retman asks for the resolution, the
  vertical datum and the format when the command does not give them (ADR-006).
- `log_level` (formerly `[log] diagnostic_level`) concerns stderr, defaults to `warning` and
  also accepts `error`; the log file in the user's log folder was never created and does not
  exist (ARCHITECTURE 5.4).
- The options of a parameter have a label for the user and a description for the model, like
  the operations: the plan and the questions show short names ("DEM (numerical terrain
  model)", "1 m"), and the model matches the command and the answers to descriptions with
  synonyms and English names (DEM, DTM, DSM, orthophoto, GPKG, SHP) (ADR-007,
  ARCHITECTURE 4.2).
- The project journal records, with every plan, the values with their sources, the decisions of
  the model with their confidence and the name of a changed value, and a command outside the
  scope as a separate event with the decision of the model (ARCHITECTURE 5.4, ADR-010).
- The collection of commands from all projects in one file (`[privacy] collect_commands`,
  `collect_path`) only after explicit consent; `retman config init` asks for it in a terminal
  (ADR-010, ARCHITECTURE 5.4, 10). The new key `collect_path` is required in the settings.
- The result layout of a cutout is recognised by code, not by the model: an EPSG code with or
  without a prefix, a name (PL-1992, S-JTSK, ETRS89/TM33 …), the role from the context
  ("result", "to", "convert" mean the result; right after the coordinates it is the
  rectangle), without Polish characters and with one typo in the words; an unclear notation
  ends with a question (ADR-009, ARCHITECTURE 4.3).
- The decision model gets a separate question about what the command names (`model_question`)
  instead of the user's question "X or Y?"; with Bielik 11B the accuracy of parameter values
  rose from 0.55 to 0.78, and that of data kinds from 16/33 to 32/33 (ADR-008,
  ARCHITECTURE 4.2).
- The tools are called through their command layer (`validate_command`, `run_command`); a
  handler gets the context of the tool (`handler(params, inputs, output_dir, ctx)`); error
  messages of the tools have Retman texts by error code (ADR-013, ARCHITECTURE 3.2.4).
- The sections `[retman.tools.kartograf]` and `[retman.tools.imgwtools]` are required in the
  settings: older files have to be generated again (`retman config init`) or completed
  (ADR-015).
- The CLI shows the warnings of a result ("Uwaga: …"), the licence conditions of the data
  included.
- A loaded plan (`Plan.from_dict`) never restores the confirmation (W-05).
- Documentation: `CLAUDE.md` is English and follows DOC-3.1; `docs/DEVELOPMENT_STANDARDS.md` is
  removed (DEV-1.3). The project rules are in `CLAUDE.md`, the checklists for a new operation,
  data kind, backend, extractor and command are `docs/ARCHITECTURE.md` 13, and the standard
  itself is the Nogat standard 2.1.
- **Breaking:** the texts inside the `--json` document of `doctor check` (titles, checks and
  hints) are English whatever `lang` says; they were in the language of the setting.
  Migration: match the English text, or `code` and `reason` of the check; the terminal still
  shows the report in the language of `lang`. `help_language` reads the real command line, so
  `--lang` decides the language of `--help`.
- **Breaking: IMGWTools data output** (ECO-051, ADR-024). Retman calls IMGWTools as its branch
  `feature/data-output` defines it: archive downloads write plain files into the results folder
  (`output_dir`; the tool stages, verifies and checksums them), exports write the one file given
  as `output`, the store operations keep `root`, and `reference_data_dir` reaches the tool as
  `IMGW_REFERENCE_DIR` (it was `IMGW_DATA_DIR`). The values of a result follow the tool: the
  synchronisation reports `values.new_versions` and `values.new_series` (they were `created` and
  `series_created`), and the statuses in `values.series`, `values.archives` and
  `values.store_versions` are `new` and `unchanged` (they were `created` and `reused`).
  Migration: read the new names in `result.json`; the plan and the settings do not change. The
  texts of the tool are English and are shown as they come, so a Polish message can quote an
  English detail, and the licence notice of an IMGW result ends with an English notice. The `tools`
  group pins IMGWTools `a304521`, the head of its branch `feature/data-output`, which is not pushed
  yet (ARCHITECTURE 3.2.11, 9.3; USAGE 5.2).
- An IMGW store folder can be a layout of a store without its marker (`archives/`, `series/`,
  `stations/` or `pmaxtp/` and no `imgw-store.json`): `retman doctor check` reports it as
  `store_unavailable`, reason `no_marker`, and the plan names it and points to the command "Utwórz
  magazyn IMGW", where IMGWTools checks the layout and writes the marker. A folder that holds only
  the `api_keys.json` of the IMGWTools server counts as empty, no longer as foreign
  (ARCHITECTURE 7.2, 9.1; ADR-024).

### Removed

- **Breaking:** the executables `retman-eval` and `retman-scaffold`, the positional sentence
  `retman "<text>"`, the interactive session `retman` without a command, the option
  `--plan-only`, the commands `retman init`, `retman doctor`, `retman results` and
  `retman log`, and the file `retman.toml`. Each has its replacement in the migration notes
  under Changed (ADR-020 to ADR-022).

[Unreleased]: https://github.com/Daldek/Retman/commits/develop

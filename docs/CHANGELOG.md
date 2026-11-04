# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html). An entry says what changed
for the user and refers to ADRs, PRD requirements and ARCHITECTURE sections in parentheses;
a breaking change is marked **Breaking** and carries its migration. Release 0.1.0 is not
tagged yet, and `develop` carries `0.1.0.dev0`.

## [Unreleased]

### Added

- The Hydrolog adapter (`hydrolog` pinned in the `tools` group at `2eb8bd0c`, the Nogat
  release set `candidate-1`): six operations in the categories `rainfall_runoff` and
  `hydrology_analysis` — a design hyetograph (`precip hietogram`), SCS-CN effective rainfall
  (`scs effective`), the design hydrograph of a catchment given by its area, CN and time of
  concentration (`hydrograph generate`), the time of concentration (`tc watershed`) and the
  morphometry (`morphometry watershed`) of a watershed file, and flood quantiles
  (`stats flood-frequency`) of the daily flows of an Obserwator series export. Hydrolog needs
  no settings; the preview lets it compute the plan offline, so a method the watershed lacks
  fields for is asked again and the plan of the quantiles shows the hydrological years of the
  sample. New data kinds `watershed_parameters` and `hydrolog_report`, the scaffold reader of
  Hydrolog's catalog, 101 eval rows (the row that called a SCS-CN hydrograph out of scope now
  expects the hydrograph).
- The rest of Hydrolog's basic routes, three operations (ARCHITECTURE 3.2.12): hydrographs
  routed through a river network file (`route network`, category `rainfall_runoff`), as
  `route_river_network` for a network whose subcatchments hold or compute their flows and
  `route_river_network_inflows` with an inflow table, and the hydrologic soil groups of
  clay, sand and silt rasters at hand (`soil hsg`, `classify_soil_groups`, category
  `soil_data` beside Kartograf's soil operations). A routed network gives the peak, the time
  to peak and the volume of every node, the table `<id>.csv` of every node and the schematic
  `network.svg`; its plan lets Hydrolog route it in memory first and shows the network, its
  nodes and its outlet, and a network that reads an inflow table, planned without one, ends
  with the advice to name it. The soil groups give the cells and the share of each group;
  one file given for two textures ends the plan. New data kinds `hydrolog_network`,
  `hydrograph_table` and `network_schematic`; 47 eval rows.
- Inputs of one kind told apart (ARCHITECTURE 5.3): an input may name the values of the
  earlier result it takes (`where`, e.g. the clay layer among SoilGrids results), and such
  inputs are asked and shown by their own names; when a command names several files or
  results for an operation with several inputs, each input takes the one that fits it.
- Extractors of numbers with units: `curve_number` („CN 72”), `rainfall_depth` („50 mm”),
  `catchment_area` („45,3 km²”, „4530 ha”) and the durations of a role, `rain_duration`,
  `time_step` („krok 5 min”, „co 10 min”) and `concentration_time` („czas koncentracji
  90 min”, „tc = 1,5 h”); an answer may give the curve number, the depth and the area as a
  bare number.
- Project documentation: product requirements (`docs/PRD.md`), architecture
  (`docs/ARCHITECTURE.md`), the user guide (`docs/USAGE.md`), the decision log, the progress
  file and this changelog; `README.md`, `CLAUDE.md`, the MIT licence.
- The `retman` package (Python 3.12 or newer, ADR-002) with `httpx` as its core dependency
  (ADR-005).
- Settings with a commented template written by `retman config init`, validation of all
  settings at once, and thresholds `"auto"` that are rejected outside the basal backend
  (ARCHITECTURE 6.2, 9.1).
- Five Kartograf 0.8.0 operations (ADR-001, ADR-012, ADR-013): DEM for a map sheet or a
  geometry file (all ASC grids: 0.15, 0.5, 0.6, 1, 5 and 10 m, and 100 m as a ZIP per
  voivodeship); child sheets of DEM, DSM and orthophoto (DSM at 0.5, 0.6 and 1 m with a
  vertical datum; orthophoto in RGB, CIR or B-W); a 1 m DEM or DSM cutout for a rectangle or a
  geometry file; BDOT10k for a county, a sheet, a rectangle or a geometry file, as GeoPackage
  or Shapefile; and the creation of the store ("Utwórz magazyn Kartografa", `kartograf store
  init`: it writes the store marker into a new or an empty folder, or into a layout that has
  lost it, after the tool has checked the layout; ECO-051).
- Two Kartograf operations on SoilGrids soils, in their own category `soil_data` ("Dane
  glebowe SoilGrids", PRD 7.2, ARCHITECTURE 3.2.10): one soil property layer (clay, sand,
  silt, organic carbon as content, density or stock, pH, bulk density, coarse fragments, CEC
  or nitrogen; a depth of 0-5 to 100-200 cm; mean, median, 5% or 95% quantile or
  uncertainty), whose result gives the unit of the integer values and the divisor to the usual
  unit (`soil download`); and the hydrologic soil groups A-D of the SCS-CN method from the
  texture of one depth, with the share and the area of each group (`soil hsg`). Both take a
  sheet code, a rectangle or a geometry file, preview the extent offline and check the
  SoilGrids edition against the store on request; the data kinds `soil_raster` and
  `hsg_raster` are new, and the command set has 34 rows for them.
- The texts of the Kartograf errors `no_data` and `source_unavailable` name the source of the
  data as GUGiK or SoilGrids instead of GUGiK alone.
- The overview of the Kartograf store ("Przegląd magazynu Kartografa", `store overview`, PRD
  7.2, ARCHITECTURE 3.2.10): a read without network that lists the segments of the store
  (product, country, dataset, whether the installed Kartograf knows them) and warns about the
  unknown ones; a store folder that does not exist ends the plan (`store_unavailable`,
  `not_initialised`); 16 rows of the command set. `retman scaffold check` tells a command the
  command layer runs (X1) from a command an operation is expected to offer (X9), so an
  operation may run a store read.
- Two Kartograf operations on spatial data ("Dane przestrzenne GUGiK", PRD 7.2, ARCHITECTURE
  3.2.10): the orthophoto cutout of an area (`imagery download --cutout`: one GeoTIFF of a
  rectangle or of the rectangle around a geometry file, the RGB orthophoto from the standard or
  the high-resolution WCS or the true orthophoto of selected cities, a pixel of 5 cm to 1 m;
  the availability check reads the sheet index of the area); and the land cover of an area
  (`landcover download`): CORINE Land Cover of an edition from 1990 to 2018, which without CLMS
  credentials is a WMS preview the result names as such, or the BDOO packages of every
  voivodeship the area touches in a yearly release, a failed voivodeship being a warning. The
  data kinds `landcover_raster` (GeoTIFF or PNG) and `topographic_archive` (ZIP) are new, and
  the command set has 34 rows for them and a near miss for the Czech land cover (ZABAGED,
  Data50, Data250), which needs an area Retman does not read yet. With ten Kartograf
  operations its recognition is two-stage as well (category, then operation).
- All Obserwator 3.0.0 (formerly IMGWTools) operations, ČHMÚ included: 19 operations in 5 categories (station
  search and catalog, current data and warnings, PMAXTP, station series, archives and the
  store; ADR-017, PRD 7.2).
- Two-stage recognition (category, then operation) when there are more than 9 operations
  (ADR-017, ARCHITECTURE 3.4).
- Extractors: station (offline, from the catalog of the Obserwator store), years, period, kind of
  year (calendar or hydrological, always a question when not given), point (WGS84 and
  PL-1992), PMAXTP grid cell, probability, duration, variables; a SHP or GPKG
  geometry file as an area, with a question about the GeoPackage layer (ADR-016, ADR-017).
- Area extractors (map sheet code in PL-1992 or PL-2000, rectangle with recognition of the
  coordinate system and of the axis order, TERYT code, geometry file), and extractors of paths
  and result numbers; an ambiguous notation raises a question (ARCHITECTURE 6.1).
- Data kinds `dem`, `dsm`, `orthophoto`, `topographic_vector`, `dem_archive`, `area_geometry`
  and 13 Obserwator kinds, each with its validator (ADR-004, ARCHITECTURE 3.2.6).
- Offline plan preview: the validation of the tool checks every call before confirmation, a
  rejected value comes back as a question, and preview rows (for example the number of sheets)
  appear in the plan (ADR-014, PRD N-12).
- The availability check as a separate step: the answer `s` in the plan, its own consent, a
  report without downloading and without a result number; `Retman.check()` and
  `plan.confirm_check()` (ADR-014, PRD W-17, ARCHITECTURE 6.5).
- Tool stores in `[retman.tools.kartograf]` and `[retman.tools.obserwator]`; `retman config init`
  creates the neighbouring folders, checks hard links and, with consent, initialises the Obserwator
  store; results point to the store files by path and SHA-256 (ADR-015).
- `retman doctor check`: the stores, hard links in both stores, the Obserwator write probe
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
- The command set `src/retman/eval/commands.jsonl`: 630 commands (Kartograf, Obserwator,
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
  `src/retman/i18n/en.toml` and an `en.toml` for the Kartograf and the Obserwator adapter
  give the questions, the plan, the messages, the reports, `--help` and the prompts that go
  to the model in English, with the Polish names and abbreviations beside the English words in
  the descriptions that the model reads. The words that the terminal dialog accepts are the
  `[answers]` table of each file (`y`, `n`, `c`, `a`, `cancel`, `end` in English). A float
  that a template formats (`{value:.2f}`) takes the decimal mark of the language.

### Changed

- The repository URL of Obserwator is `github.com/Daldek/Obserwator` (renamed from
  `Daldek/IMGWTools`; Nogat plan `2026-11-03-imgwtools-to-obserwator` step 5); same pinned commit.

- Obserwator pinned at `1ee5457` (the Nogat release set `candidate-1`), whose documents follow
  the Nogat standard 1.0 (its ADR-010). Retman reads a list command's items from `result` (a
  list; the paging is the envelope's `page`), a notice's text from `message` and passes the
  tool's `hint` with its errors; the scaffold reads Obserwator's `commands-1` catalog. The
  `command_line` of an audit call ends with `--json`, so the line prints the envelope Retman
  keeps. An Obserwator document kept as a result (`obserwator_report`) has the new shape.

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
  and `doctor` work. The default stores are `<data_dir>/kartograf` and `<data_dir>/obserwator`
  (they were `…/stores/kartograf` and `…/imgwtools` below the data folder of Retman), the
  Kartograf cache is `<cache_dir>/kartograf/metadata.db`, the Obserwator reference files are
  `<cache_dir>/obserwator/reference`, the command collection is `<data_dir>/retman/collected.jsonl`;
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
- The sections `[retman.tools.kartograf]` and `[retman.tools.obserwator]` are required in the
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
- **Breaking: Obserwator data output** (ECO-051, ADR-024). Retman calls Obserwator as its branch
  `feature/data-output` defines it: archive downloads write plain files into the results folder
  (`output_dir`; the tool stages, verifies and checksums them), exports write the one file given
  as `output`, the store operations keep `root`, and `reference_data_dir` reaches the tool as
  `OBSERWATOR_REFERENCE_DIR` (it was `IMGW_DATA_DIR`). The values of a result follow the tool: the
  synchronisation reports `values.new_versions` and `values.new_series` (they were `created` and
  `series_created`), and the statuses in `values.series`, `values.archives` and
  `values.store_versions` are `new` and `unchanged` (they were `created` and `reused`).
  Migration: read the new names in `result.json`; the plan and the settings do not change. The
  texts of the tool are English and are shown as they come, so a Polish message can quote an
  English detail, and the licence notice of an IMGW result ends with an English notice. The `tools`
  group pins IMGWTools `b0ef83c`, the head of its branch `feature/data-output`, which is on
  GitHub (ARCHITECTURE 3.2.11, 9.3; USAGE 5.2; ADR-024 erratum 3).
- An Obserwator store folder can be a layout of a store without its marker (`archives/`,
  `series/`, `stations/` or `pmaxtp/` and no `obserwator-store.json`): `retman doctor check`
  reports it as `store_unavailable`, reason `no_marker`, and the plan names it and points to the
  command "Utwórz magazyn Obserwatora", where Obserwator checks the layout and writes the marker. A
  folder that holds only the `api_keys.json` of the Obserwator server counts as empty, no longer as foreign
  (ARCHITECTURE 7.2, 9.1; ADR-024).
- **Breaking: Kartograf data output** (ECO-051, ADR-025). Retman calls Kartograf as its branch
  `feature/data-output` defines it: the folder `[retman.tools.kartograf] store_dir` is the store
  `root` of every call (it was `output_dir`, `--output-dir` on the command line of the audit and
  `DownloadManager(output_dir=...)` of the orthophoto), a run is read from the
  `kartograf-result/1` envelope (`status`, `items[]`, `notices[]` with `message`, and the
  `files[]` of its `result` with `size_bytes`), the offline lookups are `sheet parse`,
  `sheet find` and `store sidecar`, and `retman scaffold` reads `list_commands` and
  `command_schema`. The errors are the codes of the registry: the `error_code` of a result is
  `no_data` (it was `no_coverage`), `source_unavailable` (`download_failed`),
  `validation_error` (`invalid_input`) and so on, and the precision is the `details.reason` of
  the `failure` of the result; the `[errors]` texts of the tool are keyed by the codes.
  Migration: read the new codes in `result.json`; the plan and the settings do not change. The
  first write into a new folder writes the store marker `kartograf-store.json`. Retman always
  writes to the store (`root`) and offers no plain mode of Kartograf. The `tools` group pins
  Kartograf `e3c0ab3a`, the head of its branch `feature/data-output`, which is on GitHub
  (ARCHITECTURE 3.2.4, 3.2.10; USAGE 5.2, 9.1; ADR-012 erratum 3; ADR-025 erratum 1).
- A Kartograf store folder can be the layout of a store without its marker (files in a product
  tree such as `nmt/` and no `kartograf-store.json`), a folder with other files, a folder whose
  marker Kartograf cannot read, or a folder inside another store: `retman doctor check` reports
  each as `store_unavailable` (reasons `no_marker`, `foreign_folder`, `marker_unreadable`,
  `marker_unsupported`, `nested_store`), and the plan of every Kartograf operation that writes
  names it before you confirm (Kartograf itself ends a run into such a store with one error of
  the command, before any request). A missing or an empty folder stays fine: the first
  write marks it, and the command "Utwórz magazyn Kartografa" marks a layout that has lost its
  marker (ARCHITECTURE 3.2.10, 7.2; USAGE 11; ADR-025).
- The supported ranges admit the development versions of the pending releases while the
  `tools` group pins commits: Kartograf `>=0.8.0.dev0,<0.9` and Obserwator `>=3.0.0.dev0,<4`
  (REL-5.6, ADR-024 erratum 1). The version check of the loader, `retman doctor check` and
  `retman scaffold check` reads the range as a PEP 440 specifier set
  (`packaging`, a new core dependency) instead of a comparison of numbers, so `~=` and the
  other PEP 440 forms are valid in a manifest. The release change that puts the tags in place of
  the commits narrows the ranges to `>=0.8.0,<0.9` and `>=3.0.0,<4`.
- The `tools` group pins IMGWTools `b0ef83c`, which ships `py.typed`: mypy checks the calls and
  the tests against its types, and the ignore of `imgwtools` is gone from `pyproject.toml`. The
  tests that need a ready Obserwator store use the fixture store of `obserwator.testing`, not a marker
  written by hand (DEV-10.6).
- The operation "Utwórz magazyn Kartografa" (`init_kartograf_store`) is a catalog call of the
  shared executor: the command layer of Kartograf takes `store init` (AGI-2.1), so the handler
  is gone. The document saved as `tool_1_store_init.json` is the envelope `kartograf-result/1`
  with the marker as its `result` (it was the marker document), and a call gets the workers and
  the update mode of the settings only when its command declares them (ADR-025 erratum 1).
- The availability checks of Kartograf and of Obserwator report a store that the tool turns away
  (a folder with other files, a store inside another store: the plan of the tool lists the
  refusal of the root as its one position) as "the tool will refuse to write into this store",
  status `unavailable`, and no longer as "available" or as 0 files. An Obserwator store whose
  marker cannot be read is named so in the plan; the tool raises `data_error` (`invalid_marker`)
  for it, and `tests/unit/test_stores.py` holds `obserwator_store_state` against the check of the tool
  (ADR-024 erratum 3, ADR-025 erratum 1).
- The pins are the final heads of the producers: Kartograf `d11f6219` and IMGWTools
  `71bae778` (first `c655639b` and `4faf884`). The tool's `project init` refuses a store marker
  that cannot be read as `data_error` (`invalid_marker`), like `store init` (it was
  `store_unavailable`) (ADR-024 errata 4 and 5, ADR-025 errata 3 and 4).
- `retman scaffold check --tool kartograf`: X9 lists only the data commands no operation uses.
  A command whose run is read-only in `command_schema` (the source listings, the availability
  reports, `store overview`, `sheet`, `config show`) is no data command for the scaffold; the
  list went from 41 to 14 commands (ADR-025 erratum 2).
- The `tools` group pins the commits of Nogat's release set `candidate-1`: Kartograf `9deaa314`
  and Obserwator `ea158dc6` (the merge of the rename into its `develop`; the tree of `651d4d73`),
  written by `ecosystem.py set apply`, so every consumer pins the same commits.
- The `tools` group pins Kartograf `dbcfe5bb`, the head of its branch
  `feature/archiwista-projects`, which is on GitHub; the supported range stays
  `>=0.8.0.dev0,<0.9`. Kartograf keeps no projects any more (Nogat ECO-054); Retman's Kartograf
  operations used none, so they are unchanged. `retman scaffold check --tool kartograf` lists 10
  data commands under X9 (no `project *`) and takes the check of every command as a plan
  (ADR-025 erratum 5).
- **Breaking: IMGWTools is called Obserwator** (Nogat ECO-057; the tool's ADR-009; ADR-024
  erratum 7, ADR-025 erratum 6). The `tools` group pins Obserwator `651d4d73`, the head of its
  branch `feature/obserwator` (distribution and import package `obserwator`, the extra
  `obserwator[store]`), and Kartograf
  `9deaa314`, the head of its `develop`, whose `STORE_MARKERS` name `obserwator-store.json`.
  Retman follows the tool's name map: the settings table `[retman.tools.imgwtools]` is
  `[retman.tools.obserwator]` (variables `RETMAN_TOOLS_OBSERWATOR_STORE_DIR` and
  `RETMAN_TOOLS_OBSERWATOR_REFERENCE_DATA_DIR`), the default store is `<data_dir>/obserwator` and
  the reference data `<cache_dir>/obserwator/reference` (they were `<data_dir>/imgw` and
  `<cache_dir>/imgw/reference`), `reference_data_dir` reaches the tool as
  `OBSERWATOR_REFERENCE_DIR`, and the documents and the marker that Retman reads are
  `obserwator-result/1`, `obserwator-plan/1`, `obserwator-store/1` and `obserwator-store.json`.
  The tool id is `obserwator` (the key of the store in `retman-config/1` and
  `retman-config-init/1`, `tools` in `result.json`, `ToolError.tool`, `[retman.adapters] enabled`,
  `retman scaffold --tool obserwator`); the categories are `obserwator_catalog`,
  `obserwator_current`, `obserwator_pmaxtp`, `obserwator_series` and `obserwator_archives`; the
  operations `find_imgw_stations`, `build_imgw_station_catalog`, `list_imgw_datasets`,
  `build_imgw_series`, `check_imgw_archives`, `sync_imgw_store`, `sync_imgw_store_by_plan`,
  `export_imgw_archive`, `init_imgw_store` and `inspect_imgw_store` are
  `find_obserwator_stations`, `build_obserwator_station_catalog`, `list_obserwator_datasets`,
  `build_obserwator_series`, `check_obserwator_archives`, `sync_obserwator_store`,
  `sync_obserwator_store_by_plan`, `export_obserwator_archive`, `init_obserwator_store` and
  `inspect_obserwator_store`; the data kinds `imgw_archive`, `imgw_plan` and `imgw_report` are
  `obserwator_archive`, `obserwator_plan` and `obserwator_report`; the rows of the command set are
  `obserwator-*` (they were `imgw-*`), and a row says „Utwórz magazyn Obserwatora”. The plan,
  the questions and the messages name the tool and its store Obserwator („magazyn Obserwatora”,
  „Utwórz magazyn Obserwatora”, `obserwator:` in `doctor check`). The institute keeps its names:
  IMGW and IMGW-PIB in the texts, the provider option `imgw_pib`, the datasets `pl.imgw.*`, and
  the operation `fetch_imgw_warnings` with its kind `imgw_warnings` (the warnings of IMGW-PIB);
  a command that says "magazyn IMGW" still finds the store. Migration: install
  `obserwator[store]` instead of `imgwtools[store]`; rename the table `[retman.tools.imgwtools]`
  of `nogat.toml` to `[retman.tools.obserwator]` and the variables `RETMAN_TOOLS_IMGWTOOLS_*` to
  `RETMAN_TOOLS_OBSERWATOR_*` (an old table or variable is ignored, ECO-056); a store with
  `imgw-store.json`, written by a development build, is not read: download the data again into a
  new store (`retman config init` or „Utwórz magazyn Obserwatora”); read the new tool id,
  operation ids and kinds in `result.json`, the journal and the records of `retman eval run`.

### Removed

- **Breaking:** the executables `retman-eval` and `retman-scaffold`, the positional sentence
  `retman "<text>"`, the interactive session `retman` without a command, the option
  `--plan-only`, the commands `retman init`, `retman doctor`, `retman results` and
  `retman log`, and the file `retman.toml`. Each has its replacement in the migration notes
  under Changed (ADR-020 to ADR-022).
- **Breaking:** the Polish commands for IMGWTools data projects: the category "Projekty danych
  IMGW" (`imgw_projects`) and its seven operations `init_imgw_project`,
  `add_imgw_project_task`, `remove_imgw_project_task`, `set_imgw_project_store`,
  `download_imgw_project`, `check_imgw_project` and `verify_imgw_project`, with their
  previews, texts and eval rows. IMGWTools keeps no projects any more: projects, and the pins
  of store versions, belong to Archiwista (Nogat ECO-054). The `tools` group pins IMGWTools
  `8cd6844c`, the head of its `feature/archiwista-projects`, and the tool's new error code
  `unsupported` has its text. Migration: keep a project in Archiwista; Retman still downloads,
  checks and synchronises the Obserwator store (ARCHITECTURE 3.2.11).
- The task name extractor `identifier` and its text `extractors.errors.invalid_identifier`: its
  only user was the IMGWTools project task (ADR-017 erratum 2).
- The path of an option inside another option (`options.<name>` in `ToolError.option` and in
  `CatalogCall.params`, which X2 of `retman scaffold check` followed into the option): only the
  IMGWTools `project add` carried the options of another command (ADR-025 erratum 5).

### Fixed

- Planning an Obserwator operation when its store has not been created yet ends with
  `store_unavailable` (reason `not_initialised`, `details.path` the store folder) and the text
  "Magazyn Obserwatora (…) nie jest jeszcze utworzony…", no longer with `validation_error`
  `invalid_known_value` ("A value given with the command cannot be used"), which blamed a value
  the user never gave. A store folder that Obserwator or Kartograf refuses ends the plan the same
  way with the reasons of `retman doctor check` (`no_marker`, `foreign_folder`,
  `marker_unreadable`, `marker_unsupported`, `nested_store`), a missing `pyarrow` with
  `missing_dependency` (`pyarrow_missing`), and a plan file of another store with
  `validation_error` (`plan_other_store`). A preview problem without parameters now names the
  code and the reason of its error (ARCHITECTURE 3.2.4).
- Without a station catalog, a station named in words ("Pobierz aktualne dane hydrologiczne ze
  stacji Racibórz-Miedonia.") is no longer dropped: the plan asked nothing and fetched every
  station instead of the one named (W-02). The name is now a question about the station with the
  reason "Nie ma katalogu stacji IMGW, więc rozpoznaję tylko kody stacji… Katalog tworzy polecenie
  „Zbuduj katalog stacji IMGW”", answered with the code; a required station that got no reading
  is asked about with the same reason, which was never shown (ARCHITECTURE 3.2.11).
- An input with no earlier result of its kind ("Pobierz do magazynu według planu #1" in a project
  without a plan) no longer asks "Wybierz jedną z podanych możliwości." with no options to choose
  from: the question says that the project has no result of that kind (or no result #1 of it)
  and names the operations that make one, e.g. „Sprawdzenie archiwów względem magazynu”, or
  asks for a file path when no operation makes it, also when the answer names a missing result
  (ARCHITECTURE 5.3).

[Unreleased]: https://github.com/Daldek/Retman/commits/develop

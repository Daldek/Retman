# Retman: Polish natural-language commands for the Nogat hydrology tools

Retman is a command layer for the Nogat hydrology data tools: Kartograf (spatial data of GUGiK) and IMGWTools (measurements of IMGW-PIB and ČHMÚ). You write a data task in Polish; Retman recognises the operation, asks for what is missing, shows a plan to confirm and then runs the tool. CLI and Python library; the language model is a separate server.

## When to use

- A person or a program states a data task in Polish and wants to see a checked plan before anything is fetched, for example `Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4` ("download the 1 m digital elevation model for map sheet N-34-130-D-d-2-4").
- Spatial data of GUGiK through Kartograf: digital elevation model (DEM, Polish NMT), digital surface model (DSM, NMPT), orthophoto and the topographic database BDOT10k, for a map sheet, a rectangle, a county (TERYT code) or a geometry file (SHP, GPKG).
- Measurements of IMGW-PIB and ČHMÚ through IMGWTools: station search and catalog, current data and warnings, PMAXTP maximum precipitation, station series, archives and the data store, data projects.
- Work that has to be confirmed and traceable: every run needs the user's confirmation, and results are numbered and kept in the project folder with a journal.

## When not to use

- The exact call and its options are known: use the tool itself (`kartograf`, `imgw`), or its MCP server.
- The command is not in Polish: other languages are not recognised.
- Hydrological computation (design rainfall, hydrographs, runoff): use [Hydrolog](https://github.com/Daldek/Hydrolog); Retman only fetches data today.
- GIS processing of the downloaded files: use QGIS or GDAL.
- Browsing and managing the tool stores: use [Archiwista](https://github.com/Daldek/Archiwista).
- Planning without a language model: Retman contains none and needs a model server (basal-serve or any OpenAI-compatible server, for example LM Studio) to plan. Without one, only planning and `retman eval run` fail; the other commands work.

## Install

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). Retman has no extras: the tools it drives are installed next to it, in one environment, and Retman enables every supported tool that it finds. Until the tags `v0.8.0` (Kartograf) and `v3.0.0` (IMGWTools) exist, the commits that Retman is tested with are named (the IMGWTools one is the head of its branch `feature/data-output`, [PROGRESS.md](https://github.com/Daldek/Retman/blob/main/docs/PROGRESS.md) says whether it is pushed):

```sh
# CLI
uv tool install "git+https://github.com/Daldek/Retman@develop" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@8e9bcbb058d11f06afae5a65e62f31870f69d169" \
    --with "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@a30452182b01f47cc18e48466da4edf4d0c8cb6a"

# Python library (name the same tools in the project's own dependencies)
uv add "retman @ git+https://github.com/Daldek/Retman@develop"
```

Retman is not on PyPI yet (planned name `nogat-retman`), and it has no MCP server and no REST API (an MCP server is planned for v0.3, ADR-018). Then write the settings and name the model server:

```sh
retman config init     # writes the [retman] tables into nogat.toml, with every default visible
retman doctor check    # checks the settings, the model server, the tools and the stores
```

Replace the two decision tables of the written file by the settings of your server; the key of an external provider is never written there, only the name of the variable that holds it (`api_key_env`):

```toml
[retman.decision]
backend = "openai_compatible"
url = "http://127.0.0.1:1234/v1"   # LM Studio, or any OpenAI-compatible server
model = "<model-name>"
timeout_s = 30
confidence = "none"                # "auto" | "logprobs" | "consistency" | "none"
consistency_runs = 3

[retman.decision.thresholds]
operation = 0.90                   # a number in (0, 1]; "auto" only with backend = "basal"
parameter = 0.90
```

## Quick start

CLI. A command is `retman <group> <verb>`; `--json` prints one JSON document on stdout and never asks anything. `plan run --check` plans without effects:

```bash
retman config init
retman plan run --text "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4" --check --json
```

```json output
{
  "schema": "retman-result/1",
  "tool": "retman",
  "command": "plan run",
  "check": true,
  "status": "ok",
  "result": {
    "schema": "retman-plan/1",
    "text": "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4",
    "operation": "download_dem_sheet",
    "complete": true,
    "confirmed": false,
    "values": {
      "area": {"value": {"type": "sheet", "code": "N-34-130-D-d-2-4"}, "source": "command"},
      "resolution": {"value": "1m", "display": "1 m", "source": "command"},
      "vertical_crs": {"value": "evrf2007", "display": "EVRF2007", "source": "command"}
    },
    "questions": []
  },
  "items": [],
  "notices": []
}
```

The plan is complete and nothing has run. In a terminal, without `--json`, `retman plan run --text "..."` starts the dialog below. Without a terminal, or with `--json`, nothing is asked: an open question or a missing `--yes` ends with `validation_error`, reason `input_required` (`details.questions` lists what is open); `--check` shows an incomplete plan, and `--yes` runs a complete one.

```text
$ retman plan run --text "Pobierz NMT 1 m dla arkusza N-34-130-D-d-2-4"
? W którym układzie wysokościowym pobrać NMT: EVRF2007 czy KRON86?
  1) EVRF2007
  2) KRON86 (tylko 0,5 m i 1 m)
> 1
Plan:
Operacja: Pobranie NMT dla arkusza lub obszaru
Godło arkusza lub obszar NMT: godło arkusza N-34-130-D-d-2-4
Rozdzielczość NMT: 1 m
Układ wysokościowy NMT: EVRF2007
Liczba arkuszy: 1 × 1:10000 (PL-1992) ← podgląd, bez sieci
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

The question asks for the vertical datum, the plan lists every value with where it came from, and the line marked "podgląd" (preview) was worked out by the tool offline. Until you confirm, Retman uses no network of the tools; the answer `s` asks, with its own consent, which data the source has (years, resolutions, coverage). Human output is Polish by default.

Python:

```python
import json

import retman

retman.run_command("config init")  # once: writes the [retman] tables into nogat.toml
envelope = retman.check_command(
    "plan run", text="Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4"
)
plan = envelope.to_dict()["result"]
print(json.dumps({"operation": plan["operation"], "complete": plan["complete"]}))
```

```json output
{"operation": "download_dem_sheet", "complete": true}
```

The functions `retman.list_commands`, `command_schema`, `validate_command`, `check_command` and `run_command` take the options of the CLI as keyword arguments; errors are `RetmanError` subclasses with `code`, `hint` and `details`. The classes `Retman` and `Plan` serve programs that answer open questions themselves. Only planning and `eval run` need the model server; the catalog is offline:

```bash
retman commands list --json
```

```json output
{
  "schema": "retman-result/1",
  "command": "commands list",
  "status": "ok",
  "result": {
    "schema": "retman-command-list/1",
    "commands": [
      {"name": "plan run", "operation_id": "retman_plan_run", "read_only": false},
      "..."
    ]
  }
}
```

## Capabilities

The commands of the catalog; each exists as a CLI command and as a Python function with the same options. `retman commands schema --command "<name>"` gives the options, the result document, the effects and the errors of one command.

| CLI command | Python function | Task | Needs a model server |
|---|---|---|---|
| `retman plan run` | `retman.operations.plan_run` | Plan a Polish command, show the plan, and run it once confirmed | yes |
| `retman config show` | `retman.operations.config_show` | Show every setting with its value and source | no |
| `retman config init` | `retman.operations.config_init` | Write the `[retman]` tables into `nogat.toml` | no |
| `retman doctor check` | `retman.operations.doctor_check` | Check the settings, the model server, the tools and the stores | answers `failed` without it |
| `retman results list` | `retman.operations.results_list` | List the numbered results of the project folder | no |
| `retman journal show` | `retman.operations.journal_show` | Show the event journal of the project folder | no |
| `retman commands list` | `retman.operations.commands_list` | List the commands of the catalog | no |
| `retman commands schema` | `retman.operations.commands_schema` | Describe a command | no |
| `retman commands guide` | `retman.operations.commands_guide` | Print or write `AGENTS.md`, `llms.txt` or the block for another repository | no |
| `retman eval run` | `retman.operations.eval_run` | Measure the model on the test command set | yes |
| `retman scaffold check` | `retman.operations.scaffold_check` | Compare the tool descriptions with the installed tools | no |
| `retman scaffold list` | `retman.operations.scaffold_list` | List the data commands of a tool and the operations that use them | no |
| `retman scaffold draft` | `retman.operations.scaffold_draft` | Draft an operation from a command of a tool, for review by hand | no |

The operations that a Polish command can select, 30 operations in 7 categories (a command that names none of them is `unsupported`):

| Category | Id | Tool | Operations | Data source |
|---|---|---|---|---|
| Spatial data: DEM, DSM, orthophoto, BDOT10k | `spatial_data` | Kartograf 0.8.0 | 4 | GUGiK |
| Stations and data register | `imgw_catalog` | IMGWTools 3.0.0 | 3 | IMGW-PIB, ČHMÚ |
| Current data and warnings | `imgw_current` | IMGWTools 3.0.0 | 3 | IMGW-PIB |
| Maximum precipitation PMAXTP | `imgw_pmaxtp` | IMGWTools 3.0.0 | 2 | IMGW-PIB |
| Station time series | `imgw_series` | IMGWTools 3.0.0 | 3 | IMGW-PIB, ČHMÚ |
| Archives and the data store | `imgw_archives` | IMGWTools 3.0.0 | 8 | IMGW-PIB, ČHMÚ |
| Data projects | `imgw_projects` | IMGWTools 3.0.0 | 7 | IMGW-PIB, ČHMÚ |

## For AI agents

Retman is built to be driven by agents as well as by people. [llms.txt](https://raw.githubusercontent.com/Daldek/Retman/main/llms.txt) and [AGENTS.md](https://raw.githubusercontent.com/Daldek/Retman/main/AGENTS.md) describe the commands, the result envelope, the error codes and the typical flows; both are generated from the command catalog and never edited by hand.

- `retman commands guide --format agents` prints `AGENTS.md`, `--format llms` prints `llms.txt`, and `--format agents-md-block --inject AGENTS.md` puts a compact block into the `AGENTS.md` of another repository.
- `retman commands list` lists the commands and `retman commands schema --command "plan run"` describes one: options, effects, errors and examples.
- Every command prints the envelope `retman-result/1` with `--json`: one line on stdout, never a prompt. `partial` (exit 10) and `failed` (exit 11) are outcomes that print the envelope; an error ends stderr with a `retman-error/1` document.
- `plan run --check` plans without effects and writes nothing; `--yes` runs a complete plan and belongs after the user has seen it. `config init`, `eval run` and `commands guide` accept `--check` too and report each file they would write as `write`, `replace` or `conflict`.
- The command text is the user's Polish sentence: pass it unchanged.

## Related tools

- [Kartograf](https://github.com/Daldek/Kartograf) downloads Polish and Czech geodata into a versioned store; Retman calls its Python library (command catalog `kartograf-catalog/1`).
- [IMGWTools](https://github.com/Daldek/IMGWTools) provides IMGW-PIB and ČHMÚ hydro-meteorological data, PMAXTP and a versioned store; Retman calls its Python library.
- [Hydrolog](https://github.com/Daldek/Hydrolog) (hydrological calculations) and [Hydrograf](https://github.com/Daldek/Hydrograf) (watershed delineation and design hydrographs) are planned Retman tools.
- [Archiwista](https://github.com/Daldek/Archiwista) browses and manages the stores of Kartograf and IMGWTools.
- [Nogat](https://github.com/Daldek/Nogat) is the hub of the ecosystem: the standards, the registry of the tools and the shared settings file `nogat.toml`.
- When the exact call is known, the CLI of the tool is shorter; when an assistant has to call the tools in any language through MCP, use the MCP servers of Kartograf and IMGWTools. Retman is for Polish sentences and a plan that a person confirms.

## Errors and exit codes

Exit codes are the codes of the [shared Nogat error registry](https://github.com/Daldek/Nogat/blob/main/standards/ERROR_REGISTRY.md): the same code means the same in every tool. On an error the last line of stderr is a `retman-error/1` document with `code`, `title`, `message`, `hint`, `details` and `exit_code`; `details.reason` narrows the code. The five you meet first:

| Code | Exit | Meaning and what to do |
|---|---|---|
| `validation_error` | 2 | A wrong option, invalid settings, or an answer or confirmation is needed and there is no terminal (`details.reason` `invalid_config`, `input_required`): read `details.option` or `details.keys` |
| `not_found` | 3 | The settings file, an input file or a result does not exist: see `hint`, or run `retman config init` |
| `source_unavailable` | 5 | The model server or a data service did not answer: run `retman doctor check` |
| `missing_dependency` | 6 | A tool is not installed in a supported version: install it as `hint` says |
| `unsupported` | 15 | The command matches none of the operations (`details.operations` lists them): rephrase it |

## Data and licensing

Retman holds no data. The tools download it: Kartograf and IMGWTools write the files into their own versioned stores, `<data_dir>/kartograf` and `<data_dir>/imgw` by default, and Retman records their paths and SHA-256 sums in its results. What Retman itself writes goes to the project folder where it runs: the numbered results in `retman-output/`, the project journal and, only with your consent, the collection of commands. The terms of every source (IMGW-PIB regulations, ČHMÚ licence CC BY 4.0, GUGiK open data) are those of the source; the tools put the licence into the sidecar of each file, and Retman shows their licence and data-quality notes as warnings after the result and keeps them in `notices`. The duty to attribute the source when publishing results is the user's.

The stores are versioned on hard links: copy them with the links preserved (`rsync -aH`), not by copying files one by one, and note that data that the source has removed cannot be downloaded again (details in the README of each tool).

The settings are the `[retman]` tables of `nogat.toml`, which the Nogat tools share (on Linux `~/.config/nogat/nogat.toml`; another file is named by `NOGAT_CONFIG` or `--config PATH`). The file is optional except for the model server, which has no default, and a variable overrides the file. A value comes from the first of: the command-line option, `RETMAN_<KEY>` (the dotted key in capitals with underscores: `decision.url` is `RETMAN_DECISION_URL`), `NOGAT_<KEY>` (shared keys only), the `[retman]` table, the `[nogat]` table (shared keys only), the default. `retman config show` lists every setting with its value and source. Credentials are never in the file: Retman reads the key of an external model provider from the variable that `decision.api_key_env` names.

| Variable | Meaning |
|---|---|
| `NOGAT_CONFIG` | the settings file `nogat.toml` (default: in the user configuration folder) |
| `RETMAN_LANG`, `NOGAT_LANG` | language of the texts for people (questions, plan, messages, reports, `--help`): `pl` (default) or `en`; the texts inside `--json` documents are always English |
| `RETMAN_LOG_LEVEL`, `NOGAT_LOG_LEVEL` | level of the technical log on stderr: `debug`, `info`, `warning` (default), `error` |
| `RETMAN_DATA_DIR`, `NOGAT_DATA_DIR` | folder of the data stores and of the command collection (default: the user data folder of nogat) |
| `RETMAN_CACHE_DIR`, `NOGAT_CACHE_DIR` | folder of the caches (default: the user cache folder of nogat) |
| `RETMAN_DECISION_BACKEND` | `basal` or `openai_compatible` |
| `RETMAN_DECISION_URL`, `RETMAN_DECISION_MODEL` | address of the model server and the name of the model |
| `RETMAN_DECISION_TIMEOUT_S` | how many seconds to wait for the model server |
| `RETMAN_DECISION_API_KEY_ENV` | the NAME of the variable that holds the key of an external model provider |
| `RETMAN_DECISION_CONFIDENCE`, `RETMAN_DECISION_CONSISTENCY_RUNS` | confidence method and number of queries (backend `openai_compatible`) |
| `RETMAN_DECISION_THRESHOLDS_OPERATION`, `RETMAN_DECISION_THRESHOLDS_PARAMETER` | confidence thresholds: a number in (0, 1], or `auto` (basal only) |
| `RETMAN_TEXT_BACKEND` | the text model (`none` for now) |
| `RETMAN_OUTPUT_RESULTS_DIR` | results folder inside the project folder (default `retman-output`) |
| `RETMAN_ADAPTERS_ENABLED` | the tools to enable, separated by commas (default: every installed one) |
| `RETMAN_TOOLS_KARTOGRAF_STORE_DIR` | the Kartograf store (default `<data_dir>/kartograf`) |
| `RETMAN_TOOLS_KARTOGRAF_CACHE_FILE` | the metadata cache of Kartograf (default `<cache_dir>/kartograf/metadata.db`) |
| `RETMAN_TOOLS_KARTOGRAF_WORKERS`, `RETMAN_TOOLS_KARTOGRAF_UPDATE` | parallel transfers; update mode `local`, `upgrade` or `force` |
| `RETMAN_TOOLS_IMGWTOOLS_STORE_DIR` | the IMGWTools store (default `<data_dir>/imgw`) |
| `RETMAN_TOOLS_IMGWTOOLS_REFERENCE_DATA_DIR` | the reference data of IMGWTools (default `<cache_dir>/imgw/reference`) |
| `RETMAN_LOG_JOURNAL_COMMANDS` | whether the project journal records the text of commands and answers (default `true`) |
| `RETMAN_PRIVACY_COLLECT_COMMANDS`, `RETMAN_PRIVACY_COLLECT_PATH` | collection of commands from all projects, with consent only (default off), and its file |

## Documentation

| File | Content |
|---|---|
| [USAGE.md](https://github.com/Daldek/Retman/blob/main/docs/USAGE.md) | Working with Retman: commands, questions, plans, results, Python, diagnostics, with examples |
| [ARCHITECTURE.md](https://github.com/Daldek/Retman/blob/main/docs/ARCHITECTURE.md) | Technical design: architecture, tool adapters, models, settings |
| [PRD.md](https://github.com/Daldek/Retman/blob/main/docs/PRD.md) | Product requirements: users, scenarios, scope of the versions |
| [DECISIONS.md](https://github.com/Daldek/Retman/blob/main/docs/DECISIONS.md) | Architecture decision records (ADR) |
| [CHANGELOG.md](https://github.com/Daldek/Retman/blob/main/docs/CHANGELOG.md) | Changes per release |

## Development

Rules, commands and the documentation map for people and agents who work on the code are in [CLAUDE.md](https://github.com/Daldek/Retman/blob/main/CLAUDE.md); `scripts/gate.sh` runs the formatting, lint, type and test checks and must pass before every commit. The contribution workflow is in [CONTRIBUTING.md](https://github.com/Daldek/Retman/blob/main/CONTRIBUTING.md).

## Status, licence, author

Under construction (before v0.1.0). Working: four Kartograf 0.8.0 operations (DEM for a map sheet or an area from a file, child sheets with the orthophoto in three colour variants, a DEM or DSM cutout, BDOT10k) and 26 IMGWTools 3.0.0 operations (two-stage recognition: category, then operation), from the CLI and from Python, with a decision model on any OpenAI-compatible server (for example Bielik 11B in LM Studio); the offline plan preview, the availability check on request, `retman doctor check`, `retman eval run` and `retman scaffold`. The `basal` backend does not exist yet. Versions 0.x are public but not recommended for production before 1.0.0.

MIT licence, see [LICENSE](https://github.com/Daldek/Retman/blob/main/LICENSE). Author: [Piotr de Bever](https://www.linkedin.com/in/piotr-de-bever/).

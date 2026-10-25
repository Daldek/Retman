# Retman — Architecture

> **Document status:** draft (2026-10-11, updated 2026-10-25) · **Licence:** MIT · **Document language:** English
> **Product requirements and scope:** [PRD.md](PRD.md)

This document describes **how** to implement the requirements from the PRD. Markers in square brackets,
e.g. [W-02] or [N-03], point to the PRD requirements that a given part implements.

---

## 1. Design principles

### 1.1. Principles

| Principle | What it means in practice | Requirements |
| --- | --- | --- |
| **Tools know nothing about Retman** | Hydrograf and the rest contain no code, files or dependencies related to Retman. Retman uses only their public Python API (section 3.2; not their MCP servers, section 3.2.1). The only possible exception in the future: an optional chat panel in the GUI (section 7.4). | [N-03] |
| **Retman does not contain a model** | The model is a separate service (e.g. LM Studio, Ollama, basal-serve, a provider's API) that Retman connects to via an API. The code does not depend on a specific model — the choice of model is just configuration (section 3.3). | [N-02], [N-10] |
| **Code computes numbers, not the model** | The model chooses the operation and options. Coordinates, dates, probabilities and other values are extracted and checked by code. | [W-01], [W-08] |
| **Lists for choices, numbers for values** | Methods or analysis types are a choice from a list. Continuous values (e.g. probability) are numbers, not lists. | [W-08] |
| **No silent guessing** | When confidence is too low or data is missing, Retman asks follow-up questions. When several earlier results match, it asks which one to use (section 5.3). Default values and earlier results are always shown in the plan. | [W-02], [W-04], [W-07] |
| **Always confirmation before execution** | The user sees the plan and approves it. In 0.x versions without exceptions (section 6.3). Confirmation cannot be loaded from a saved plan. | [W-05] |
| **No network before confirmation** | Before `plan.confirm()` Retman calls no tool function with a network or write side effect: planning consists of extractors in code, offline validation by the tool and a plan preview, and the planning code sees only the offline half of the tool client (section 3.2.4). Network access comes only after the plan is confirmed or — as a separate step with its own consent — in the availability check (section 6.5). The model server is outside this rule (N-04). | [N-12], [W-17] |

### 1.2. Deliberate design limitations

- **The model does not plan chains.** Chains (v0.2) are built by code based on dependencies between
  operations, and the model only chooses the goal and parameters (section 4.5).
- **Tool catalogs and documentation are not read at runtime.** They serve for drafts
  and conformance checks of descriptions (section 3.2.3); options in manifests are static.
- **No execution mode without confirmation** in 0.x versions and no tool network access before
  confirmation, apart from the on-demand availability check.

### 1.3. Language

| Element | Language |
| --- | --- |
| Code: identifiers, operation and parameter names, comments, docstrings | **English** |
| Texts for the user and the model: questions for basal, option descriptions, messages, plan | **translation files** (section 4.2): Polish by default, English on request (`lang`); machine output is English (AGI-9.2) |
| README, PRD, this document and other documents outside the code | **English** |

Texts for the user and the model must not be written in the code, because basal works best
when the questions and options are in the same language as the command (section 3.4). That is why they go
into translation files, and the code refers to them through English keys.

---

## 2. How it works

Every command goes through six steps [W-01], [W-02], [W-04], [W-05], [W-17], [N-12]:

```
 User command
        │
        ▼
 1 OPERATION RECOGNITION ─── decision model: "which operation to choose?" (choice);
        │                    with more than 9 operations: the category first, then the operation (section 3.4)
        ▼
 2 PARAMETERS FROM LISTS ─── decision model: "which data kind? which method?" (choice)
        │
        ▼
 3 FREE PARAMETERS ───────── code: extractors (coordinates, dates, probabilities, stations, files)
        │                    + workspace (earlier results, chapter 5)
        ▼
 4 VALIDATION AND QUESTIONS  what is missing? what has too low confidence? → a question to the user;
        │                    the complete plan is checked offline by the tool (preview): a rejection → the question again
        ▼
 5 PLAN + CONFIRMATION ───── "Pobiorę dobowe opady ze stacji Poznań (2000–2020). Wykonać?" (the plan, in Polish)
        │                    optionally `s`: availability check (network, separate consent, section 6.5)
        ▼  ─────────────── up to here no network of the tools (N-12) ───────────────
 6 EXECUTION + DESCRIPTION ─ calls or a handler in Retman → public API of the tool → result
                            → saved in the workspace → (optionally) a description in Polish by the text model
```

### Example (single operation, decision model: basal)

Command: *"Pobierz dobowe opady ze stacji Poznań z lat 2000–2020"* (fetch daily precipitation
from the Poznań station for the years 2000–2020)

| Step | Who | Result |
| --- | --- | --- |
| ① | basal | operation = `fetch_imgw_data` (confidence 0.96) |
| ② | basal | `variable` = `precipitation` (0.98), `interval` = `daily` (0.94) |
| ③ | extractors | station "Poznań" → matched against the IMGW station list; period = 2000-01-01 – 2020-12-31 |
| ④ | validator, tool | all required parameters are present, confidences above thresholds; if several stations matched the name "Poznań", Retman would ask which one is meant; the tool checks the complete plan offline (e.g. a year before the start of the series) |
| ⑤ | Retman | shows the plan (with preview rows) and waits for confirmation; the user may first request an availability check (`s`) |
| ⑥ | IMGWTools call executor in Retman | executes the IMGWTools catalog commands, saves the result in the workspace (chapter 5) |

> The example is illustrative: operation and parameter names will be fixed together with the list of operations (PRD).

When an operation requires data that the command does not contain (e.g. flow requires catchment
characteristics), Retman in v0.1 looks for it in a file indicated in the command or in earlier
results (chapter 5). If it is not there, it reports what is missing. Adding steps automatically
is chains in v0.2 (section 4.5).

---

## 3. Architecture

### 3.1. Modules

```
src/retman/
├── catalog/
│   ├── spec.py              # Command, Option and Rule: the declarations (AGI-2.2, AGI-2.3)
│   ├── commands.py          # the commands of the catalog: the one declaration of every interface (AGI-1.1)
│   ├── describe.py          # the catalog as text for people: --help and the terminal view
│   ├── dispatch.py          # lookup, validation, catalog documents and execution of commands (AGI-2.1)
│   ├── envelope.py          # the result envelope retman-result/1 and the return protocol of operations (AGI-4.2)
│   └── document.py          # serialization of the catalog: retman-commands/1 and the command list
├── operations/              # one function per catalog command: plan_run, config_show, doctor_check ... (section 7.1)
├── cli/
│   ├── main.py              # retman <group> <verb>: parse, run through the catalog, report (section 6.4)
│   ├── parser.py            # the command line, generated from the catalog (AGI-3.1)
│   └── conversation.py      # the conversation in a terminal, built on core/dialog.py (section 6.4)
├── core/
│   ├── pipeline.py          # steps ①–⑥, main logic; Retman.check() (section 6.5)
│   ├── plan.py              # Plan object (operation + parameters + confidences + sources, review state, consent)
│   ├── result.py            # Result object (section 7.3)
│   ├── check.py             # CheckReport: the availability check report (section 6.5)
│   ├── geometry.py          # geometry files as areas: GeoPackage layers (stdlib sqlite3), checksums (section 6.1)
│   ├── workspace.py         # project results: numbering, lookup by kind, input selection (ch. 5)
│   ├── journal.py           # project journal and audit data (section 5.4)
│   ├── collection.py        # optional collection of commands from all projects (section 5.4, ADR-010)
│   └── dialog.py            # questions and answers, independent of the user interface (section 6.4)
├── registry/
│   ├── operation.py         # internal Operation and parameter model; two-stage recognition helpers (section 3.4)
│   ├── manifest.py          # manifest schema, hook output types and validation (section 4.1)
│   └── loader.py            # loading tool descriptions, checking installed tool versions, category limits
├── adapters/
│   ├── catalog.py           # command layer: CatalogCall, ToolRun, ToolError, PlanClient/RunClient, ToolContext, run_calls (section 3.2.4)
│   └── manifest_adapter.py  # generic adapter: params → handler/calls → Result; offline preview, availability check
├── tools/                   # descriptions, call builders, clients and handlers for each supported tool (section 3.2.2)
│   ├── imgwtools/
│   ├── kartograf/
│   └── hydrograf/, hydrolog/, basichydraulics/   # planned (v0.2)
├── devtools/                # retman scaffold: readers of the tool catalogs, draft, drift check, the light check of doctor (section 3.2.3)
├── kinds.py                 # registry of data kinds and their file validators (section 3.2.6)
├── i18n/
│   ├── loader.py            # loading translation files; Message: an English text that can be shown in Polish
│   ├── pl.toml              # Polish texts for core messages, the answer words and the Polish catalog texts
│   └── en.toml              # English texts for core messages and the answer words (the catalog texts are English in catalog/commands.py)
├── backends/                # connections to separately installed models (section 3.3)
│   ├── base.py              # DecisionBackend and TextBackend interfaces
│   ├── openai_compatible.py # any OpenAI-compatible API: LM Studio, Ollama, vLLM, providers
│   └── basal.py, native/    # basal-serve API (blocked: no specification) and providers with their own API (v0.2); not written yet
├── extractors/
│   ├── base.py              # Match, Reading, Hint and ExtractionContext: offline facts for context-aware extractors (section 4.3)
│   ├── text.py              # folding, word spans and typo tolerance shared by the extractors
│   ├── coordinates.py       # points (WGS84, PL-1992 converted in pure Python) and PMAXTP grid cells
│   ├── areas.py             # areas: map sheet codes (godło), bounding boxes, TERYT codes, geometry files (ADR-001, ADR-016)
│   ├── crs.py               # coordinate systems and their role: input rectangle vs result (ADR-009)
│   ├── numbers.py           # Polish numerals and durations (15 min, 2 godziny)
│   ├── probability.py       # exceedance probability and return period (section 4.4)
│   ├── dates.py             # years, periods and the kind of year (hydrological or calendar)
│   ├── stations.py          # station names and codes → the offline station catalog of the IMGWTools store
│   ├── places.py            # place and river names as search fragments for the station search
│   ├── variables.py         # measured variables checked against the chosen dataset
│   ├── identifiers.py       # names given by the user (e.g. a project task)
│   ├── paths.py             # file paths mentioned in the command
│   └── results.py           # result numbers mentioned in the command, e.g. "#3" (section 5.2)
├── chains/                  # chain building from input/output dependencies, resolver.py (v0.2; not written yet)
├── eval/
│   ├── runner.py            # retman eval run: plans the test command set, prints the report (section 8.2)
│   ├── dataset.py           # loading and validating the test command set (section 8.1)
│   ├── metrics.py           # quality measures, threshold curve (section 8.2)
│   ├── report.py            # Markdown report (section 8.2)
│   ├── offline.py           # offline tool clients, placeholder geometry files and a station catalog for a run
│   └── commands.jsonl       # test command set, shipped as package data (section 8.1)
├── agent_guide.py           # generator of AGENTS.md and llms.txt from the catalog (AGI section 8); templates in _data/agents/
├── schemas/                 # JSON Schemas of the domain documents (AGI-4.1)
├── environment.py           # the sources of the settings: nogat.toml, variables, user directories (DEV-18.1)
├── config.py                # the settings: [retman] of nogat.toml, checked and written out (section 9.1)
├── config_show.py           # retman config show (DEV-18.6)
├── config_template.toml     # the commented template that `retman config init` writes (section 9.1)
├── initialize.py            # retman config init in a terminal: questions, store folders, IMGWTools store (section 9.1)
├── doctor.py                # retman doctor check: environment check (section 7.2)
├── stores.py                # tool stores on disk: checks for doctor, set-up for config init (section 9.1)
├── logs.py                  # the technical log: one handler on stderr (DEV-12, section 5.4)
├── outcomes.py              # exit codes, error documents, SIGTERM (ERR-4)
├── exceptions.py, _errors.py  # RetmanError hierarchy (sections 6.3, 6.5); the registry, generated (ERR-3)
├── testing.py               # test helpers: FakeDecisionBackend, FakeToolClient, tool_context (section 8.3)
└── add_tool.py              # retman add-tool: installs a known tool via uv (v0.5+, section 9.4; not written yet)
```

### 3.2. Adapters: how Retman connects to the tools [N-03], [W-06]

#### 3.2.1. Principle: the tools know nothing about Retman

The tools contain no code, files or dependencies related to Retman.
Everything Retman needs lives in the Retman repo, and it uses the tools exclusively
through their **public Python API** — just like any other user of these libraries.
The tools' MCP servers (`kartograf-mcp`, `imgw mcp`) are not used (ADR-018): they are a thin layer
over the same library calls, they would add dependencies, and the W-05 and N-12 gates would have
to be maintained in a separate process with its own write policy.

From the tools Retman expects only good practices that are beneficial regardless of it:
- a **stable public API** and semantic versioning (a compatibility-breaking change = new major version),
- a **machine-readable command catalog** (command names, options with allowed values, effects:
  network and writes), **offline validation** (`validate_command`), JSON result documents with a
  `schema` field and stable error codes — Kartograf 0.8.0 and IMGWTools 3.0.0 have these, and the
  command layer builds on them (section 3.2.4),
- for tools without a catalog: **type hints**, especially `Literal` (or `Enum`) for choices
  and `Path` for files, plus **NumPy-style docstrings**.

#### 3.2.2. What lives in Retman

```
src/retman/tools/hydrolog/
├── manifest.py    # operations: params, inputs, outputs, supported versions (section 4.1)
├── handlers.py    # thin wrappers around the hydrolog public API (section 3.2.4)
├── pl.toml        # Polish texts and synonyms (section 4.2)
└── en.toml        # English texts, the same keys (section 4.2)
```

A tool with a command catalog (Kartograf, IMGWTools) additionally has, in the same folder,
call builders, a client, and preview and check functions (section 3.2.4).

| Element | Role |
| --- | --- |
| **Manifest** | description of the operations: parameters, allowed values, inputs and outputs, supported tool versions, references to builders, preview and check |
| **Call builders** | pure functions that turn Retman parameters into calls to the tool's catalog commands (`CatalogCall`); the same ones serve validation in the plan and execution |
| **Tool client** | one thin class per tool: imports it lazily, translates calls into its public API, tool errors into `ToolError`, and result documents into `ToolRun` |
| **Handlers** | functions that call the public API (or the shared call executor) and turn results into files — where the result requires processing |
| **Preview and check** | an offline function that supplies plan rows and problems (preview), and an on-demand network function (availability check) |
| **Translations** | Polish texts and synonyms for basal and the user, error and warning messages |
| **Shared adapter** | one for all tools: validates parameters, executes calls or a handler, builds `Result` |
| **Data kind registry** | `kind` names and their file formats (section 3.2.6) |

Rules:
- **Each operation is described once**, with the tool that actually executes it. Hydrograf
  imports Hydrolog, but the Hydrograf description does not repeat Hydrolog's operations.
- Composite procedures that a tool already has (e.g. in Hydrograf) are **one operation**.
  Retman does not recreate them step by step.

#### 3.2.3. Role of catalogs and tool documentation

Command catalogs and tool documentation are the **source from which Retman generates drafts
and checks the conformance of its descriptions**. They are not read at runtime, and manifests are static
(ADR-019): options are never derived from the installed tool at load time. Reasons:

1. every option needs Polish texts and synonyms, otherwise the tool will not load,
   and machine-written text would violate section 1.3 and ADR-007;
2. the catalog does not have the shape of Retman's options: Kartograf's allowed resolutions are
   the sum of 14 values across products and countries, while basal accepts 9 options (section 3.4) —
   the correct values depend on the product and the vertical reference system;
3. the `retman eval run` set must be repeatable, and the contents and order of the catalog change
   between tool versions; the descriptions stored in Retman are reviewed, tested
   and change only deliberately;
4. loading manifests must not import the tools (section 3.2.5), and a small model will not reliably
   build a call from the description alone.

**The developer tool `retman scaffold`** (package `retman.devtools`, for the author, not for
the end user; a command group of the `retman` executable, with no dependencies of its own) reads the machine
catalogs of the tools (Kartograf's and IMGWTools' `list_commands` and `command_schema`) through
small readers in `src/retman/devtools/readers/` — with no network access:

```bash
retman scaffold list --tool <tool>        # catalog commands, which operations use them, suggested use
retman scaffold draft --tool <tool> --command "<command>" [--fix k=v] [--only a,b] [--id op] [--write] [--check]
retman scaffold check [--tool T] [--operation OP] [--commands FILE] [--require-tools] [--include-info]
```

The draft (`draft`) overwrites nothing: it writes to standard output, and with `--write` to
`src/retman/tools/<tool>/_drafts/` (a folder outside git). The author fills in what the catalog does
not have (table below); Polish texts, category, data kinds and extractors carry a `TODO` marker
in the draft, and a test rejects every such marker in an approved `pl.toml`. A check prints the envelope
`retman-result/1` with `--json`; its exit code is `0` when every tool passes, `10` (`partial`) or `11` (`failed`)
when errors were found in some or in all tools, and `2` for incorrect usage (ADR-022).

**What can be read from the catalog and what has to be added by hand:**

| Information | From the tool catalog? |
| --- | --- |
| parameters, their types and whether required | yes (Kartograf: command parameter description; IMGWTools: command JSON schema) |
| allowed choices | yes (`allowed`, `enum`), but as a sum across products and countries — the values valid for an operation are narrowed by a trial through `validate_command`; lists longer than 9 have to be split |
| default values | yes, but Retman does not adopt them: there are no hidden default values (ADR-006) |
| value ranges | IMGWTools yes (`minimum`, `maximum`); Kartograf usually has to be added by hand |
| dependencies between parameters | partially (description of constraints); they are enforced by `validate_command` |
| description in English | IMGWTools yes; Kartograf only in Polish, without diacritics |
| command side effects (network, writes) | yes |
| input and output files | only as product names; the data kind (`kind`) has to be added by hand |
| Polish texts and synonyms | no — have to be added by hand |
| which commands to expose in Retman | no — the author's decision |

**Conformance check** (`retman scaffold check`, ADR-019) is **conformance by execution**: for
every installed tool within the supported version range it runs the real call builders
on a grid of choices from the manifest, and every call is checked offline by the tool itself
(`validate_command`, just as in the plan). The whole thing runs under a guard that records every attempt
to use the network and every file created. The coverage invariant (X4) makes "all resolutions"
true by construction: a new tool value does not appear unnoticed.

| Check | What it finds | Severity |
| --- | --- | --- |
| X1 | a declared command that is not in the catalog or that is not a data command; a builder emits an undeclared command | error |
| X2 | a rejection that is not an answer the user can change (missing or unknown option, a rejection that does not point to a parameter); rejected pairs of the Cartesian grid (e.g. 5 m with KRON86) are only reported | error; info |
| X3 | a manifest option that the tool does not accept at any point of the grid | error |
| X4 | **coverage:** a value the tool accepts that the manifest neither offers nor lists in `excluded` | error |
| X5 | an obsolete `excluded` entry | warning |
| X6 | a default value on an option required by the tool, or an optional parameter after such an option (ADR-006) | warning |
| X7 | the client's `lookup` accepts a command with side effects; the offline check touched the network or wrote a file; an operation with a network and writing command without `check` and without a justified `no_check`; `no_check` on an operation none of whose commands needs it | error; warning |
| X8 | a tool error code without a `[errors.<code>]` text; a document schema unknown to the client | error |
| X9 | data commands of the catalog that no operation exposes | info |
| X10 | no complete `retman eval run` row with free values for the operation (the grid was not built) | warning |

The check runs in pytest and in Retman's CI (section 3.2.7).

#### 3.2.4. Calls, handler, preview and check

Translating "Retman's language" into a call to the tool's public API lives in Retman and takes
two forms; an operation declares at least one of them (section 4.3):

- **`calls` — the command layer.** For tools with a command catalog (Kartograf, IMGWTools): a pure
  *call builder* turns the parameters into a list of catalog command calls, and a shared executor
  runs them through a *tool client* (`src/retman/adapters/catalog.py`). Reason: the catalog is the
  declared source of truth for these tools — it has offline validation with the same rules as a
  run, stable error codes and result documents — whereas the typed functions and provider classes
  changed in Kartograf 0.8.0 in a way that broke every handler (ADR-013).
- **`handler` — a custom function.** For operations that must post-process the result (e.g. unpack
  an archive) or for tools without a catalog. The handler may itself call the shared executor
  (`run_calls`) or the client (`ctx.runner`).

**Calls and the client.** The builder is pure: it touches neither the file system nor the network
and is called twice by the same code — in the plan (validation) and at execution:

```python
# src/retman/tools/<tool>/calls.py (illustrative)
def fetch_dem(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    area = params["area"]
    options = {
        "product": "nmt",
        "resolution": ctx.tool_value("resolution", params["resolution"]),   # "0_5m" -> "0.5m"
        "sheet": area["code"],
    }
    return [CatalogCall("elevation download", options, kind="dem", params={"sheet": "area"})]
```

`CatalogCall` carries: `command` (the catalog command), `options` (in JSON form, exactly as
`validate_command` and `run_command` accept them; **without** environment arguments — the store,
thread count, cache, update mode — because the client adds those from `[retman.tools.<tool>]`, section 9.1),
`kind` (the kind of files the call produces: the key in `files`) and `params` (tool option →
Retman parameter, when the names differ; it routes a rejection by the tool to the parameter that
must be asked about again). A composite operation is several calls; the executor stops at the
first call that ends `failed` or `cancelled`, while `partial` continues with warnings.

The client is **split by capability**, so the gate [W-05], [N-12] follows from the code structure:

| Object | Where it exists | Methods |
| --- | --- | --- |
| `PlanClient` (wrapped in `PlanView` for planning code) | in planning: builders, preview, context extractors | `validate(call)` — validation by the tool, offline; `command_line(call)` — the exact command line (offline, for the audit trail); `lookup(call)` — a command without side effects (no network and no writes), e.g. the station list from the store; any other command is `ToolError("not_offline")` |
| `RunClient` (adds to `PlanClient`) | only in `execute()` and in `Retman.check()` after consent to the check | `run(call)` — a data command (writes to the tool's store); `check(call)` — the tool's freshness plan (network step); `query(call)` — a read-only network query (e.g. an availability report) |

`PlanView` has no `run`, `check` or `query` attributes: a network step before confirmation is
impossible by construction, not merely by convention. The client comes from a factory in the
manifest (key `client`): `factory(settings) -> RunClient` receives the validated
`[retman.tools.<tool>]` table, may not use the network or write anything on creation, is built
lazily, once per `Retman` and tool, and an `ImportError` ends in a `RetmanError` with a hint to run
`retman doctor check`. The client reports tool errors as `ToolError` (stable `code`, the option or options
affected, allowed values, the tool's text and hint) and results as `ToolRun` (`status`: `ok`,
`partial`, `failed`, `cancelled`; files with SHA-256 checksum and version label; failures; notices
`info`, `warning`, `error`; the full JSON document; the exact command line; the document schema).

Everything the builder, preview, check and handler are allowed to know about their surroundings is
carried by `ToolContext`: `tool`, `settings` (the `[retman.tools.<tool>]` table), `project_dir`,
`output_dir` (`None` in planning — the results folder does not exist yet), `inputs` (validated
inputs), `client`, `specs` (the operation's parameters from the manifest), `operation` (the
operation being planned or executed — so that a handler can hand plain catalog calls to the
`run_calls` executor) and the helpers `ctx.runner` (the full client; raises an error in planning),
`ctx.store_dir`, `ctx.tool_value(parametr, klucz)` and `ctx.option_meta(parametr, klucz)`.

**Plan preview (offline) [N-12].** When the plan is complete, the adapter runs `preview_operation`:

1. the tool validates every call from the builder (`PlanClient.validate`) — the same request that
   would execute the operation, without network or writes. A rejection (`ToolError` with the option
   or options affected) is routed to Retman parameters (via `CatalogCall.params` or identical
   names) and becomes a question asked again with a reason (`Plan.reopened`, section 6.3).
   An option nested inside another option (e.g. task options in IMGWTools `project add`) has the
   path `options.<name>` in `ToolError.option` and in `CatalogCall.params`, so it also reaches its
   parameter. A rejection that cannot be routed to any parameter is a `ToolDriftError`: the
   installed tool no longer accepts what the manifest describes (`retman doctor check`,
   `retman scaffold check`);
2. if the tool accepted all calls, it calls `preview(params, ctx)`, which returns
   `PreviewOutput` = `{values, rows, problems}`: `values` go only to the audit
   (`result.json["preview"]`), `rows` are additional plan rows (marked
   `← podgląd, bez sieci` ("← preview, no network"); texts `[preview.<key>]`), `problems` are
   further reasons to ask again (a non-empty list of operation parameters and a text key from
   `[problems.<key>]`).

For areas from a geometry file the preview shows e.g. the bounding box and the number of map
sheets, which Retman computes with the tool's public offline functions, so the plan says what the
file actually means for this operation (sections 6.1, 6.3).

**Availability check (network, on request).** `check(params, ctx) -> CheckOutput` =
`{status, items}` is called exclusively by `Retman.check()` after separate consent (section 6.5),
with the full client: `ctx.runner.check(call)` (the tool's freshness plan) or
`ctx.runner.query(call)` (a read-only query). We treat every declared `check` as a network step,
even when the tool in some cases does not connect to the network.

**Result and files.** The executor saves the full document of each call as
`output_dir/tool_<n>_<command>.json` and attaches to the result the audit block `tool` (command,
options, command line, status, files with checksums, document name and checksum; section 5.4). The
operation's `describe` function (or the generic mapping) converts the calls and their results into
`HandlerOutput` = `{values, files, warnings[, tool]}`. Keys in `files` are data kinds (`kind`,
section 3.2.6); a file must lie in `output_dir` **or in the tool's store**
(`[retman.tools.<tool>] store_dir`) — anywhere else is an error. Files from the store are
referenced in the result by absolute path and SHA-256 checksum, without copying anything.

**Messages.** The user sees Retman's own text, selected by the tool's error code, a code of the
shared registry (`[errors.<code>]`, section 4.2; the tool's precision is its `details.reason`, which
stays in the `failure` of the result, ADR-025), and the tool's text only as a quotation (`{detail}`): Kartograf's
is often Polish without diacritics and with command-line flags, IMGWTools' is English. Notices about
data quality and licensing are shown verbatim, because tool documents do not provide structured
numbers or legal wording for them; `info` notices remain in the audit trail. Retman does not
translate the tool's texts: a tool document carries the text, and no message key crosses the
process boundary, so a Polish sentence can quote an English detail, and the licence notice of an
IMGW result is the provider's attribution (Polish, in the wording the terms of use prescribe)
followed by the tool's English notice (ADR-024). The documents saved with the result keep the
originals; the one text that Retman compares is `not published` (section 3.2.11).

Example handler (a tool without a catalog):

```python
# src/retman/tools/hydrograf/handlers.py
from pathlib import Path

import hydrograf  # public API only

from retman.adapters.catalog import ToolContext
from retman.registry.manifest import HandlerOutput


def delineate_catchment(
    params: dict, inputs: dict[str, Path], output_dir: Path, ctx: ToolContext
) -> HandlerOutput:
    """
    Delineate a catchment for a point using the hydrograf public API.

    params     – validated parameter values, e.g. {"point": {"latitude": 52.41, "longitude": 16.93, ...}}
    inputs     – input files by input name (none for this operation)
    output_dir – the only directory the handler may write to
    ctx        – [retman.tools.hydrograf] settings and the tool's client (section 3.2.4)
    """
    point = params["point"]
    catchment = hydrograf.delineate(lat=point["latitude"], lon=point["longitude"])  # illustrative name of a public function

    out_file = output_dir / "catchment.geojson"
    catchment.to_geojson(out_file)                     # illustrative method

    return {
        "values": {"area_km2": catchment.area_km2},     # short results
        "files": {"catchment_characteristics": [out_file]},  # key = output kind, value = list of paths
        "warnings": [],
    }
```

> The Hydrograf function names in the example are illustrative.

Rules for handlers and builders:
1. **Only the tool's public API** — no references to private members (`_nazwa`).
2. **Input data arrives as files**, results leave as files in `output_dir` or in the tool's store.
   Keys in `files` are data kinds (`kind`, section 3.2.6). Converting tool objects to files (and
   back) is the job of the handler or the client.
3. **No conversation with the user**: no `input()` and no `print()`. Asking follow-up questions and
   messages are Retman's job.
4. **Errors are raised as exceptions.** The client converts a tool error into `ToolError`; the
   common adapter catches every exception and returns `Result(ok=False)` (with `error_code` when it
   is a tool error); a failure of one tool does not block the others.
5. **Writing only to `output_dir`.** The handler does not modify the user's files; the tool's store
   is written by the tool itself, through the client.
6. **Builders, preview and extractors are pure and offline** [N-12]: they do not touch the file
   system or the network and see only `PlanClient`.

#### 3.2.5. What the common adapter does

1. **At startup:** for each tool in `src/retman/tools/` it checks — without importing it —
   whether it is installed and whether its version falls within the supported range
   (section 3.2.7). It loads the descriptions and validates them: uniqueness of identifiers, known
   data kinds, complete translations, rules for the `handler`/`calls`/`client`/`excluded` keys,
   category limits (section 3.4). Operations of tools that are not installed are unavailable
   (`retman doctor check` suggests how to install them).
2. **At planning:** it converts manifests into internal `Operation` objects, which the pipeline
   uses. The tool of the selected operation is imported only now, through the client, and the
   planning code receives only its offline half (`PlanView`): contextual extractors search the
   catalog, and the preview validates calls (section 3.2.4). There is no network and no writing
   (N-12).
3. **At execution:** it builds the full client (`RunClient`), prepares `output_dir` and input
   files, computes checksums of geometry files, calls the handler or the call executor, checks the
   returned files against the `outputs` declaration (kind, validator, location in `output_dir` or
   in the tool's store), translates warnings, builds a `Result` and saves it in the workspace. A
   broken tool does not break the rest: the error is the result of that operation.
4. **At the availability check:** after separate consent it calls the operation's `check` function
   with the full client, translates the report items and returns a `CheckReport`; it does not
   create a result (section 6.5).

#### 3.2.6. Registry of data kinds (`kind`)

A data kind is a name + accepted extensions + a simple offline validator, written exclusively on
the standard library (no geospatial libraries and no network). The registry
(`src/retman/kinds.py`) lives in Retman. Tools do not know these names — calls and handlers take
care of turning their results into files of a given kind. One result may contain several files of
the same kind (e.g. DEM map sheets), so `files` assigns a list of paths to a kind. The validator
checks the extension and the header (or the columns, or the schema), and reports a mismatch as
`KindValidationError` with a reason (a key in `[kinds.errors]` of the translation file).

Kartograf data kinds (ADR-004, ADR-016) — the format is whatever Kartograf returns:

| `kind` | Format | The validator checks, among others |
| --- | --- | --- |
| `dem` | DEM (NMT): ESRI ASCII Grid (`.asc`, map sheets) or GeoTIFF (`.tif`, cutout) | extension; `ncols` header (ASC) or TIFF signature |
| `dsm` | DSM (NMPT): as `dem` | as `dem` |
| `orthophoto` | GeoTIFF (`.tif`) | TIFF signature |
| `topographic_vector` | BDOT10k: GeoPackage (`.gpkg`) or Shapefile (`.shp`) | SQLite header (GPKG) or Shapefile file code |
| `dem_archive` | DEM 100 m: ZIP archive with an XYZ file per voivodeship (`.zip`) | ZIP signature |
| `area_geometry` | user file with area geometry: GeoPackage or Shapefile | as `topographic_vector`; validates the area from a file in the plan (section 6.1), also reserved as the output kind of future operations (chains, v0.2) |

IMGWTools data kinds (ADR-017) — tabular files and JSON documents; validators read only the
beginning of the file (header and the first few rows):

| `kind` | Format | The validator checks, among others |
| --- | --- | --- |
| `station_list` | station list (CSV) | columns `provider`, `kind`, `station_code`, `name`, `river`, `latitude`, `longitude` |
| `hydro_series` | time series of a hydrological station (CSV) | header `date,year,<variable> [<unit>],<variable>_flag,…,attribution_source,attribution_processed`; variables H, Q, T (also `_min`, `_mean`, `_max`); ČHMÚ adds `_quality` and `_source_flag` columns |
| `meteo_series` | time series of a meteorological station (CSV) | as `hydro_series`, without hydrological variables |
| `pmaxtp_table` | PMAXTP maximum precipitation (CSV) | columns `duration_min`, `probability_percent`, `ks_mm`, `sg_mm`, `rb_mm`, `attribution_source`, `attribution_processed` |
| `current_hydro` | current hydrological data (CSV) | columns `station_code`, `station_name`, `water_level_cm`, `flow_m3s` |
| `current_meteo` | current meteorological data (CSV) | columns `station_code`, `station_name`, `air_temp_c`, `wind_speed_ms` |
| `current_synop` | current synoptic data (CSV) | columns `station_code`, `station_name`, `measurement_date`, `temperature_c` |
| `imgw_warnings` | IMGW warnings (CSV) | columns `id`, `kind`, `level` |
| `hydro_states` | water states at stations (CSV) | columns `station_code`, `name`, `water_state` |
| `archive_records` | records exported from the archive store (CSV or JSON Lines) | fields `station_code`, `dataset`, `date` (CSV header or first record) |
| `imgw_archive` | IMGW archive as published (`.zip`, `.json`, `.csv`, `.txt`) | ZIP signature, JSON start (`{` or `[`) or non-binary text |
| `imgw_plan` | IMGWTools download or synchronisation plan (JSON) | document with `schema` equal to `imgw-plan/1` |
| `imgw_report` | IMGWTools report (JSON) | `imgw-result/1` document — the first key is `schema` |

The kinds of the remaining tools (Hydrolog, Hydrograf, BasicHydraulics) are an open question
(chapter 12).

#### 3.2.7. Versions and conformance

Guarding conformance is Retman's job, not the tools'. Tools evolve independently,
and Retman adapts to them:

- Each tool has a **supported version range** in its manifest: Kartograf `>=0.8.0.dev0,<0.9`
  (0.x releases may break compatibility), IMGWTools `>=3.0.0.dev0,<4` (semantic versioning and
  `/1` document contracts; ADR-012). The range corresponds to release tags in the tool's
  repository on GitHub; until the `v0.8.0` and `v3.0.0` tags are pushed, the `tools` dependency
  group pins commits (section 9.3) and the range starts at the development version of the pending
  release (`.dev0`, REL-5.6), because PEP 440 puts `0.8.0.dev0` below `0.8.0`; the release change
  that replaces the commits by tags narrows the ranges to `>=0.8.0,<0.9` and `>=3.0.0,<4`. Every
  check of a version (the loader, `retman doctor check`, `retman scaffold check`, the conformance
  tests) reads that one range, as a PEP 440 specifier set with development versions admitted
  (`retman.registry.loader.version_matches`). Retman checks the installed tool's version at
  startup (section 3.2.5); it does not install tools on its own (sections 9.3, 9.4).
- **Retman's CI** runs the handler tests and the conformance check (`retman scaffold check`,
  section 3.2.3) on the oldest and newest supported version of each tool, and regularly
  (e.g. nightly) also on the tools' current main branch — an API change that would break Retman
  surfaces immediately.
- `retman doctor check` shows the installed version of each tool against its supported range.

#### 3.2.8. Tool tests

All tool-related tests live in the Retman repo:
- manifest validation (identifiers, data kinds, complete translations, key rules),
- call builders and result mappers on **recorded real documents** from the tools
  (`tests/fixtures/<tool>/`), with a `FakeToolClient` stub instead of monkeypatching
  the tool's internals (section 8.3),
- tests on real tools with small data, offline (IMGWTools: its packaged fixture store,
  `imgwtools.testing.build_fixture_store`); skipped (`pytest.importorskip`) when the tool is
  absent, plus `live` tests run deliberately,
- conformance check against the current API (`retman scaffold check`).

#### 3.2.9. Ecosystem tools

| Tool | Operation scope | Depends on | Status |
| --- | --- | --- | --- |
| Kartograf | downloading spatial data (DEM (NMT), DSM (NMPT), orthophoto, BDOT10k) | — | v0.1, version 0.8.0 |
| IMGWTools | IMGW-PIB and ČHMÚ measurement data: stations, current data, PMAXTP, time series, archives and store, data projects | — | v0.1, version 3.0.0 |
| Hydrolog | hydrological calculations (flows, methods) | — | planned (v0.2) |
| BasicHydraulics | simple hydraulic calculations | — | planned (v0.2) |
| Hydrograf | catchment delineation, composite procedures | Hydrolog (and others) | planned (v0.2) |

The concrete operations are set by the PRD (section 7.2); descriptions of the Kartograf and
IMGWTools operations: sections 3.2.10 and 3.2.11. Third-party tools are handled the same way:
a description, builders or handlers, and a client in `src/retman/tools/`.

#### 3.2.10. Kartograf 0.8.0 operations

Five operations (ADR-001, ADR-012, ADR-016) in one category, `spatial_data` ("GUGiK spatial
data"). The four data operations go through the command layer (`calls`) and have an offline
preview and an availability check (`check`); the fifth writes the store marker (below the
table):

| Operation (`id`) | Catalog commands | Area (`accepts`) | Parameters Retman asks about | Output kinds |
| --- | --- | --- | --- | --- |
| `download_dem_sheet` — DEM (NMT) for a map sheet or area | `elevation download` | `sheet`, `geometry` | resolution (0.15; 0.5; 0.6; 1; 5; 10 or 100 m); vertical datum (EVRF2007 or KRON86; not applicable to 100 m) | `dem`; DEM 100 m: `dem_archive` |
| `download_sheet_hierarchy` — child map sheets: DEM (NMT), DSM (NMPT) or orthophoto | `elevation download`, `imagery download` | `sheet`, `geometry` (orthophoto only `sheet`) | product; target scale (1:10000 in PL-1992; 1:5000, 1:2000, 1:1000, 1:500 in PL-2000); DEM resolution (0.15–10 m) or DSM resolution (0.5; 0.6; 1 m); vertical datum; orthophoto color (RGB, CIR, B/W) | `dem`, `dsm`, `orthophoto` |
| `download_elevation_cutout` — DEM or DSM 1 m cutout | `elevation download` | `bbox`, `geometry` | product; result CRS (EPSG:2180, 5514, 3045 — read by code, not the model, ADR-009); vertical datum | `dem`, `dsm` |
| `download_bdot10k` — BDOT10k (current county packages) | `landcover download` | `teryt`, `bbox`, `sheet`, `geometry` | format (GeoPackage or Shapefile) | `topographic_vector` |
| `init_kartograf_store` — create the store: write its marker | `store init` | — | — | — |

`init_kartograf_store` has no parameters. `store init` is a command of the catalog like the
others (the command layer of Kartograf takes every command of it), so the operation is a `calls`
builder run by the shared executor, with its own `describe` and `preview`. The client gives the
call the store `root` only: it adds the workers and the update mode to a command only when
`command_schema` declares them, and `store init` does not. The offline preview says what will
happen to the folder (missing or empty: marked; a layout without its marker: checked and marked;
a store with its marker: nothing) or why Kartograf refuses it. The run is offline and idempotent,
saves the document of the tool (the envelope `kartograf-result/1`, whose `result` is the marker,
`kartograf-store-init/1`) as `tool_1_store_init.json` and names the call in the audit like every
other call; it is the way out of the `no_marker` that `retman doctor check` and the plans report
(the command "Utwórz magazyn Kartografa"). It declares no `check`: the plan of `store init
--check` is offline, so an availability step would be a consent notice without a network, and
the preview judges the folder by the same rules (ADR-025 erratum 1).

Kartograf operations have no default values (ADR-006): Retman asks about resolution, vertical
datum, scale, color and format when the command does not include them. All ASC grid resolutions
of Kartograf are supported (ADR-012); whatever the tool nevertheless does not accept is listed
in `excluded` with a justification (e.g. DEM 100 m in child map sheets: those are voivodeship
files). The model is offered the combined list of resolutions to choose from, and an invalid pair
(e.g. 5 m with KRON86) is rejected by Kartograf in the preview, offline — Retman then asks again
about both parameters, with the reason ("Kartograf rejects this choice: …", section 6.3).

**Area from a geometry file** (ADR-016). Kartograf reads the file; Retman only lists GeoPackage
layers (asks when there are several), computes SHA-256 checksums of the files and shows the
bounding box (EPSG:2180) in the preview and — for map sheets — the number of map sheets. What the
file means is stated by the plan (`geometry_note`):

| Operation | Meaning of the file | Notes |
| --- | --- | --- |
| DEM (NMT) for a map sheet, child map sheets | map sheets at the given scale whose bounding box touches the bounding box of any feature in the layer; the polygon shape is not taken into account | a sheet count of 0 is a preview problem |
| cutout | one rectangle covering all features of the layer, with no clipping to the polygon | no data outside the land area of Poland |
| BDOT10k | full packages of all counties intersecting the bounding box | an area outside Poland is rejected by the preview; the list of counties is known only to the PRG service (network, after confirmation or during the check) |
| orthophoto (child map sheets) | the file is not accepted — the tool's provider class takes sheet codes (godło) only | preview problem: Retman asks again for the product and the area |

**Result and store.** Kartograf saves downloaded files in its store (`[retman.tools.kartograf]
store_dir`, always passed as `root`; Retman offers no plain mode of Kartograf, ADR-025) as immutable versions; the result points to them by absolute path and SHA-256 checksum
(section 5.4) and contains the tool document (`tool_<n>_<command>.json`). Exception: for BDOT10k in
Shapefile Kartograf returns ZIP archives in the store, and the mapper unpacks all `.shp` files
together with their companion files into the results folder (rejecting unsafe paths in the archive).
An orthophoto in the chosen colour goes through its own handler (the tool's provider class, ADR-013),
into the same store. Kartograf's notices about data quality (e.g. an incomplete flight, a different
sheet layout, no data for some of the sheets) are shown in the result either with Retman's own text
from `[warnings]` or verbatim; a partial result is a result with a warning.

**The store folder.** Kartograf marks its store with `kartograf-store.json` (schema
`kartograf-store/1`) and writes the marker by itself on the first write into a missing or an
empty folder (a product folder without a file, a staging folder `.incoming` and the temporary
file of a writer that is just marking the folder are no content). Before it writes a byte it
refuses a folder with the layout of a store and no marker (`store_unavailable`, reason
`no_marker`; `store init` verifies the layout and writes the marker), a folder with other files
(`conflict`, reason `not_empty`), a marker that is not a `kartograf-store/1` document
(`data_error`) and a folder that lies in, is or holds the store of another tool or place
(`conflict`, reason `nested_store`). A run into such a folder ends with that one error of the
command, before the index of the sheets is asked, and `--check` lists a root that is a conflict
(`nested_store`, `not_empty`) as the one position of its plan, which the availability check of
Retman reports as `store_refused`. Retman still judges the folder itself, so that a plan that
cannot run is never shown (`retman.stores.kartograf_store_state`: the
rules of `kartograf.marker`, held against the tool by `tests/unit/test_stores.py`, with no
import of the tool) in two places: `retman doctor check` (section 7.2) and the offline preview
of every Kartograf operation that writes, where a folder the tool refuses is the one blocking
problem of the plan (`store_no_marker`, `store_not_kartograf`, `store_marker_unreadable`,
`store_unsupported`, `store_nested`; it names no parameter, so there is nothing to answer
again). The search for a store below a folder that is refused anyway is left to the tool.

**Availability check** (`s`, section 6.5): for DEM (NMT), DSM (NMPT) and the cutout it asks the GUGiK
services (the WFS sheet index and the PRG layer) about years, resolutions, vertical reference
systems and completeness of the map sheets for the area from the plan (`elevation availability`);
for the cutout this is an approximation, because the cutout is assembled by the WCS server. For the
orthophoto it checks the freshness plan for the RGB variant (the index knows only RGB); for BDOT10k
it asks the PRG service which counties the area intersects and how many of their packages are
already in the store (for a TERYT code, with no network). DEM (NMT) 100 m (voivodeship files) and the
CIR and black-and-white variants have no index — the check then checks nothing and says so plainly.

#### 3.2.11. IMGWTools 3.0.0 operations

All of IMGWTools in v0.1 (ADR-017): 26 operations in six categories, on IMGW-PIB and ČHMÚ data.
Together with Kartograf's `spatial_data` category there are seven of them (none with more than 9
operations), so recognition is two-stage (section 3.4). All operations go through the command layer;
those that connect to a server do so only after the plan is confirmed. Operations marked `check`
offer an availability check (section 6.5).

| Category (`id`) | Operation (`id`) — what it does | Result kind | Network and writes |
| --- | --- | --- | --- |
| `imgw_catalog` — stations and data registry | `find_imgw_stations` — search for stations by name, river, provider and kind | `station_list` | from the store without network; from the server network |
| | `build_imgw_station_catalog` — build the station catalog in the store, optionally with a locations file; `check` | — | network; writes to the store |
| | `list_imgw_datasets` — datasets and providers | `imgw_report` | no network |
| `imgw_current` — current data and warnings | `fetch_current_observations` — current measurements of a hydrological, meteorological or synoptic station | `current_hydro`, `current_meteo`, `current_synop` | network |
| | `fetch_imgw_warnings` — hydrological and meteorological warnings | `imgw_warnings` | network |
| | `fetch_hydro_states` — water levels at stations (alarm and warning levels) | `hydro_states` | network |
| `imgw_pmaxtp` — PMAXTP maximum precipitation | `get_pmaxtp` — table of maximum precipitation for a point (POT or AMP method; filters: probability and duration; cell saved in the store or not) | `pmaxtp_table` | network; with saving also the store |
| | `read_stored_pmaxtp` — read a saved grid cell | `pmaxtp_table` | no network |
| `imgw_series` — station time series | `export_station_series` — station series (dataset, period, year type, variables) to CSV; `check` | `hydro_series`, `meteo_series` | from the store without network; from the server download of archives to the store (network, writes) |
| | `show_station_coverage` — data coverage of a station in the store (years, gaps) | `imgw_report` | no network |
| | `build_imgw_series` — build dataset series from archives in the store | — | writes to the store |
| `imgw_archives` — archives and store | `download_hydro_archives`, `download_meteo_archives` — download archives as plain files to the results folder (`output_dir`), without the store | `imgw_archive` | network |
| | `check_imgw_archives` — plan: what needs to be downloaded relative to the store | `imgw_plan` | network |
| | `sync_imgw_store` — download archives to the store; `check` | — | network; writes to the store |
| | `sync_imgw_store_by_plan` — download per a plan from the result of `check_imgw_archives` (input `imgw_plan`, e.g. "#5") | — | network; writes to the store |
| | `export_imgw_archive` — export saved archives to CSV or JSON Lines | `archive_records` | no network |
| | `init_imgw_store` — create the store | — | writes (store marker) |
| | `inspect_imgw_store` — description of the store (entries, versions, problems) | `imgw_report` | no network |
| `imgw_projects` — data projects | `init_imgw_project`, `add_imgw_project_task`, `remove_imgw_project_task`, `set_imgw_project_store` — project manifest (`imgw-project.json`) in the project folder | — | writes to the project folder |
| | `download_imgw_project` — download and pin the data of the project's tasks; `check` | — | network; writes |
| | `check_imgw_project` — plan of the project data's currency | `imgw_plan` | network |
| | `verify_imgw_project` — verification of pinned data (state or checksums) | `imgw_report` | no network |

Operations that write only to the store or to the project folder (no result kind) leave
`result.json` and the tool's documents in the results folder; the others write CSV files and reports in the
results folder — IMGWTools never points to store files in a result. Operations whose result is
a document without a file (lists, tables) save it as CSV (tables) or JSON.

**Rules common to IMGWTools operations:**

- **Store** (`[retman.tools.imgwtools] store_dir`, section 9.1) is the `root` option of the commands
  that read or write it; the client adds it unless the call names plain files (the next rule). A
  missing store, a folder with the layout of a store but no marker, a foreign folder or a store with
  an unsupported schema is a **preview problem**; the problem of a missing store comes with the
  repair commands ("Utwórz magazyn IMGW" (create the IMGW store), `retman config init`), and that of
  a layout without a marker with the first one, which makes the tool check the layout and write the
  marker (`retman config init` does not run again on a settings file that has its tables); a folder
  that holds only the `api_keys.json` of the tool's server counts as a missing store, not as a
  foreign folder; no operation creates a store silently. The client exports `reference_data_dir`
  once as the `IMGW_REFERENCE_DIR` variable before the first import of the tool — the only
  exception to the "no environment variables" rule, because the tool has no option for the static
  station positions file; the value comes from the settings, not from the environment.
- **Output: plain files or the store** (the data output convention ECO-051, ADR-024). IMGWTools
  writes either plain files into a directory (`output_dir`) or a versioned store (`root`), never
  both: its catalog declares such options `exclusive`, and the client adds `root` only to a call that
  names none of the options of a group that holds it. The two download operations pass the **results
  folder** as `output_dir`: the tool stages the files, verifies them and moves them into place
  atomically, and the audit block `tool` of the result carries the `files[]` it reports (path,
  SHA-256 computed while writing, status) as they are. While a plan is built there is no results
  folder yet, and a download without `output_dir` would write the store and be refused for a
  dataset the store does not hold (`retman scaffold check` reports such a dataset as a dead option,
  X3, section 3.2.3), so the **project folder stands in** for `output_dir` in the offline validation;
  the tool only validates the option and writes nothing there. The exports (`export_station_series`,
  `export_imgw_archive`) pass the file as `output` (it was `path`) and take it from `files[]` in the
  same way. The store operations keep `root`. Their results use the statuses of the tool, `new`,
  `unchanged`, `relabeled` and `failed`, and the synchronisation counts `new_versions` and
  `new_series` (they were `created`, `series_created`; CHANGELOG).
- **Not published.** A file that the server does not publish (a year without an archive) is an item
  of the plan with the status `unverifiable` and the error `not published`, the English text of the
  tool; Retman compares it with one constant (`plans.UNPUBLISHED`), and a test holds that constant
  against `imgwtools.fetch.UNPUBLISHED`.
- **Stations** are read by the `station` extractor **offline from the catalog in the store** (codes:
  9 IMGW-PIB digits, ČHMÚ WIGOS identifier; names with Polish inflection, an inflected name requires
  confirmation, section 6.1). Without a catalog Retman reads only codes and points to the
  `build_imgw_station_catalog` operation (explicit, confirmed, with network); until then it does not
  search for stations over the network while asking questions.
- **Period: two semantics, never mixed.** Archive operations take `years` — years in the numbering of
  the tool's archives (for IMGW-PIB hydrological datasets these are hydrological years). Series
  operations take `period` (years or dates) and `year_type` (hydrological or calendar year) —
  **always a question** when it is not stated in the command, because it changes the dates (1 November
  – 31 October versus 1 January – 31 December). Retman does not expose the tool's `months` (for
  hydrological data it is the file index within the hydrological year).
- **Datasets** (`dataset`) are closed lists for the model (keys without dots; `tool_values` converts
  them to the tool's registry keys, e.g. `pl_hydro_daily` → `pl.imgw.hydro_daily`):
  seven datasets for store and series commands (IMGW-PIB: hydro daily, monthly and semi-annual,
  meteo climatic daily and precipitation daily; ČHMÚ: hydro daily and meteo daily), and for
  downloading archives to the results folder two operations — hydrological (5 datasets, including
  hydrological phenomena) and meteorological (7 datasets, including monthly, synoptic and fixed-time) —
  the datasets of the second operation are in the `excluded` of the first (coverage check, section 3.2.3).
  Dataset metadata (provider, kind, variables, year numbering) is carried by `option_meta`; it is used
  by the contextual extractors (e.g. variables available in the dataset, stations of the right provider
  and kind).
- **PMAXTP:** the request to the tool accepts only a point and a method, and the result is a table
  (duration × probability; columns `ks_mm`, `sg_mm`, `rb_mm`). `probability` and `duration` from the
  command are therefore **output filters** (section 4.4): a value outside the table is not lost silently
  but produces a warning, and when none occurs, the whole table is saved. Retman converts a point in
  PL-1992 itself, without geospatial libraries; a point outside the PMAXTP frame (49–55° N, 14–24.5° E)
  is rejected with a reason.
- **License and attribution:** the provider's `license_terms` notices are shown verbatim in the result
  warnings, and the registry attribution is in the CSV columns (`attribution_source`, `attribution_processed`).
- **Preview** (offline) adds to the plan, among other things, the store state and the number of stations
  matching the name, the range of data in the store (years, gaps) and the number of archive files to check,
  and rejects a plan the store cannot serve (e.g. no series for the dataset or no station in the series
  with the "store" source). **Availability check** (`check`) exists only for operations where the network
  changes what will happen: building the station catalog (whether the source lists are newer), exporting
  a series (with the "server" source: how many archives must be downloaded; with the "store" source the
  check does not connect to the network and says so explicitly) and synchronising archives (how many
  files are newer or missing and how much data that is — HEAD requests without downloading), downloading
  project data (task state). Point and "live" operations and artifact operations (`check_imgw_archives`,
  `check_imgw_project`) have no `check`: the check would say nothing that the execution itself would not
  say, and the result of these operations is a plan (`imgw_plan`) that the user confirms and executes
  (`sync_imgw_store_by_plan`).
- **Excluded catalog commands** (8 of 38, each reachable through the IMGWTools CLI and API): `datasets
  files`, `pmaxtp url`, `pmaxtp check` and `series select` are offline lookups used by previews and
  mappers, not separate operations; `series read` yields the same records as the series export (and a
  file with license columns is produced by `export_station_series`); `commands list`, `commands schema`
  and `commands guide` describe the catalog itself (Retman reads schemas only in `retman scaffold`).
  The `project add` command is exposed for `series select` and `pmaxtp sync` tasks; the other task
  types have nothing to pin or are covered by the series task.

### 3.3. Models: Retman contains no model [N-01], [N-02], [N-10]

Retman is not distributed with any language model. The model runs as a **separate service** —
locally (e.g. LM Studio, Ollama, basal-serve), on the organisation's network or at a provider —
and Retman connects to it through an API. As a result the basic Retman installation is small and
contains no machine-learning libraries.

**Default configuration:** the decision model is **basal** via **basal-serve** — a separate
program from the `basal` package that asks the model questions in a special way and returns
calibrated option probabilities (section 3.3.3). basal-serve **is not a Retman dependency**, not
even an optional one, because it requires PyTorch and GPU libraries; it is installed separately
per basal's instructions.

#### 3.3.1. Two roles of the model

| Role | Interface | Purpose | Required? |
| --- | --- | --- | --- |
| **Decision model** | `DecisionBackend` | choosing the operation and options (steps ①–②) | yes |
| **Text model** | `TextBackend` | describing results in Polish (from v0.2) | no |

Both roles can be filled by the same model (e.g. a single model in LM Studio) or by two different
ones (e.g. basal for decisions and Bielik for descriptions). Retman talks to the models solely
through these two interfaces, so swapping a model requires no changes in the rest of the code.

```python
from typing import Protocol


class DecisionBackend(Protocol):
    """A model that picks one of the given options and reports how confident it is."""

    def choose(self, state: str, question: str, options: dict[str, str]) -> "Decision":
        """
        state    – the user's command (plus optional context)
        question – question for the model in the user's language (from translation
                   files; for parameters: `model_question`, section 4.2)
        options  – {key: description}, e.g. {"punzet": "Metoda Punzeta", ...}
        Returns the chosen key, probabilities of all options and the confidence.
        """
        ...

    def yes_no(self, state: str, question: str) -> "Decision":
        """A yes/no question, e.g. whether the command specifies a location."""
        ...


class TextBackend(Protocol):
    """A model that writes text — used only for describing results (optional)."""

    def describe(self, result_summary: dict, language: str = "pl") -> str:
        ...
```

#### 3.3.2. Connection types (backends)

| Backend | What it connects to | Role | Version |
| --- | --- | --- | --- |
| `basal` | basal-serve, installed separately per basal's instructions | **decisions — default**, with calibrated confidence | v0.1 |
| `openai_compatible` | any server with an OpenAI-compatible API: LM Studio, Ollama, llama.cpp server, vLLM, as well as providers offering such an API | decisions (alternative to basal); from v0.2 also result descriptions | v0.1 |
| native provider APIs | providers with their own API (e.g. Anthropic) | decisions and/or text | v0.2, optional add-ons |
| `none` | — | no result description: the result shows a text template | v0.1 |

Backends talk to the APIs directly over HTTP, without provider SDKs — the basic installation
stays small. The `basal` backend is a custom HTTP request to basal-serve, without the client from
the `basal` package, so as not to install its dependencies.

#### 3.3.3. How the model makes a decision

**basal (via basal-serve).** basal-serve builds a fixed prompt from the command, the question
and the options labelled with letters. It does not let the model write — it only reads the
probabilities of the next letter (A, B, C…). It repeats the question with the option order
reversed and averages the result, and finally applies the calibration bundled with the model.
The result: a probability for each option and a confidence, without any text.

**Generative model (alternative).** A generative model (e.g. Bielik, Qwen, a frontier model)
does not return such probabilities, so the `openai_compatible` backend works like this:

1. **Choice.** It asks the model for one of the options and enforces the answer format: a list of
   allowed keys, if the server supports structured responses; otherwise it validates the answer
   and repeats the question if needed.
2. **Confidence** — per the `confidence` setting (section 9.1):
   - `auto` (default): from `logprobs` (token probabilities), if the server returns them;
     otherwise **consistency** — several requests (e.g. 3) and the share of agreeing answers,
   - `logprobs` or `consistency` — force one of the methods,
   - `none` — no confidence; only by the user's explicit choice (e.g. to limit the number of
     calls to a paid API).

   Confidence thresholds for these methods must be entered as a number — `"auto"` means basal's
   calibration and is a configuration error with this backend (section 6.2).
3. **Low confidence or disagreeing answers** — Retman asks follow-up questions, just as with low
   basal confidence (PRD N-05). In `none` mode every value chosen by the model is marked in the
   plan as **unverified**, and the mandatory plan confirmation remains the safeguard
   (section 6.3).

#### 3.3.4. Example configurations

| Configuration | Decisions | Result description | Notes |
| --- | --- | --- | --- |
| **Default** | basal (basal-serve) | Bielik in LM Studio (from 0.2; template in 0.1) | calibrated decision confidence, Polish model for text; two services next to Retman |
| **Simplest** | one model in LM Studio (`openai_compatible`) | the same model (from 0.2) | one service; confidence from `logprobs` or from agreement of several answers (section 3.3.3); confidence thresholds entered as a number (section 6.2) |
| **With a frontier model** | provider model via API | provider model (from 0.2) | requires an API key; commands go to the provider (chapter 10); confidence thresholds entered as a number (section 6.2) |
| **Minimal** | any model | `none` | results described by a template |
| **Unit server** | basal-serve on a server in the internal network | as in the default | user's computer without a GPU; from v0.1 — just change `url` in the configuration |

Result description by the text model works from v0.2; in v0.1 results are described by a text
template.

> Access to a model through a chat subscription usually does not include API access — working
> with Retman requires an API key (check with the specific provider).

### 3.4. Limitations of basal that the architecture must account for

Applies to configurations with basal. Some rules (items 2, 4–6) also apply to generative
models, because they simplify their task.

1. **Max. 10 options per question.** The operation question contains the operations and the
   `out_of_scope` option (item 6), so one question handles up to 9 operations. There are more
   operations (from v0.1 Kartograf and all of IMGWTools), so recognition is **two-stage**: the
   model first picks a **category** (options: categories and `out_of_scope`), then an
   **operation within the category** (options: that category's operations and `out_of_scope`).
   The decisions are named `category` and `operation` (section 5.4); an uncertain category
   choice ends with a `category` question listing the 2–3 most likely groups (section 6.1).
   The loader enforces the limits at startup: at most 9 categories, at most 9 operations per
   category, and every category has a `label` and `description` in the tool's translation
   file (`[categories.<id>]`, section 4.2; a category with the same name in several tools is
   described by the first of them that has its text). The `choice` parameter has a separate
   limit: at most 9 options plus `unspecified` (section 4.3) — longer lists of tool values are
   split into parameters or operations.
2. **Weak at exact numbers.** Numeric values are always extracted by extractors (step ③).
3. **Option order matters.** basal averages the straight and reversed order; even so, tests
   (chapter 8) must check stability when options are shuffled.
4. **Ask in the language of the command.** Questions and option descriptions must exist in the
   translation file for the command's language (section 4.2).
5. **The "cannot be determined" option.** Every question about a parameter that may not appear
   in the command has an extra option `unspecified` ("the command does not specify this").
6. **The "none of the above" option** [W-03]. The operation question (step ①) always contains
   the `out_of_scope` option ("the command does not concern any of the available operations")
   — in two-stage recognition at both stages. Choosing it ends with a message about what
   Retman can do (with two stages: about the operation groups), not with guessing the closest
   operation. The option counts toward the 10-option limit.

---

## 4. Operation registry

### 4.1. Manifest — operation definition

The operations of each tool are described by a manifest in `src/retman/tools/<tool>/manifest.py`:
a plain Python dictionary, in English. The manifest is **static and reviewed by a human**:
options are never derived from the installed tool at load time (ADR-019) — they have
Polish texts and synonyms, the `retman eval run` set must be repeatable, and Retman's startup does not
import tools. A manifest draft can be generated from the tool's command catalog
(`retman scaffold draft`, section 3.2.3), and the manifest's conformance with the installed tool is checked by
`retman scaffold check`. Each operation also declares **what it accepts** (`inputs`) and **what it returns**
(`outputs`) — the workspace (chapter 5) works on this basis, and in v0.2 so do chains (section 4.5).

Tool keys: `tool`, `distribution` (package name used to check the version), `source`
(requirement for `--with` in `retman doctor check` hints, section 9.4), `supported_versions`,
`translations`, `operations` and `client` — the tool client factory (`"moduł:funkcja"`,
section 3.2.4), required when any operation declares `calls`.

```python
# src/retman/tools/hydrolog/manifest.py — a tool without a command catalog: operations with a handler
MANIFEST = {
    "tool": "hydrolog",
    "distribution": "hydrolog",              # package name for the installed-version check
    "source": "git+https://github.com/Daldek/Hydrolog",  # for `--with` in retman doctor check hints (section 9.4)
    "supported_versions": ">=1.1,<2",        # checked at startup and in CI (section 3.2.7)
    "translations": {"pl": "pl.toml", "en": "en.toml"},  # relative to this package
    "operations": [
        {
            "id": "peak_flow",
            "category": "flows",
            "description": "Peak flow with a given exceedance probability",
            "inputs": [
                # Catchment characteristics: from a file, a previous result (ch. 5)
                # or, from v0.2, an earlier chain step.
                {"name": "catchment", "kind": "catchment_characteristics"},
            ],
            "outputs": ["peak_flow"],
            "params": [
                {
                    "name": "method",
                    "type": "choice",
                    "options": ["punzet", "bogdanowicz_stachy", "scs_cn"],
                    "default": "punzet",       # used when the command does not specify a method
                },
                {
                    "name": "probability",
                    "type": "free",
                    "extractor": "probability",  # a number, not a list (section 4.4)
                    "required": True,
                    "multiple": True,            # e.g. "Q1% i Q10%"
                    "range": [0.0001, 0.5],      # allowed range, example values
                },
            ],
            "handler": "retman.tools.hydrolog.handlers:compute_peak_flow",
        },
    ],
}
```

An operation of a tool with a command catalog (Kartograf, IMGWTools) has a call builder
instead of a handler, plus a preview and a check. A fragment of the Kartograf manifest:

```python
# src/retman/tools/kartograf/manifest.py (fragment)
MANIFEST = {
    "tool": "kartograf",
    "distribution": "kartograf",
    "source": "git+https://github.com/Daldek/Kartograf",
    "supported_versions": ">=0.8.0.dev0,<0.9",
    "translations": {"pl": "pl.toml", "en": "en.toml"},
    "client": "retman.tools.kartograf.client:create",    # factory(settings) -> RunClient (section 3.2.4)
    "operations": [
        {
            "id": "download_dem_sheet",
            "category": "spatial_data",                   # first stage of the recognition (section 3.4)
            "description": "Download a GUGiK digital terrain model for a map sheet",
            "inputs": [],
            "outputs": ["dem", "dem_archive"],
            "commands": ["elevation download"],           # commands the builder may use (section 3.2.3)
            "calls": "retman.tools.kartograf.calls:download_dem_sheet",          # pure builder: params → catalog calls
            "describe": "retman.tools.kartograf.describe:download_dem_sheet",    # runs → files, values, warnings
            "preview": "retman.tools.kartograf.preview:download_dem_sheet",      # offline: plan rows and problems
            "check": "retman.tools.kartograf.checks:download_dem_sheet",         # network step on request (section 6.5)
            "params": [
                {"name": "area", "type": "free", "extractor": "area",
                 "accepts": ["sheet", "geometry"], "required": True},
                {
                    "name": "resolution",
                    "type": "choice",
                    "options": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m", "100m"],
                    "tool_values": {"0_15m": "0.15m", "0_5m": "0.5m", "0_6m": "0.6m"},  # option keys have no dots
                    "required": True,
                },
                {
                    "name": "vertical_crs",
                    "type": "choice",
                    "options": ["evrf2007", "kron86"],
                    "tool_values": {"evrf2007": "EVRF2007", "kron86": "KRON86"},
                    "required": True,
                    # NMT 100 m has no height system: asking would be a question the call drops
                    "depends_on": {"resolution": ["0_15m", "0_5m", "0_6m", "1m", "5m", "10m"]},
                },
            ],
        },
        # ... download_sheet_hierarchy, download_elevation_cutout, download_bdot10k
    ],
}
```

The `download_sheet_hierarchy` operation has a `handler` alongside `calls`: an orthophoto with a colour
variant (RGB, CIR, B/W) goes through the tool's provider class, because the catalog command `imagery download`
has no colour option (ADR-013). It also has `excluded` — tool values that Retman deliberately
does not expose, with a justification (e.g. `"resolution": {"100m": "NMT 100 m is published as province
files, not as sheets"}`); the coverage check (section 3.2.3) requires that every tool value is
either offered or listed here.

### 4.2. Texts for the user and the model (translation files)

Questions to the user, option descriptions and labels in the plan are in translation files, with keys
matching the identifiers from the manifest. Each tool has one file per language in Retman (`pl.toml`,
`en.toml`), and the core has its own pair (`src/retman/i18n/`: plan, dialog, CLI, results, journal,
errors, warnings, availability check, data kinds, `retman config init`, `retman doctor check`,
extractors, and the `[answers]` table with the words the terminal dialog accepts). The files of a pair
have the same keys and the same placeholders (`tests/unit/test_i18n.py` compares them); the one
difference is that the English texts of the command catalog are the declarations in
`src/retman/catalog/commands.py`, so `en.toml` has no `[catalog.<operation_id>]` tables (AGI-9.1).
The example below is the Polish file of a tool; its `en.toml` has the same keys with English texts,
and its English `description` texts keep the Polish names and abbreviations beside the English words
(NMT, godło, TERYT; DEV-2.4), because the commands are still typed in Polish. A machine document
carries English texts whatever `lang` says (AGI-9.2); where the terminal shows the same report in
Polish (`retman doctor check`), such a text is a `Message` that remembers its key and values and is
written again from the Polish file (`retman.i18n.loader`).

```toml
# src/retman/tools/hydrolog/pl.toml

[operations.peak_flow]
label = "Obliczenie przepływu maksymalnego"
description = "Obliczenie przepływu maksymalnego o zadanym prawdopodobieństwie: przepływ miarodajny, woda stuletnia"

[operations.peak_flow.params.method]
label = "Metoda"
question = "Jaką metodą policzyć przepływ?"
model_question = "Jaką metodę wymienia polecenie?"
options.punzet.label = "Metoda Punzeta"
options.punzet.description = "Metoda Punzeta, Punzet"
options.bogdanowicz_stachy.label = "Metoda Bogdanowicz-Stachy"
options.bogdanowicz_stachy.description = "Metoda Bogdanowicz-Stachy, Bogdanowicz i Stachý"
options.scs_cn.label = "Metoda SCS-CN"
options.scs_cn.description = "Metoda SCS-CN, Soil Conservation Service, curve number, CN"
options.unspecified.description = "Polecenie nie określa metody"

[operations.peak_flow.params.probability]
label = "Prawdopodobieństwo przewyższenia"
```

Rules:
- The `label` of an operation and of an option is a short name shown to the user (plan, questions, list
  of operations); `description` goes only to the decision model and may contain synonyms,
  colloquial terms and English names and abbreviations (DEM, DSM, SHP), because these help
  match the command and the user's answer (ADR-007). The `unspecified` option is not
  shown to the user, so it has only a `description`.
- `question` is the question for the user ("Czy pobrać NMT w rozdzielczości 1 m czy 5 m?" —
  "Download the DEM at 1 m or 5 m resolution?"); a parameter chosen by the model (`choice`, `bool`)
  also has `model_question` — a question about **what the command mentions** ("Jaką rozdzielczość
  wymienia polecenie?" — "What resolution does the command mention?"). The model receives
  it with the command and with the user's answer in their own words; a question in the form
  "X or Y?" the model reads as an unknown and more often chooses `unspecified`
  (ADR-008).
- A `free` parameter also has `example` (a format example in the question), and every parameter may
  have `help` (the answer to `?`, section 6.4).
- Option keys and categories are simple words `[a-z0-9_]+`: a dot in a key breaks translation
  lookup (it splits keys on dots). A tool value with a dot therefore has a separate key
  and a `tool_values` entry — the resolution "0.5 m" is the option `0_5m` corresponding to the tool
  value `0.5m` (section 4.3).
- An automated test (`validate_manifest`) checks that every operation, parameter and option has a text
  in every supported language; for operations with `check` also `check.notice`, and for a parameter
  read by an extractor only the texts for the user (without texts for the model). A missing
  translation = the test fails.

In `[operations.<id>]`, besides `label` and `description`, there may be: `summary` — a template for the result
row (slots for the result's `values` keys and for `number`, `operation`, `directory`; without it
the core's generic text is used), `check.notice` — a sentence about what the availability check
contacts (mandatory with `check`, section 6.5), and in the area parameter `geometry_note` — a sentence
appended in the plan to an area from a geometry file, saying what this operation does with it.
Outside `[operations.*]` the tool file has tables supporting recognition and messages:

| Table | Content |
| --- | --- |
| `[categories.<id>]` | `label` and `description` of a category (for the model and the user); required for every category when the total number of operations exceeds 9 (two-stage recognition, section 3.4); the text is taken from the first tool that describes the category |
| `[errors.<code>]` | Retman's text for a stable tool error code (placeholders `{tool}`, `{code}`, `{detail}`, `{hint}`, `{option}`, `{option_label}`, `{allowed}`); the tool's own text appears only as `{detail}`; without an entry the generic core text applies |
| `[problems.<key>]` | texts of preview problems (`PreviewProblem.key`, section 3.2.4) |
| `[preview.<key>]` | `label` and `value` of an additional plan row from the preview |
| `[check.<key>]` | lines of the availability check report (`CheckItem.key`) |
| `[warnings.<key>]` | texts of warnings composed by Retman (tool notice codes and `HandlerWarning` keys); other `warning` and `error` notices of the tool are shown verbatim after the generic core text, and `info` notices stay in the audit trail. When a single call reports more than 5 notices with the same code, the result shows the first 3 and one `tool_notices_more` line with the number of remaining ones (the full list stays in the tool document `tool_<n>_<command>.json`) |

### 4.3. Parameter types and operation fields

| Parameter type | Source of the value | Examples |
| --- | --- | --- |
| `choice` | decision model, selection from a list (at most 9 options, 10 with `unspecified`; section 3.4); with the `extractor` key — code (extractor), no model | method, data kind, resolution, dataset; output coordinate system of a cutout (`crs`), year type (`year_type`) |
| `free` | extractor in code | coordinates, point, date, period, years, probability, duration, area, station, variables, file path, name |
| `bool` | decision model, yes/no | "include retention?" |

Additional parameter keys: `required`, `default`, `multiple` (several values at once; a value
given singly is wrapped in a list), `range` (allowed range for numbers), `accepts`
(which kinds of extractor values the operation accepts, e.g. the `area` extractor yields a map sheet
code (godło), a rectangle, a TERYT code or a geometry file, while a cutout accepts only `["bbox",
"geometry"]`), `depends_on` (the parameter applies only to selected values of another `choice`
parameter, e.g. resolution only for DEM (NMT): `{"product": ["dem"]}`). For `choice` there are three
more keys.

- `option_values` (with the `extractor` key): option key → extractor value, e.g.
  `{"epsg_2180": "EPSG:2180"}`. The value is then set by code: exactly one supported value
  from the command → plan; none, several or an unsupported value → question with a list of
  options. The model does not receive such a parameter, so it has no `model_question` and no
  option descriptions for the model (ADR-009). We use this where the model confuses the role of a
  value in the sentence — e.g. the coordinate system of the input rectangle with the coordinate
  system of the result — or where we may only ask about what the user actually said (year type).
- `tool_values`: option key → the value the tool knows, when they differ, e.g.
  `{"0_5m": "0.5m", "evrf2007": "EVRF2007"}`. The call builder reads it via
  `ctx.tool_value(parametr, klucz)`; without an entry the tool value is the key itself. Tool
  values must be non-empty and unique within a parameter.
- `option_meta`: option key → an opaque JSON dictionary for builders and contextual
  extractors, e.g. provider, kind and variables of a dataset (`ctx.option_meta(parametr,
  klucz)`). The keys of `tool_values` and `option_meta` must be option keys.

| Operation field | Meaning |
| --- | --- |
| `id` | identifier (in English), unique across all of Retman |
| `category` | category (`[a-z0-9_]+`) — the first stage of two-stage recognition (section 3.4) |
| `description` | short description in English (for developers; the user-facing text is in the translations) |
| `inputs` | inputs: name + data kind (`kind`); the source is a file, the workspace, (v0.2) an earlier step of a chain |
| `outputs` | data kinds returned by the operation |
| `params` | parameters |
| `handler` | handler in Retman (`moduł:funkcja`), called as `handler(params, inputs, output_dir, ctx)` — for operations that must process the result (section 3.2.4) |
| `calls` | pure call builder (`moduł:funkcja`) `calls(params, ctx) -> list[CatalogCall]`; called offline during planning (validation by the tool) and at execution by the shared executor (section 3.2.4) |
| `commands` | catalog commands the builder may use (inventory for the conformance check, section 3.2.3); non-empty when `calls` is present |
| `describe` | mapper of call results onto `HandlerOutput` (`moduł:funkcja`); requires `calls`, without it the generic mapping applies |
| `excluded` | deliberately unsupported tool values in `choice` parameters: `{parametr: {wartość narzędzia: uzasadnienie}}`; a value cannot be offered at the same time, the justification is non-empty (coverage check, section 3.2.3) |
| `preview` | offline function `preview(params, ctx) -> PreviewOutput`, called when the plan is complete (section 3.2.4) |
| `check` | availability check function `check(params, ctx) -> CheckOutput`; its presence enables the `s` answer (section 6.5) and requires the `check.notice` text |
| `no_check` | explicit, reviewed justification (in English, for maintainers) why an operation with a network and writing command has no `check` step; excludes `check`, accepted by check X7 |

An operation declares at least one of `handler` and `calls` (a handler may itself call the shared
executor, section 3.2.4); `calls` requires a non-empty `commands` and a `client` key in the tool;
`handler`, `calls`, `describe`, `preview`, `check` and `client` are `"module:attribute"` references
imported lazily. On loading, `validate_manifest` also checks: uniqueness of `id`, known data kinds
(`kind`), `default` among the options, consistency of `depends_on`, `option_values`,
`tool_values`, `option_meta` and `excluded`, and the complete set of translations. With more than 9
operations the loader requires at most 9 categories, at most 9 operations per category and texts
for every category (section 3.4).

**Extractors** (values are read by code, never by the model; registry in
`src/retman/extractors/__init__.py`). Contextual extractors (`station`, `years`, `period`,
`variables`) additionally receive an `ExtractionContext`: the `[retman.tools.<tool>]` settings, the
project folder, today's date (constant within a single `Retman`, so planning is repeatable),
`scope` — the merged `option_meta` of options already selected in `choice` parameters (e.g.
provider, kind and variables of a dataset; the dataset parameter must therefore precede the station
and variables in the manifest) and `lookup` — an offline search in the tool's catalog
(`PlanClient.lookup`; the only such search is the station list from the IMGWTools store,
`stations find` with `source=store`). They do not import tools and do not use the network.

| Extractor | What it reads | Value |
| --- | --- | --- |
| `area` | map sheet code (godło; also the 8-part PL-1992 sheet code), a rectangle in PL-1992 or WGS84, a county TERYT code, a geometry file (SHP, GPKG) | `{type: sheet\|bbox\|teryt\|geometry, …}`; geometry: `{type: geometry, path, layer}` (section 6.1) |
| `crs` | coordinate reference system of the result (not of the input rectangle) | `EPSG:<code>` via `option_values` |
| `point` | a WGS84 or PL-1992 point; axis order is never guessed | `{type: point, latitude, longitude, input_crs}` (PL-1992: also `easting`, `northing`) |
| `grid_cell` | a PMAXTP grid cell ("751/317") | `{type: grid_cell, ind_x, ind_y}` |
| `probability` | exceedance probability and return period (section 4.4) | fraction `p` (a list with `multiple`) |
| `duration` | rainfall duration ("15 min", "2 godziny" (2 hours), "półgodzinny" (half-hour)) | number of minutes (a list with `multiple`) |
| `station` | an IMGW-PIB or ČHMÚ station by code (9 digits, WIGOS) or by name, offline from the catalog in the store; narrowed by `scope` (provider, kind) | `{type: station, provider, kind, code, name, river, in_catalog}` |
| `synop_station` | a synoptic station (5-digit code or a name fragment) | `{type: synop_station, code, name}` |
| `place_query` | a fragment of a station or river name for searching (inflected form reduced to its stem) | `{type: query, text, raw}` |
| `years` | archive years in the tool's numbering ("2000–2020", "2010, 2012 i 2015" (2010, 2012 and 2015)) | `{type: years, first, last}` or `{type: year_list, years}` |
| `period` | a period: years or dates ("od 1 stycznia 2000 do 31 grudnia 2020" (from 1 January 2000 to 31 December 2020)) | a `years` value or `{type: dates, start, end}` |
| `year_type` | hydrological or calendar year; when absent from the command, always a question | choice of `hydrological` / `calendar` via `option_values` |
| `variables` | measurement variables of a dataset (codes or words: "przepływ" (flow), "stan wody" (water level)), checked against `scope["variables"]` | list of variable codes |
| `identifier` | a name given by the user (e.g. of a project task) | text matching `^[a-z0-9][a-z0-9_-]{0,63}$` — without silent "fixing" |
| `path` | a file path mentioned in the command | path |
| `result` | a result number ("#3", section 5.2) | number |

### 4.4. Probability and return period [W-08]

Probability is a **number**, because the calculations can be done for any value.
The `probability` extractor pulls it out in code, without the model. In PMAXTP operations (IMGWTools)
it serves as an **output filter**: the request to the tool does not accept a probability, and the
result table contains many of them, so the value from the command is not silently lost (the same
applies to rainfall duration, extractor `duration`).

**Storage:** always as a fraction `p` (e.g. `0.01`). In the plan shown as a percentage
and a return period: "1% (T = 100 lat)", where T = 1/p.

**Recognized forms:**

| Spelling in the command | Result |
| --- | --- |
| "1%", "p = 1%", "Q1%", "Q 1 %" | 0.01 |
| "prawdopodobieństwo 0,01" (probability 0.01) | 0.01 |
| "woda stuletnia", "przepływ stuletni" (hundred-year water, hundred-year flow) | 0.01 |
| "pięćdziesięcioletnia", "okres powtarzalności 50 lat", "T = 50", "raz na 50 lat" (fifty-year, return period 50 years, T = 50, once in 50 years) | 0.02 |
| "Q1% i Q10%" (Q1% and Q10%) | [0.01, 0.10] (when `multiple`) |
| "dla 1, 2 i 10%" (for 1, 2 and 10%) | [0.01, 0.02, 0.10] (when `multiple`) |

Numeral adjectives ("dziesięcioletnia", "dwudziestoletnia", "pięćsetletnia",
"tysiącletnia" etc.: ten-year, twenty-year, five-hundred-year, thousand-year) are recognized by
a dictionary in code, covered by tests.

**Ambiguous spellings — Retman asks:**

| Spelling | Problem | Reaction |
| --- | --- | --- |
| "Q50", "Q20", "Q2" (without %) | may mean p = 50% or T = 50 years (p = 2%) | asks which one is meant |
| "Q10" | both readings give 10% | assumes 10%, without asking |
| "Q1", "Q100", "Q500" | one of the readings (T = 1 year, or p = 100% and above) is impossible | takes "Q1" as 1%; "Q100" and "Q500" as T (1%, 0.2%) and shows this in the plan |
| "dla 1", "dla 0,5" (for 1, for 0.5: a number without "%", without "Q" and without a period in years) | 1% or p = 1? 0.5% or p = 0.5? | **always** asks — even when one of the readings is impossible |
| "Q50 i Q10" (Q50 and Q10: a list with an ambiguous element) | the same problem for every element | the whole list has several readings (p = 50%, 10% or T = 50 years, p = 10%): asks about the reading of the whole list, does not mix them |

A number without a marker ("%", "Q", "T =", a period in years) is read only after an indicating
word ("dla", "prawdopodobieństwo", "p =" — for, probability, p =) or in a list started by such
a word — never as part of a point, a date, a year, a sheet code (godło) or another number.

**Validation:** `0 < p < 1` (both bounds excluded) and the `range` from the operation manifest
(a method may have its own limits). A value outside the range → a message with the allowed range.

### 4.5. Operation chains (v0.2) [W-12]

The `inputs`/`outputs` declarations are already written in v0.1, where they serve to look up data
in the workspace (chapter 5). The resolver described below is built in v0.2.
An alternative to evaluate after more tools are added — chains as author recipes: chapter 12
item 14.

The model **does not plan** chains. It only picks the goal; the further steps follow from the
`inputs`/`outputs` declarations — much as formulas in a spreadsheet are computed in dependency order.

**Example:** *"Policz przepływ stuletni metodą Punzeta dla punktu 52.41, 16.93"* (compute the
hundred-year flow with the Punzet method for point 52.41, 16.93)

1. basal recognizes the goal: `peak_flow` (Hydrolog).
2. The operation needs the `catchment_characteristics` input, but the command gives only a point.
3. The resolver finds an operation that returns this input: `delineate_catchment` (Hydrograf),
   and adds it before the computation.
4. The user confirms a plan with two steps: catchment → flow.

**Algorithm (resolver):**

1. The decision model recognizes the target operation.
2. For each input the resolver checks in order:
   1. whether the command points to a file or an earlier result (chapter 5) → takes it,
   2. whether an operation exists that returns this data kind → adds a step,
   3. if not → asks the user.
3. Step 2 repeats for the added operations until all inputs are known.
4. If several operations can supply an input, the choice belongs to the decision model (`choice` question)
   or to the user when confidence is low.
5. The resolver detects cycles and a missing installed tool
   ("this requires Hydrograf" together with the install command, section 9.4).

**Chain execution:**

- The user confirms the **whole plan** (all steps at once), not each step separately.
- Questions about missing parameters are collected from the whole chain and asked together.
- After each step a **sanity check** of the result is performed (e.g. catchment area
  in the expected range, no gaps in the data). On a mismatch the chain stops
  and shows what is suspicious.
- Intermediate results go to the workspace, so after an error the chain can be resumed
  from the point where it stopped.

---

## 5. Workspace [W-07]

The workspace lets the next command use the result of the previous one. Without it,
v0.1 could not perform operations that need complex input data
(e.g. catchment characteristics), because such data cannot be given in a single sentence.

### 5.1. Project = folder

The workspace belongs to a **project**, and a project is the folder in which Retman is run.
Results go to the results subfolder in that folder; its name is set by the `output.results_dir`
setting (default `retman-output`, section 9.1). Results from different projects never mix.

```
~/projekty/zlewnia-a/              ← run here: cd ~/projekty/zlewnia-a && retman plan run
└── retman-output/                 ← created with the first result
    ├── 001_delineate_catchment/
    │   ├── catchment.geojson
    │   └── result.json
    └── 002_peak_flow/
        └── ...
```

The result's files lie in its subfolder or — when the tool keeps data in its own store —
in the store, which lies outside the project folder and is shared between projects (section 9.1): the result
then points to those files by absolute path and SHA-256 checksum (section 5.4), copying nothing.
The result can be the input of the next operation in both cases (section 5.3).

### 5.2. Result numbers

- Each result gets a **consecutive number within the project** (#1, #2, …), which Retman shows
  after execution, e.g. "Result #1: catchment, point 52.41° N, 16.93° E — 118.4 km²".
- The number is part of the subfolder name (`001_delineate_catchment/`) and is stored
  in `result.json` together with the operation, parameters, output data kinds (`kind`), date, files
  and a short description that lets results be told apart (full contents: section 5.4).
- A result can be referenced directly: *"Policz Q1% dla zlewni #1"* (compute Q1% for catchment #1).
  The number is extracted by the `results` extractor (code, no model).
- `retman results list` displays the list of results in the current project.

### 5.3. Input selection — no guessing

When an operation needs an input of a given kind (e.g. `catchment_characteristics`):

| Situation | What Retman does |
| --- | --- |
| the command points to a file ("…z pliku warta.geojson", i.e. "…from file warta.geojson") or a result number ("#1") | takes exactly that; the file is checked by the data kind validator (section 3.2.6) |
| the project has **one** matching result | proposes it in the plan, clearly marked |
| there is **more than one** matching result | **always asks** which one to use — even when one of them is the newest |
| there is none | says what is missing and how to obtain it (e.g. "first delineate the catchment") |

Retman **does not try to guess** which thread the user means. With more than one
possibility it asks, so mixing threads in one project does not lead to silent mistakes.
Candidates are described by what lets them be told apart: number, the most important parameters and time.

```
? Której zlewni użyć?
  1) #1  punkt 52.41, 16.93 — 118,4 km² (dziś 14:32)
  2) #3  punkt 52.28, 17.05 — 36,1 km² (dziś 15:10)
> 1
```

**Step-by-step example** (the project has one catchment):

```bash
retman plan run --text "Wyznacz zlewnię dla punktu 52.41, 16.93"            # → Wynik #1
retman plan run --text "Policz przepływ stuletni Punzetem dla tej zlewni"
```

Plan of the second command:

```
Plan:
  Operacja:                          Obliczenie przepływu maksymalnego
  Zlewnia:                           ← wynik #1: punkt 52.41° N, 16.93° E, 118,4 km² (2026-10-11 14:32)
  Metoda:                            Punzet
  Prawdopodobieństwo przewyższenia:  1% (T = 100 lat)
Wykonać? [t]ak / [n]ie / [z]mień
```

Because every execution requires confirmation (section 6.3), the user always sees which result
was used and can change it (`z`).

### 5.4. Project journal and audit trail [W-15]

Goal: from the project folder alone it is possible to determine **what was computed, with what and how** — even after
months and on another computer. This matters especially for public administration, which issues decisions based
on computations.

Exception: with `journal_commands = false` (section 9.1) `result.json` and the journal do not contain the text of
commands or the user's answers, and the journal also omits other texts shown to the user
that may quote them (the plan, the reason for re-asking a question, the lines of the availability report);
the remaining audit data is always stored (PRD W-15).

**1. Audit data in `result.json`** (with every result):

| Section | Content |
| --- | --- |
| `number`, `operation` | result number and executed operation |
| `command` | the user's command and answers to Retman's questions (if `journal_commands = true`, section 9.1) |
| `params` | every value used together with its source: `command`, `default`, `workspace`, `known`, `user` (section 7.1); for an area from a geometry file the value also carries the selected layer, and the entry has `files` — SHA-256 checksums of the geometry files by name (Shapefile: `.shp`, `.shx`, `.dbf`, `.prj`) |
| `decisions` | model decisions: question, selected option, probabilities, confidence and its method (`basal`, `logprobs`, `consistency`, `none`) |
| `inputs` | source of each input: result #N or a file — path and SHA-256 checksum, so it is visible whether the file changed later |
| `outputs`, `values`, `files`, `warnings`, `error` | as in `Result` (section 7.3); every output file with a SHA-256 checksum: path relative to the project, and for a file in a tool's store an absolute path and `store` (tool name) |
| `error_code` | stable tool error code when the operation failed because of the tool (only then) |
| `tool` | block of calls to the tool catalog (only operations through the command layer, section 3.2.4): the tool and its version, and for each call the command, options, exact command line (with environment arguments), document schema, status, files (path, SHA-256, version label, status) and the name and SHA-256 checksum of the full tool document, saved in the result folder as `tool_<n>_<command>.json` |
| `unset` | optional parameters the command did not provide, with a text explaining what that means (section 6.3); only when non-empty |
| `preview` | values determined by the offline preview (e.g. area bounding box, number of map sheets); only when non-empty |
| `checks` | reports of availability checks run for the final state of the plan (`CheckReport.to_dict()`, section 6.5); only when there were any |
| `environment` | Retman version, versions of the tools used, decision model (backend, name, server address), Python version, operating system |
| `timing` | plan approval, start and end of execution, duration |

**2. Project journal** — `retman-output/journal.jsonl`, one line per event:

| Event | Recorded |
| --- | --- |
| command | text (if `journal_commands = true`), time, session identifier |
| question and answer | question text, user's answer (if `journal_commands = true`); for a question asked again after rejection by the tool also the reason (`reason`, if `journal_commands = true`) |
| plan | the plan shown and its decision: **approved / rejected / changed / cancelled**; plus data: values with sources (`values`, `inputs`), open questions, model decisions with confidence (`decisions`), and on change — the name of the changed value (`changed`) |
| out of scope | the model's decision that the command does not concern any operation (with confidence) |
| availability check | `check` (section 6.5): consent and execution (`approved`, "executed") or refusal of consent (`rejected`, "skipped", without network use); result (`available`, `partial`, `unavailable`, `unknown`), error, tool and its version, report lines (if `journal_commands = true`) and the plan data that were sent (values with sources, inputs, model decisions); also recorded on interruption (Ctrl+C); not written to the command set (ADR-010) |
| execution | result number or error description |

The journal is **append-only** — Retman never changes or deletes entries. It also records
what was **not** executed (rejected plans, cancellations, errors), because that too is part
of the work history.

`retman journal show` shows the journal in a readable form:

```
$ retman journal show
2026-10-11 14:31  polecenie: „Wyznacz zlewnię dla punktu 52.41, 16.93”
2026-10-11 14:31  plan zatwierdzony → wynik #1 (zlewnia, 118,4 km², 12 s)
2026-10-11 15:02  polecenie: „Policz przepływ dla tej zlewni”
2026-10-11 15:02  pytanie: Której zlewni użyć? → #1
2026-10-11 15:03  plan odrzucony
```

`retman journal show` also shows the "availability check" event with the outcome "executed"
or "skipped".

**3. Technical log** — separate, for diagnosing Retman problems (connections, response times,
errors); the library logs via `logging`, and the CLI prints the log to stderr (DEV-12). **Without
command and answer text.** Level: `--verbose` (debug) or `--quiet` (errors only), then
`RETMAN_LOG_LEVEL`, `NOGAT_LOG_LEVEL` and the `log_level` setting in `[retman]` and `[nogat]` (section 9.1); by default
`warning`.

**4. Command set** (optional, ADR-010) — a single file from **all** projects, for building
and tuning the test set (`retman eval run`). Each line is a planning result: status
(approved with execution result, rejected, changed, cancelled, out of scope),
command, answers, values with sources, questions, model decisions, Retman and tool
versions, backend and model name — **without the server address** and without local paths (of a
geometry file only the name remains). It is enabled only by explicit consent: `retman config init` asks for it in the terminal,
without a terminal it writes `false`; the file path is set in `[retman.privacy]` (`collect_path`,
by default `<data_dir>/retman/collected.jsonl`: on Linux `~/.local/share/nogat/retman/collected.jsonl`,
on macOS `~/Library/Application Support/nogat/retman/collected.jsonl`, on Windows
`%LOCALAPPDATA%\nogat\retman\collected.jsonl`). The set is independent of `journal_commands`;
`retman eval run` never writes to it. The file stays on the user's computer.

**Three things that must not be confused:**

| What | Where | Command text |
| --- | --- | --- |
| project journal + audit data | project folder | **yes** — this is a record of the user's work; can be disabled (`journal_commands`) |
| technical log | stderr (CLI) | no |
| command set | a single user file (`collect_path`) | **yes**, only after explicit consent (`collect_commands`, chapter 10) |

### 5.5. Later (v0.2+)

- Result names alongside numbers ("zapisz jako zlewnia_warta" — "save as zlewnia_warta").
- Workspace as a place for intermediate results of chains (section 4.5).
- Re-execution of a saved plan based on audit data (e.g. `retman rerun #3`).

---

## 6. Asking follow-up questions and confirmation

### 6.1. When Retman asks [W-02], [W-03]

| Situation | Reaction |
| --- | --- |
| Confidence of operation choice < threshold | Shows the 2–3 most likely operations to choose from |
| Confidence of category choice < threshold (two-stage recognition, section 3.4) | Shows the 2–3 most likely operation groups to choose from; the model then picks the operation within the chosen group |
| `out_of_scope` chosen (at either recognition stage) | Reports that the command matches no operation (with two-stage recognition — no group) and shows the list of available ones |
| Required parameter = `unspecified` | Asks for that parameter, showing the list of options |
| Parameter confidence < threshold | Asks: "Did you mean X?" |
| Extractor found nothing | Asks for the value and gives an example of the format |
| Extractor found several matches (e.g. several stations with similar names) | Shows the candidates to choose from |
| Inexact match: station name only in an inflected form ("w Poznaniu", "z Opola" — "in Poznań", "from Opole") | Shows the reading and asks for its confirmation by choosing from a list; an inflected name is not accepted silently. Names are not corrected after typos either |
| Station given by name, but the IMGWTools store has no station catalog | The catalog exists only after the operation that builds it (network, after confirmation), so until then Retman reads only station codes (9 digits, WIGOS) and asks for the code |
| Year type (hydrological or calendar) not stated in the command | **Always** asks — there is no default value. The word "hydrologiczne" describing the data ("dane hydrologiczne z lat 2000–2020" — "hydrological data from the years 2000–2020") is not an answer |
| Relative or open period ("ostatnie 10 lat", "od 2010" — "the last 10 years", "since 2010") | Does not guess dates: asks for years or dates. A bare four-digit number is not a year (it may be a TERYT code, a sheet code (godło) or an EPSG code) |
| The project has several matching results (e.g. several catchments) | Asks which one to use (section 5.3) |
| Ambiguous notation (e.g. "Q50", section 4.4) | Asks which reading is correct |
| Geometry file in GeoPackage with several layers | Shows the list of layers to choose from; the layer is not guessed (a single layer is used and shown in the plan; Shapefile has no layers) |
| Area file in a format the tools do not read (GeoJSON, GML) | Refuses with a reason: the geometry must be an SHP or GPKG file |
| Tool rejects the choice offline (e.g. resolution and vertical datum that do not form a valid pair) | Asks again for the parameters the tool indicated, with the reason in the question (section 6.3) |
| Required input missing (neither in a file nor in the workspace) | Reports what is missing and how to obtain it |
| Value out of range (e.g. coordinates outside Poland, probability outside `range`) | Reports and asks for a correction |
| Probably swapped coordinate order | See the note below |

**Note on coordinates.** Axis order can be confusing: in WGS84 people sometimes write "latitude,
longitude" and sometimes the reverse, and in the PL-1992 system (EPSG:2180) the X axis points north,
the opposite of the intuitive "X = east". The extractor recognises the system and the order by labels
and by the disjoint value ranges for Poland; a pair that fits both orders yields two readings, so
Retman asks instead of choosing. It converts PL-1992 coordinates in pure Python, without geospatial
libraries and without a tool. The plan always shows how Retman read the coordinates
(e.g. "52.41° N, 16.93° E") and asks for confirmation when the interpretation is ambiguous.

### 6.2. Confidence thresholds [N-05]

- **By default** (`"auto"`) Retman takes the thresholds from basal's calibration (`CALIBRATION.json`,
  1% error level). The value `"auto"` is allowed only with `backend = "basal"`.
- They can be **overridden** with a number in the configuration (section 9.1).
- The basal thresholds were chosen on simple question formats (option descriptions, yes/no
  questions). For Retman's questions they should be **tuned on your own test set** (chapter 8) and
  entered into the configuration.
- There is a separate threshold for operation recognition (also for category selection,
  section 3.4) and for parameters.
- For models without calibrated confidence the thresholds from basal's calibration do not apply.
  With confidence from `logprobs` or from agreement, the thresholds have to be tuned separately for
  the given model and entered as a number; `"auto"` with a backend other than `basal` (e.g.
  `openai_compatible`) is a **configuration error** — Retman reports it at startup, and
  `retman doctor check` shows it with a hint, because Retman has no hidden default values
  (section 9.1). In `none` mode the thresholds are skipped (their value is not checked), and the
  values chosen by the model are marked in the plan as unverified (section 3.3.3).

### 6.3. Confirmation [W-04], [W-05]

Before execution Retman always shows the plan in a readable form, e.g.:

```
Plan:
  Operacja:      Pobranie danych pomiarowych IMGW
  Rodzaj:        opad
  Krok czasowy:  dobowy
  Stacja:        Poznań (kod stacji z listy IMGW)
  Okres:         2000-01-01 – 2020-12-31
  Format:        CSV   ← wartość domyślna, nie podano w poleceniu
Wykonać? [t]ak / [n]ie / [z]mień
```

Rules:
- In 0.x versions **every execution requires confirmation**. There is no mode that skips it.
- A plan is complete if and only if there are no open questions. When it is complete, the tool
  checks it **offline** (preview, section 3.2.4): it validates every call that would perform the
  operation and may add rows to the plan marked `← podgląd, bez sieci` (e.g. the number of map
  sheets for an area from a geometry file). When the tool rejects a value, Retman asks again about
  the parameters the tool pointed to, with the reason in the question — a plan the tool does not
  accept cannot be confirmed. It does not reopen values supplied from outside (`known`), and when
  there is nothing to reopen, it raises an error (`RetmanError`) instead of looping the questions.
  A rejection that no answer can fix (the installed tool no longer accepts what the manifest
  describes) ends with a `ToolDriftError` and a hint to run `retman doctor check`.
- Parameters filled with a default value, readings of ambiguous notations, inputs taken from the
  workspace and preview rows are clearly marked so that the user can change them.
- An optional parameter (without `required` and without `default`) that the command did not provide
  is not a question, but it has its own plan row with the text `params.<p>.unset` (e.g. "Rodzaj
  stacji: wszystkie rodzaje (hydrologiczne i meteorologiczne) ← nie podano w poleceniu, parametr
  nieobowiązkowy" — "Station type: all types (hydrological and meteorological) ← not given in the
  command, optional parameter"); `validate_manifest` requires this text, and
  `result.json["unset"]` records it (N-11: nothing happens silently).
- Confirmation applies to exactly that plan: every change (an answer, `z`) and every availability
  check (section 6.5) revokes it. The order is always: check, confirmation, execution.
- In the Python API `execute()` accepts only a plan confirmed via `plan.confirm()`. Without it,
  it raises `PlanNotConfirmedError`. Serialization does not carry confirmation over:
  `Plan.from_dict` always returns an unconfirmed plan (section 7.1).
- Quality tests (chapter 8) check planning, not execution, so the mandatory confirmation does not
  get in their way.

### 6.4. Conversation in the terminal [W-02], [W-05], [W-11]

Asking follow-up questions and confirming in the CLI take the form of a **conversation in the
terminal**.

| Command | Mode |
| --- | --- |
| `retman plan run --text "…"` | **single command**: questions → plan → confirmation → result, then exit |
| `retman plan run` (no `--text`, in a terminal) | **session**: many commands in one conversation (e.g. first a catchment, then a flow "for this catchment"); exit: `koniec` ("end"; `end` with `--lang en`) or Ctrl+D |

**Example** (station names and numbers are illustrative):

```
$ retman plan run --text "ściągnij opady z poznania"
Rozumiem: pobranie danych pomiarowych IMGW (opad).

? Za jaki okres pobrać dane?
  np. „2000–2020”, „ostatnie 10 lat”, „od 2015”
> od 2010 do 2020

? Nazwie „Poznań” odpowiada kilka stacji. Którą wybrać?
  1) Poznań-Ławica
  2) Poznań-Strzeszyn
> 1

Plan:
  Operacja:      Pobranie danych pomiarowych IMGW
  Rodzaj:        opad
  Krok czasowy:  dobowy   ← wartość domyślna, nie podano w poleceniu
  Stacja:        Poznań-Ławica
  Okres:         2010-01-01 – 2020-12-31
Wykonać? [t]ak / [n]ie / [z]mień
> t

Gotowe. Wynik #4: pobrano 4018 dni pomiarów. Pliki: retman-output/004_fetch_imgw_data/
```

**Rules of the conversation:**
- **One question at a time**: first the operation (if it is uncertain), then the parameters in the
  order given by the manifest.
- When choosing from a list, the user can give **the option number or answer in their own words**.
  Words go through the same mechanism as the command (decision model for choices, extractors for
  values). If the answer is still unclear, Retman says how it understood it and asks again.
- A question about a value shows an **example of the format**. A wrong answer → a short explanation
  of what is wrong, and the same question again.
- When a parameter has a default value, it is shown in parentheses and **Enter** accepts it.
- **`?`** at any question shows a short explanation of the parameter (from the translation file).
- **`anuluj`** ("cancel") or Ctrl+C aborts without executing anything.
- At the plan: **`t`** executes, **`n`** declines, **`z`** lets the user change a selected value
  (numbered list) without typing the command again; **`s`** — only when the operation offers an
  availability check — runs a separate step with its own notice and consent (section 6.5). These are
  the Polish words; with `--lang en` they are `y`, `n`, `c`, `a` and `cancel`, from the `[answers]`
  table of the translation file.
- After execution the CLI prints a summary of the result, then each tool warning on its own line
  "Uwaga: …" ("Note: …") (data quality and licensing notices).
- Answers go into the plan with the source `user` (section 7.1).

**Without a terminal** (scripts, pipes, CI — the input is not a terminal) Retman asks no questions
and executes nothing, nor does it check availability (section 6.5). It prints what is missing or
what the plan would be, and exits with the appropriate exit code. This is a consequence of the
mandatory confirmation (section 6.3) and the "no network before confirmation" rule (N-12).

**Modes of one command** (ADR-022): `--check` shows the plan with its open questions and exits with 0, so the
plan is the result and no open question is an error; `--yes` confirms a complete plan and runs it without a
terminal; the two exclude each other. With `--json` the document is the envelope `retman-result/1` and nothing is
ever asked.

| Exit code | Meaning |
| --- | --- |
| 0 | operation executed (or plan shown with `--check`) |
| 2 | `validation_error`: invalid option or configuration, or answers or confirmation needed while the input is not a terminal (`details.reason` `input_required`) |
| 15 | `unsupported`: command out of scope (W-03, `details.reason` `out_of_scope`) |
| 130 | `cancelled`: aborted by the user (`anuluj`, `n`, Ctrl+C) |
| other | Nogat registry code of the error that ended the call (ERR §2): e.g. 5 — model not responding, 14 — source has no data, 1 — error in Retman |

The last line of stderr on error is a `retman-error/1` document (AGI-3.3); the full table of codes
is in USAGE section 8. The mapping of exception classes to codes is described in ADR-020.

**One logic, many interfaces.** The conversation in the terminal is only a display layer. Questions
are created and answers are checked by `core/dialog.py`, also available from Python
(`plan.questions`, `plan.answer()`, `plan.can_check`, `plan.confirm_check()`, section 7.1). Thanks
to this, the same questions will later serve the MCP server, the HTTP API and the GUI (sections 7.4,
7.5).

**Dependencies:** in v0.1 only the Python standard library (`input()`), no libraries for terminal
interfaces.

### 6.5. Availability check [W-17], [N-12]

Offline validation (section 6.3) knows whether the tool will accept the request, but it does not
know **what the data source actually has** for the selected area: which years and resolutions
exist, whether coverage is complete, which IMGW archives are already published. This can only be
learned over the network, and before plan confirmation Retman does not use it (N-12). That is why
the check is a **separate step on request**, with its own notice and its own consent — the only
exception to this rule.

The answer **`s`** to the plan question is available only when the operation declares `check`
(section 4.3) and the plan is complete (illustrative example; the report lines come from the
tool's `pl.toml`):

```
Plan:
  Operacja:                 Pobranie NMT dla arkusza
  Godło arkusza NMT:        godło arkusza N-34-130-D-d-2-4
  Rozdzielczość NMT:        1 m
  Układ wysokościowy NMT:   EVRF2007
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
> s
Sprawdzenie dostępności to osobny krok i jedyny, który łączy się z internetem przed wykonaniem planu.
Zapytam usługi GUGiK (skorowidz arkuszy WFS i warstwę PRG) o dane dla godła z planu.
Nie pobiera plików, niczego nie zapisuje w wynikach i nie wysyła Twojego polecenia — tylko wartości z planu.
Połączyć się z internetem i sprawdzić? [t]ak / [n]ie
> t
Sprawdzam… (Ctrl+C przerywa)
Sprawdzenie dostępności (Kartograf 0.8.0, 2026-10-19 16:12): dane dostępne
  Twój wybór: NMT, 1 m, EVRF2007 — dostępny, rok 2023, komplet arkuszy
  Dostępne także dla tego obszaru:
    NMT 0,5 m, EVRF2007 — rok 2025, komplet
    NMT 1 m, KRON86 — rok 2019, komplet
Wykonać? [t]ak / [n]ie / [z]mień / [s]prawdź dostępność (sieć)
```

**Gate rules** (testable invariants):

1. `Retman.check()` raises `CheckNotConfirmedError` if there was no `plan.confirm_check()`. Consent
   is single-use (`check()` consumes it), is not part of the plan state (`to_dict()` does not save
   it, and `from_dict` always yields "no consent") and is revoked by every change to the plan.
2. `confirm_check()` does not confirm the plan. `check()` **revokes** the plan confirmation,
   because the summary has changed — the user confirms only after seeing the report.
3. `confirm_check()` and `check()` require a complete plan and a declared `check`
   (otherwise `PlanIncompleteError`).
4. The check creates no result number or result folder and writes nothing to the workspace. The
   only entry points able to use the tool's network access are `execute()` (after `confirm()`)
   and `check()` (after `confirm_check()`) — only they build the full tool client (`RunClient`,
   section 3.2.4).
5. The check **never changes plan values**: it informs, and the user decides (W-02).
   `plan.checks` always describes exactly the current state of the plan (a plan change clears it);
   earlier checks remain in the journal. After a check the plan shows the row "Sprawdzenie
   dostępności: <status> (<time>)" (Availability check: <status> (<time>)), so the approved plan and
   the journal record that the user decided after seeing the report. The check does not block `t`
   — even with the status "no data".
6. A failure of the check (no network, service error) is **a report with status `unknown`** and
   the reason in `error`, not an exception. An interruption (`KeyboardInterrupt`) propagates, and
   the journal still receives a `check` event.

**Statuses** (`CheckReport.status`): `available` — the selection from the plan can be served as
specified; `partial` — part of it (missing or incomplete map sheets, files); `unavailable` —
nothing; `unknown` — could not be determined. Report lines (`items` → `lines`) are ordered: first
the plan's own selection, then alternatives (e.g. other years or resolutions for this area); the
text of each line comes from the `[check]` table in the tool's `pl.toml`.

**What the check sends:** only values from the plan (area, product, years…) to the same data
services that execution would query; never the content of the command, answers, model data or
file contents. The notice before consent (`operations.<id>.check.notice`) says which services will
be queried. There is no switch in the settings that disables checks: each one requires consent
on screen.

**CLI:** any answer other than `t` to the consent question is a **refusal** (fail-safe): the journal
records "skipped", Retman says "Sprawdzenie pominięte." (Check skipped.) and returns to the plan
question. After the report the same plan question returns, and `z` works as usual — every new value
goes through the offline preview again. Without a terminal and with `--check` Retman never
checks (exit codes unchanged). Ctrl+C during a check ends the conversation with code 130
("Anulowano." — Cancelled.).

**Journal and result:** the `check` event (section 5.4) records consent or refusal, status, error,
the tool and its version, the report lines and the plan data that were sent; it is also recorded on
interruption. Reports for the final plan state go to `result.json` (`checks`).

---

## 7. Interfaces

### 7.1. Python library + CLI (v0.1) [W-11]

**CLI:**

```bash
retman plan run --text "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020"   # one command: questions, plan, confirmation, result (section 6.4)
retman plan run                         # in a terminal: a session, many commands in one conversation (section 6.4)
retman plan run --text "..." --check    # show the plan only, run nothing; open questions are part of the plan
retman plan run --text "..." --yes      # confirm and run a complete plan without a terminal
retman plan run --text "..." --explain  # show model decisions and confidences (diagnostics)
retman plan run --text "..." --json     # the envelope retman-result/1 on stdout, never asks (ADR-022)
retman config show                      # every setting with its value and source (section 9.1); --json: retman-config/1
retman config init                      # write the [retman] tables into nogat.toml and set up the tool stores (section 9.1); a wizard from v0.5
retman doctor check                     # environment check (section 7.2); --deep: also the slow checks; --json: the report as JSON
retman results list                     # list results of the current project (section 5.2)
retman journal show                     # show the project journal (section 5.4)
retman commands list                    # the command catalog; `commands schema` describes one command, `commands guide` prints AGENTS.md and llms.txt
retman eval run                         # measure the model on the test command set (section 8.2)
retman scaffold check                   # compare the tool descriptions with the installed tools; also `scaffold list`, `scaffold draft` (section 3.2.3)
retman add-tool kartograf               # add a known tool to Retman's environment (from v0.5, section 9.4; not in the catalog yet)
```

Every command also takes `--json`, `--lang pl|en`, `--verbose` and `--quiet`; `--config PATH` names another settings
file (for example in tests) for the commands that read the settings.

**Python:**

```python
from retman import Retman

retman = Retman.from_config()        # central config file (section 9.1); an explicit path is optional, e.g. in tests

plan = retman.plan("ściągnij opady z poznania")

# Answer Retman's questions one by one (the CLI does the same in the terminal, section 6.4)
while plan.questions:
    question = plan.questions[0]
    print(question.text)                 # question in the user's language
    for number, option in enumerate(question.options, start=1):
        print(f"  {number}) {option.label}")
    plan = plan.answer(question.name, input("> "))
    # The answer is checked with the same extractors and validators as the command.
    # An invalid answer keeps the question open and explains why in question.error.
    # A complete plan has been checked offline by the tool (section 3.2.4): if the tool
    # rejects a value, the parameters it names come back as questions with the reason.

print(plan.summary())                    # human-readable plan; defaults, workspace inputs and preview rows are marked

# Optional: ask the tool's data services what exists for this plan (a separate network step, section 6.5)
if plan.can_check:
    print(plan.check_notice())           # what the step contacts and what it sends
    if input("Check availability? [y/n] ") == "y":
        plan.confirm_check()             # separate, single-use consent; does NOT confirm the plan
        report = retman.check(plan)      # CheckReport; raises CheckNotConfirmedError without confirm_check()
        print(report.summary())          # status and lines; the plan's values are untouched
    else:
        retman.record_check(plan, "rejected")    # journal entry; no network was used

if input("Execute? [y/n] ") == "y":
    plan.confirm()                       # explicit confirmation is mandatory (check() withdraws it)
    result = retman.execute(plan)        # raises PlanNotConfirmedError without confirm()

    if result.ok:
        print(result.summary)            # short description of the result
        print("Files:", result.files)
    else:
        print("Error:", result.error)
    for warning in result.warnings:      # tool notices (data quality, licence): always show them
        print("Warning:", warning)
```

`Retman.from_config()` without an argument loads the settings (section 9.1) — the same ones
the CLI uses; an explicit path (`path`), a model stub (`backend`) and a project folder (`project_dir`)
can be given optionally, e.g. in tests. The constructor `Retman(config, backend, project_dir)`
additionally accepts `clients={tool: client}` (injection of tool clients, e.g.
`FakeToolClient`; by default the client is built lazily from the manifest, section 3.2.4) and `today`
(the date relative to which extractors read relative expressions).

| Element | Meaning |
| --- | --- |
| `plan.questions` | list of open questions (`Question`); empty when the plan is complete (and accepted by the tool's preview) |
| `Question` | `name` (parameter), `type` (`choice`, `value`, `confirm`), `text` (wording in the user's language), `options` (for choices), `default`, `example` (format example), `error` (why the previous answer was wrong or why the tool rejected the value), `help` (answer to `?`) |
| `plan.answer(name, answer)` | returns a new plan with the answer; an option number or the user's own words |
| `plan.change(name)` | reopens a shown value for correction (`z` in the CLI) |
| `plan.preview_rows`, `plan.preview_values` | what the tool determined offline about the complete plan: rows (shown in the plan with a marker) and values (for audit only, section 5.4) |
| `plan.reopened` | parameters the tool rejected after the user's answer, with the text shown when the question is asked again (section 6.3) |
| `plan.can_check` | whether the operation offers an availability check and the plan is complete (section 6.5) |
| `plan.check_notice()` | text to show before consent: what the check contacts and what it sends |
| `plan.confirm_check()` | one-time consent for a single check; does not confirm the plan |
| `retman.check(plan)` | availability check; returns a `CheckReport`; without consent `CheckNotConfirmedError`; revokes the plan's confirmation; does not create a result |
| `retman.record_check(plan, "rejected")` | project journal entry about refused consent (no network use) |
| `plan.checks` | check reports for the current state of the plan |
| `CheckReport` | `operation`, `tool`, `version`, `checked_at`, `status` (`available`, `partial`, `unavailable`, `unknown`), `header`, `items` (machine-readable facts), `lines` (lines shown to the user), `error`; `summary()`, `to_dict()` |
| `result.warnings` | translated operation warnings; the caller must show them (section 7.3) |
| `result.error_code` | stable tool error code when the operation failed because of the tool |

**Plan as data and externally known values** (preparation for cooperation with a GUI, section 7.4):

```python
from retman import Plan

# Values already known from another source (e.g. filled in a GUI form) are treated as fixed:
# Retman does not ask about them and never overwrites them, it only fills in what is missing.
plan = retman.plan(
    "Policz przepływ dla tej zlewni, nie wiem jaką metodą",
    known={"probability": [0.01]},
)

state = plan.to_dict()          # JSON-serializable: operation, values and the source of each value
same_plan = Plan.from_dict(state, retman=retman)    # `retman=` lets the loaded plan answer questions
```

`to_dict()` contains the values with their sources, questions, model decisions, `reopened`, preview rows
and values, and check reports. Consent to a check is not part of the state, and `Plan.from_dict`
**always returns an unconfirmed plan** — even when the saved state carries `confirmed`: the confirmation
must be given again (`plan.confirm()`), which closes the gap through which a transmitted plan could
execute without a human [W-05].

The source of each value in the plan: `command` (from the command), `default` (default value),
`workspace` (an earlier result), `known` (supplied externally, e.g. in a GUI), `user` (answer to a Retman question).

### 7.2. `retman doctor check` — environment check [W-10]

`retman doctor check` shows in one place what works, what does not, and how to fix it.

**What it checks:**

| Area | Checks |
| --- | --- |
| Configuration | path and validity of the settings file `nogat.toml` (all problems at once; a missing file is not an error, default values apply) and model settings (their absence blocks planning); the current project folder and whether the results folder is writable |
| Decision model | **server address**; whether it responds; which model is loaded; a **test question** with an obvious answer (whether the model answers sensibly); where the confidence comes from (`basal`, `logprobs`, agreement, unavailable) and the thresholds (`"auto"` with a backend other than `basal` is a configuration error, section 6.2) |
| Text model | whether it is enabled; **server address**; whether it responds |
| Tools | which are installed; whether their versions fall within the supported range; number of available operations |
| Tool data stores | for tools in use (installed, in a supported version, not disabled): store path without symbolic links (IMGWTools does not accept one: error; Kartograf: warning), the folder exists or can be created and is writable, **hard links work in both stores** (attempted in the store or in the nearest existing folder on the same disk); Kartograf: the `kartograf-store.json` marker and its schema (a missing or an empty folder is only not marked yet, the first write marks it; a folder with the layout of a store, that is files in a product tree such as `nmt/`, but no marker (reason `no_marker`; the hint is the command "Utwórz magazyn Kartografa", which runs `store init`), a folder with other files (`foreign_folder`), a marker that is corrupted or has another schema (`marker_unreadable`, `marker_unsupported`) and a folder that lies in, is or holds the store of another tool or place (`nested_store`) are errors), metadata cache (missing is a warning — Kartograf runs slower); IMGWTools: the `imgw-store.json` marker and its schema (a missing store, or a folder that holds only the `api_keys.json` of the tool's server, is a warning with a hint; a folder with the layout of a store but no marker (reason `no_marker`; the hint is the command "Utwórz magazyn IMGW", which runs `store init`), a foreign folder or a corrupted marker is an error), `pyarrow` (time series), reference data folder; with `--deep` also a trial write to the IMGWTools store |
| Conformance of descriptions with tools | a light version of `retman scaffold check` (section 3.2.3) for tools in use: the commands from the manifest are in the installed tool's catalog, and the tool does not offer a value that the manifest neither offers nor disables (e.g. "kartograf 0.8.1 accepts a resolution of 0.3 m"); operations without a row in the `retman eval run` set are reported as unchecked. These lines warn but do not block work (exit code unchanged) |
| Translations | complete set of texts for the language from the `lang` setting |
| Workspace | results folder of the current project; number of results; whether the `result.json` files can be read |

**Example result:**

```
$ retman doctor check
Retman 0.1.0

Konfiguracja
  ✓ plik ustawień: ~/.config/nogat/nogat.toml (istnieje)
  ✓ projekt: ~/projekty/zlewnia-a → wyniki w retman-output/ (5 wyników, zapis możliwy)

Model decyzyjny
  ✓ adres modelu (basal): http://127.0.0.1:8000
  ✓ model: basal-1.5-mini dostępny na serwerze
  ✓ pytanie testowe: poprawna odpowiedź (pewność 0,99 z basala)
  ! progi pewności: "auto" — zalecane dostrojenie na własnym zbiorze testowym (retman eval run, ARCHITECTURE 6.2)

Narzędzia
  ✓ imgwtools 3.0.0, obsługiwane >=3.0.0.dev0,<4, 26 operacji
  ✓ kartograf 0.8.0, obsługiwane >=0.8.0.dev0,<0.9, 5 operacji

Magazyny danych narzędzi
  ✓ kartograf: magazyn /dane/retman/stores/kartograf (zapis możliwy, dowiązania twarde działają)
  ✓ kartograf: cache metadanych /home/ola/.local/share/retman/kartograf_cache.db
  ✓ imgwtools: magazyn /dane/retman/stores/imgwtools (znacznik imgw-store.json, schemat imgw-store/1, dowiązania twarde działają)
  ✓ imgwtools: pyarrow 18.1.0 (szeregi czasowe)
  ✓ imgwtools: dane referencyjne /home/ola/.local/share/retman/imgw-reference (hydro_stations_locations.csv: brak)

Zgodność opisów z narzędziami (retman scaffold check)
  ✓ imgwtools 3.0.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)
  ✓ kartograf 0.8.0: komendy z manifestu są w katalogu narzędzia, a jego wartości są oferowane albo wyłączone (X1, X4)

Tłumaczenia (pl)
  ✓ komplet

Model tekstowy
  – wyłączony ([retman.text] backend = "none")
```

The address of each model is shown without judging it — the user decides in the settings where
the model runs (chapter 10).

When the model server is not running or the store is not writable, the report suggests what to do, e.g.:

```
Model decyzyjny
  ✗ serwer modelu nie odpowiada (http://127.0.0.1:8000) → uruchom serwer modelu (np. LM Studio albo basal-serve, instrukcja w README) i sprawdź [retman.decision] url w ~/.config/nogat/nogat.toml albo zmienną RETMAN_DECISION_URL

Magazyny danych narzędzi
  ✗ imgwtools: system plików magazynu (/mnt/usb/imgw) nie obsługuje dowiązań twardych (Operation not permitted) → oba magazyny narzędzi wymagają dowiązań twardych (nie ma ich FAT/exFAT ani część udziałów sieciowych); wskaż magazyn na innym dysku w [retman.tools.imgwtools] store_dir (~/.config/nogat/nogat.toml)
```

Rules:
- Every problem has a **hint on how to fix it** (a command, a setting or a link to the README).
- Exit code: `0` when every check passes or only warns (work is possible); `10` (`partial`) when something blocks
  work (e.g. no model, no operations at all, or a store in which the tool cannot write data) and some checks passed,
  `11` (`failed`) when none passed; the report is printed in both cases (ADR-022).
- `retman doctor check --json` — the same report in a format to paste into a bug report.
- `retman doctor check --deep` — additional, slower checks: a trial write to the IMGWTools store
  using the tool's built-in test data, in a temporary directory and without network access (store
  initialisation, archives, a time series, the station catalog). It shows that the installed tool
  version writes the store on this system; requires `pyarrow`.
- When a regular command cannot connect to the model, the error message suggests `retman doctor check`.

### 7.3. Operation result [W-09]

`execute()` always returns a `Result` object with the same structure, regardless of the tool:

| Field | Content |
| --- | --- |
| `ok` | `True` if the operation succeeded |
| `number` | result number in the project (#1, #2, …; section 5.2) |
| `operation` | identifier of the executed operation |
| `params` | parameters actually used (marking which were default) |
| `inputs` | input sources (file, earlier result) |
| `outputs` | kinds of returned data (`kind`) — the basis of the workspace |
| `values` | numeric or short results (e.g. `{"file_count": 12}`) |
| `files` | paths to saved files, by data kind: in the result folder or in the tool's store (section 3.2.4) |
| `warnings` | translated warnings: partial result, tool notices about data quality and licence (verbatim; purely informational notices stay in the audit trail). The caller must show them — the CLI prints them after the summary |
| `error` | error description when `ok = False`; for a tool error — Retman's text selected by the stable error code, with the tool's text only as a quote |
| `error_code` | the tool's error code, a code of the registry (e.g. `no_data`), when the operation failed because of it; otherwise `None`; the tool's precision (e.g. `no_coverage`) is the `details.reason` of the `failure` document |
| `tool` | audit block of the tool's catalog calls (section 5.4); `None` for operations without such calls |
| `summary` | short description in the user's language (operation template, generic template or `TextBackend`) |

Files go to the results folder of the current project, in a subdirectory with the result number and
operation name, e.g. `retman-output/004_export_station_series/`, together with a `result.json` file,
which also contains audit data (section 5.4). Exception: files that the tool keeps in its own store
(Kartograf) stay in the store — the result points to them by absolute path and SHA-256 checksum, and
the result subdirectory contains `result.json` and the tool's documents (`tool_<n>_<command>.json`);
the summary then says where the files are.

### 7.4. Integration with tool GUIs (v0.5+) [W-13]

The user scenarios are described in the PRD. Here: how to realise them technically.

**Model:** a Retman plan is a **form state** — the operation, parameter values and the source of each
of them. Confirming the plan corresponds to the "Run" button in the GUI. The scenario "I fill in part
in the GUI, the rest I settle with Retman" is a plan with some values from the `known` source.

**What v0.1 already provides** (low cost, path left open for later):
- plan serialised to JSON (`to_dict()` / `from_dict()`), with the source of each value (section 7.1);
  a plan read back is always unconfirmed,
- values known from outside (`known`): Retman does not change them, it only fills in the missing ones,
- separation of planning from execution (section 6.3),
- availability check as a separate step with its own consent (`plan.can_check`, `plan.confirm_check()`,
  `retman.check()`, section 6.5) — in the GUI this is a separate "Check availability" button,
- results as files with `result.json` (section 7.3), which the GUI can load.

**Good practice on the GUI side:** forms based on the same public API functions that Retman's
handlers use. Then field and parameter names are shared, and passing a plan to a form is simple.

**Connection variants** (to be decided when the GUIs are built):

| Variant | How it works | Tool independence |
| --- | --- | --- |
| A. File exchange | Retman saves the plan to a JSON file; the GUI can load parameters from a file and watches the results directory | full — the GUI knows nothing about Retman |
| B. Optional chat panel | When the GUI detects a running Retman server (HTTP API), it shows a chat panel and exchanges plans with it | the GUI works fully without Retman; the integration is an optional add-on |

Convenient realisation of the PRD scenarios requires variant B. This is the only place where the
rule "tools know nothing about Retman" is relaxed — and only as an optional add-on.

**Who runs the analysis in GUI scenarios:** recommendation — the GUI (its "Run" button), with
Retman only planning. Then there is a single execution path and results appear in the GUI
naturally. Standalone Retman (CLI, Python API) still executes operations itself.

### 7.5. Other interfaces (later)

| Interface | Version | Notes |
| --- | --- | --- |
| MCP server | v0.3 | optional extra `retman[mcp]` (stdio): Retman plans with human confirmation in the client and an audit trail (section 7.5.1, ADR-018) |
| HTTP API | v0.4 | access to Retman for a web application and GUI integration (a model on a unit's server works without this from v0.1, section 3.3.4) |
| Chat in the browser | v0.5+ | for end users |

#### 7.5.1. MCP server (v0.3) [W-16]

The design is recorded in ADR-018; in v0.1 and v0.2 there is no MCP code, dependency or
configuration. Retman talks to tools through their Python APIs (section 3.2.1), and itself becomes
an MCP server for external AI assistants. This gives them what the tools' own MCP servers lack: a
plan shown with the source of every value, human confirmation, an audit trail and a numbered
workspace.

- **Package:** module `src/retman/mcp_server.py` (SDK imported lazily), optional extra
  `retman[mcp]` (`mcp>=2.3,<3`), never in the base dependencies (section 9.3). Start with:
  `retman mcp --project <directory>` (stdio; `--project` is mandatory, with no default to the current
  directory). Streamable HTTP only arrives with the HTTP API (v0.4).
- **Server-side state:** plans in memory (`plan_id` → `Plan`, with a time-to-live and count limit).
  The server **never loads a plan sent by the client**; `Plan.from_dict` does not restore
  confirmation anyway (section 7.1).

| MCP tool | Behaviour |
| --- | --- |
| `retman_operations` | list of operations of the installed tools (id, Polish label, parameters, data kinds); read-only |
| `retman_plan(command, known?)` | `Retman.plan`; returns the plan and its summary; values passed by the agent in `known` are marked in the plan with that source |
| `retman_answer(plan_id, name, answer)` | `plan.answer`; returns a new plan with open questions |
| `retman_check(plan_id)` | availability check (section 6.5) with its own elicitation and its own human consent; consent never comes from the agent |
| `retman_execute(plan_id)` | the **only** execution path |

`retman_execute` keeps the W-05 invariant: the plan must exist and have no open questions; the
server asks the **human** through MCP elicitation, showing the full plan summary (`plan.summary()`
with values marked as default, from the workspace and from `known`) and a boolean field
`confirm`; only on consent for that plan does it call `plan.confirm()`, and then `execute()`.
Refusal or cancellation ends with a "plan rejected" entry in the journal. **Fail-safe:** a client
that does not declare elicitation (or answers otherwise) executes nothing — it receives the
`confirmation_unavailable` error with the plan summary and instructions to run it in the terminal;
`retman_plan` and `retman_answer` keep working. The agent has no `confirm` argument and no switch in
the configuration.

Retman's questions (W-02) go back to the agent as data, but every value supplied by the agent is
marked in the plan (source `known` or `user` with `channel: "mcp"`), so it ends up in the plan that
the human reviews: the human gate is on the final plan, not on every question (to be settled at the
start of v0.3: chapter 12, item 16).

**Audit trail** (additively): `result.json` and the journal get `channel` (`cli`, `python`, `mcp`),
and for `mcp` also `client` (name and version from `initialize`), `confirmation` (method and time)
and `command.origin = "agent"` (the command text is the agent's paraphrase, not the user's words).

**Privacy** (N-04): the agent client is a service outside Retman's settings, usually a cloud model.
The `[retman.mcp]` table will appear in the settings template only in v0.3: `transport = "stdio"`,
`confirmation = "elicitation"`, `plan_ttl_seconds`, `max_open_plans` and `expose_command_text = false`
(command content is hidden from the agent even with `journal_commands = true`). The
`retman://results` resources return `result.json` without `command` and without absolute paths;
`retman doctor check` gets an "MCP" line. The audit covers only operations executed by Retman — whoever
runs the tools' MCP servers directly bypasses the trail.

**Tests** (offline, in-memory SDK transport with `FakeDecisionBackend`): `retman_execute` without
consent in elicitation has no effect; a client without elicitation receives
`confirmation_unavailable` and nothing is executed or written; a plan dictionary with
`confirmed = true` is not honoured; the resource does not reveal command content or absolute paths;
the journal records `channel = "mcp"` and refusals.

---

## 8. Tests and Quality Assessment

Target values of the quality metrics are set by the PRD. Here: how to measure them.

### 8.1. Test Command Set

The file `src/retman/eval/commands.jsonl` (package data, installed together with Retman), one line =
one command with its expected result.
Commands are in Polish (they are input data), identifiers in English:

```json
{"command": "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020", "operation": "fetch_imgw_data", "params": {"variable": "precipitation", "interval": "daily", "station": "Poznań", "period": ["2000-01-01", "2020-12-31"]}}
{"command": "ściągnij opady z poznania", "operation": "fetch_imgw_data", "params": {"variable": "precipitation", "station": "Poznań"}, "expect_clarify": ["period"]}
{"command": "Wyznacz zlewnię dla punktu 52.41, 16.93", "operation": "delineate_catchment", "params": {"point": [52.41, 16.93]}}
{"command": "Policz Q1% i Q10% Punzetem dla tej zlewni", "operation": "peak_flow", "params": {"method": "punzet", "probability": [0.01, 0.10]}}
{"command": "Ile wynosi Q50 dla tej zlewni?", "operation": "peak_flow", "expect_clarify": ["probability"]}
{"command": "Jaka będzie jutro pogoda?", "operation": "out_of_scope"}
```

Rules for building the set:
- at least 15 differently phrased commands per operation (formal, colloquial, with typos,
  abbreviations),
- deliberately incomplete and ambiguous commands (they test asking follow-up questions),
- commands outside the scope (expected operation `out_of_scope`),
- after the tool is released: extending the set with real user commands, collected with their
  consent (chapter 10).

### 8.2. Quality Metrics

| Metric | Meaning |
| --- | --- |
| Operation accuracy | % of correctly recognised operations |
| Parameter accuracy | % of correct parameter values |
| Automatic coverage | % of commands handled without asking follow-up questions |
| Error at confidence | % of wrong decisions among those above the threshold; initial target ≤ 1% (PRD W-02) |
| Relevant follow-ups | % of cases in which Retman asked about what was actually missing |

With two-stage recognition (section 3.4), `retman eval run` also records in the record the category
question (`category_question`: whether it was asked and what was proposed), answers it with the
category of the expected operation and counts it as a user follow-up. There is no separate
category accuracy metric — correctness is decided by the final operation.

The command `retman eval run --backend basal` runs the set and prints a report. The same set is used
to compare backends (basal-1.5-mini vs basal-1.5 vs a generative model).

`retman eval run` is part of the **base package** (section 9.3), with no additional dependencies. Every
user and deployer can use it to tune the confidence thresholds for their own model, which is
mandatory for backends other than basal (section 6.2).

### 8.3. Unit and Integration Tests

- Extractors are tested without a model (pure code, `pytest`), including all forms from
  section 4.4; contextual extractors (stations, variables) on an artificial catalog and an offline
  search stub.
- The pipeline is tested with a **backend stub** (`FakeDecisionBackend`) — tests do not require a
  GPU.
- The shared adapter is tested on a stub tool (`tests/fixtures/dummy_tool`: manifest, call
  builders, handlers, preview, check and client) with the client stub `FakeToolClient`
  (`src/retman/testing.py`). The stub records every call (`calls`, `network_calls`), so the gate
  test [N-12] verifies that before `plan.confirm()` there was no `run`, `check` or `query` call,
  and before `plan.confirm_check()` — no `check` or `query` call (section 6.5).
- Tool descriptions: validation of manifests and translations (including category texts and
  messages for the tool's error codes), call builders and result mappers on recorded real tool
  documents (`tests/fixtures/<tool>/`), conformance with the installed tool's catalog by
  execution (`retman scaffold check`, section 3.2.3) and tests on real tools with small data, and
  for IMGWTools on the package's fictitious store (`imgwtools.testing.build_fixture_store`),
  offline (sections 3.2.7–3.2.8).
- Workspace: writing and reading `result.json`, result numbering, input selection rules from
  section 5.3 (including the question when there are several candidates).
- Project journal: an entry for every step, including rejected plans, cancellations and errors,
  and for availability checks (executed, rejected and aborted); the complete audit data in
  `result.json` (section 5.4).
- Availability check and preview: one-time consent, revoked by a plan change, not saved in the
  plan; reopening parameters after rejection by the tool (sections 6.5, 6.3).

---

## 9. Configuration and technical requirements

### 9.1. Settings: the `[retman]` tables of the `nogat.toml` file [N-11, ADR-021]

Settings **independent of the project** — among others the models, confidence thresholds, language,
privacy and the data stores of the tools — Retman reads from **a single file per computer, shared
by the Nogat tools** (DEV-18.1): `nogat.toml` in the user's settings folder
(`platformdirs.user_config_path("nogat")`), from the file named by `NOGAT_CONFIG`, or by the
`--config PATH` option. The file is read with `tomllib`; Retman requires neither the `nogat`
package nor a `.env` file. The `[nogat]` table holds the shared keys (`lang`, `log_level`,
`data_dir`, `cache_dir`); the `[retman]` table and its subtables hold Retman's settings.

**Order of sources** for every setting: a command option (for now no setting has one; `--config`
names the file), the `RETMAN_<KEY>` variable, the `NOGAT_<KEY>` variable (shared keys only),
the `[retman]` table, the `[nogat]` table (shared keys only), the default value. `<KEY>` is the key
with dots replaced by `_`, in upper case (`decision.url` — `RETMAN_DECISION_URL`); an empty
variable means "not set". The `retman.environment` module finds the value (the `KEYS` key table,
`Environment.setting`); the `retman.config` module checks it and builds `Settings` (without the
model server) and `Config` (with it). An unusable value is rejected with a description, and
`load_settings` and `load_config` report all such problems at once as a `ConfigError`
(`validation_error`, reason `invalid_config`); a file that is unreadable, has a TOML error, or is
named but does not exist ends every command with the same error.

- **No hidden default values** [N-11]: `retman config show` (`retman-config/1`, DEV-18.6)
  shows every setting with its value and source (`default`, `env`, `file`), the file (even an unusable
  one), the variable holding the model provider key (`present` or `missing`), the tool stores with
  their size (a hard link counted once); `retman config init` writes all tables with visible values.
  It appends the `[retman]` table at the end of an existing file without touching other tables; an
  existing `[retman]` table is a `conflict` (reason `output_exists`).
- **The model server has no default values**: `[retman.decision]` (address, model, thresholds) has no
  sensible default value, so `load_config` reports missing keys (`missing_key`), and commands without
  a model (`retman results list`, `retman journal show`, `retman config show`, `retman config init`, `retman doctor check`) run
  from default values alone (`load_settings`). The API key is not a setting: it is read from the
  variable named by `decision.api_key_env` (chapter 10, DEV-18.4).
- **Project-dependent things are not in the settings.** Results and the journal go to the project folder
  (chapter 5, a deviation from DEV-18.2: the settings hold only the name of the results subfolder
  `output.results_dir`).
- **Tool stores** [ADR-015, ADR-021]: Kartograf and IMGWTools keep downloaded data in a store
  outside the results folders, shared by all projects. The client takes the tools' environment
  arguments (store, thread count, cache, update mode) exclusively from the
  `[retman.tools.<tool>]` tables (section 3.2.4); they have default values: Kartograf store
  `<data_dir>/kartograf`, IMGWTools store `<data_dir>/imgw`, Kartograf cache
  `<cache_dir>/kartograf/metadata.db`, IMGWTools reference data `<cache_dir>/imgw/reference`,
  command set `<data_dir>/retman/collected.jsonl`. `data_dir` and `cache_dir` are the nogat user data
  and cache folders (`platformdirs.user_data_path("nogat")`, `user_cache_path("nogat")`;
  on Linux `~/.local/share/nogat` and `~/.cache/nogat`). Paths are absolute, without `..`; the
  Kartograf and IMGWTools stores are two separate folders side by side on one disk, and neither
  contains the other (the Kartograf cache and the IMGWTools reference data do not lie in the store
  either). The disk must support hard links (FAT/exFAT and some network shares do not); the Kartograf
  metadata cache must lie on a local disk. Kartograf `update`: `local` — use the saved versions and do
  not ask the sources for newer ones, `upgrade` — also download newer ones, `force` — download again.
  In a terminal `retman config init` asks about command collection (section 5.4) and about the folder for
  tool stores (default `data_dir`), creates the folders (Kartograf store, cache and reference data
  folder), checks that the disk supports hard links, and only then writes the tables; at the end, with
  consent, it initialises the IMGWTools store (`store init`, without network). Without a terminal it
  writes the tables with visible default paths and creates nothing. A disk without hard links ends
  `retman config init` with an error before writing (exit code 8 or 9), and a refusal of `store init` by
  IMGWTools for this reason leaves the file in place and suggests changing both `store_dir`. From the
  easy release (0.5+) `retman config init` works as a wizard: it also asks where the model runs, checks the
  connection and writes the file (section 9.4).
- **Language** (`lang`, `pl` or `en`): the language of the texts for people: questions, plan, messages,
  reports, `--help` and the prompts that go to the model. Polish is the default, English comes from the
  `en.toml` files. Machine-readable data is always in English (AGI-9.2).
- The file contains no tool descriptions (manifests) nor texts (translations) — those are part of
  Retman's code, tested in CI (sections 3.2, 4.2). It contains no API keys either, only the names of
  environment variables (chapter 10). The `[retman.mcp]` section will appear only in v0.3 (without
  unused keys).

All variables are listed in the README and `.env.example`; the table template
(`src/retman/config_template.toml`):

```toml
[retman]
# lang = "pl"            # language of questions, options and messages: "pl" | "en"
# log_level = "warning"  # technical log on stderr: "debug" | "info" | "warning" | "error"
# data_dir = "..."       # parent of the data stores and of the command collection
# cache_dir = "..."      # parent of the caches

[retman.decision]
backend = "basal"                   # "basal" (default) | "openai_compatible"
url = "http://127.0.0.1:8000"       # basal-serve running locally (started separately)
model = "basal-1.5-mini"
timeout_s = 30                      # how long to wait for the model server
# Generative model instead of basal, e.g. LM Studio:
# backend = "openai_compatible"
# url = "http://127.0.0.1:1234/v1"
# model = "<model-name>"
# api_key_env = "PROVIDER_API_KEY"  # external providers: NAME of the environment variable holding the key
# confidence = "auto"               # "auto" | "logprobs" | "consistency" | "none" (ARCHITECTURE 3.3.3)
# consistency_runs = 3              # queries per decision for the consistency check
# With this backend [retman.decision.thresholds] must be numbers tuned for the model
# (ARCHITECTURE 6.2); with confidence = "none" the thresholds are ignored.

[retman.decision.thresholds]
operation = "auto"      # "auto" = basal calibration, allowed only with backend = "basal"; after tuning set a number, e.g. 0.90
parameter = "auto"

[retman.text]
backend = "none"        # from v0.2: "openai_compatible" (e.g. Bielik in LM Studio)

[retman.output]
results_dir = "retman-output"  # results folder created inside the project folder, i.e. where Retman runs

[retman.adapters]
# By default Retman enables every supported tool that is installed in a supported version.
# The optional "enabled" list only NARROWS that set.
# enabled = ["kartograf"]

[retman.tools.kartograf]
# The store: every downloaded file is kept here as an immutable version and shared by all
# projects. Absolute path without symbolic links, on a disk with hard links (not FAT/exFAT).
# Keep it on the same disk as the IMGWTools store, in a separate folder.
store_dir = '/home/<user>/.local/share/nogat/kartograf'
# Metadata cache (SQLite). Keep it on a LOCAL disk, never on a network share.
cache_file = '/home/<user>/.cache/nogat/kartograf/metadata.db'
workers = 4         # parallel transfers
update = "local"    # "local" = use stored versions, ask no source | "upgrade" = also download newer versions | "force" = download again

[retman.tools.imgwtools]
# The IMGWTools store (archives, series, station catalog): a separate folder next to the
# Kartograf store; neither store may contain the other. Absolute path without symbolic links.
store_dir = '/home/<user>/.local/share/nogat/imgw'
# Optional reference files for the station catalog (hydro_stations_locations.csv); may stay empty.
reference_data_dir = '/home/<user>/.cache/nogat/imgw/reference'

[retman.log]
journal_commands = true    # store command texts and answers in the project journal

[retman.privacy]
# Collect planning outcomes (command, plan, answers, model decisions) from ALL projects
# in one file, to build and tune the test set (ARCHITECTURE 5.4, chapter 10). Separate from
# the project journal; stays on this computer, nothing is sent anywhere. retman config init asks.
collect_commands = false
collect_path = '/home/<user>/.local/share/nogat/retman/collected.jsonl'
```

### 9.2. Systems and hardware [N-06], [N-09]

Target systems: **Windows, Linux and macOS**. Retman's CI runs the tests on all three.

**Retman itself** has no hardware requirements beyond Python ≥ 3.12. The requirements apply to the
**model server** and depend on the chosen configuration (section 3.3.4). As a rough guide:

| Model | Where | Notes |
| --- | --- | --- |
| basal-1.5-mini (1.5B) | GPU 6–8 GB, Apple Silicon, possibly CPU | ~3 GB of memory |
| basal-1.5 (4.5B) | GPU 8–12 GB, Apple Silicon 16 GB+ | better accuracy |
| basal-1.5-max (11B) | server | highest accuracy |
| generative model in LM Studio / Ollama | depends on size and quantisation | e.g. Bielik for decisions or descriptions |
| provider model via API | no local requirements | requires an API key |

**Recommended hardware for local work** (PRD N-06): an NVIDIA card with about 6–8 GB of memory or
Apple Silicon with about 16 GB of memory — with headroom for the text model from v0.2.

**Response time measurements (v0.1):** time from command to plan for the configurations from
section 3.3.4 on the author's hardware (macOS, Linux) and — if possible — on a laptop without
a GPU. The results go into the documentation as guidance for model selection (PRD, N-07).

### 9.3. Package [N-08]

- Python ≥ 3.12 (ADR-002: Kartograf requires that much, and the tools run in Retman's
  environment), `pyproject.toml` compliant with PEP 639, MIT licence.
- Code, identifiers, comments and docstrings in English; user-facing texts in translation files;
  README and documentation in English (section 1.3).
- Core dependencies: minimal — an HTTP client. The central file is read by `tomllib` from the
  standard library; `retman config init` writes it from a commented template (section 9.1), so a library
  for writing TOML is not needed. **The package contains no model and no machine learning
  libraries** (e.g. PyTorch) and no provider SDKs. The hydrology tools **are not** core
  dependencies. The MCP protocol library (`mcp`) is not a core dependency either — it is neither
  a model provider SDK nor an ML library, but it would break the "HTTP client only" rule — and it
  may be added only as an optional extra `retman[mcp]` for the interface from v0.3 (ADR-018).
  In v0.1 Retman has no MCP code, dependencies or configuration.
- **basal (basal-serve) is not a dependency of Retman** — neither core nor optional. The `basal`
  backend is a plain HTTP request, without the client from the `basal` package (section 3.3.2).
- **Distribution via GitHub for now.** Retman is installed from the repository, e.g.
  `uv tool install git+https://github.com/Daldek/Retman` (details: section 9.4). Publication on PyPI as
  `nogat-retman` is phase 6 of the Nogat adoption plan and needs the author's approval (PROGRESS).
- Tool descriptions are built into Retman (`src/retman/tools/`). **Retman never installs anything
  on its own.** The user installs the tools together with Retman, in the same environment
  (section 9.4), and from the easy release also on the explicit `retman add-tool` command (with
  confirmation). Retman checks their versions, and `retman doctor check` suggests how to install the
  missing ones. Tools are imported lazily (`importlib`, section 3.2.5), so neither Retman's startup
  nor `mypy src tests` depends on what is installed.
- The `tools` dependency group in `pyproject.toml` serves tests and manual runs; it is not
  a dependency of the user's environment. Until the tags `v0.8.0` (Kartograf) and `v3.0.0`
  (IMGWTools) it pins commits: Kartograf `8a36e977` and IMGWTools with the `store` extra
  (`7b11755`), the heads of the branches `feature/data-output` of the two tools, not pushed yet:
  `uv lock` resolves them only where the git cache holds them, until the author pushes both
  tools; PROGRESS Next 2); after release it switches to tags (ADR-012, ADR-024). The IMGWTools `store`
  extra installs `pyarrow` (time series are Parquet files).
- Retman **has no extras that install tools** (`retman[hydrograf]` etc.). Dependencies pointing
  directly to Git repositories would force fixed versions instead of ranges and would block any
  later publication on PyPI.
- `retman eval run` and `retman scaffold` are command groups of the `retman` executable and belong to the core
  package, with no additional dependencies: `retman eval run` together with the test command set (section 8.2),
  `retman scaffold` (section 3.2.3) as an author's tool that reads the catalogs of installed tools. The code
  development tools (pytest, ruff, mypy) are the `dev` dependency group (DEV-6.5).

### 9.4. Installation [N-09], [W-14]

**Foundation: `uv`** — a single program for Windows, Linux and macOS that installs Python itself
and creates a separate environment for Retman. The user does not need to have Python installed
beforehand. Both paths (hard and easy) perform **the same steps**; the easy one only automates
them, so a single installation mechanism is maintained.

**Three layers:**

| Layer | What | From where | Who installs |
| --- | --- | --- | --- |
| 1 | Python + Retman | GitHub (releases marked with tags) | `uv` |
| 2 | tools | GitHub (one also PyPI) | `uv`, in **the same environment** as Retman |
| 3 | model server: basal-serve (default) or a server with an OpenAI-compatible API, e.g. LM Studio (section 3.3.2); from 0.2 also a text model server, e.g. Bielik in LM Studio | per their own instructions | separately (PRD N-10); with an institutional server — the deployer |

**Tools must be in Retman's environment**, because the handlers import them. A tool installed
in another environment is invisible to Retman — `retman doctor check` reports it as not installed
and gives the command that will add it.

#### Hard version (0.x — author and testers)

```bash
# 1. Install uv (once). Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh
#    Windows (PowerShell):
#    irm https://astral.sh/uv/install.ps1 | iex

# 2. Retman together with the tools you need, in ONE environment
#    (@v0.1.0 = a tagged release, so testers have a stable version).
#    imgwtools[store] brings pyarrow: its time series are Parquet files
uv tool install "git+https://github.com/Daldek/Retman@v0.1.0" \
    --with "kartograf @ git+https://github.com/Daldek/Kartograf@v0.8.0" \
    --with "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools@v3.0.0"

# 3. Model server: installed separately, following basal's instructions, then started
basal-serve --model Remek/basal-1.5-mini --mode <depends on hardware>

# 4. Central config (asks where to keep the tool stores) and environment check
retman config init
retman doctor check
```

- **Adding a tool later:** the same command with an additional `--with`.
- **Updating:** the same command with a new release tag. Until the tags `v0.8.0` and `v3.0.0`
  are pushed, a commit from the `tools` group in `pyproject.toml` is given instead of a tag
  (section 9.3).
- **Tool stores** are created at `retman config init` (section 9.1); `retman doctor check` checks their
  paths, write permissions, hard links, `pyarrow` and reference data, and with `--deep` also
  a trial write to the IMGWTools store (section 7.2).
- **basal-serve** must be started before working with Retman; if it is not running, `retman doctor check`
  and the error message suggest how to start it (section 7.2).

#### Easy version (0.5+, before 1.0)

1. **Installation script** — `install.sh` (Linux, macOS) and `install.ps1` (Windows) in the Retman
   repository. It installs `uv`, Retman and tools selected from a list, that is, it performs steps
   1–2 of the hard version.
2. **`retman config init` wizard** — asks where the model runs (on this computer / on the institutional
   server at a given address / at a provider), immediately checks the connection and saves the
   settings (section 9.1).
3. **`retman add-tool <tool>`** — installs a tool known to Retman into its environment,
   in a version from the supported range, via `uv`. Like every operation it requires confirmation:

   ```
   $ retman add-tool kartograf
   Doinstaluję Kartograf 0.8.0 (obsługiwane wersje: >=0.8.0,<0.9) z GitHuba do środowiska Retmana.
   Wykonać? [t]ak / [n]ie
   ```

   It works only for tools that Retman knows (has their descriptions in `src/retman/tools/`).
4. **Model** — with an institutional server the user installs nothing, only enters the address
   in the wizard. Locally they receive instructions (or a separate script) for basal-serve; Retman
   does not include a model (PRD N-10).

#### Checking in CI

- **Installation test on clean systems** (Windows, Linux, macOS): installation of Retman with all
  tools, then `retman doctor check --deep` (with a trial write to the IMGWTools store on each system).
  Tool dependencies (e.g. geospatial libraries) were deemed unproblematic — the test confirms this
  on each system before the problem reaches the testers.
- From the easy version on, the same test covers the installation scripts.

---

## 10. Security and privacy [N-04], [W-05]

- Every execution of an operation requires confirmation of the plan (section 6.3), without
  exceptions in versions 0.x. Confirmation cannot be loaded from data: `Plan.from_dict` always
  returns an unconfirmed plan (section 7.1), so a saved or transmitted plan never executes without
  a new confirmation.
- **No network before confirmation** [N-12]: planning code (call builders, preview, contextual
  extractors) sees only the offline half of the tool client (`PlanView`: validation, command line,
  catalog lookup without side effects; section 3.2.4). Functions with a network effect or writes
  (`run`, `check`, `query`) exist only in `execute()` and in the availability check after separate
  consent (section 6.5). The model server is outside this rule — the user configures it.
- **The availability check sends only values from the plan** (area, product, years…) to the same
  data services that execution would query; never the text of the command, answers, model data
  or file contents. Consent is one-off, is not part of the saved plan, and every change to the plan
  revokes it (section 6.5).
- Handlers write exclusively to the assigned results directory (section 3.2.4). Only the tool
  itself writes to the tool store, through its client, in the folder from
  `[retman.tools.<tool>] store_dir`; Retman changes or deletes nothing in it.
- **Tool stores** (section 9.1): paths are absolute, without `..` and without a component that is
  a symbolic link (IMGWTools does not accept such a path; `retman doctor check` reports it also for
  Kartograf), stores are siblings (none lies inside another; the Kartograf cache and the IMGWTools
  reference data do not lie in the store) and they lie on a disk with hard links (section 7.2).
  Files from the store are referenced in the result by absolute path and SHA-256 sum
  (section 5.4).
- **The user's geometry files** (SHP, GPKG) are only read by Retman: it reads the GeoPackage layer
  list through `sqlite3` in read-only mode, and in the audit trail it records the layer name and
  the SHA-256 sums of the files (section 5.4). The tool reads the file; the data services receive
  request parameters, not the file.
- Retman does not send the user's commands or answers anywhere beyond the configured model
  backends. The tools connect to public data services (GUGiK, IMGW, ČHMÚ) after the plan is
  confirmed or, on request, in the availability check; the services receive request parameters.
- The default model configuration points exclusively to `localhost`.
- **The user decides where the model runs** in the settings. Retman does not evaluate addresses
  and does not warn; `retman doctor check` shows the address of every model (section 7.2).
- basal-serve has no access control of its own. On an institutional server, securing access is
  the responsibility of the deployer (mentioned in the README).
- **API keys** are read exclusively from environment variables (the configuration contains only
  the variable name). They never end up in configuration files, logs or `result.json`.
- **The project journal and audit data** contain the text of commands, because they are a record
  of the user's work; they stay in the project folder, and recording the text of commands and
  answers in them can be disabled (`journal_commands = false`, section 5.4). Then the journal also
  does not contain other texts that may quote the user's words or paths: the displayed plan, the
  reason for re-asking a question and the availability report lines.
- **The technical log** is written locally, without the text of commands (section 5.4).
- Collecting commands from all projects in one file (`[retman.privacy] collect_commands`,
  section 5.4) is **optional, disabled by default and requires explicit consent** — `retman config init`
  asks for it. The file stays on the user's computer. Passing commands on to the author requires
  separate, explicit consent from the user and never happens automatically.
- **MCP server (from v0.3, section 7.5.1):** execution via MCP only after human confirmation in
  the client; a client that cannot obtain it receives only the plan (fail-safe). An AI assistant
  connected via MCP is a service outside Retman's settings (N-04): the text of commands and
  absolute paths are hidden from it by default.

---

## 11. Components in Subsequent Versions

The product scope of each version is described in the PRD. Here: which technical components are built
in which version.

| Version | Components |
| --- | --- |
| **0.1** | core pipeline, `basal` backend (default) and `openai_compatible` (alternative), extractors (including probability, stations, periods, points, geometry file), shared adapter with command layer (`calls`, tool clients, offline preview, availability check), adapters for Kartograf 0.8.0 and all of IMGWTools 3.0.0 with two-stage operation recognition, tool stores in the configuration, `retman scaffold` (`list`, `draft`, `check`), CI with tests on supported tool versions, translation files (PL, EN), CLI and Python API (including the plan as data and `known`), `retman doctor check`, workspace in the project folder (numbered results, input selection without guessing, `retman results list`), central file and `retman config init`, project journal and audit trail (`retman journal show`), `retman eval run`, response time measurements (section 9.2), CI on Windows, Linux and macOS, including an installation test on clean systems (section 9.4) |
| 0.2 | chain resolver, sanity checks between steps, chain resumption, named results, result descriptions by the text model, native provider APIs (optional), descriptions and handlers for the remaining ecosystem tools (Hydrolog, Hydrograf, BasicHydraulics) |
| 0.3 | MCP server (`retman[mcp]`, stdio, confirmation via elicitation, `channel` field in the audit trail; section 7.5.1) |
| 0.4 | HTTP API |
| 0.5+ | chat window for the simple path, installation scripts (`install.sh`, `install.ps1`), `retman config init` wizard, `retman add-tool`, GUI integration (section 7.4), measured recognition of commands in English |

---

## 12. Open Technical Issues

1. **Types in the tools' public API** — settled for Kartograf and IMGWTools: choices are not
   typed as `Literal` (Kartograf: `str | None`), and the machine-readable source of truth is the
   command catalog (`allowed`, `enum`, `validate_command`), so `retman scaffold` reads catalogs,
   not docstrings (ADR-013, ADR-019). To check for Hydrolog, Hydrograf and BasicHydraulics:
   whether they have a command catalog, and if not — whether choices are typed as
   `Literal`/`Enum` and files as `Path`.
2. **Extraction of free parameters** — for IMGW stations, code resolves names offline, from the
   catalog in the store (section 4.3). What remains open is whether, in hard cases (e.g. an area
   given by river or town name instead of coordinates), code is enough, or whether Bielik or a
   geocoder will be needed.
3. **`facts: "auto"` in basal** — check whether the built-in recognition of Polish dates and
   amounts can replace some of the extractors.
4. **Confidence thresholds** — tune on our own test set instead of the defaults.
5. **Domain vocabulary** — check how basal handles hydrological terms (e.g. "przepływ
   miarodajny" (design flow), "SNQ", "WWQ") and how many synonyms are needed in operation and
   option descriptions.
6. **Data sanity checks** — where to put them: in the tools themselves (everyone uses them, also
   without Retman) or in Retman? Recommendation: result checks in the tools, in Retman only
   checks of transitions between chain steps.
7. **Data kinds** — the full list of `kind` names, their file formats and required attributes
   (section 3.2.6). Formats should be chosen from the start so that future GUIs can load them.
   Settled for Kartograf (ADR-004, ADR-016) and IMGWTools (ADR-017); Hydrolog, Hydrograf
   and BasicHydraulics open.
8. **GUI integration** (section 7.4) — connection variant (A or B) and GUI technology, once GUIs
   are built.
9. **LM Studio as model server** — whether its API returns `logprobs` and supports structured
   responses (list of allowed values). The quality of generative model decisions depends on this
   (section 3.3.3). Checked 2026-10-11 for Bielik 11B and 4.5B (MLX): `logprobs`
   and enumeration in `json_schema` work; Qwen not tested
   (`docs/research/2026-10-11-lm-studio-openai-compatible.md`).
10. **basal in LM Studio** (low priority — by default basal runs via basal-serve) — basal has GGUF files, but its decisions require a special readout
    (option letter probabilities, both orderings, calibration), which basal-serve provides today.
    To check: whether this readout can be reproduced in Retman via the API with `logprobs`, so
    that basal runs in LM Studio without a separate basal-serve.
11. **Generative models vs basal** — comparison of accuracy and automatic coverage on the test
    set (chapter 8) for the configurations from section 3.3.4.
12. **basal-serve on Windows** — which mode of operation (PyTorch, Ollama, llama.cpp) works most
    reliably; the model installation instructions for Windows testers depend on this (section 9.4).
13. **Starting basal-serve** — manually before work or as a service started with the system
    (in the easy version); a service is convenient, but it is also an intrusion into the user's
    system.
14. **Chains: resolver or author's recipes** (section 4.5) — alternative: chains as recipes
    written and reviewed by the author, with resolver logic used only for drafting and checking
    recipes. To evaluate after more tools are added; together with it, possible uses of n8n
    as Retman's surroundings (monitoring, quality control, results registry, job channels).
    Description: `docs/PROGRESS.md`, Backlog, "Do rozważenia" ("To consider").
15. **MCP clients and confirmation** (section 7.5.1) — which clients implement elicitation from
    the 2026-07-28 protocol release. Smoke test before v0.3; the emergency fallback applies
    regardless of the result.
16. **Retman's questions via MCP** (section 7.5.1) — values supplied by the agent as `known`
    or also choices via elicitation. Decision at the start of v0.3.
---

## 13. Checklists for typical tasks

The steps of the tasks that repeat. Each task ends with the gate (`scripts/gate.sh`), and the
change ships with its documentation (CLAUDE.md, Process rules).

### 13.1. A new operation of a tool

1. **Draft from the catalog of the tool.** `retman scaffold list --tool <tool>` shows which
   commands the catalog exposes and which operations use them; `retman scaffold draft --tool
   <tool> --command "<command>" --write` writes a draft of the call builder and of the texts
   into the git-ignored folder `src/retman/tools/<tool>/_drafts/` (section 3.2.3). The draft is
   reviewed and moved by hand. The manifest stays static: options are never derived from the
   installed tool when it loads (ADR-019).
2. **Manifest** `src/retman/tools/<tool>/manifest.py`: `id` (unique in Retman), `category`,
   `inputs` and `outputs` with data kinds, `params` with the types `choice`, `free` and `bool`,
   `required`, `default`, `multiple` and `range`. Option keys have no dots (`0_5m`) and carry
   `tool_values` when the value of the tool differs; `option_meta` holds per-option facts
   (sections 4.1 and 4.3).
3. **Execution.** `calls`: a pure call builder, without file system and network, from the
   `commands` of the catalog; `describe` when the generic mapping is not enough; or a `handler`,
   only when the result needs processing: it uses only the public API of the tool, takes inputs
   as files, writes only into `output_dir`, and never calls `input()` or `print()` (section
   3.2.4). Every value the tool accepts is either offered or listed in `excluded` with a reason
   (the coverage check).
4. **`preview`** (offline): plan rows and problems that make Retman ask again; the adapter
   validates the calls. A test with `FakeToolClient` asserts that no `run`, `check` or `query`
   call happens before `plan.confirm()` (N-12).
5. **`check`** only when a check over the network is meaningful (available years, resolutions,
   published archives) and the call itself does not carry the answer: the text
   `operations.<id>.check.notice` and the `[check.*]` lines (section 6.5). An operation with a
   network command that writes, and without `check`, declares `no_check` with a reason (drift
   check X7).
6. **Optional parameter** (no `required` and no `default`): the text `params.<p>.unset` says
   what its absence means (a plan row, N-11).
7. **Texts**, in every language file of the tool (`src/retman/tools/<tool>/<lang>.toml`):
   `label` and `description` of the operation; the questions (`question` for the user,
   `model_question`, "what does the command name", for `choice` and `bool` parameters, ADR-008);
   the options with `label` (for the user) and `description` with synonyms and English names
   (for the model; section 4.2, ADR-007); a parameter that a command may omit has an option
   `unspecified` with only a `description` (section 3.4). Also `[errors.<code>]` for the error
   codes of the tool, `[warnings.*]`, `[problems.*]`, `[preview.*]` and, for a new category,
   `[categories.<id>]` with `label` and `description`.
8. **A new data kind?** Section 13.2.
9. **Tests:** builders and mappers on recorded documents, the run with `FakeToolClient`,
   conformance with the real tool offline (section 8.3); `retman scaffold check` reports no
   error.
10. **Command set:** at least 15 commands in `src/retman/eval/commands.jsonl`, among them
    incomplete, ambiguous and out-of-scope ones (section 8.1); run `retman eval run`.
11. **Category limits:** a category above 9 operations, or more than 9 categories, is split;
    the loader rejects it (section 3.4, point 1).

### 13.2. A new data kind

1. An entry in `src/retman/kinds.py`: the name, the accepted extensions and a validator (a
   `Path` to an error key of `[kinds.errors]`, or `None`): standard library only, only the
   beginning of the file, no network (section 3.2.6).
2. Choose a format that the GUIs of the tools can load (section 12, item 7).
3. Tests of the validator in `tests/unit/test_kinds*.py`: a valid file, every rejection reason
   and the extension.
4. The description in section 3.2.6, in the same commit.

### 13.3. A new model backend

1. A class in `src/retman/backends/` that implements `DecisionBackend` and/or `TextBackend`
   (section 3.3.1): HTTP directly, no provider SDK.
2. Confidence: calibrated, or `logprobs`, `consistency` or `none` (section 3.3.3); the
   threshold `auto` with this backend is a configuration error (section 6.2).
3. Settings in `[retman.decision]` with comments in the template of `retman config init`
   (`src/retman/config_template.toml`, section 9.1), the variables in
   `src/retman/environment.py`, and the README table and `.env.example` (DEV-18.3).
4. Checks in `retman doctor check`: the address, the answer and a test question (section 7.2).
5. Offline tests on fixtures from real server responses (`tests/fixtures/<backend>/`).
6. `retman eval run` on the new backend; the report goes into the plan it belongs to.

### 13.4. A new extractor

1. A module in `src/retman/extractors/`, without a tool import and without network: a text
   reader that returns `list[Match]` with a normalised value that serialises to JSON. An
   ambiguous notation gives several readings (Retman asks, section 6.1), never a silent choice;
   a fuzzy match sets `Match.confirm`.
2. A value validator (an error key of `[extractors.errors]`, or `None`).
3. Entries in the registries of `src/retman/extractors/__init__.py`: `EXTRACTORS` (or
   `CONTEXT_EXTRACTORS` when the reader needs an `ExtractionContext`), `VALIDATORS`
   (`CONTEXT_VALIDATORS`), optionally `ANSWER_EXTRACTORS` (a looser reader of the answer to a
   question about this parameter), `CONTEXT_HINTS` and `DESCRIBERS` (the text of the value in the
   plan).
4. Texts in the core translation files under `[extractors.*]`: labels of the readings, errors,
   the text in the plan and hints; `tests/unit/extractors/test_registry.py` checks that every
   key that the code names exists.
5. Tests without a model: every notation, ambiguous forms, an answer to a question and boundary
   values. Run doctests through `importlib`, not by file path (`extractors/numbers.py` shadows
   the standard module `numbers`).
6. Use in a manifest: `extractor` in a `free` or `choice` parameter (section 4.3); rows of
   `commands.jsonl` with values of the parameter.

### 13.5. A new command of the catalog

1. Write the operation in `src/retman/operations/` and export it in
   `src/retman/operations/__init__.py`; it takes keyword-only parameters named like the options.
2. Declare `Command` and `Option` in `src/retman/catalog/commands.py`; add the Polish texts to
   `src/retman/i18n/pl.toml` under `[catalog.<operation_id>]` (a contract test requires one for
   every command, option, rule and choice, AGI-9.1); add the schema of its document to
   `scripts/generate_result_schemas.py`.
3. Regenerate what follows from the catalog: `uv run scripts/generate_result_schemas.py`,
   `retman commands guide --format agents --output AGENTS.md --force` and
   `retman commands guide --format llms --output llms.txt --force`.
4. A command that writes files has `--check` and `--force` and reports its targets as
   `retman-targets/1` (ADR-022); the contract tests then cover parity of the interfaces.

# Retman — product requirements document (PRD)

> **Document status:** draft (2026-10-11, updated 2026-10-25) · **Licence:** MIT · **Document language:** English
> **Technical design:** [ARCHITECTURE.md](ARCHITECTURE.md)

This document describes **what** Retman is supposed to do, **for whom** and **why**. It does not describe
the implementation — that is in ARCHITECTURE.md. Places marked **[TO BE COMPLETED]** are the subject
of ongoing brainstorming.

The name comes from the retman — the leader of the raftsmen, who guided the crew and the raft down the river to its destination.

---

## 1. Problem and context

The ecosystem of hydrology tools (Hydrograf, Kartograf, IMGWTools, Hydrolog, BasicHydraulics)
gives access to data and computations through a Python API and — in some of the tools — through a GUI.
Some of the GUIs do not exist yet.

**[TO BE COMPLETED]** What concrete user problem Retman solves: what users do by hand
today, how long it takes, where they make mistakes or get stuck.

---

## 2. Vision and Retman's role

Retman is a natural-language command layer for the tool ecosystem. The user describes
a task in a plain Polish sentence, and Retman recognises what is meant, collects the missing data,
shows a plan for approval and runs the right tool.

**Retman does not replace the tools' GUIs.** It is an additional path for users who want
to simplify typical tasks or go beyond what the GUI offers. Eventually Retman may also work
as a chat window cooperating with the GUI (chapter 4, scenarios S-06 and S-07).

**The tools are independent of Retman.** Each of them evolves on its own (possibly
aligned with Hydrograf), and keeping conformance with them is Retman's job.

**Retman does not include a language model.** The model is installed separately (e.g. in LM Studio)
or a provider's model is used through an API. Retman connects to it through an API, and its
basic installation is as small as possible. Polish and European models are recommended
(e.g. Bielik), but the user may also plug in a frontier model if they have access to one.

**Default configuration:** decisions are made by **basal** through a separately started
**basal-serve** server, and result descriptions in Polish (from 0.2) are written by **Bielik**, run e.g. in LM Studio.
Other models, including frontier ones, are plugged in by changing the configuration.

**Retman compared to general-purpose assistants.** An AI assistant can already control the tools' MCP servers
directly today. Retman provides what they do not: a plan shown with the source of every value
and human confirmation, an audit trail in the project folder, a numbered workspace
and Polish texts. From version 0.3 Retman will also be an MCP server for such assistants (W-16);
it always calls the tools through their Python API (ADR-018).

---

## 3. Users

### 3.1. Priorities

**To start with:** a working tool in the author's environment. Versions 0.x are **publicly available
on GitHub**, but are not recommended for production deployments before version **1.0.0** —
they serve to refine the product.

| Group | Who they are | Role |
| --- | --- | --- |
| **Water administration** | e.g. Wody Polskie (Polish Waters), local governments — verification of studies, decisions | **target group** (from 1.0); requires a reliable product |
| **Designers** | engineers in design offices preparing water-law reports and designs | **target group** (from 1.0), on a par with the administration |
| **Students and independent testers** | students, teaching, people willing to test | **testers of versions 0.x** — the actual priority before 1.0 |

Researchers may use Retman, but they are not a target group.

### 3.2. Technical level

Varied — Retman must support **two paths**:

| Path | For whom | How they work |
| --- | --- | --- |
| **Simple** | hydrologist with no knowledge of Python or the command line | simple installation (N-09), types commands in a chat window — from version 0.5 (chapter 9) |
| **Advanced** | hydrologist with Python basics | CLI and Python library (W-11), own scripts |

### 3.3. Ways of running and hardware

| Way | For whom | Where the model runs |
| --- | --- | --- |
| **Institution server** | offices, universities | on the institution's dedicated hardware, in its internal network; the user's computer needs no GPU. Available from v0.1 — Retman connects to the model server after changing the address in the configuration |
| **Locally** | independent designers with better hardware, willing at least to test the capabilities | on the user's computer with an NVIDIA graphics card or an Apple Silicon processor (N-06) |
| **Author's environment** | the author, testers of versions 0.x | on the author's hardware |

- Operating systems: **Windows, Linux and macOS**.
- Retman itself has no special hardware requirements. The requirements depend on the chosen model
  and the place where it runs (locally, institution server, provider API).
- CPU mode (the smallest model on the processor) — optional, if measurements show acceptable
  response time (N-07).

### 3.4. Expectations and barriers

**[TO BE COMPLETED]** What each group expects and what will discourage it.

---

## 4. Usage scenarios

| ID | Scenario | Version |
| --- | --- | --- |
| S-01 | **Single operation.** The user types one sentence (e.g. "Pobierz dobowe opady ze stacji Poznań z lat 2000–2020" — download daily precipitation from the Poznań station for the years 2000–2020), sees the plan, approves it and gets files with the result. | 0.1 |
| S-02 | **Step-by-step work.** The user delineates a catchment, and with the next command computes the flow for it ("…dla tej zlewni" — "…for this catchment"). Retman takes the catchment from the earlier result in this project and shows that in the plan; if there are several catchments, it asks which one to use. | 0.1 |
| S-03 | **Incomplete or ambiguous command.** Retman asks follow-up questions about missing data or the correct reading (e.g. "Q50" — 50% or a 50-year return period?). | 0.1 |
| S-04 | **Command out of scope.** Retman honestly answers that it cannot do this, and shows what it can do. | 0.1 |
| S-05 | **Chain of operations.** One command ("policz przepływ stuletni dla punktu…" — compute the 100-year flow for a point…) runs several steps (catchment → flow) after a single plan confirmation. | 0.2 |
| S-06 | **Chat drives the GUI.** The user talks to Retman, and Retman fills in the form in the tool's GUI. | 0.5+ |
| S-07 | **GUI with hints.** The user fills in what they know in the GUI and settles the rest with Retman. | 0.5+ |

**[TO BE COMPLETED]** Scenarios characteristic of the main user groups (chapter 3).

---

## 5. Functional requirements

| ID | Requirement | Version | Acceptance criterion |
| --- | --- | --- | --- |
| W-01 | Retman recognises the operation from a command given in Polish. | 0.1 | Accuracy on the test set ≥ **[TO BE COMPLETED]** |
| W-02 | Retman asks follow-up questions about missing, uncertain and ambiguous data instead of guessing. In the CLI this takes the form of a conversation in the terminal — one question at a time. | 0.1 | Among decisions made without asking follow-up questions, ≤ **1%** are wrong (preliminary, for the default configuration; to be verified on the test set) |
| W-03 | A command outside the scope ends with information about what Retman can do. | 0.1 | Out-of-scope commands from the test set do not start any operation |
| W-04 | Before execution Retman shows a plan; default values and values taken from earlier results are marked, as are rows that the tool fills in offline based on the plan (preview). | 0.1 | Every value in the plan has a visible source |
| W-05 | Every execution requires the user's confirmation. Confirmation cannot be loaded together with a saved plan: a plan read from data is always unconfirmed. | 0.1 | There is no execution path without confirmation, including from a plan read from data |
| W-06 | Each tool is available on its own; the user sees the operations of installed tools only. | 0.1 | Installing a single tool is enough to work with its operations |
| W-07 | Retman uses the results of previous commands within the project and files indicated by the user; when more than one result matches, it asks which one to use. | 0.1 | Scenario S-02 works without providing paths; with several matching results Retman never chooses on its own |
| W-08 | Probability can be given as any number in the usual notations (1%, Q1%, "stuletnia" (hundred-year), T = 100 lat); ambiguous notations trigger a question. | 0.1 | All forms from ARCHITECTURE section 4.4 are recognised correctly |
| W-09 | The result is files plus a short summary. Files go to the project's results folder; when the tool keeps data in its own store (Kartograf), the result points to the store files (absolute path and checksum) instead of copying them. Tool warnings (data quality, licence notices) are part of the result and are shown to the user. | 0.1 | **[TO BE COMPLETED]** (file formats) |
| W-10 | Retman diagnoses the environment and suggests how to fix problems. | 0.1 | Every detected problem has a fix suggestion |
| W-11 | Interfaces: command line (CLI) as a conversation in the terminal — a single command or a session of many commands — and a Python library. | 0.1 | — |
| W-12 | Chains of operations (scenario S-05). | 0.2 | — |
| W-13 | Cooperation with the tools' GUIs (scenarios S-06, S-07). | 0.5+ | — |
| W-14 | Installing a known tool with a single command (`retman add-tool`), after confirmation. | 0.5+ | The tool ends up in Retman's environment in a supported version; `retman doctor check` sees it without extra steps |
| W-15 | Work log and audit trail: every result contains information that makes it possible to reconstruct what it was computed with and how, and the project has a journal of all commands, questions, plans and decisions — including rejected and interrupted ones. | 0.1 | From the project folder alone it is possible to determine for every result: the values used and their sources, the versions of Retman and the tools, the model and the confidence of the decision, and with the setting `journal_commands = true` (the default; ARCHITECTURE sections 5.4 and 9.1) also the text of the command and the answers to the questions |
| W-16 | Retman is available as an MCP server for external AI assistants; execution requires human confirmation in the assistant's client, and a client that cannot obtain it gets only the plan. | 0.3 | There is no execution path via MCP without human confirmation (test with a client that cannot confirm) |
| W-17 | Data availability check on demand: after seeing the plan, the user can request a check of what the data source has for their selection (years, resolutions, completeness of coverage, published archives). This is a separate step with its own message and its own consent; the report only informs and changes nothing in the plan. | 0.1 | Without the user's consent Retman does not connect to the tool's network (N-12); the report does not change plan values and does not take a result number; every check, including rejected ones, is in the project journal |

---

## 6. Non-functional requirements

| ID | Requirement | Target value |
| --- | --- | --- |
| N-01 | **Own resources as the default path.** Retman works with a model run locally or on the organisation's network and does not require paid APIs. | — |
| N-02 | **Interchangeable models without code changes.** By default Polish models: basal (decisions) and Bielik (result descriptions); other models are also possible, including frontier models via API, if the user has access to them. | — |
| N-03 | **Tool independence.** Tools contain nothing related to Retman; Retman maintains conformance. | — |
| N-04 | **Privacy.** Data does not leave the configured services; by default everything runs locally; commands are not passed on or collected outside the project without explicit consent (the project journal is part of the user's work and stays in their folder, W-15). The user decides in the configuration where the model runs; `retman doctor check` shows the address of each model. Tools connect to public data services (e.g. GUGiK, IMGW) only after the plan is confirmed or with consent in the availability check (N-12), and the services receive the request parameters, not the user's command. An AI assistant connected via MCP (from 0.3) is a service outside the configuration file: command text and paths are hidden from it by default (ARCHITECTURE section 7.5.1). | — |
| N-05 | **Reliability over convenience.** Retman prefers to ask rather than be wrong — in every configuration, including with a model without calibrated confidence (ARCHITECTURE section 3.3.3). | see W-02 |
| N-06 | **Minimum hardware.** | locally recommended: an NVIDIA card with about 6–8 GB of memory or Apple Silicon with about 16 GB of memory. The default model itself (basal-1.5-mini) needs about 3 GB; result descriptions via Bielik (from 0.2) — more, depending on model size (ARCHITECTURE section 9.2). With an organisation server the user's computer does not need a GPU (section 3.3) |
| N-07 | **Response time** (from typing the command to showing the plan). | **[TO BE COMPLETED]** |
| N-08 | **Openness.** MIT licence; code, documentation and machine output in English; the texts that users read are Polish by default and English on request (DEV-2.1, DEV-2.2). | — |
| N-09 | **Installation.** | The basis is `uv` (Windows, Linux, macOS). Retman and the tools come from GitHub release tags (REL-5.1) in one environment until phase 6 of the Nogat adoption plan publishes them on PyPI (Retman as `nogat-retman`, REL-3.1, subject to the author's approval); then they are installed from PyPI ranges (REL-5.2). The model is installed separately (N-10). **Hard version (0.x):** `uv` commands + a separately started model server. **Easy version (0.5+):** install script, `retman config init` wizard, `retman add-tool` (W-14). No compilation on the user's side; the installation test in CI checks this (ARCHITECTURE section 9.4) |
| N-10 | **No model in the package.** Retman is not distributed with any language model; it connects to a model via API (e.g. LM Studio, Ollama, basal-serve, a provider's API). The basic installation is as small as possible. This also applies to basal: basal-serve is a separate program, not a dependency of Retman. | — |
| N-11 | **Configuration.** Project-independent settings (including models, confidence thresholds, language, privacy, tool data stores) are in the `[retman]` tables of one shared `nogat.toml` file on the computer (DEV-18.1) and in `RETMAN_*` variables, with no hidden default values: every value in use is visible in `retman config show` together with its source, and `retman config init` writes them to the file (ADR-021). Results belong to the project and are saved in its folder. | — |
| N-12 | **No network before confirmation.** Before the plan is confirmed, Retman does not call any tool function with a network effect or a write: planning consists of extractors in code, offline validation by the tool and the plan preview. The only exception is the availability check on request, after separate consent (W-17). The model server is outside this rule (N-04). | Structurally: before confirmation the planning code receives only the offline view of the tool client (ARCHITECTURE section 3.2.4); a test with a client that records calls checks that there is no `run`, `check` or `query` call before `plan.confirm()` |

---

## 7. Scope

### 7.1. In scope for v0.1

- Single operations (no chains) of two tools: Kartograf 0.8.0 (four operations on spatial data)
  and the whole of IMGWTools 3.0.0 (all user-facing capabilities, including ČHMÚ data;
  26 operations in 6 categories) — section 7.2, ADR-012, ADR-017.
- Scenarios S-01 to S-04.
- Requirements W-01 to W-11, W-15 and W-17, plus N-12.

### 7.2. Operations in v0.1

Selection criteria: Kartograf — four operations from ADR-001, carried over to version 0.8.0 (ADR-012);
IMGWTools — all user-facing capabilities of the tool's command catalog (ADR-017; author: "all of IMGW
goes into v0.1"), with justified exclusions. There are more than 9 operations, so recognition
is two-stage: category, then operation (ARCHITECTURE section 3.4).

**Kartograf 0.8.0** (ADR-001, ADR-012, ADR-016):

| Operation | Tool | Area in the command |
| --- | --- | --- |
| download DEM (NMT) for a map sheet (resolutions 0.15, 0.5, 0.6, 1, 5, 10 and 100 m; vertical datum EVRF2007 or KRON86 where both exist) | Kartograf | sheet code (godło), geometry file |
| download DEM (NMT), DSM (NMPT) or orthophoto (RGB colour, CIR or B/W) for a parent map sheet | Kartograf | sheet code (godło); geometry file — except for orthophoto |
| DEM (NMT) or DSM (NMPT) cutout for an area | Kartograf | rectangle in PL-1992 or WGS84, geometry file |
| download BDOT10k (topographic objects database) | Kartograf | county TERYT code, rectangle, sheet code, geometry file |

**IMGWTools 3.0.0** (ADR-017): 26 operations in six categories, on IMGW-PIB and ČHMÚ data
(ARCHITECTURE section 3.2.11):

| Category | Operations |
| --- | --- |
| stations and data registry | search for IMGW-PIB and ČHMÚ stations (by name, river, kind); build a station catalog in the store; list datasets and providers |
| current data and warnings | current measurements of a hydrological, meteorological or synoptic station; hydrological and meteorological warnings; water levels at stations (alarm and warning levels) |
| PMAXTP maximum precipitation | maximum precipitation table for a point (POT or AMP method; optionally for selected probabilities and durations); read a stored grid cell |
| station time series | export a station series to CSV (dataset, period, hydrological or calendar year, variables); data coverage of a station in the store; build series |
| archives and store | download hydrological or meteorological archives to the results folder; check archives against the store (plan); download archives to the store, also per plan; export stored archives; create and describe the store |
| data projects | create a project, add and remove a task, point to a store; download and pin project data; check freshness and verify pinned data |

The first scenario S-01 ("Pobierz dobowe opady ze stacji Poznań z lat 2000–2020" — download daily
precipitation from the Poznań station for 2000–2020) is a station series export. Seven catalog
commands of the tool are deliberately excluded, with justification (offline lookups used inside
plans, duplicated reads and commands describing the catalog itself).

### 7.3. Out of scope

Each item has its reason and what covers it instead; the same list is the "When not to use" of the README.

| Out of scope | Why | What covers it |
| --- | --- | --- |
| Answering substantive hydrology questions | Retman runs the operations of the tools; it does not interpret results or teach hydrology | a separate assistant project |
| Hydrological computation (design rainfall, hydrographs, runoff) | Retman fetches data today; the adapters of Hydrolog and Hydrograf are planned for 0.2 (chapter 9) | Hydrolog and Hydrograf, called directly |
| GIS processing of the downloaded files | the files are the result; processing them is another job | QGIS, GDAL |
| Browsing and managing the stores of the tools | Retman records the paths and sums of the files, not the stores | Archiwista |
| Replacing the tools' GUIs | Retman is an additional path (chapter 2) | the GUIs of the tools |
| Executing operations without confirmation before version 1.0 | W-05: no silent execution while the product is refined | the tool itself, when the exact call is known |
| Voice control | not needed to refine the product | none |
| Commands in English before version 0.5 | the English texts of the questions, the options and the messages exist (`lang = en`), but the extractors read Polish notation only, the evaluation command set is Polish and the recognition of English commands is not measured; basal works best when the questions are in the language of the command (ARCHITECTURE section 3.4) | the tools' own CLIs and MCP servers |
| Calling tools through their MCP servers | ADR-018: a thin wrapper over the same functions, more packages, harder to guarantee W-05 and to test | the Python API of the tools, which Retman uses |

---

## 8. Success metrics

| Area | Metric | Target |
| --- | --- | --- |
| Quality | accuracy of operation recognition | **[TO BE COMPLETED]** |
| Quality | errors among decisions made without asking follow-up questions | **≤ 1%** — preliminary, to be verified on the test set (W-02) |
| Convenience | share of commands handled without asking follow-up questions | **[TO BE COMPLETED]** after the first tests — the lower the acceptable error, the more often Retman asks |
| Product | **[TO BE COMPLETED]** (e.g. number of users, time saved, reports) | **[TO BE COMPLETED]** |

---

## 9. Releases

Versions 0.x are **publicly available on GitHub**, but are not recommended for production
deployments. They serve development in the author's environment and testing (students, independent
testers). The first version recommended for production deployments: **1.0.0**.

| Version | What the user (tester) gets |
| --- | --- |
| **0.1** | single operations from the CLI and Python on Kartograf 0.8.0 and all of IMGWTools 3.0.0 (two-stage recognition of operations), geometry file as area, asking follow-up questions, plan with offline preview and confirmation, data availability check on request, step-by-step work, tool data stores in the configuration, environment diagnostics; model locally or on the organisation's server; project journal and audit trail |
| 0.2 | chains of operations, result descriptions in Polish, remaining tools of the ecosystem (Hydrolog, Hydrograf, BasicHydraulics) |
| 0.3 | MCP server (optional extra `retman[mcp]`): an external AI assistant plans, and a human confirms execution in their own client (W-16, ADR-018) |
| 0.4 | access to Retman via an HTTP API (e.g. for a web application and GUI) |
| 0.5+ | **simple path**: chat window, installation script, configuration wizard and `retman add-tool` (Windows, Linux, macOS); cooperation with tool GUIs; commands in English |
| **1.0.0** | **first version for production deployments** — a reliable product for public administration and designers |

---

## 10. Assumptions and risks

**Draft for review.**

| Risk | Impact | Mitigation |
| --- | --- | --- |
| basal (the default model) is a young one-person project | no further development or support of the model | replaceable model (N-02); backend for generative models ready from v0.1 as an alternative |
| generative models (e.g. via LM Studio or a provider's API) often do not provide calibrated confidence | harder to recognise when to ask | by default confidence from token probabilities (`logprobs`), and when the server does not return them — from the agreement of several answers (ARCHITECTURE section 3.3.3); mandatory plan confirmation (W-05); quality tests separately for each kind of model |
| model of an external provider | the content of commands leaves the computer or the organisation's network | the configuration belongs to the user, and `retman doctor check` shows the address of each model (N-04); the default route is the user's own resources |
| unknown accuracy of a small model on hydrological vocabulary | a lot of follow-up questions or errors | test set from day one, synonyms in descriptions, option of a larger model |
| weak hardware of users | Retman too slow or impossible to run | smallest model, diagnostics, model on the organisation's server (from 0.1, section 3.3) |
| maintaining conformance with five tools | Retman breaks after changes in the tools | tests on tool versions and conformance check by execution (`retman scaffold check`, ADR-019) in CI |
| Kartograf 0.8.0 and IMGWTools 3.0.0 without pushed release tags | Retman depends on unreleased commits | the `tools` group pins commits until tags exist (the IMGWTools one is not pushed yet, PROGRESS), then tags; version ranges in manifests (`>=0.8.0,<0.9`, `>=3.0.0,<4`; ADR-012, ADR-024) |
| tool stores on a disk without hard links (FAT/exFAT, some network shares) | tools will not save data | `retman config init` checks hard links before writing the configuration file, `retman doctor check` — in both stores (ARCHITECTURE sections 7.2, 9.1) |
| MCP client without the ability to confirm or with a model in the cloud (from 0.3) | execution without a human or leakage of command content | fail-safe closure: without confirmation the client gets only the plan; command content and paths are hidden by default (ADR-018, ARCHITECTURE section 7.5.1) |
| GUI part missing | integration with GUI postponed | plan as data from v0.1, decision on integration later |
| office laptops without a GPU in public offices and at universities | users will not run the model locally | organisation's server on the internal network (section 3.3) |
| installation with compilation on the user's side | the user gets stuck on installation | model outside the Retman package (N-10); tool dependencies are checked by an installation test on clean systems in CI (N-09) |
| no feedback from target groups before 1.0 | product polished for the author, not for public administration and designers | testers of versions 0.x; **[TO BE COMPLETED]** whether and how to show Retman to public administration before 1.0 |

**Assumptions:**
- Users know hydrology and the methods they use; Retman does not teach hydrology.
- Users of the simple path know neither Python nor the command line.

---

## 11. Open product questions

1. The problem Retman solves, described from the perspective of administration and designers (chapter 1).
2. Expectations and barriers of the individual groups (section 3.4).
3. Whether and how to show Retman to the target groups before 1.0 (chapter 10).
4. The list of first operations (section 7.2) — settled for Kartograf and IMGWTools (ADR-001, ADR-012, ADR-016, ADR-017); to be settled for Hydrolog, Hydrograf and BasicHydraulics (from 0.2).
5. Target values: response time, quality and success measures (chapters 5, 6 and 8).
6. Cooperation with GUIs — decision once the GUIs exist.
7. Scenarios characteristic of the main user groups (chapter 4).
8. Result file formats (W-09; technical side: ARCHITECTURE chapter 12, item 7) — settled for Kartograf and IMGWTools (ADR-004, ADR-016, ADR-017); open for the remaining tools.

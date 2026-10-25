# Decision log: Retman

Every architectural or design decision is recorded here (DOC-8.1): ID, title, date, status,
context, options considered, decision, consequences and errata. The decisions 001 to 019 are
entries of this file; from ADR-020 on, each decision is a file in [decisions/](decisions/)
(DOC-8.2), and the index below lists them all.

An entry describes the state at the time of the decision and is not modernised. Later changes
of facts and further findings are appended at the end of the entry as errata
`**Erratum N (YYYY-MM-DD, source or reason):**`, numbered chronologically within the ADR. An
amendment is also noted on the `**Status:**` line at the top of the amended ADR, with its date
and the amending ADR. Template for a new entry: [New ADR template](#new-adr-template).

**Status vocabulary** (the `**Status:**` line of each entry, DOC-8.1):

- `proposed`: not decided yet;
- `accepted`: the decision applies in full;
- `accepted; amended by ADR-x (date, scope)`: the decision applies, and a later decision
  extends it or replaces the part named in the scope;
- `superseded by ADR-x (date)`: the decision no longer applies.

After the semicolon the status may give the reverse relations (`amends ADR-x`, `supersedes
ADR-x`); each relation is recorded on both sides.

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-001](#adr-001-first-v01-operations-from-kartograf) | First v0.1 operations from Kartograf | accepted; amended by ADR-016, ADR-017 | 2026-10-11 |
| [ADR-002](#adr-002-python--312) | Python ≥ 3.12 | accepted | 2026-10-11 |
| [ADR-003](#adr-003-supported-kartograf-versions-and-developer-installation) | Supported Kartograf versions and developer installation | accepted; amended by ADR-012 | 2026-10-11 |
| [ADR-004](#adr-004-kartograf-data-kinds-a-separate-kind-per-product) | Kartograf data kinds: a separate `kind` per product | accepted; amended by ADR-016, ADR-017 | 2026-10-11 |
| [ADR-005](#adr-005-http-client-httpx) | HTTP client: `httpx` | accepted | 2026-10-11 |
| [ADR-006](#adr-006-kartograf-operations-without-default-values) | Kartograf operations without default values | accepted; amended by ADR-012 | 2026-10-11 |
| [ADR-007](#adr-007-options-with-a-label-for-the-user-and-a-description-for-the-model) | Options with a label for the user and a description for the model | accepted | 2026-10-12 |
| [ADR-008](#adr-008-separate-question-for-the-model-model_question) | Separate question for the model (`model_question`) | accepted | 2026-10-12 |
| [ADR-009](#adr-009-cutout-result-crs-recognised-in-code) | Cutout result CRS recognised in code | accepted | 2026-10-12 |
| [ADR-010](#adr-010-command-set-from-all-projects) | Command set from all projects | accepted; amended by ADR-011, ADR-021 | 2026-10-12 |
| [ADR-011](#adr-011-exporting-the-command-set-and-drafting-retman-eval-entries) | Exporting the command set and drafting `retman-eval` entries | accepted; amends ADR-010; amended by ADR-022 | 2026-10-12 |
| [ADR-012](#adr-012-kartograf-080-and-imgwtools-300) | Kartograf 0.8.0 and IMGWTools 3.0.0 | accepted; amends ADR-003, ADR-006; amended by ADR-024 | 2026-10-19 |
| [ADR-013](#adr-013-tools-called-through-the-command-layer) | Tools called through the command layer | accepted | 2026-10-19 |
| [ADR-014](#adr-014-no-network-before-confirmation-preview-and-check) | No network before confirmation: preview and check | accepted | 2026-10-19 |
| [ADR-015](#adr-015-tool-stores-outside-results-folders) | Tool stores outside results folders | accepted; amended by ADR-021 | 2026-10-19 |
| [ADR-016](#adr-016-geometry-file-as-an-area) | Geometry file as an area | accepted; amends ADR-001, ADR-004 | 2026-10-19 |
| [ADR-017](#adr-017-all-of-imgwtools-in-v01-and-two-stage-recognition) | All of IMGWTools in v0.1 and two-stage recognition | accepted; amends ADR-001, ADR-004 | 2026-10-19 |
| [ADR-018](#adr-018-mcp-tools-via-the-python-api-retman-server-in-v03) | MCP: tools via the Python API, Retman server in v0.3 | accepted | 2026-10-19 |
| [ADR-019](#adr-019-static-manifests-and-retman-scaffold-from-tool-catalogs) | Static manifests and `retman-scaffold` from tool catalogs | accepted; amended by ADR-022 | 2026-10-19 |
| [ADR-020](decisions/0020-error-registry.md) | Adopt the shared error registry | accepted | 2026-10-24 |
| [ADR-021](decisions/0021-user-environment.md) | User environment: `[retman]` in `nogat.toml`, variables and user directories | accepted; amends ADR-010, ADR-015 | 2026-10-24 |
| [ADR-022](decisions/0022-agent-interfaces.md) | Agent interfaces: one command catalog, one `retman` executable | accepted; amends ADR-011, ADR-019 | 2026-10-24 |
| [ADR-023](decisions/0023-structure-gate-ci-and-log.md) | Repository structure, quality gate, CI, test tree and technical log | accepted | 2026-10-24 |
| [ADR-024](decisions/0024-imgwtools-data-output.md) | IMGWTools data output: plain files or a store, called as the tool defines them | accepted; amends ADR-012 | 2026-10-25 |

---

## ADR-001: First v0.1 operations from Kartograf

**Date:** 2026-10-11
**Status:** accepted; amended by ADR-016 (2026-10-19, geometry file), ADR-017 (2026-10-19, IMGWTools operations)

**Context:** PRD 7.2 required a list of the first operations; without it, no manifests,
handlers or test set could be created. The author chose Kartograf v0.7.2 as the first
tool for checking Retman's capabilities.

**Options (operations of the public API of Kartograf 0.7.2):**
- A) DEM (NMT) for a map sheet (`DownloadManager.download_sheet`),
- B) DEM/DSM/orthophoto for a parent map sheet (`DownloadManager.download_hierarchy`),
- C) DEM/DSM cutout for an area via WCS (`download_pl_cutout`),
- D) LAZ point cloud for an area (`download_laz_area`),
- E) BDOT10k for a county or an area (`LandCoverManager`),
- F) HSG soil groups (`calculate_hsg_by_*`).

**Decision:** A, B, C and E. Area in the command: sheet code (godło), rectangle in PL-1992
coordinates, rectangle in WGS84 degrees, geometry file (SHP/GPKG).

**Consequences:** PRD 7.2 gets its list; the PRD 7.1 requirement "from at least two tools"
remains — the operation of the second tool is to be determined. Extractors are needed for
the sheet code, the rectangle (with coordinate system recognition), the TERYT code and paths
(ARCHITECTURE 3.1).

**Erratum 1 (2026-10-19, Kartograf 0.8.0):** in 0.8.0, operations A–E call Kartograf's command
layer (ADR-013), not the functions listed; `LandCoverManager` and `download_pl_cutout` in their
former form do not exist. The geometry file works from 0.8.0 (ADR-016); the operations of the
second tool — ADR-017.

---

## ADR-002: Python ≥ 3.12

**Date:** 2026-10-11
**Status:** accepted

**Context:** Kartograf 0.7.2 requires Python ≥ 3.12, and the tools must run in the same
environment as Retman (PRD N-09, ARCHITECTURE 9.4). Retman was going to require ≥ 3.11.

**Options:**
- A) raise Retman to ≥ 3.12 — a single environment with no exceptions,
- B) keep ≥ 3.11 — Kartograf operations only on 3.12+, CI in two variants.

**Decision:** A.

**Consequences:** `requires-python = ">=3.12"`; changed ARCHITECTURE 9.2, 9.3,
README, CLAUDE.md and the former developer standards (today DEV-6.1, DEV-7.1, DEV-7.3).

---

## ADR-003: Supported Kartograf versions and developer installation

**Date:** 2026-10-11
**Status:** accepted; amended by ADR-012 (2026-10-19, the version range and the pinning of ADR-012 replace those of this ADR)

**Context:** The manifest states the supported version range of the tool (ARCHITECTURE 3.2.7),
and the handler tests need the real tool in `.venv`. Retman has no extras that install
tools (ARCHITECTURE 9.3).

**Options:**
- A) `>=0.7.2,<0.8`; Kartograf from a Git tag in the developer dependency group,
- B) `==0.7.2`; as above,
- C) `>=0.7.2,<0.8`; editable installation from the `../Kartograf` directory.

**Decision:** A. Group `tools` in `[dependency-groups]` of `pyproject.toml`
(`kartograf @ git+https://github.com/Daldek/Kartograf@v0.7.2`) — it does not end up in the
package metadata, so the user still installs the tools themselves (`--with`).

**Consequences:** CLAUDE.md (environment and commands) describes `uv sync --locked --all-extras`,
which also installs the `tools` group. The `../Kartograf` directory is not used (its working
branch need not match the release).

**Erratum 1 (2026-10-19, ADR-012):** the range `>=0.7.2,<0.8` and the pin `@v0.7.2` replaced by
`>=0.8.0,<0.9` and a pinned Kartograf commit (to tag `v0.8.0`); the `tools` group also contains
`imgwtools[store]`. The `tools` group mechanism is unchanged.

---

## ADR-004: Kartograf data kinds: a separate `kind` per product

**Date:** 2026-10-11
**Status:** accepted; amended by ADR-016 (2026-10-19), ADR-017 (2026-10-19): new data kinds

**Context:** ARCHITECTURE 12 item 7 — the list of data kinds was open. The operations
from ADR-001 return DEM (NMT) and DSM (NMPT) rasters, orthophotos and BDOT10k vectors.

**Options:**
- A) a separate `kind` per product: `dem`, `dsm`, `orthophoto`, `topographic_vector`,
- B) format-based kinds: `raster`, `vector`,
- C) a separate `kind` per product and form (set of map sheets / cutout).

**Decision:** A. The file format is whatever Kartograf returns (Retman does not convert files);
the kind validator checks the file extension and header, without geospatial libraries.

**Consequences:** ARCHITECTURE 3.2.6 gets a table of Kartograf kinds; one result may
have several files of the same kind (map sheets). The list for the remaining tools stays open.

**Erratum 1 (2026-10-19, Kartograf 0.8.0 and IMGWTools 3.0.0):** new kinds `dem_archive`
(100 m DEM (NMT) — voivodeship ZIP), `area_geometry` (ADR-016) and 13 IMGWTools kinds (ADR-017);
`retman/kinds.py` has a validator per kind.

---

## ADR-005: HTTP client: `httpx`

**Date:** 2026-10-11
**Status:** accepted

**Context:** The core dependencies are only an HTTP client (ARCHITECTURE 9.3); backends
need explicit timeouts and offline tests on recorded responses (DEV-10.2, DEV-13.2).

**Options:**
- A) `httpx` — per-request timeouts, built-in `MockTransport` for offline tests,
- B) `requests` — already in the environment via Kartograf, but offline tests would require
  an additional mocking library,
- C) `urllib` from the standard library — no dependencies, more own code.

**Decision:** A.

**Consequences:** `dependencies = ["httpx>=0.27"]`.

---

## ADR-006: Kartograf operations without default values

**Date:** 2026-10-11
**Status:** accepted; amended by ADR-012 (2026-10-19, new questions of Kartograf 0.8.0)

**Context:** The Kartograf manifest (ADR-001) had default values for the DEM (NMT) resolution
(1 m), the vertical reference system (EVRF2007) and the BDOT10k format (GeoPackage). While writing
the `retman-eval` specification (`docs/specs/2026-10-11-retman-eval.md`) it had to be settled
whether a question about such a parameter is an error or an unnecessary cost.

**Options:**
- A) keep the default values — fewer questions, but the result depends on values the user
  did not choose,
- B) remove the default values — Retman asks about every detail the command does not provide.

**Decision:** B — the author prefers Retman to ask about details rather than assume default
values. Parameters with no value in the command are required (`required`), so they go into
questions. Fixed values that cannot be chosen (DSM (NMPT) only 1 m / EVRF2007, orthophoto)
are not parameters.

**Consequences:** `retman/tools/kartograf/manifest.py` has no `default` keys; the
`unspecified` texts in `pl.toml` announce a question. In `retman-eval`, a question about a parameter not
given in the command is expected (`expect_clarify`), while assuming a value without asking is silent
guessing.

**Erratum 1 (2026-10-19, Kartograf 0.8.0):** "fixed values that cannot be chosen"
no longer exist: since 0.8.0, DSM (NMPT) has several resolutions and two vertical reference systems, and
the orthophoto has three colour variants. All of them become parameters with a question (ADR-012).

---

## ADR-007: Options with a label for the user and a description for the model

**Date:** 2026-10-12
**Status:** accepted

**Context:** Operations already had separate `label` (for the user) and `description`
(with synonyms, for the model only), but a parameter option had a single text. The same text
went to the model, to the question in the terminal and to the plan, so synonyms added for the
model ("DEM", "rzeźba terenu") cluttered what the user sees.

**Options:**
- A) split options like operations: `label` for the user, `description` for the model,
- B) remove synonyms from options and keep them only in operation descriptions,
- C) remove synonyms altogether — Retman understands only official Polish names.

**Decision:** A — in practice English names and abbreviations (DEM, DSM, SHP) are used often,
even though communication is in Polish, so the model must know them while the user sees
short names.

**Consequences:** every option in the translation file has `options.<key>.label`
and `options.<key>.description`; `unspecified` is never shown, so it has only
`description`. Manifest validation requires both fields. The user's answer in their own words
is also matched by the model against descriptions (of options and operations), not labels.
ARCHITECTURE 4.2, 13.1.

---

## ADR-008: Separate question for the model (`model_question`)

**Date:** 2026-10-12
**Status:** accepted

**Context:** The first `retman-eval` run with Bielik 11B
(`docs/research/2026-10-12-bielik-11b-retman-eval.md`): the model chose "not specified" for
the data kind in 17/34 commands, despite "NMT"/"DSM" in the text. The model received the same
question as the user ("Czy wycinek ma zawierać NMT (teren) czy NMPT (pokrycie terenu)?" —
"Should the cutout contain DEM (terrain) or DSM (land cover)?").
Diagnostics on the same server: a question about what the command mentions gave 32/34 (21 confident
≥ 0.9 instead of 4) and also improved format, vertical datum, resolution and scale, with no new
high-confidence errors.

**Options:**
- A) a separate `model_question` text for parameters chosen by the model,
- B) reword `question` so that it serves both sides,
- C) recognise values in code (synonym dictionaries) instead of in the model.

**Decision:** A — the question for the user should stay natural ("1 m czy 5 m?"), and the model
needs a question about the content of the command; a split like `label`/`description` (ADR-007). C remains
under consideration for the result coordinate system (`target_crs`), which A does not improve.

**Consequences:** `choice` and `bool` parameters have `model_question` in the translation file
(required by manifest validation); the pipeline uses it when deciding from the command and when
handling an answer in the user's own words, while the user question (`question`) is used only in the terminal
and in the journal. The operation question (`dialog.operation`) is unchanged. With the basal backend
it needs to be checked whether its calibration fits such wording. ARCHITECTURE 3.3.1, 4.2,
13.1.

---

## ADR-009: Cutout result CRS recognised in code

**Date:** 2026-10-12
**Status:** accepted

**Context:** In the `retman-eval` runs with Bielik 11B
(`docs/research/2026-10-12-bielik-11b-retman-eval.md`) the only wrong decisions accepted without
a question concerned `target_crs`: the model took the coordinate system given for the input
rectangle ("… 382100 PL-1992") as the result coordinate system with confidence up to 0.97.
Neither the option description nor `model_question` (ADR-008) fixed this — the error comes from
the role of the code in the sentence.

**Options:**
- A) code recognises coordinate systems and their role (rectangle / result); unclear → question,
- B) as A, and when the code recognises nothing — the model,
- C) leave the model with a threshold so high that such cases always end with a question.

**Decision:** A (author's choice). Numbers and codes are read by code (ARCHITECTURE 1.1); the
model confuses roles with high confidence, so path B would bring back silent guessing.

**Consequences:** extractor `retman/extractors/crs.py`: names and codes of coordinate systems
(with `EPSG:`, a bare number next to a word about a coordinate system, by name: PL-1992,
PUWG 1992, S-JTSK, Křovák, ETRS89/TM33, UTM 33N, WGS84), role from position (right after the
rectangle = input), from words before the mention ("wynik", "do", "przelicz", "zapisz",
"docelowy" (result, to, convert, save, target) = result; "prostokąt", "współrzędne"
(rectangle, coordinates) = input) and from inconsistency with the coordinate system of the
rectangle's numbers. Text without Polish diacritics and case-insensitive; one typo tolerated in
words of 5 letters or more, short words and codes — exact match (a typo in a code ends with a
question). The answer to the question is read by a separate function (the bare code "2180" is
enough). Manifest schema: `choice` with `extractor` and `option_values` (ARCHITECTURE 4.3);
validation requires only user-facing texts for it. Kartograf:
`download_elevation_cutout.target_crs`.

---

## ADR-010: Command set from all projects

**Date:** 2026-10-12
**Status:** accepted; amended by ADR-011 (2026-10-12, handing over the set and drafting entries for `retman eval run`), ADR-021 (2026-10-24, the table `[retman.privacy]` and the file under `data_dir` replace those of this ADR)

**Context:** `[privacy] collect_commands` existed in the configuration without a defined
behaviour (storage location "—" in ARCHITECTURE 5.4). The author wants to evaluate command
recognition based on work with Retman and build a test set from it. The project journal stays
in the project folder and did not contain the model's decisions for plans that were not
executed.

**Options:**
- A) remove the setting — the project journal is enough,
- B) collection in one file from all projects, with explicit consent.

**Decision:** B (author's choice): disabled by default, but `retman init` asks for consent at
first configuration. The project journal extended with plan data (values with their sources,
model decisions with confidence, the changed value) and with an "out of scope" event.

**Consequences:** `retman/core/collection.py`; `[privacy] collect_path` (full path written by
`retman init`, no hidden default value, N-11); `init_config(…,
collect_commands=)`; an entry after every planning result (for an approved plan — after
execution, with its result), without the server address and local paths; `retman-eval` does not
collect. ARCHITECTURE 5.4, 9.1, chapter 10. Open: how the set is handed over to the author
(separate, explicit consent, never automatically) and the step "set → draft of `retman-eval`
entries".

---

## ADR-011: Exporting the command set and drafting `retman-eval` entries

**Date:** 2026-10-12
**Status:** accepted; amends ADR-010; amended by ADR-022 (2026-10-24, command layout: `retman-eval` is `retman eval run`). **Implementation deferred** (author's decision, 2026-10-12).

**Context:** ADR-010 left two questions open: how the user hands the command set over to the
author (never automatically, ARCHITECTURE chapter 10) and how full entries of the set become
test set entries for `retman-eval` (spec `docs/specs/2026-10-11-retman-eval.md`).

**Options:**
- handover: A) export to a file and manual sending by the user (e-mail, private channel);
  B) attachment to a GitHub issue (public — commands contain locations); C) a private
  repository or a form with upload;
- entry draft: 1) an option of `retman-eval`; 2) part of the export; 3) a separate
  subcommand next to the export.

**Decision:**
- handover: **A** (author's choice); **C with a form** to be considered later — it will accept
  the same full entries, so it does not change the format;
- draft: **3** — the `retman collect` command with two subcommands:
  - `retman collect export [--from YYYY-MM-DD] [--to YYYY-MM-DD] --output FILE` — copies
    the full entries from the period, prints their count by operation and status (to review
    before sending), sends nothing; exit code 1 when collection is disabled or the selection
    is empty;
  - `retman collect draft FILE --output DRAFT` — converts full entries (from an export or
    the set) into `retman-eval` entries with a stable `id`, the `collected` tag and a `review`
    field at the places a human has to resolve.

Rationale for choosing 3: `retman-eval` measures and requires a model, while the draft is a
format conversion without a model, followed by a human review anyway; the export is done by
the user, who should not decide the test expectations, and the draft loses data (model
decisions, probabilities, status) that the author needs for analyses; the author makes the
draft — also from files received from testers.

**Draft rules:** a value with source `command` in an approved plan → `params`; a value with
source `user` → `review` (the command did not provide it — `expect_clarify` — or the model
was uncertain or wrong); a rejected, modified or cancelled plan → `review`; "out of scope"
→ `operation: "out_of_scope"` with `review` asking whether that was correct. An entry with an
unreviewed `review` field is rejected by the set validation (`retman/eval/dataset.py`).

**Consequences (at implementation):** draft code next to the set validation
(`retman/eval/dataset.py`), a command in the CLI; ARCHITECTURE 5.4 and 7.1 (command list),
USAGE 6.4, the `retman-eval` specification section 2 (`review` field, `collected` tag). To
be settled at implementation: whether the export can anonymise entries (e.g. skip selected
ones), given that coordinates are needed for the tests.

---

## ADR-012: Kartograf 0.8.0 and IMGWTools 3.0.0

**Date:** 2026-10-19
**Status:** accepted; amends ADR-003 (version ranges, pinning) and ADR-006; amended by ADR-024 (2026-10-25, the IMGWTools pin)

**Context:** The author releases Kartograf 0.8.0 and IMGWTools 3.0.0 with breaking API changes
(`docs/research/2026-10-19-kartograf-0.8.0-imgwtools-3.0.0-wplyw.md`). On Kartograf 0.8.0
all four adapter operations stopped working; IMGWTools 2.x had no adapter.

**Options:**
- A) stay on Kartograf 0.7.2 until it stabilises,
- B) migrate immediately, pinning the pushed commits until the tags exist.

**Decision:** B (author: "as soon as possible; the biggest changes are already in"). Ranges:
Kartograf `>=0.8.0,<0.9`, IMGWTools `>=3.0.0,<4` (semver and IMGWTools `/1` contracts). The
`tools` group pins, until the tags exist, `kartograf@8e9bcbb0` (`origin/develop`) and
`imgwtools[store]@0d98f3b` (`origin/slave`, publishing store versions via hard links —
works on Linux, macOS and Windows; the author includes it in v3.0.0). Retman asks about every new
required value (author): DSM (NMPT) resolution and vertical reference system, orthophoto colour
(RGB/CIR/B-W). All resolutions of Kartograf ASC map sheets are supported (DEM (NMT) 0.15; 0.5;
0.6; 1; 5; 10; 100 m; DSM (NMPT) 0.5; 0.6; 1 m).

**Consequences:** once the `v0.8.0` and `v3.0.0` tags are pushed, the `tools` group switches to tags.
Completeness of the resolutions is guarded by the coverage check (ADR-019). Details:
`docs/research/2026-10-19-kartograf-0.8.0-migracja.md`, `…-imgwtools-3.0.0-operacje.md`.

**Erratum 1 (2026-10-25, IMGWTools data output, ADR-024):** the IMGWTools pin of the decision,
`0d98f3b` (`origin/slave`), is replaced by `a304521`, the head of the IMGWTools branch
`feature/data-output`. That commit is not pushed, so the rule "pin the pushed commits" holds for
Kartograf only, until the author pushes IMGWTools. The ranges and the other decisions stand.

---

## ADR-013: Tools called through the command layer

**Date:** 2026-10-19
**Status:** accepted

**Context:** Kartograf 0.8.0 and IMGWTools 3.0.0 have a command catalog (`validate_command`,
`run_command`, `check_command`, `format_command`) with error codes and JSON result documents.
The change of typed functions and provider classes in 0.8.0 broke all handlers. The author left
the ruling to a study (2026-10-19); its recommendation became the decision.

**Options:**
- A) typed functions and provider classes of the tools in handlers,
- B) command layer: a pure call builder per operation, a shared executor, a client per
  tool,
- C) CLI subprocess with `--json`; D) MCP servers of the tools (ADR-018).

**Decision:** B. `retman/adapters/catalog.py` (`CatalogCall`, `ToolRun`, `ToolError`,
`PlanView`/`RunClient`, `ToolContext`); manifest: `client` (client factory), in an operation `calls`,
`commands`, `describe`, `preview`, `check`, `handler(params, inputs, output_dir, ctx)` (at
least one of `handler`/`calls`), in a parameter `tool_values`, `option_meta`, `excluded`;
option keys without dots. Before confirmation only the offline view exists (`validate`,
`command_line`, `lookup`); `run`/`check`/`query` — only during execution and in an approved
availability check. Exception: orthophoto with colour via `GugikOrtoProvider` + `DownloadManager`
(the `imagery download` command has no colour option; author's decision), only for map sheet codes (godło).
Messages: Retman texts per the tool's error code (`[errors.<code>]`), the tool's text as
`{detail}`; data quality and licence warnings verbatim.

**Consequences:** ARCHITECTURE 3.2, 4.1, 4.3; tests via `FakeToolClient` and recorded tool
documents. Study: `docs/research/2026-10-19-integracja-narzedzi.md`.

---

## ADR-014: No network before confirmation: preview and check

**Date:** 2026-10-19
**Status:** accepted

**Context:** Author: the availability check must not use the network before confirmation;
two steps with an explicit network query are acceptable.

**Options:**
- A) network during planning; B) a separate "check" operation; C) offline preview always +
  optional network check as a separate step with its own consent.

**Decision:** C. Invariant N-12: before `plan.confirm()` Retman calls no tool function with a
network side effect. Preview (`preview`, required): offline validation of every call and the
plan rows; a rejection by the tool reopens the indicated parameters (`Plan.reopened`). Check
(`check`): answer `s` in the plan, its own message and consent (`plan.confirm_check()`,
one-off), the report is informational only, does not change the plan, does not take a result
number; a `check` event in the journal.

**Consequences:** PRD N-12, W-17; ARCHITECTURE 2, 6.3–6.5, 5.4. Research:
`docs/research/2026-10-19-sprawdzanie-dostepnosci.md`.

---

## ADR-015: Tool stores outside results folders

**Date:** 2026-10-19
**Status:** accepted; amended by ADR-021 (2026-10-24, the settings file `nogat.toml` and the default paths of stores and cache replace those of this ADR)

**Context:** Kartograf 0.8.0 writes to a version store (immutable versions, sidecars, hard
links), IMGWTools 3.0.0 to its own store. Author: the IMGW store next to the Kartograf store
(same disk, different folders).

**Options:** A) a store in every result folder; B) one store per tool in `retman.toml`.

**Decision:** B. `[tools.kartograf] store_dir, cache_file, workers, update` and
`[tools.imgwtools] store_dir, reference_data_dir`; `retman init` writes adjacent folders and
(with consent) initialises the IMGW store; hard links are required. A result refers to store
files by absolute path and SHA-256; exported files go to the result folder.
`retman doctor` checks the stores and hard links (IMGW write probe with `--deep`).

**Consequences:** configurations without `[tools.*]` are rejected (`retman init` from scratch
or adding the section); ARCHITECTURE 3.2.4, 5.4, 7.2, 9.1.

---

## ADR-016: Geometry file as an area

**Date:** 2026-10-19
**Status:** accepted; amends ADR-001 and ADR-004

**Context:** The backlog item "geometry file as an area" was waiting for Kartograf's public
API; 0.8.0 has `get_overall_bbox`, `find_sheets_for_geometry` and `geometry=`/`layer=` in the
command functions. The decision was delegated to research.

**Options:** A) bounding rectangle of the geometry computed by Retman; B) map sheets
intersecting the geometry; C) passing the file to the tool (`geometry=`).

**Decision:** C. Area `{type: "geometry", path, layer}`; for a GeoPackage with several tables
the user selects the layer (list via `sqlite3`, `retman/core/geometry.py`). Semantics per
operation in the plan (preview: envelope, number of map sheets). Orthophoto accepts only
sheet codes (godło) (ADR-013). Data kind `area_geometry`; SHA-256 of the file in the audit
trail.

**Consequences:** ARCHITECTURE 3.2.6, 4.3, 6.1. Research:
`docs/research/2026-10-19-plik-geometrii.md`.

---

## ADR-017: All of IMGWTools in v0.1 and two-stage recognition

**Date:** 2026-10-19
**Status:** accepted; amends ADR-001 and ADR-004

**Context:** PRD 7.1 requires operations from at least two tools. Author: "all of IMGW goes into
v0.1", along with ČHMÚ.

**Options:** A) a few IMGWTools operations; B) all user-facing capabilities of the IMGWTools
catalog.

**Decision:** B — 26 operations in 6 categories (stations and catalog, current data, PMAXTP, time
series, archives and store, data projects); 7 catalog commands excluded with justification. More
than 9 operations ⇒ two-stage recognition: the model picks a category, then an operation (≤ 9
options per step, `[categories.<id>]` in `pl.toml`). New extractors: station (offline from the
store catalog), years, period, year kind (always a question), point, grid cell, probability,
duration, variables, task name. 13 new data kinds.

**Consequences:** PRD 7.2; ARCHITECTURE 3.1, 3.2.6, 3.4, 4.4, 6.1. Research:
`docs/research/2026-10-19-imgwtools-3.0.0-operacje.md`.

---

## ADR-018: MCP: tools via the Python API, Retman server in v0.3

**Date:** 2026-10-19
**Status:** accepted

**Context:** Kartograf (`kartograf-mcp`) and IMGWTools (`imgw mcp`) have MCP servers. The author
did not know what was optimal; the resolution was delegated to research.

**Options:** A) Retman calls the tools via the Python API; B) Retman as an MCP client of the
tools; C) Retman as an MCP server; D) defer.

**Decision:** A in every version; B rejected (a thin wrapper over the same functions, +23
packages, harder W-05 and tests); C in v0.3 as an optional extra `retman[mcp]`, with human
confirmation via elicitation and refusal to execute when the client cannot do that. No MCP code,
dependencies or configuration in v0.1.

**Consequences:** ARCHITECTURE 3.2.1, 7.5, 9.3, 11, 12; PRD 9. Research:
`docs/research/2026-10-19-mcp.md`.

---

## ADR-019: Static manifests and `retman-scaffold` from tool catalogs

**Date:** 2026-10-19
**Status:** accepted; amended by ADR-022 (2026-10-24, command layout: `retman-scaffold` is `retman scaffold`)

**Context:** The author wants support for all resolutions; tool catalogs describe options in a
machine-readable way. `retman-scaffold` was in the gate but did not exist. Resolution delegated.

**Options:** A) options derived from the installed catalog at load time; B) static options in the
manifest + drift check.

**Decision:** B. Options have Polish texts, and the `retman-eval` set must be reproducible.
`retman-scaffold list | draft | --check` reads the tool catalogs (no new dependencies);
`--check` is conformance by execution: real call builders on the grid of manifest options via
`validate_command` offline, coverage check (every tool value offered or in `excluded`), network
effects, error code texts (X1–X10). A light version in `retman doctor`.

**Consequences:** ARCHITECTURE 3.2.3, 3.2.7, 8.3, 13. Research:
`docs/research/2026-10-19-integracja-narzedzi.md` (chapters 2–3).

---

## New ADR template

New decisions are files `docs/decisions/NNNN-slug.md` (DOC-8.2). Copy the block below, take
the next number, use a status from the vocabulary at the top of this file, add a row to the
index and record every relation on both sides. Append errata at the end of the file and never
rewrite the decision.

````markdown
# ADR-XXX: Title

**Date:** YYYY-MM-DD
**Status:** proposed | accepted | accepted; amended by ADR-YYY (date, scope) | superseded by ADR-YYY (date)

## Context

Why the topic arose.

## Options considered

- A) ...
- B) ...

## Decision

Which option and why.

## Consequences

What follows (including changes to PRD.md and ARCHITECTURE.md).

## Errata

**Erratum 1 (YYYY-MM-DD, source or reason):** appended later.
````

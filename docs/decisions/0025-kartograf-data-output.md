# ADR-025: Kartograf data output: one store root, the registry codes, the marker states judged by Retman

**Date:** 2026-10-25
**Status:** accepted; amends ADR-012 (2026-10-25, the Kartograf pin is a commit that is not
pushed) and ADR-024 (2026-10-25, erratum 2: the Kartograf pin)

## Context

The Nogat data output convention (ECO-051, DEV §19) applies to Kartograf as it does to IMGWTools
(ADR-024). Kartograf 0.8.0 is not tagged, so its branch `feature/data-output` changed the tool
before its first release and without a migration: the store folder is `root` (it was
`output_dir`, `--output-dir`, `DownloadManager(output_dir=...)`), plain files go to `output_dir`,
a run is a `kartograf-result/1` envelope (`status`, `items[]`, `notices[]`, `files[]` with
`size_bytes`), the offline lookups are `sheet parse`, `sheet find` and `store sidecar`, the
catalog is read with `list_commands` and `command_schema`, the errors are the codes of the shared
registry with the precision in `details.reason` (`no_data` and not `no_coverage`,
`validation_error` and not `invalid_input`, and so on), and a store has the marker
`kartograf-store.json` (schema `kartograf-store/1`) that the tool writes on the first write into a
new or an empty folder. A folder that has the layout of a store and no marker, a folder with other
files, a marker that is not a `kartograf-store/1` document and a store inside another store are
refused. On the head of the branch, `8a36e977`, the Kartograf tests of Retman failed.

## Options considered

Where a download goes:

- A) offer both ways, as for IMGWTools: plain files into the results folder (`output_dir`) or the
  store (`root`). In plain mode Kartograf takes the newest *full* flight of a sheet and skips a
  sheet that has none (a mode-dependent selection, Z3.1), so the same command would give other
  data than the store, and the plain files would be a second copy of data that ADR-015 keeps once,
  shared by all projects;
- B) the store only, with `root` (chosen).

Who judges the folder of the store before a run:

- A) Kartograf alone: a run reports a refused store as the failure of every sheet
  (`source_unavailable`, after the work has begun), and the plan of the tool judges the folder
  only after the network. The user would confirm a plan that cannot run, and the first
  sign of it would be a run that failed sheet by sheet;
- B) Retman judges the folder itself, before anything is counted, by the rules of
  `kartograf.marker`, without importing the tool (chosen: it is the way `retman.stores` treats the
  IMGWTools store too, ADR-024 item 5);
- C) import `kartograf.marker` into Retman: a module that is not the public interface of the tool.

How the marker is written when the layout has lost it:

- A) tell the user to run `kartograf store init --root <folder>` in a shell;
- B) an operation of Retman, "Utwórz magazyn Kartografa", the counterpart of "Utwórz magazyn IMGW"
  (chosen). Kartograf's command layer (`validate_command`, `run_command`, `check_command`,
  `format_command`) takes the twelve data commands only; `store init` is refused there ("only the
  data commands are accepted"), so the operation is a handler that calls `kartograf.init_store`.

## Decision

1. **Calls.** The folder `[retman.tools.kartograf] store_dir` is the `root` of every call and of
   `DownloadManager(provider, root=...)`. Retman offers no operation for the plain mode of
   Kartograf (option B above) and passes no `output_dir`. The orthophoto in a chosen colour keeps
   its handler (the colour exists only on the provider class, ADR-013) and keeps its own summary,
   `retman-orthophoto-download/1`: the provider route has no `kartograf-result/1` document. The
   command ids are `sheet parse`, `sheet find` and `store sidecar`; `retman scaffold` reads
   `list_commands` and `command_schema`.
2. **Results and errors.** The files of a result are the `files[]` of the tool, with the
   checksum it reports. A failure carries the registry code and the tool's `details.reason`
   (`ToolFailure.reason`); the `error_code` of a result is the registry code (`no_data`,
   `source_unavailable`, `validation_error`, ...). The `[errors]` texts of the tool are keyed by
   the registry codes, and the precision stays in the document of the result. The Kartograf rows
   of `_TOOL_CODES` are gone: every registry code passes through.
3. **Marker states.** `retman.stores.kartograf_store_state` judges a folder: `missing`,
   `not_a_directory`, `empty`, `ready`, `no_marker`, `foreign`, `unreadable`, `unsupported` and
   `nested`. Only a file in a product tree counts as a layout; an empty product folder, a
   `.incoming` folder and the temporary marker file are no content. The state is a mirror of
   `kartograf.marker`, and the tests hold it against the tool (its 18 product trees, and 20
   folders judged by both sides, `kartograf.marker.lenient_store` among them). `retman doctor check` reports each refused state
   as a blocking `store_unavailable` (reasons `no_marker`, `foreign_folder`, `marker_unreadable`,
   `marker_unsupported`, `nested_store`) with a hint, and the offline preview of every operation
   that writes returns one blocking problem without a parameter (so there is nothing to ask
   again). The search for a store *below* a folder that is refused anyway is left to the tool: in
   that corner Retman says `foreign`, where the tool says `nested_store`.
4. **The operation `init_kartograf_store`** ("Utwórz magazyn Kartografa", no parameters) is a
   handler: it calls `kartograf.init_store`, maps the refusals through `translated()` to
   `ToolError` (`conflict` with the reasons `not_empty` and `nested_store`, `data_error` with
   `invalid_layout`), saves the document as `tool_1_store_init.json` and writes the audit. It is
   offline and idempotent. Its preview names the state of the folder (missing, empty, no marker,
   ready) and blocks only on the refused states; a layout without its marker is no problem
   there. The plan problem and the hint of `doctor check` for `no_marker` name this command, with
   `kartograf store init --root <folder>` as the alternative.
5. **Tests.** The Kartograf tests run the real tool in process, offline: its command layer
   validates, plans and downloads into a real store in a folder of the test, and only what would
   leave the machine is replaced, by stubs of the public provider classes
   (`tests/integration/tools/kartograf/kartograf_offline.py`). The stores the tests only read
   are built by `kartograf.testing` (DEV-10.6). The recorded documents of the old API are gone.
6. **The pin.** The `tools` group pins Kartograf `8a36e977`, the head of its branch
   `feature/data-output`. The commit is not pushed, which departs from ADR-012 ("pin pushed
   commits") in the same way as the IMGWTools pin (ADR-024 item 1); both are fetched into the uv
   git cache of this machine, and the author pushes both tools first.
7. **A bug waited for.** A refused store should be one command error, with its registry code
   and reason, raised before any work (DEV-17.5: to be fixed in Kartograf; nothing was
   changed in its repository from here). The test
   `test_a_run_into_a_store_kartograf_refuses_is_an_error_with_its_registry_code` (`no_marker` is
   `store_unavailable`, `not_empty` and `nested_store` are `conflict`) is written against the
   fixed behaviour and is `xfail(strict=True)`: when the pin has the fix, the three cases pass
   unexpectedly and fail the gate, which is the signal to drop the marker. A separate test, which
   holds before and after the fix, says that a run into a refused store writes and fetches
   nothing.

## Consequences

- **Breaking** for the readers of `result.json`: the `error_code` is a code of the registry
  (`no_data` was `no_coverage`, `source_unavailable` was `download_failed`, `validation_error` was
  `invalid_input`) and the precision is in the `failure` of the result. The CHANGELOG carries the
  migration; the plan and the settings do not change. A new or empty folder gets the marker on
  the first write.
- ARCHITECTURE 3.2.3 and 3.2.4 (the catalog readers, messages), 3.2.10 (the operations, the
  store folder), 7.2 and 9.3; USAGE 1.1, 9.1, 11 and the exit codes; README; PRD 7.1, 7.2 and 10.
- The operation count is 31 in seven categories (five from Kartograf) and the command set of
  `retman eval` has 630 commands (16 rows for the store, `kartograf-init-store-001` to `-016`).
  The sentence "Utwórz magazyn" now fits two tools: the rows `imgw-init-store-014` and `-015`
  expect IMGW after a question about the operation. `retman eval run` has not run on the new rows
  (it needs a model server), so the recognition of the two commands is unmeasured.
- `tests/unit/test_stores.py` needs Kartograf installed for the template and the agreement
  tests, and skips them otherwise.
- **`store init` through the command layer (AGI-2.1).** Kartograf is making `store init`
  reachable through `run_command` (in progress; not in the pinned commit). When the pin has it,
  `init_kartograf_store` leaves the handler: its call is a catalog call like the others, run by
  the generic executor, with the preview, the `check` and the audit of the other operations, and
  `handlers.init_kartograf_store` goes. Until then the handler path stands.
- The pins become tags once they exist (PROGRESS Next 3).

## Errata

**Erratum 1 (2026-10-25, Kartograf `b73aad33`):** the pin of item 6 is now Kartograf
`b73aad3327cf6faf7ec7d15fe47e9a897f21954a`, the head of `feature/data-output`, which is on
GitHub (the departure from ADR-012 ends for Kartograf). It has what items 4 and 7 waited for.
(a) A refused store is one error of the command with its registry code and reason, before any
request: the test `test_a_run_into_a_store_kartograf_refuses_is_an_error_with_its_registry_code`
lost its `xfail` and says as well that the index of the sheets is not asked and nothing is
written (the separate test of "writes and fetches nothing" is merged into it). `--check` lists a
root that is a conflict (`nested_store`, `not_empty`) as the one position of the plan (track
`store`, action `conflict`) instead of raising; the availability checks of BDOT10k and of the
orthophoto read it and report `store_refused` (status `unavailable`) instead of counting
counties or sheets. (b) The command layer takes every command of the catalog, `store init`
included (AGI-2.1), so item 4 is carried out: `init_kartograf_store` is a catalog call
(`calls.init_kartograf_store`, `describe.init_kartograf_store`, `preview`, the saved document and
the audit of the other operations; the document is the envelope `kartograf-result/1` and the
marker is its `result`, `kartograf-store-init/1`), `handlers.init_kartograf_store` is removed, and
the client gives a command the workers and the update mode only when `command_schema` declares
them (`store init` declares `root` and `check`). The operation declares no `check`: the plan of
`store init --check` is offline, so an availability step would be a consent notice without a
network, and the preview judges the folder by the same rules. The reader of `retman scaffold`
takes every command as one the layer accepts (`data` is true for all, so X9 lists the commands
no operation uses) and knows the document `kartograf-store-init/1`.

**Erratum 2 (2026-10-25):** the reader of `retman scaffold` no longer takes every command as
data: `data` is `not effects.read_only` of `command_schema`, so X9 lists the 14 commands that
download, write or delete (the downloads, `soil hsg`, `project *`, `cache clear`) and not the
source listings, the availability reports, the store reads, `sheet` and `config show`. This
replaces the sentence of erratum 1 that `data` is true for all.

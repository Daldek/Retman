# ADR-024: IMGWTools data output: plain files or a store, called as the tool defines them

**Date:** 2026-10-25
**Status:** accepted; amends ADR-012 (2026-10-25, the IMGWTools pin is a commit that is not
pushed); amended by ADR-025 (2026-10-25, the Kartograf pin)

## Context

The Nogat data output convention (ECO-051, DEV §19) gives every tool that writes data the same
two ways of writing: plain files in a directory (`output_dir`) or a versioned store with metadata
(`root`); `output` names exactly one file. IMGWTools 3.0.0 is not tagged, so the tool adopted the
convention before its first release and without a migration: `output_dir` and `root` exclude each
other, an export writes `output` (it was `path`), `IMGW_STORE_ROOT` is `IMGW_ROOT`, the folder of
the static station locations is `IMGW_REFERENCE_DIR` (`IMGW_DATA_DIR` is the user data directory
now), the statuses of a stored version are `new` and `unchanged` (`created` and `reused` are gone),
a writing command lists `files[]` (path, size, SHA-256 computed while writing, status), `forbidden`
joins the error codes, a folder with the layout of a store and no marker is `store_unavailable`
until `store init` has verified it, and the texts of the tool are English. On the head of its
branch `feature/data-output`, 23 tests of Retman failed.

## Options considered

Where an archive download goes:

- A) into the store, then copy the files to the results folder: two copies, and a store that
  holds only some of the datasets;
- B) as plain files into the results folder, with `output_dir` (chosen).

What stands in for `output_dir` while a plan is built, when there is no results folder yet:

- A) nothing: the tool then writes the store and refuses a dataset the store does not hold, and
  `retman scaffold check` reports that dataset as a dead option (X3);
- B) a temporary directory: an effect on the file system before the user has confirmed anything
  (PRD N-12);
- C) the project folder, which the tool only validates and never writes to (chosen).

The texts of the tool, which are English strings in its documents:

- A) write them in Polish with `Message.localized("pl")` of IMGWTools: Retman reads documents, in
  which a text is a string, so no message key crosses the process boundary and there is nothing to
  look up; the saved documents have to stay English (AGI-9.2), and Retman compares one of the
  texts;
- B) show them as they come, inside Retman's Polish sentences (chosen).

## Decision

1. **Pin.** The `tools` group pins IMGWTools `a304521`, the head of its branch
   `feature/data-output`. The commit is not pushed, which departs from ADR-012 ("pin pushed
   commits"): `uv lock` and `uv sync` resolve it only on a machine whose uv git cache holds it,
   the author pushes IMGWTools first, and until then a pushed Retman has no green CI. Kartograf
   stays at `8e9bcbb` until its own `feature/data-output` is pushed (PROGRESS Next 2).
2. **Calls.** The client reads the `exclusive` groups of the catalog of the tool and adds `root`
   (from `store_dir`) only to a call that names no option of a group that holds `root`. The two
   download operations pass the results folder as `output_dir`, with the project folder as the
   stand-in while a plan is built. The exports pass `output`. The store operations (`store sync`,
   `pmaxtp sync`, the series build, the reads) keep `root`; Retman offers no operation for the
   plain mode of `store sync` or `pmaxtp sync`. The reference data folder reaches the tool as
   `IMGW_REFERENCE_DIR`. Retman sets neither `IMGW_ROOT` nor `IMGW_STORE_ROOT` and uses no `imgw_*`
   operation id of the MCP and REST servers of the tool: it calls the command layer by command
   name (ADR-013, ADR-018).
3. **Results.** The files of an export and of a download are the `files[]` that the tool reports,
   with the checksum it computed while writing. The statuses are those of the tool: `new`,
   `unchanged`, `relabeled`, `failed`; the synchronisation counts `new_versions` and `new_series`.
   The text of a file that the server does not publish is one constant, `not published`, which a
   test holds against `imgwtools.fetch.UNPUBLISHED`. `[errors.forbidden]` has its text, and the
   text of a `conflict` no longer says "in the store", because plain files conflict too.
4. **Texts.** Option B above: Retman does not translate the texts of the tool. A Polish message
   can quote an English detail, and the licence notice of an IMGW result is the provider's
   attribution (Polish, in the wording of the terms of use) followed by the English notice of the
   tool. The saved documents keep the originals, and the user documents say so (USAGE 5.2, 13;
   ARCHITECTURE 3.2.4).
5. **Store folders.** `retman.stores.imgw_store_state` follows the rules of `store init` without
   importing the tool. A folder with the layout of a store (`archives/`, `series/`, `stations/` or
   `pmaxtp/`) and no marker is `no_marker`: `doctor check` reports a blocking `store_unavailable`
   with the reason `no_marker`, and the way out is the command "Utwórz magazyn IMGW", which makes
   the tool verify the layout and write the marker (`store init`). A folder that holds only
   `api_keys.json`, the state file of the REST server of the tool in its default store folder,
   counts as empty. A project (`project init`, `project set store`) refuses both folders, as the
   tool does.

## Consequences

- **Breaking** for the readers of `result.json`: in the results of the synchronisation
  `values.created` and `values.series_created` are `values.new_versions` and `values.new_series`;
  in `values.series`, `values.archives` and the `status` of `values.store_versions` the statuses
  `created` and `reused` are `new` and `unchanged`. The CHANGELOG carries the migration.
- ARCHITECTURE 3.2.4 (messages), 3.2.7 and 9.3 (the pin), 3.2.11 (store, output, `not published`,
  excluded commands), 7.2 (store checks); USAGE 1.1, 5.2, 11 and 13; README; PRD 10.
- The IMGW tests run the real tool offline: a plain download with replayed HTTP, the check plan of
  an export target, and `store init` and `project init` on the store folders of item 5.
- Kartograf follows the same convention in its own `feature/data-output`; its calls
  (`output_dir=` becomes `root=`) and its error codes wait for it (PROGRESS Next 2). The pins
  become tags once they exist (PROGRESS Next 3).
- Polish output can show English text of the tool (item 4); a machine document is English anyway.

## Errata

**Erratum 1 (2026-10-25, REL-5.6, ECO-053):** the pin of item 1 is now IMGWTools `7b11755`, the
head of the same branch (it ships `py.typed` and refuses a nested store in the plan of every store
write), and it is still not pushed. While a commit is pinned, the supported range admits the
development versions of the pending release: the manifests say `>=0.8.0.dev0,<0.9` (Kartograf)
and `>=3.0.0.dev0,<4` (IMGWTools), and `retman.registry.loader.version_matches` tests the declared
range itself with `packaging` (`SpecifierSet(range).contains(version, prereleases=True)`), the
one check that the loader, `doctor check`, `scaffold check` and the conformance tests use. The
release change that replaces the commits by tags narrows the ranges to `>=0.8.0,<0.9` and
`>=3.0.0,<4`. The mypy ignore of `imgwtools` is removed (the tool ships `py.typed`), and the tests
that need a ready IMGW store use `imgwtools.testing` (DEV-10.6).

**Erratum 2 (2026-10-25, Kartograf data output, ADR-025):** item 1 says that Kartograf stays at
`8e9bcbb` until its own `feature/data-output` is pushed, and a consequence says that its
calls and error codes wait for the tool. Neither holds any longer: the `tools` group pins
Kartograf `8a36e977`, the head of that branch, which is not pushed either, and the Kartograf
calls (`root` in place of `output_dir`) and error codes (the registry) are migrated (ADR-025).
Both pins wait for the author's push (PROGRESS Next 2).

**Erratum 3 (2026-10-25, IMGWTools `7e2114e`):** the pin of item 1 is now IMGWTools
`7e2114e1424903f1fd8fc036a2cb7aa81df44287`, the head of the same branch, which is on GitHub.
Two Nogat decisions (R1, R2) changed its refusals, and Retman reads them so. An `output_dir` that
is or lies in a store is `conflict` (`output_in_store`) before any request and `details.paths`
is the directory, not every target (it is kept in the `tool_details` of the failure). A store
write into a root that holds other files (`not_empty`; also a file) is a `conflict` like
`nested_store`: `--check` lists it as the one action `conflict` of the root, the plan is ok and
asks no server, and every run refuses it before any request; the checks of Retman (the
synchronisation, the catalog and the export) report it as `store_refused`, status `unavailable`,
and no longer as 0 files. A root with the layout and no marker is `store_unavailable`
(`no_marker`), a marker of another schema `store_unavailable`, and a marker that cannot be read
(invalid JSON, no `schema`) `data_error` (`invalid_marker`; it was `store_unavailable`), in the
plan and in the run; the plans of Retman name such a marker as unreadable instead of "other
files". `tests/unit/test_stores.py` holds `imgw_store_state` against the check of `series build`
of the tool for every state.

**Erratum 4 (2026-10-25, IMGWTools `3f7de36`):** the pin is now IMGWTools
`3f7de36f98f1ba40d72ab5556942567cfbc55b92`, the head of the same branch, which is on GitHub. `project init` reads the
marker as `store init` does: a marker that cannot be read is `data_error` (`invalid_marker`)
there too (it was `store_unavailable`, `unsupported`), so the test of the store folders that a
project meets expects `data_error` for the damaged one. The tool has `store_root()` for its
default root; Retman does not use it, because it passes `root` from `[retman.tools.imgwtools]
store_dir` to every command and resolves no default root of a tool.

**Erratum 5 (2026-10-25, IMGWTools `6bd35a49`):** the pin is now IMGWTools
`6bd35a49b329f99b591ffdee39367daec0e75af7`, the head of the same branch, which is on GitHub. The
head only flushes stray stdout to stderr before the MCP server leaves stdio; Retman calls the
command layer, not the MCP server, so nothing in Retman changes.

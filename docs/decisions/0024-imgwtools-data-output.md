# ADR-024: IMGWTools data output: plain files or a store, called as the tool defines them

**Date:** 2026-10-25
**Status:** accepted; amends ADR-012 (2026-10-25, the IMGWTools pin is a commit that is not
pushed)

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

# ADR-034: The raw and data roots of Obserwator: two settings, routed by command

**Date:** 2026-11-14
**Status:** accepted (the author approved the pin of the Nogat release set `candidate-4` on
2026-11-14); amends ADR-015 (one store per tool), ADR-021 (the default paths) and ADR-024 (the
`root` of every Obserwator call)

## Context

Obserwator `0394af7c`, its member of the Nogat release set `candidate-4`, splits its one store
into two roots (Obserwator ADR-017 "The data root", Nogat ECO-059):

- the **raw root**, marker `obserwator-store.json` (schema `obserwator-store/1`), trees
  `archives/` and `pmaxtp/`: what the providers publish. `datasets download`, `store sync` and
  `pmaxtp sync` write it; `store check`, `store export`, `pmaxtp check` and `pmaxtp read` read it;
- the **data root**, marker `obserwator-data.json` (schema `obserwator-data/1`), trees `series/`,
  `stations/` and `analyses/`: what the tool builds. `series *`, `store catalog`, `stations find`
  with `source=store`, `stations export` and `analyses *` work on it; `series build` and
  `store catalog` take the raw root as `raw_root`, read it only and write the data root.

The tool's defaults are `root` = `<data_dir>/obserwator` (data) and `raw_root` =
`<data_dir>/obserwator-raw` (raw). `store init --kind raw|data` (default `raw`) creates either.
A folder holding only the marker of the other kind is refused (`store_unavailable`,
`details.reason="wrong_root"`); a store written before the split, which holds the trees of both
kinds under `obserwator-store.json`, is `wrong_root` as a data root. No command converts such a
store: Obserwator's USAGE ("Splitting a store") splits it once by a copy with hard links. In the
same release `store sync` lost its `series` option (it writes the raw root only), and
`store catalog` became offline: it builds the catalog from the station sources (`*_stations`,
`*_now` of IMGW-PIB and ČHMÚ) that `store sync --datasets` keeps in the raw root.

Retman had one setting, `[retman.tools.obserwator] store_dir`, passed as `root` to every
Obserwator command (ADR-024 item 2), and its operations relied on `store sync` building the series
and on `store catalog` downloading the station lists. On `0394af7c` the store operations,
`retman doctor check` and `retman config init` failed.

## Options considered

| Option | Verdict |
|---|---|
| A. `store_dir` is the data root, a new `raw_store_dir` the raw root, with the tool's default folders | Chosen: the names and defaults mirror Obserwator's `root` and `raw_root`, so the default folder `<data_dir>/obserwator` keeps meaning the root Obserwator calls `root` |
| B. `store_dir` stays the raw root (where the archives were), a new setting names the data root | Rejected: departs from the tool's naming and defaults; Retman's `store_dir` and Obserwator's `root` would name different folders |
| C. One setting naming a parent folder that holds both roots as subfolders | Rejected: Obserwator treats the two as independent roots, each named on its own; a parent folder holding both is not a root, and its own data root would lie in it |
| D. Keep `build_obserwator_station_catalog` offline only, a separate synchronisation of the station sources first | Rejected: one user task ("build the station catalog") would become two operations, the first of them a download the user cannot name |

## Decision

Option A.

1. **Settings** (ARCHITECTURE 9.1). `[retman.tools.obserwator] store_dir` is the data root
   (default `<data_dir>/obserwator`); the new `raw_store_dir` is the raw root (default
   `<data_dir>/obserwator-raw`, variable `RETMAN_TOOLS_OBSERWATOR_RAW_STORE_DIR`). `retman config
   init` writes both into the folder of the stores, beside the Kartograf store; the path check
   flags any two of the three store folders that nest (`paths_overlap`).
2. **Client** (ARCHITECTURE 3.2.11). The client adds `root` by the kind of the command: the raw root
   for `datasets download`, `pmaxtp check|sync|read` and `store check|sync|export`, the root of its
   `kind` option for `store init`, the data root for every other command; it adds `raw_root` from
   `raw_store_dir` to the commands that take it (`series build`, `store catalog`). The rule of
   ADR-024 item 2 (no `root` with plain files) stands.
3. **Operations.**
   - `init_obserwator_store` initialises both roots: `store init` of the raw root, then of the
     data root (`kind=data`).
   - `sync_obserwator_store` runs `store sync` and then `series build` of the dataset, so the series
     land in the data root as before. `sync_obserwator_store_by_plan` stays raw only; the root of
     the plan is compared with the raw root.
   - `export_station_series` with the source "server" runs `store sync`, `series build`,
     `series export` and `series select`.
   - `build_obserwator_station_catalog` runs `store sync` of the provider's four station-source
     datasets (network, raw root), then `store catalog` (offline, data root); its availability
     check is the check of that synchronisation. `pl.imgw.hydro_details` is not synchronised: it
     takes about 910 requests, one per station page, and the catalog does not need it.
   - `inspect_obserwator_store` reads the data root, or the raw root for the kinds `archive`,
     `pmaxtp` and `observation`, and offers the kind `analyses`. The PMAXTP store operations and
     the archive export use the raw root; the station search in the store, the station coverage
     and the series build need a ready data root (the build also a ready raw root).
4. **Folder states** (`retman.stores`). `obserwator_store_state(folder, kind=...)` judges each root
   by the rules of `store init --kind`; the new state `wrong_root` is a folder holding only the
   marker of the other kind. `retman doctor check` and `retman config init` check and initialise
   both roots, and the `--deep` probe builds both fixture roots. A preview blocks on a root in
   state `wrong_root` with `store_unavailable`, reason `wrong_root`, and the hint names the split
   of Obserwator's USAGE.

## Consequences

- **Breaking** for existing users: a store written before the split is refused as the data root.
  It is split once (CHANGELOG; USAGE 1.3): move it aside, copy `archives/` and `pmaxtp/` into the
  raw root and `series/`, `stations/` and `analyses/` into the data root with hard links
  (`cp -al`), then `store init` of each root.
- The plans of `build_obserwator_station_catalog` and `sync_obserwator_store` gain calls (the
  station-source synchronisation, the series build), and the catalog operation now connects to the
  network through its synchronisation, as it did before through `store catalog`.
- Obserwator's catalog has 35 commands; `stations export` and `analyses build|list|read|export` are
  excluded with a reason (ARCHITECTURE 3.2.11), so 11 of 35 are excluded and the operations stay 19.
- The same pin emits the providers' attribution of Nogat DEV §20, so the decision of ADR-033 takes
  effect for Obserwator.
- Kartograf `c9afdd3f` does not yet treat `obserwator-data.json` as the marker of a store (its
  `STORE_MARKERS`), so neither does Retman's nested-store check, which follows Kartograf's rule
  (ADR-025 erratum 8); the settings check (`paths_overlap`) still keeps the three store folders
  apart. The need is a `request` issue in Kartograf, not filed yet.
- ARCHITECTURE 3.1, 3.2.4, 3.2.11, 4.3, 6.1, 7.2, 9.1, 9.3, 9.4 and 10; USAGE 1.1, 1.3, 7.2, 9.2
  and 11; README; `.env.example`; PRD 10; ADR-015, ADR-021 and ADR-024 carry the amendment on
  their status lines.

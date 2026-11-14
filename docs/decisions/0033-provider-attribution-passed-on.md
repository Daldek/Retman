# ADR-033: The providers' attribution of the tools is passed on into every result and table

**Date:** 2026-11-13
**Status:** accepted (the author's order of 2026-11-13: every product with IMGW-PIB or
ČHMÚ data carries the attribution their terms require; Nogat DEV §20, ECO-060)

## Context

Nogat DEV §20 asks every product with provider data, or with results derived from them,
to carry the lines `attribution` (source, processed mark, PMAXTP monograph, ČHMÚ
licence) and `terms_notice` (the conditions of use of IMGW-PIB data and the terms that
apply). The tools put them at the top level of their `<tool>-result/1` envelopes. Retman
writes CSV tables of its own from Obserwator's results (stations, current data, warnings,
water states, PMAXTP), keeps result folders with `result.json` and shows warnings. Until
now it showed the licence text it built from Obserwator's provider registry, which knows
neither the PMAXTP terms nor the hydro.imgw.pl terms.

## Options considered

| Option | Verdict |
|---|---|
| A. Pass on the tools' `attribution` and `terms_notice` verbatim: `Result` fields, warnings, trailing CSV columns | Chosen: ADR-024 (the tool's texts as they are), DEV-20.6 |
| B. Retman words the lines itself, by operation | Rejected: a second copy of the texts, and Retman cannot know which lines a tool's data need (hydro.imgw.pl coordinates in a store, ČHMÚ processing) |
| C. Only the saved tool documents carry them | Rejected: the tables Retman writes and the result the user reads are products too |

## Decision

Option A (`retman.attribution`, `retman.adapters.catalog.attribute`):

- The generic runner merges the lines of every run of an operation (in the order first
  seen, each once) into `HandlerOutput` and `Result` (`attribution`, `terms_notice`,
  also in `result.json` when not empty) and adds each line as a warning after the others,
  so every surface that shows a result shows them.
- Every CSV table Retman writes gets the trailing columns `attribution` and
  `terms_notice` of DEV-20.5; the existing `attribution_source` and
  `attribution_processed` of the PMAXTP table stay and take PMAXTP's own lines when the
  tool gives them.
- The registry-built licence text stays for an Obserwator of the supported range that
  gives no DEV §20 lines; when the lines are there it is left out.
- The series validator accepts the trailing columns after Obserwator's own.

## Consequences

- Retman shows and writes the lines once its pins of Obserwator and Hydrolog move to
  commits that emit them (the next release set); with today's pins the registry text is
  shown as before.
- When Obserwator writes `ATTRIBUTION.txt` into a download folder and lists it in
  `files[]`, the download operations must give that file a kind of its own (follow-up of
  the pin update).

## Errata

**Erratum 1 (2026-11-14, Nogat ECO-065 and ECO-068):** DEV §20 changed after this decision. The
`terms_notice` lines are the links to the terms, RD, RH and RK („Regulamin …: <address>”), and no
product restates the terms (ECO-065); the `attribution` lines also cover GUGiK (G), ISRIC
SoilGrids (SG) and ČÚZK (Z), whose data, like those of ČHMÚ, take no terms line (ECO-068). The
decision stands, since Retman words no line: the generic runner passes on the lines of any
tool's documents, so Kartograf's reach the results once its pin emits them (`d0990c89` emits
none). The orthophoto sheets of `download_sheet_hierarchy`, which Kartograf's provider class
fetches without a `kartograf-result/1` document, would get no lines.

**Erratum 2 (2026-11-14, Nogat DEV-20.4 and DEV-20.7):** the lines are no longer merged in the
order first seen: `retman.attribution` puts `attribution` in the order S, P, PS, PP, M, C, CP,
G, SG, Z and `terms_notice` in the order RD, RH, RK, each once, a line the standard does not
name after them in the order first seen. To place a line it compares it with the table of
DEV §20 (G, CP and Z by their fixed parts); it still words none.

**Erratum 3 (2026-11-14, Nogat release set `candidate-4`):** the first consequence is met: the
pins Obserwator `0394af7c` and Hydrolog `9e2cb618` emit the lines, so Retman shows and writes them
and the registry text is no longer shown for these pins. Kartograf `c9afdd3f` still emits none
(a deviation the tool records).

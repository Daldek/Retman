# ADR-030: Design documents in `docs/`

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

The design was one file, `DESIGN.md`, in the repository root. Kartograf already kept its documents
in `docs/` with a fixed set of names.

## Options considered

- A) `DESIGN.md` becomes `docs/ARCHITECTURE.md`, and the documents follow Kartograf's layout in
  `docs/` (chosen);
- B) keep `DESIGN.md` in the root.

## Decision

A: one documentation layout across the tools of the author.

## Consequences

`docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`,
`docs/CHANGELOG.md`; no reference to `DESIGN.md` is left.

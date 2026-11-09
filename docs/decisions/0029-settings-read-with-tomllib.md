# ADR-029: Settings read with `tomllib`, written from a template

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

Retman reads a TOML settings file and its first-run command writes one. Writing TOML needs either
a library or a fixed text.

## Options considered

- A) read with `tomllib` (standard library), write from a commented template (chosen);
- B) a TOML writing library as a dependency.

## Decision

A: no dependency for writing TOML; the written file keeps its comments.

## Consequences

ARCHITECTURE 9.3; `src/retman/config_template.toml`. Since ADR-021 and ADR-022 the file is
`nogat.toml` (`[retman]`) and the command is `retman config init`.

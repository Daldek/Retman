# ADR-031: LF line endings in every file

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

The line endings of the repository had to be fixed before the first commit, for work on Linux,
macOS and Windows.

## Options considered

- A) LF in every file, no exceptions (chosen);
- B) LF with exceptions (e.g. Windows scripts with CRLF).

## Decision

A: LF in the repository and in every working copy.

## Consequences

The former STANDARDS 5.5; today `.gitattributes` (`* text=auto eol=lf`, DEV-14.1) and CLAUDE.md.

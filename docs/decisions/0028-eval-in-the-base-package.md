# ADR-028: The evaluation runner and its command set in the base package

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

Recognition quality is measured on a set of test commands with `retman-eval`
(spec `docs/specs/2026-10-11-retman-eval.md`). It could ship in the package or stay a developer
script.

## Options considered

- A) `retman-eval` and the test command set in the base package (chosen);
- B) a developer-only script or an extra.

## Decision

A: the evaluation runs from the installed package, without a checkout of the repository.

## Consequences

ARCHITECTURE 3.1, 8.1, 8.2 and 9.3; the set is `src/retman/eval/commands.jsonl`. Since ADR-022 the
runner is `retman eval run`.

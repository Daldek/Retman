# ADR-026: A bare probability number always asks

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

A probability in a command can be a percentage or a fraction ("dla 1" is 1 % or p = 1), and a
return period is a third reading. The extractor of ARCHITECTURE 4.4 reads numbers in code, so the
rule for a number without a marker had to be fixed.

## Options considered

- A) a number without "%", "Q" and a period in years always gets a question (chosen);
- B) guess the reading when the other one is impossible.

## Decision

A: such a number **always** asks, even when one of its readings is impossible.

## Consequences

ARCHITECTURE 4.4 (table "Ambiguous spellings", row "dla 1", "dla 0,5"); the extractor
`probability` and its tests.

# ADR-027: No execution without confirmation in 0.x

**Date:** 2026-10-11
**Status:** accepted

**Recorded:** retroactively on 2026-11-10 (the author's decision of 2026-11-09), from the entry
"Start projektu" of the first session in `docs/PROGRESS.md` (commit `8c7657c`; the session log
was removed in `e1ac15e`). The entry names only the choice; the options below are the
alternatives it rules out.

## Context

W-05 requires a human to approve a plan. The question was whether a mode that runs a plan without
confirmation is excluded for good or only while the product is refined.

## Options considered

- A) excluded in the 0.x versions, not permanently (chosen);
- B) excluded permanently.

## Decision

A: every execution in 0.x needs confirmation; the exclusion is not a permanent design rule.

## Consequences

PRD 7.3 (today: "before version 1.0"), ARCHITECTURE 1.1, 1.2, 6.3 and chapter 10.

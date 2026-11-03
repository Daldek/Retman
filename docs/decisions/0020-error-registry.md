# ADR-020: Adopt the shared error registry

**Date:** 2026-10-24
**Status:** accepted

## Context

The Nogat standard 2.1 gives every tool one error registry (ERR-3): the same codes, exit
codes and error document in every tool, so that an agent or a script handles the errors of
all tools alike. Retman had its own exit codes (`0` ok, `1` error, `2` input needed,
`3` cancelled, `4` W-03 of `retman-eval`), no error codes and plain text on stderr. The
release 0.1.0 is not tagged, so the change needs no migration path (ECO-020).

## Options considered

- Keep the codes and document a mapping table: consumers of Retman would branch on codes
  that no other tool has.
- One exception class per registry code: the classes of Retman carry meaning of their own
  (`except OutOfScopeError`) and several of them share a code.
- Give each existing class a registry code and a default `details.reason` (chosen, as in
  Hydrolog and Kartograf).

## Decision

1. `schemas/nogat/` holds verbatim copies of `error_registry.json` and the three agent
   schemas (Nogat commit `cc656e7`); `scripts/generate_errors.py` writes
   `src/retman/_errors.py`; `tests/contract/test_error_registry.py` compares the module with
   the generator and validates error documents against `error-1`.
2. `RetmanError` has `code`, `message`, `details` and `hint` (DEV-11.1) and a `text` for the
   translated wording a user sees; subclasses select a default code and reason. Retman adds
   no code of its own (ERR-1): `UsageError` `validation_error` (`usage`), `ConfigError`
   `validation_error` (`invalid_config`; a missing file `not_found`, an existing one
   `conflict`), `InputRequiredError` and `PlanIncompleteError` `validation_error`
   (`input_required`, AGI-3.5), `OutOfScopeError` `unsupported` (`out_of_scope`),
   `BackendError` `source_unavailable`, `KindValidationError` `data_error` (`not_found` or
   `io_error` by its reason), `EvalDatasetError` `data_error`, `ManifestError`,
   `TranslationError` and `ToolDriftError` `internal_error`, the plan-state errors
   `conflict`. `ToolError` maps the code of the tool to the registry (`no_coverage` to
   `no_data` and so on, ERR §4); the rows of the pinned Kartograf in that map go when a
   Kartograf that uses the registry is pinned.
3. The CLI reports every error through `retman.outcomes.report_error`: the text for the user,
   then, as the last line of stderr, the English `retman-error/1` document as compact JSON
   (AGI-3.3). `retman`, `retman-eval` and `retman-scaffold` do the same. SIGTERM is
   `terminated` (143).
4. A plan that needs an answer or a confirmation while stdin is not a terminal is
   `validation_error` with the reason `input_required` and the open questions in
   `details.questions` (AGI-3.5); it is no outcome.
5. Outcomes that are not errors: a declined plan or Ctrl+C is `cancelled` (130) and prints no
   document; `retman doctor` (a check blocks work), `retman-eval` (a command that must be
   refused was planned, W-03) and `retman-scaffold --check` (errors found) end with `partial`
   (10), or `failed` (11) when no check or tool passed.

## Consequences

- **Breaking:** exit codes 1 (out of scope), 3, 4 change as listed in the CHANGELOG; scripts
  read USAGE 8.
- `ToolError.code` is the registry code, `ToolError.tool_code` the tool's own; `ConfigError`
  keeps its problem texts as `problem_details`.
- The message and hint of an error are English; the Polish text stays in the translation
  files and in `RetmanError.text`.
- Next: the agent interfaces fold `retman-eval` and `retman-scaffold` into `retman` (AGI-3.1)
  and print the outcomes `partial` and `failed` as the result envelope.

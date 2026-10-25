# ADR-023: Repository structure, quality gate, CI, test tree and technical log

**Date:** 2026-10-24
**Status:** accepted

## Context

The Nogat standard 2.1 gives every tool the same repository layout (DEV-5), one quality gate
(DEV-7.6), CI on three systems (DEV-7.7), one test tree with markers (DEV-5.2, DEV-10.1), the
static-checking rules (DEV-7.2, DEV-7.3) and the logging rules (DEV-12). Retman had a flat
layout (`retman/` in the repository root), one test folder, a gate that was a list of commands
in a document (ruff, mypy, pytest), no CI, and a technical log that ARCHITECTURE 5.4 described
but no code wrote. Release 0.1.0 is not tagged, so no step needs a migration path (ECO-020).

## Options considered

- Layout: keep the flat layout, or move the package to `src/retman` (ECO-011, DEV-5.1).
- Gate: keep the commands in a document, or copy `gate.sh` and `check-commits.sh` from Nogat
  `standards/ci` unchanged (chosen: one command for agents, DEV-7.6).
- Environment of the gate: install the tools Retman adapts (Kartograf, IMGWTools) only when
  asked, or in every environment, so that the conformance tests never skip in the gate.
- mypy: bring the 36 test modules whose helpers and fixtures are not annotated to `strict`
  now, or list them in a per-module override and shrink the list (DEV-7.3).
- Log: write the file in the user's log directory that ARCHITECTURE 5.4 describes, or log to
  stderr only (DEV-12.2).

## Decision

1. **Layout.** The package is `src/retman` and ships `py.typed` with the classifier
   `Typing :: Typed` (DEV-5.1, DEV-7.4); Hatch builds `packages = ["src/retman"]`. The old
   paths stay in ADRs and research reports, which keep the paths of their day.
2. **Gate.** `scripts/gate.sh` and `scripts/check-commits.sh` are the Nogat templates:
   `uv sync --locked --all-extras`, `ruff format --check`, `ruff check`, mypy over `src` and
   `tests`, one pytest call over `tests/` with coverage (`-m "not live"`, floor 80%) and the
   commit step (DEV-7.6, DEV-4.5). The development tools are the `dev` dependency group, and
   `[tool.uv] default-groups = ["dev", "tools"]` makes `uv sync --locked --all-extras` install
   the `tools` group too: Kartograf and IMGWTools pinned by commit (ADR-012), so the
   conformance tests run against the real tools (DEV-6.3, DEV-6.5). The old
   `retman-scaffold --check --require-tools` is replaced by a contract test that fails when the
   gate environment lacks a tool that Retman adapts, because the conformance checks skip a
   missing tool (DEV-10.4).
3. **CI.** `.github/workflows/ci.yml` runs the gate on Linux, macOS and Windows with Python 3.12
   and the newest Python, audits the locked PyPI dependencies weekly with `pip-audit` and checks
   commit messages once, on pull requests into `develop` (DEV-7.7, DEV-4.5, DEV-13.6).
   `live.yml` runs the tests marked `live` weekly; those that need a model server skip without
   `--live-openai-url` (DEV-10.3). Dependabot updates GitHub Actions weekly. The workflows are
   written and not run: nothing is pushed yet.
4. **Test tree.** `tests/unit` (offline, one module), `tests/integration` (several modules,
   the dummy tool, the tool adapters), `tests/contract` (the installed tools against Retman's
   descriptions, the generated files, package data, the interfaces) and `tests/fixtures`
   (DEV-5.2). pytest runs with `--strict-markers`, registers `live`, `slow` and `db`, and
   excludes `live` by default (DEV-10.1). The contract tests read the package data from the
   package (DEV-5.4). The test folders are not packages (`namespace_packages = false`): a
   folder named like a tool, such as `tests/integration/tools/imgwtools`, would otherwise
   shadow the installed tool; so test file names are unique across `tests/`.
5. **Static checking.** ruff selects `E`, `F`, `W`, `I`, `UP`, `B`, `SIM`, `C4` and `D` with the
   numpy docstring convention, and tests ignore `D` (DEV-7.2). mypy runs in `strict` mode over
   `src` and `tests` (DEV-7.3). The second option of mypy is chosen, and it is the deviation
   DEV-7.3: 36 test modules, listed in `[[tool.mypy.overrides]]` of `pyproject.toml`, leave
   helpers and fixtures unannotated. A new test module is strict, and a module leaves the list when it is
   annotated. CLAUDE.md lists the deviation (DEV-1.2).
6. **Technical log.** Modules create `logging.getLogger(__name__)`; the library never configures
   a handler and never logs a command, an answer or a secret (DEV-12.1, DEV-12.3). The CLI puts
   one handler on stderr. The level is `--verbose` (debug) or `--quiet` (error), then
   `RETMAN_LOG_LEVEL`, `NOGAT_LOG_LEVEL`, the setting `log_level` and the default `warning`
   (DEV-12.2, DEV-18.1; the setting was `[log] diagnostic_level` before ADR-021). The log file
   in the user's log directory is dropped with its unused path helper.

## Consequences

- One command, `scripts/gate.sh`, proves a change; it runs before every commit, and CLAUDE.md
  names it with the other commands.
- The conformance tests need the pinned tools in the environment, so the gate needs network
  access once to fetch the two commits; the pins become tags when Kartograf 0.8.0 and
  IMGWTools 3.0.0 are tagged (REL-5.3, PROGRESS Next 3).
- Moving a test module off the mypy list is the way to retire the deviation; PROGRESS keeps no
  separate item for it.
- The first CI run, on a pushed branch, may find platform differences (hard links on Windows
  and macOS stores); PROGRESS Next 5 lists it.
- ARCHITECTURE 3.1 (modules) and 5.4 (journal and log) follow the layout and the stderr log.

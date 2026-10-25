# ADR-021: User environment: `[retman]` in `nogat.toml`, variables and user directories

**Date:** 2026-10-24
**Status:** accepted; amends ADR-010 (2026-10-24: the `[privacy]` table is now
`[retman.privacy]`, its default file is below `data_dir`) and ADR-015 (2026-10-24: the settings
file, the default store and cache paths)

## Context

The Nogat standard 2.1 gives every tool one user environment (DEV-18, ECO-028): a shared
`nogat.toml` in the user configuration directory, the variables `<TOOL>_<KEY>` and `NOGAT_<KEY>`,
a data and a cache directory per user, credentials from the environment only, and
`<tool> config show --json`. Retman had its own `retman.toml` in a folder of its own, no
variables for its settings (only `RETMAN_LOG_LEVEL` and `NOGAT_LOG_LEVEL`, read by the logging
module), paths of the stores and the cache chosen by `retman init` below
`<data>/retman`, and the requirement N-11 of the PRD: one central file, no hidden defaults. N-11
and DEV-18.1 differ: the standard has a default layer. The release 0.1.0 is not tagged, so the
change needs no migration path (ECO-020).

## Options considered

- Keep `retman.toml` and add variables: two files per user for one ecosystem, against DEV-18.1.
- Take `pydantic-settings` as IMGWTools does: a heavy dependency; Retman has no `.env` file and
  needs `platformdirs` only.
- Read the `[retman]` tables of `nogat.toml` through one module that resolves each key in the
  order of DEV-18.1, with every default shown by `retman config show` (chosen; the design of
  Kartograf's ADR-050).

## Decision

1. **File and order (DEV-18.1).** A setting comes from the first of: the command-line option (no
   setting has one yet; `--config PATH` names the file), `RETMAN_<KEY>`, `NOGAT_<KEY>` (shared
   keys only), the table `[retman]` of `nogat.toml`, the table `[nogat]` (shared keys only), the
   default. `<KEY>` is the dotted key in capitals with `_` for `.`: `decision.url` is
   `RETMAN_DECISION_URL`. An empty variable counts as unset. The file is `nogat.toml` in
   `platformdirs.user_config_path("nogat")`, or the path in `NOGAT_CONFIG`; it is read with
   `tomllib`, and Retman needs neither the `nogat` package nor a `.env` file. `platformdirs>=4`
   is a core dependency.
2. **Keys.** The sub-tables of `retman.toml` stay under `[retman]`: `decision`,
   `decision.thresholds`, `text`, `output`, `adapters`, `tools.kartograf`, `tools.imgwtools`,
   `log`, `privacy`. Two keys move to the shared names: `[ui] language` is `lang` and
   `[log] diagnostic_level` is `log_level`; the shared keys are `lang`, `log_level`, `data_dir`
   and `cache_dir`. `log_level` is shared like in Hydrolog, so `NOGAT_LOG_LEVEL` keeps working.
3. **Defaults and N-11.** N-11 is read as "no hidden default": `retman config show` lists every
   value with its source (`default`, `env`, `file`) and `retman init` writes the tables out, with
   the shared keys left as comments so that it does not override a `[nogat]` table of the user.
   Every key has a default except the model server (`decision.backend`, `url`, `model`,
   `timeout_s`, `thresholds`), which has no meaningful one: `load_config` reports the missing
   keys (`validation_error`, reason `invalid_config`, problem `missing_key`), and every command
   that needs no model (`results`, `log`, `config show`, `init`, `doctor`) works from the defaults
   through `load_settings`. `Config` is `Settings` plus the model server.
4. **Paths (DEV-18.2, DEV-19.2).** `tools.kartograf.store_dir` is `<data_dir>/kartograf`,
   `tools.imgwtools.store_dir` is `<data_dir>/imgw`, the Kartograf metadata cache is
   `<cache_dir>/kartograf/metadata.db`, the IMGWTools reference files are
   `<cache_dir>/imgw/reference`, the command collection is `<data_dir>/retman/collected.jsonl`.
   `data_dir` and `cache_dir` default to `platformdirs.user_data_path("nogat")` and
   `user_cache_path("nogat")`. The stores keep meaning the store root of the tool: they stay
   siblings, absolute, without `..`. The journal and the results stay in the project folder
   (`output.results_dir`, ARCHITECTURE 5): a deviation from DEV-18.2 listed in `CLAUDE.md`.
5. **Unusable settings.** A file named by `--config` or `NOGAT_CONFIG` that does not exist is
   `not_found` (`missing_config`); one that cannot be read, is not valid TOML or has a `retman`
   or `nogat` that is not a table, and every value that cannot be used (also from a variable,
   named with the variable), are `ConfigError` (`validation_error`, `invalid_config`), all
   problems at once. A missing default file is no error. `config show` reports instead of raising.
6. **Language.** `lang` is `pl` or `en`. The texts of Retman exist in Polish only, so `en` is
   accepted and shown, and the texts stay Polish until the English ones are written
   (`Settings.language` is the language of the texts); a deviation from DEV-2.2 listed in
   `CLAUDE.md`. Machine output is English whatever `lang` says.
7. **`retman init`** appends the tables to an existing file and leaves its other tables as they
   are; a file that has a `[retman]` table is `conflict` (reason `output_exists`, problem
   `already_exists`), one that is not valid TOML is not touched.
8. **`retman config show`** (library: `get_config`) is the document `retman-config/1` in the shape
   of `kartograf-config/1`: `config_file` (`path`, `source`, `exists`, `error`, `ignored`),
   `keys` (`value`, `source`, `name`, `error`), `credentials` (the variable named by
   `decision.api_key_env`: `present` or `missing`, never the value), `store` (`root` is null:
   Retman keeps no store) and, additive within `/1`, `stores` (the stores of the two tools with
   source and size, a hard-linked file counted once). A key of the file that nothing reads is in
   `ignored`, as `credential` when its name asks for a secret. DEV-18.5 does not apply: the
   stores are those of Kartograf and IMGWTools; the README points to `rsync -aH`.
9. **Code.** `retman.environment` finds the values (`KEYS`, `Environment`), `retman.config`
   checks them (`Settings`, `Config`, `load_settings`, `load_config`, the template and
   `init_config`), `retman.config_show` builds the report.

## Consequences

- **Breaking:** `retman.toml` is no longer read and the tables lose their top level: write them
  as `[retman.<table>]` (`retman init` does it); `[ui] language` and `[log] diagnostic_level`
  are `lang` and `log_level`; the default stores are `<data_dir>/kartograf` and
  `<data_dir>/imgw` (they were `<data>/retman/stores/kartograf` and `…/imgwtools`), the cache
  and the reference files are below `cache_dir`.
- An invalid `RETMAN_LOG_LEVEL` is `invalid_config` (it was a usage error); the log level is no
  longer read by `retman.logs`.
- `retman-eval --config` is optional.
- The tests run with the user environment isolated (`tests/conftest.py::user_environment`).
- Next: the agent interfaces put `config show` and `config init` in the command catalog (ADR-022).

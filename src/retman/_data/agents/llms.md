# Retman

> A CLI and Python library that turns a data task written in Polish into a plan for Kartograf and IMGWTools, asks for what is missing, shows the plan and, once confirmed, runs it and saves the result in the project folder.

Retman is not for exact calls of a tool with known options (use Kartograf or IMGWTools directly), for commands in other languages, or for hydrological computation (Hydrolog). A language model on a separate OpenAI-compatible server only chooses between listed options; code reads numbers, dates, coordinates and identifiers.

Interfaces: Python (<!-- retman:python_example -->) and the CLI (`retman <group> <verb> --option value --json`); no MCP server, no REST API. Install with `pip install "retman @ git+https://github.com/Daldek/Retman.git"`; the tools are separate installs and the model server is set in `nogat.toml` (`retman config init`, `retman doctor check`).

Work in four steps: discover (`retman commands list`, `retman commands schema --command NAME`), check (`--check` plans without effects), run (`--yes` after the user approved the plan), read (`result`, `items`, `notices`). A result is a `retman-result/1` envelope; an error is a `retman-error/1` document whose `code` is one of: <!-- retman:error_codes -->.

Command groups: <!-- retman:group_names -->.

## Documentation

- [AGENTS.md](https://raw.githubusercontent.com/Daldek/Retman/main/AGENTS.md): the full guide for agents: interfaces, envelope, error codes, command index, typical flows
- [README.md](https://raw.githubusercontent.com/Daldek/Retman/main/README.md): what Retman is for, installation and a first command
- [Usage](https://raw.githubusercontent.com/Daldek/Retman/main/docs/USAGE.md): task-oriented guide to the CLI and the Python interface
- [Architecture](https://raw.githubusercontent.com/Daldek/Retman/main/docs/ARCHITECTURE.md): how a command becomes a plan and a result
- [Changelog](https://raw.githubusercontent.com/Daldek/Retman/main/docs/CHANGELOG.md): changes per release

## Optional

- [PRD](https://raw.githubusercontent.com/Daldek/Retman/main/docs/PRD.md): product requirements and scope
- [Decisions](https://raw.githubusercontent.com/Daldek/Retman/main/docs/DECISIONS.md): architecture decision records

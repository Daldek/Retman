"""Generate the JSON Schemas of the domain documents (AGI-4.1).

Every command of the catalog declares the id of its result document
(``Command.result_schema``, for example ``retman-doctor/1``), and a command that writes
files has the plan ``retman-targets/1`` for its ``check`` mode. The documents come from
operations that need a model server, installed tools or a terminal project, so the
schemas are written by hand below, not inferred from a run. They are deliberately
loose: the top-level properties with their types, the properties that every document
has as ``required``, and little about nested keys, so a new optional field keeps the
version (AGI-4.1). ``retman-commands/1`` is the Nogat ``commands-1`` schema
(``schemas/nogat/``) and has no file here. ``tests/contract/test_result_schemas.py``
validates real documents against these files and requires that every id of the catalog
has one.

Usage::

    uv run scripts/generate_result_schemas.py            # write the schemas
    uv run scripts/generate_result_schemas.py --check    # fail when they are stale
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from retman.catalog import data_commands
from retman.catalog.document import COMMANDS_SCHEMA
from retman.operations.documents import TARGETS_SCHEMA

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src" / "retman" / "schemas"
BASE = "https://github.com/Daldek/Retman/blob/main/src/retman/schemas"

Schema = dict[str, Any]

STRING: Schema = {"type": "string"}
NULL_STRING: Schema = {"type": ["string", "null"]}
NULL_NUMBER: Schema = {"type": ["number", "null"]}
BOOLEAN: Schema = {"type": "boolean"}
INTEGER: Schema = {"type": "integer", "minimum": 0}
OBJECT: Schema = {"type": "object"}
ARRAY: Schema = {"type": "array"}
FILES: Schema = {
    "type": "array",
    "description": "Files the command wrote (DEV-19.19), added by the envelope.",
    "items": {
        "type": "object",
        "required": ["path", "size_bytes", "sha256", "status"],
        "properties": {
            "path": STRING,
            "size_bytes": INTEGER,
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "status": {"enum": ["written", "replaced"]},
        },
    },
}


def _file_name(schema_id: str) -> str:
    return schema_id.replace("/", "-") + ".schema.json"


def _document(
    schema_id: str,
    description: str,
    properties: dict[str, Schema],
    required: list[str],
) -> Schema:
    """Return the schema of one domain document."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE}/{_file_name(schema_id)}",
        "title": schema_id,
        "description": (
            f"{description} It is the `result` of the envelope retman-result/1. "
            "Unknown fields are allowed: adding optional fields keeps the version "
            "(AGI-4.1)."
        ),
        "type": "object",
        "required": ["schema", *required],
        "properties": {"schema": {"const": schema_id}, **properties},
    }


def _list(item: Schema) -> Schema:
    return {"type": "array", "items": item}


def _record(properties: dict[str, Schema], required: list[str]) -> Schema:
    return {"type": "object", "required": required, "properties": properties}


def _plan() -> Schema:
    question = _record(
        {
            "name": STRING,
            "type": STRING,
            "text": STRING,
            "options": _list(_record({"key": STRING, "label": STRING}, ["key"])),
        },
        ["name", "type", "text", "options"],
    )
    return _document(
        "retman-plan/1",
        "The plan of a Polish command: the operation, the values and inputs with "
        "their source and confidence, the offline preview and the open questions; "
        "with `yes` also the `run`.",
        {
            "text": STRING,
            "operation": NULL_STRING,
            "operation_label": NULL_STRING,
            "operation_confidence": NULL_NUMBER,
            "operation_unverified": BOOLEAN,
            "complete": BOOLEAN,
            "confirmed": BOOLEAN,
            "values": OBJECT,
            "inputs": OBJECT,
            "unset": ARRAY,
            "preview": ARRAY,
            "questions": _list(question),
            "decisions": ARRAY,
            "run": OBJECT,
        },
        [
            "text",
            "operation",
            "complete",
            "confirmed",
            "values",
            "inputs",
            "unset",
            "preview",
            "questions",
        ],
    )


def _config() -> Schema:
    key = _record(
        {
            "value": {},
            "source": {"enum": ["default", "env", "file", "option"]},
            "name": NULL_STRING,
            "error": NULL_STRING,
        },
        ["value", "source", "name", "error"],
    )
    return _document(
        "retman-config/1",
        "Every setting with its value and source, the credentials and the stores "
        "(DEV-18.6).",
        {
            "tool": {"const": "retman"},
            "version": STRING,
            "config_file": _record(
                {
                    "path": STRING,
                    "source": {"enum": ["default", "NOGAT_CONFIG", "option"]},
                    "exists": BOOLEAN,
                    "error": NULL_STRING,
                    "ignored": _list(
                        _record({"key": STRING, "reason": STRING}, ["key", "reason"])
                    ),
                },
                ["path", "source", "exists", "error", "ignored"],
            ),
            "keys": {"type": "object", "additionalProperties": key},
            "credentials": OBJECT,
            "store": OBJECT,
            "stores": OBJECT,
        },
        ["tool", "version", "config_file", "keys", "credentials", "store", "stores"],
    )


def _config_init() -> Schema:
    return _document(
        "retman-config-init/1",
        "The settings file `config init` wrote and the folders it chose.",
        {
            "config_file": STRING,
            "collect_commands": BOOLEAN,
            "collect_path": STRING,
            "stores": _record(
                {"kartograf": STRING, "imgwtools": STRING}, ["kartograf", "imgwtools"]
            ),
            "files": FILES,
        },
        ["config_file", "collect_commands", "collect_path", "stores"],
    )


def _doctor() -> Schema:
    check = _record(
        {
            "id": STRING,
            "status": {"enum": ["ok", "warning", "error", "off"]},
            "text": STRING,
            "hint": NULL_STRING,
            "blocking": BOOLEAN,
            "code": STRING,
            "reason": STRING,
        },
        ["id", "status", "text", "hint", "blocking"],
    )
    section = _record(
        {"key": STRING, "title": STRING, "checks": _list(check)},
        ["key", "title", "checks"],
    )
    return _document(
        "retman-doctor/1",
        "The report of `doctor check`: sections of numbered checks; the envelope lists "
        "each check as a unit.",
        {"sections": _list(section)},
        ["sections"],
    )


def _results() -> Schema:
    row = _record(
        {
            "number": {"type": "integer", "minimum": 1},
            "operation": STRING,
            "ok": BOOLEAN,
            "summary": STRING,
            "finished_at": NULL_STRING,
        },
        ["number", "operation", "ok", "summary", "finished_at"],
    )
    return _document(
        "retman-results/1",
        "The numbered results of the project folder, in numeric order.",
        {"directory": STRING, "results": _list(row)},
        ["directory", "results"],
    )


def _journal() -> Schema:
    event = _record({"time": STRING, "event": STRING}, ["time", "event"])
    return _document(
        "retman-journal/1",
        "The events of the journal of the project folder, oldest first.",
        {"file": STRING, "events": _list(event)},
        ["file", "events"],
    )


def _command_list() -> Schema:
    command = _record(
        {
            "name": STRING,
            "operation_id": STRING,
            "summary": STRING,
            "read_only": BOOLEAN,
        },
        ["name", "operation_id", "summary", "read_only"],
    )
    return _document(
        "retman-command-list/1",
        "The summary of the catalog commands (`commands list`).",
        {"tool": {"const": "retman"}, "version": STRING, "commands": _list(command)},
        ["tool", "version", "commands"],
    )


def _guide() -> Schema:
    return _document(
        "retman-guide/1",
        "A guide for agents: the text itself, or the size of the file that was "
        "written.",
        {
            "format": {"enum": ["agents", "llms", "agents-md-block"]},
            "text": STRING,
            "lines": INTEGER,
            "bytes": INTEGER,
            "files": FILES,
        },
        ["format"],
    )


def _ratio() -> Schema:
    return _record(
        {"count": INTEGER, "total": INTEGER, "fraction": NULL_NUMBER},
        ["count", "total", "fraction"],
    )


def _eval() -> Schema:
    return _document(
        "retman-eval/1",
        "The measures of an evaluation of the model on the command set; the envelope "
        "lists the commands that had to be refused as units.",
        {
            "commands": INTEGER,
            "runs": INTEGER,
            "repeat": {"type": "integer", "minimum": 1},
            "target_error": NULL_NUMBER,
            "overall": {
                "type": "object",
                "additionalProperties": {"type": ["object", "null"]},
            },
            "recommendations": {"type": ["object", "null"]},
            "violations": ARRAY,
            "files": FILES,
        },
        ["commands", "runs", "repeat", "target_error", "overall", "violations"],
    )


def _scaffold_check() -> Schema:
    finding = _record(
        {
            "check": STRING,
            "severity": {"enum": ["error", "warning", "info"]},
            "operation": NULL_STRING,
            "key": STRING,
            "args": OBJECT,
            "text": STRING,
        },
        ["check", "severity", "key", "args", "text"],
    )
    tool = _record(
        {
            "tool": STRING,
            "status": {
                "enum": ["checked", "skipped", "missing", "unsupported", "failed"]
            },
            "version": NULL_STRING,
            "supported": STRING,
            "operations": INTEGER,
            "points": INTEGER,
            "calls": INTEGER,
            "findings": _list(finding),
        },
        ["tool", "status", "findings"],
    )
    return _document(
        "retman-scaffold-check/1",
        "The drift check of the tool descriptions: one block per tool with its "
        "findings; the envelope lists each tool as a unit.",
        {"tools": _list(tool)},
        ["tools"],
    )


def _scaffold_list() -> Schema:
    command = _record(
        {
            "id": STRING,
            "group": NULL_STRING,
            "network": BOOLEAN,
            "writes": BOOLEAN,
            "operations": _list(STRING),
            "use": STRING,
        },
        ["id", "group", "network", "writes", "operations", "use"],
    )
    return _document(
        "retman-scaffold-list/1",
        "The data commands of the catalog of a tool and the operations that use them.",
        {"tool": STRING, "version": STRING, "commands": _list(command)},
        ["tool", "version", "commands"],
    )


def _scaffold_draft() -> Schema:
    return _document(
        "retman-scaffold-draft/1",
        "The draft of an operation: Python for the call builder and the translation "
        "table, as text.",
        {
            "operation_id": STRING,
            "python": STRING,
            "translations": STRING,
            "files": FILES,
        },
        ["operation_id", "python", "translations"],
    )


def _targets() -> Schema:
    target = _record(
        {
            "option": STRING,
            "path": STRING,
            "action": {"enum": ["write", "replace", "conflict"]},
        },
        ["option", "path", "action"],
    )
    return _document(
        TARGETS_SCHEMA,
        "The plan of a `check` run that writes files: each target with its action "
        "(DEV-19.10). A plan that lists a conflict is a successful result.",
        {"targets": _list(target)},
        ["targets"],
    )


def build() -> dict[str, Schema]:
    """Return every schema by document id.

    Raises
    ------
    SystemExit
        The catalog declares a result document that has no schema here, or the
        script has a schema that no command declares.
    """
    schemas = {
        schema["title"]: schema
        for schema in (
            _plan(),
            _config(),
            _config_init(),
            _doctor(),
            _results(),
            _journal(),
            _command_list(),
            _guide(),
            _eval(),
            _scaffold_check(),
            _scaffold_list(),
            _scaffold_draft(),
            _targets(),
        )
    }
    declared = {command.result_schema for command in data_commands()} | {TARGETS_SCHEMA}
    declared.discard(COMMANDS_SCHEMA)  # the Nogat schema commands-1 describes it
    if declared != set(schemas):
        raise SystemExit(
            f"missing schemas: {sorted(declared - set(schemas))}, "
            f"unused schemas: {sorted(set(schemas) - declared)}"
        )
    return schemas


def _text(schema: Schema) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write the schemas, or with ``--check`` fail when they are stale."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="do not write")
    args = parser.parse_args(argv)
    expected = {
        TARGET / _file_name(schema_id): _text(schema)
        for schema_id, schema in build().items()
    }
    if args.check:
        stale = [
            path.name
            for path, text in expected.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != text
        ]
        extra = [
            path.name for path in TARGET.glob("*.schema.json") if path not in expected
        ]
        if stale or extra:
            print(
                f"stale: {stale}, unexpected: {extra}: "
                "run scripts/generate_result_schemas.py"
            )
            return 1
        return 0
    TARGET.mkdir(parents=True, exist_ok=True)
    for path in TARGET.glob("*.schema.json"):
        if path not in expected:
            path.unlink()
    for path, text in expected.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

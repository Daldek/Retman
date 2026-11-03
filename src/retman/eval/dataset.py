"""Load and validate offline planning expectations against every packaged tool."""

import json
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from retman.eval.stations import catalog_lookup
from retman.exceptions import EvalDatasetError
from retman.extractors import read_command, validate_value
from retman.extractors.base import ExtractionContext
from retman.registry.loader import discover_manifests
from retman.registry.manifest import OperationSpec, ParamSpec

DEFAULT_COMMANDS: Path = Path(
    str(resources.files("retman.eval").joinpath("commands.jsonl"))
)


@dataclass(frozen=True)
class EvalCommand:
    """Expected planning outcome for one Polish-language command."""

    id: str
    command: str
    operation: str
    params: dict[str, Any]
    expect_clarify: list[str]
    tags: list[str]
    note: str | None


def _invalid_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def load_commands(path: Path) -> list[EvalCommand]:
    """Read JSONL commands; report all malformed records with their line numbers."""
    commands: list[EvalCommand] = []
    problems: list[str] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                try:
                    record = json.loads(line, parse_constant=_invalid_constant)
                except (json.JSONDecodeError, ValueError) as err:
                    problems.append(f"line {number}: invalid JSON: {err}")
                    continue
                if not isinstance(record, dict):
                    problems.append(f"line {number}: expected a JSON object")
                    continue
                identifier = record.get("id")
                prefix = (
                    f"{identifier} (line {number})"
                    if isinstance(identifier, str) and identifier
                    else f"line {number}"
                )
                required = ("id", "command", "operation", "tags")
                for name in required:
                    if (
                        not isinstance(
                            record.get(name), str if name != "tags" else list
                        )
                        or not record[name]
                    ):
                        problems.append(f"{prefix}: missing or invalid {name}")
                if any(
                    not isinstance(record.get(name), str) or not record[name]
                    for name in ("id", "command", "operation")
                ):
                    continue
                if not isinstance(record.get("tags"), list) or not record["tags"]:
                    continue
                params = record.get("params", {})
                clarify = record.get("expect_clarify", [])
                tags = record["tags"]
                note = record.get("note")
                if not isinstance(params, dict) or any(
                    not isinstance(name, str) for name in params
                ):
                    problems.append(
                        f"{prefix}: params must be an object with string keys"
                    )
                elif not isinstance(clarify, list) or any(
                    not isinstance(name, str) for name in clarify
                ):
                    problems.append(f"{prefix}: expect_clarify must be a list of names")
                elif any(not isinstance(tag, str) or not tag for tag in tags):
                    problems.append(f"{prefix}: tags must be nonempty strings")
                elif note is not None and not isinstance(note, str):
                    problems.append(f"{prefix}: note must be a string")
                else:
                    commands.append(
                        EvalCommand(
                            record["id"],
                            record["command"],
                            record["operation"],
                            params,
                            clarify,
                            tags,
                            note,
                        )
                    )
    except (OSError, UnicodeError) as err:
        raise EvalDatasetError([f"{path}: {err}"]) from err
    if problems:
        raise EvalDatasetError(problems)
    return commands


def _valid_free(
    param: ParamSpec, value: Any, command: str, context: ExtractionContext
) -> str | None:
    """Use the pipeline's extractor registry and matching/acceptance semantics."""
    accepts = param.get("accepts")
    values = value if param.get("multiple") and isinstance(value, list) else [value]
    matches = read_command(param["extractor"], command, context)
    readings = [
        reading.value
        for match in matches
        for reading in match.readings
        if not accepts
        or (isinstance(reading.value, dict) and reading.value.get("type") in accepts)
    ]
    for item in values:
        if accepts and (not isinstance(item, dict) or item.get("type") not in accepts):
            return "area form outside accepts"
        if validate_value(param["extractor"], item, context) is not None:
            return "invalid extracted value"
        bounds = param.get("range")
        if bounds is not None and (
            type(item) not in (int, float) or not bounds[0] <= item <= bounds[1]
        ):
            return "value outside range"
        if item not in readings:
            return "value not extracted from command"
    if param.get("multiple") and not isinstance(value, list):
        return "multiple value must be a list"
    return None


def _applicable(param: ParamSpec, values: dict[str, Any]) -> bool | None:
    """Match the pipeline's three-way dependency decision, including defaults."""
    for controller, options in param.get("depends_on", {}).items():
        if controller not in values:
            return None
        if values[controller] not in options:
            return False
    return True


def validate_commands(commands: list[EvalCommand]) -> None:
    """Check per-entry validity against all shipped manifests, installed or not."""
    operations: dict[str, tuple[str, OperationSpec]] = {
        operation["id"]: (manifest["tool"], operation)
        for manifest, _ in discover_manifests()
        for operation in manifest["operations"]
    }
    problems: list[str] = []
    seen: set[str] = set()
    for entry in commands:
        identifier = entry.id
        if not identifier or identifier in seen:
            problems.append(f"{identifier!r}: duplicate or empty id")
        seen.add(identifier)
        if not entry.command:
            problems.append(f"{identifier}: empty command")
        if not entry.tags or any(
            not isinstance(tag, str) or not tag for tag in entry.tags
        ):
            problems.append(f"{identifier}: invalid tags")
        if entry.operation == "out_of_scope":
            if entry.params or entry.expect_clarify:
                problems.append(f"{identifier}: out_of_scope cannot have parameters")
            continue
        found = operations.get(entry.operation)
        operation = found[1] if found is not None else None
        tool = found[0] if found is not None else ""
        if operation is None:
            problems.append(f"{identifier}: unknown operation {entry.operation}")
            continue
        params = {param["name"]: param for param in operation["params"]}
        supplied = set(entry.params)
        clarified = set(entry.expect_clarify)
        for name in supplied | clarified:
            if name not in params:
                problems.append(f"{identifier}: unknown parameter {name}")
        for name in supplied & clarified:
            problems.append(f"{identifier}: {name} both supplied and expect_clarify")
        if len(clarified) != len(entry.expect_clarify):
            problems.append(f"{identifier}: duplicate expect_clarify parameter")
        values = {
            name: entry.params[name] if name in entry.params else param["default"]
            for name, param in params.items()
            if name in entry.params or "default" in param
        }
        for name, param in params.items():
            applicable = _applicable(param, values)
            if applicable is False:
                if name in supplied | clarified:
                    problems.append(f"{identifier}: inapplicable parameter {name}")
                continue
            if "default" in param and name in clarified and name not in supplied:
                problems.append(f"{identifier}: default parameter {name} is redundant")
            # An optional parameter (no ``required``, no ``default``) is left unset
            # when the command does not state it, and Retman never asks about it:
            # it is no expectation either way, and cannot be a clarification
            optional = not param.get("required") and "default" not in param
            if optional and name in clarified and name not in supplied:
                problems.append(
                    f"{identifier}: optional parameter {name} is never asked"
                )
            if (
                applicable is True
                and name not in supplied | clarified
                and "default" not in param
                and not optional
            ):
                problems.append(f"{identifier}: missing applicable parameter {name}")
            if name not in supplied:
                continue
            value = entry.params[name]
            if param["type"] == "choice":
                if not isinstance(value, str) or value not in param["options"]:
                    problems.append(f"{identifier}: {name} outside choice options")
            elif param["type"] == "bool":
                if type(value) is not bool:
                    problems.append(f"{identifier}: {name} must be boolean")
            else:
                scope: dict[str, Any] = {}
                for other_name, other in params.items():
                    if other["type"] == "choice" and other_name in values:
                        scope.update(
                            other.get("option_meta", {}).get(values[other_name], {})
                        )
                context = ExtractionContext(
                    tool=tool,
                    settings={},
                    project_dir=Path("."),
                    scope=scope,
                    lookup=catalog_lookup,
                    today=date.today(),
                )
                invalid = _valid_free(param, value, entry.command, context)
                if invalid:
                    problems.append(f"{identifier}: {name} {invalid}")
    if problems:
        raise EvalDatasetError(problems)

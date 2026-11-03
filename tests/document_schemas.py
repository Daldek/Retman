"""Validate a domain document against the JSON Schema that the package ships."""

import json
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator


def schema_file(schema_id: str) -> str:
    """Return the file name of the schema of ``schema_id`` (``retman-plan/1``)."""
    return schema_id.replace("/", "-") + ".schema.json"


def shipped_schema(schema_id: str) -> dict[str, Any]:
    """Return the schema of ``schema_id`` as the installed package ships it."""
    text = (
        resources.files("retman")
        .joinpath("schemas", schema_file(schema_id))
        .read_text(encoding="utf-8")
    )
    schema: dict[str, Any] = json.loads(text)
    return schema


def violations(schema_id: str, document: object) -> list[str]:
    """Return what in ``document`` breaks the shipped schema of ``schema_id``."""
    validator = Draft202012Validator(shipped_schema(schema_id))
    return [error.message for error in validator.iter_errors(document)]

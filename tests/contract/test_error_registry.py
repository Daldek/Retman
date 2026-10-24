"""The error module is generated from the vendored Nogat registry (ERR-3, ERR-4)."""

import importlib.util
import json
from types import ModuleType
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from nogat_schemas import NAMES, ROOT, SCHEMAS, load, validator

from retman import _errors
from retman.exceptions import (
    ERROR_CODES,
    BackendConnectionError,
    CheckNotConfirmedError,
    ConfigError,
    EvalDatasetError,
    InputRequiredError,
    InvalidValueError,
    KindValidationError,
    ManifestError,
    OutOfScopeError,
    PlanIncompleteError,
    PlanNotConfirmedError,
    RetmanError,
    Terminated,
    TranslationError,
    UsageError,
    error_document,
)

REGISTRY = SCHEMAS / "error_registry.json"


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_errors", ROOT / "scripts" / "generate_errors.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_error_module_equals_the_generator_output() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    generated = _generator().render(registry)

    module = ROOT / "src" / "retman" / "_errors.py"
    assert module.read_text(encoding="utf-8") == generated


def test_error_module_carries_every_code_and_outcome_of_the_registry() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert [c.code for c in _errors.CODES] == [e["code"] for e in registry["errors"]]
    assert {
        o["status"]: o["exit_code"] for o in registry["outcomes"]
    } == _errors.OUTCOMES


def test_codes_of_retman_are_registry_codes_with_an_exit_code() -> None:
    for code, entry in ERROR_CODES.items():
        assert _errors.BY_CODE[code] is entry
        assert entry.exit_code is not None


@pytest.mark.parametrize("name", NAMES)
def test_vendored_schema_is_a_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(load(name))


def test_vendored_error_schema_lists_the_registry_codes() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert load("error-1")["$defs"]["code"]["enum"] == [
        e["code"] for e in registry["errors"]
    ]


ERRORS: list[BaseException] = [
    UsageError("bad", details={"option": "x", "value": "y", "allowed": ["a"]}),
    InputRequiredError("needs input", details={"questions": [{"name": "area"}]}),
    PlanIncompleteError("open questions"),
    PlanNotConfirmedError("not confirmed"),
    CheckNotConfirmedError("no consent"),
    InvalidValueError("bad value", details={"option": "name", "value": "x"}),
    ConfigError(ROOT / "nogat.toml", ["missing_file"]),
    ConfigError(ROOT / "nogat.toml", ["invalid_value"], {"invalid_value": "a.b"}),
    ConfigError(ROOT / "nogat.toml", ["already_exists"]),
    EvalDatasetError(["line 3: unknown operation"]),
    ManifestError("bad manifest"),
    TranslationError("missing text"),
    OutOfScopeError(["Utworzenie NMT"], "Polish text"),
    KindValidationError("dem", ROOT / "x.asc", "missing_file"),
    KindValidationError("dem", ROOT / "x.asc", "bad_header"),
    BackendConnectionError("http://127.0.0.1:1234/v1"),
    RetmanError("bug"),
    Terminated(),
    FileNotFoundError(2, "No such file", "x"),
    RuntimeError("bug"),
]


@pytest.mark.parametrize("error", ERRORS, ids=lambda error: type(error).__name__)
@pytest.mark.parametrize("lang", ["en", "pl"])
def test_error_documents_validate_against_the_error_schema(
    error: BaseException, lang: Any
) -> None:
    document = error_document(error, command="plan run", lang=lang)

    validator("error-1").validate(document)
    assert document["exit_code"] == _errors.BY_CODE[document["code"]].exit_code
    assert document["schema"] == "retman-error/1"

"""Generic adapter from a validated manifest to a public tool handler."""

import importlib
from pathlib import Path
from typing import Any

from retman.core.result import Result
from retman.i18n.loader import Texts
from retman.kinds import validate_file
from retman.registry.operation import Operation


def execute_operation(
    operation: Operation,
    params: dict[str, Any],
    inputs: dict[str, Path],
    output_dir: Path,
    number: int,
    params_audit: dict[str, dict[str, Any]],
    inputs_audit: dict[str, dict[str, Any]],
    texts: Texts,
) -> Result:
    """Lazy-import a handler, check its files and build a uniform result."""
    result = Result(True, number, operation.id, params_audit, inputs_audit)
    try:
        module_name, function_name = operation.spec["handler"].split(":", 1)
        handler = getattr(importlib.import_module(module_name), function_name)
        data = handler(params, inputs, output_dir)
        for kind, paths in data["files"].items():
            if kind not in operation.spec["outputs"]:
                raise ValueError(f"undeclared output kind {kind}")
            for path in paths:
                checked = Path(path).resolve()
                if not checked.is_relative_to(output_dir.resolve()):
                    raise ValueError(f"output outside result directory: {checked}")
                validate_file(kind, checked)
                result.files.setdefault(kind, []).append(checked)
        result.outputs = list(result.files)
        result.values = data["values"]
        result.warnings = [
            operation.texts.get(f"warnings.{warning['key']}", **warning["args"])
            for warning in data["warnings"]
        ]
        result.summary = texts.get(
            "results.success",
            number=number,
            operation=operation.text("label"),
            directory=str(output_dir),
        )
    except Exception as err:
        result.ok = False
        result.outputs = []
        result.values = {}
        result.files = {}
        result.error = str(err)
        result.summary = texts.get("results.failure", number=number, error=err)
    return result

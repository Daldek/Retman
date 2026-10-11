"""Public result of a confirmed operation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Result:
    """Outcome of execution, including outputs by data kind and a short summary."""

    ok: bool
    number: int
    operation: str
    params: dict[str, dict[str, Any]]
    inputs: dict[str, dict[str, Any]]
    outputs: list[str] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)
    files: dict[str, list[Path]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Represent the public result with JSON-compatible values."""
        return {
            "ok": self.ok,
            "number": self.number,
            "operation": self.operation,
            "params": self.params,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "values": self.values,
            "files": {
                kind: [str(path) for path in paths]
                for kind, paths in self.files.items()
            },
            "warnings": self.warnings,
            "error": self.error,
            "summary": self.summary,
        }

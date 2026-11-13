"""Public result of a confirmed operation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retman.registry.manifest import ToolAudit


@dataclass
class Result:
    """Outcome of execution, including outputs by data kind and a short summary.

    ``warnings`` are the translated notices of the operation (partial results,
    the tool's data-quality and licence notices); callers must show them.
    ``error_code`` is the tool's stable error code when a tool error failed the
    operation; ``tool`` is the audit block of the catalog commands that ran.
    ``failure`` is the ``retman-error/1`` document (English, registry code and exit
    code) of the failure when ``ok`` is false.
    ``attribution`` and ``terms_notice`` are the lines the data providers' terms
    require with the data or with what was made from them (Nogat DEV §20), passed on
    verbatim from the tools; they are also the last warnings.
    """

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
    error_code: str | None = None
    tool: ToolAudit | None = None
    failure: dict[str, Any] | None = None
    attribution: list[str] = field(default_factory=list)
    terms_notice: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Represent the public result with JSON-compatible values.

        ``error_code``, ``tool``, ``failure``, ``attribution`` and ``terms_notice``
        appear only when they carry information.
        """
        record: dict[str, Any] = {
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
        if self.error_code is not None:
            record["error_code"] = self.error_code
        if self.tool is not None:
            record["tool"] = self.tool
        if self.failure is not None:
            record["failure"] = self.failure
        if self.attribution:
            record["attribution"] = self.attribution
        if self.terms_notice:
            record["terms_notice"] = self.terms_notice
        return record

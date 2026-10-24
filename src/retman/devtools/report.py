"""Rendering of the drift check: the report for the terminal and its JSON form."""

import json
from collections.abc import Sequence

from retman import __version__
from retman.devtools.drift import Finding, ToolReport, count_problems
from retman.exceptions import TranslationError
from retman.i18n.loader import Texts
from retman.outcomes import EXIT_FAILED, EXIT_OK, EXIT_PARTIAL

# Document schema of ``retman-scaffold --check --json``
JSON_SCHEMA = "retman-scaffold-check/1"
_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def finding_text(finding: Finding, texts: Texts) -> str:
    """Return the Polish text of a finding from ``[scaffold.finding]``.

    A finding whose text is missing or does not fit its arguments is shown by its
    key and arguments, so that nothing is hidden; the tests keep every key
    translated.
    """
    arguments = {
        "tool": finding.tool,
        "operation": finding.operation or "",
        **finding.args,
    }
    try:
        return texts.get(f"scaffold.finding.{finding.key}", **arguments)
    except (KeyError, IndexError, ValueError, TranslationError):
        listed = ", ".join(f"{name}={value}" for name, value in finding.args.items())
        return f"{finding.key} ({listed})" if listed else finding.key


def _order(finding: Finding) -> tuple[int, str, str, str]:
    return (
        _SEVERITY_ORDER[finding.severity],
        "" if finding.check == "T" else f"{finding.check:0>3}",
        finding.operation or "",
        finding.key,
    )


def exit_code(reports: Sequence[ToolReport]) -> int:
    """``0`` when no finding is an error, else ``10`` (``partial``).

    ``11`` (``failed``) when every tool report holds an error (usage errors are
    ``2``, as the registry says).
    """
    failing = [
        report
        for report in reports
        if any(finding.severity == "error" for finding in report.findings)
    ]
    if not failing:
        return EXIT_OK
    return EXIT_FAILED if len(failing) == len(reports) else EXIT_PARTIAL


def render_check(
    reports: Sequence[ToolReport], texts: Texts, *, verbose: bool = False
) -> str:
    """Render the report for the terminal: one block per tool, then the summary.

    Information lines are counted and shown only with ``verbose``.
    """
    lines: list[str] = []
    for report in reports:
        if report.status == "checked":
            lines.append(
                texts.get(
                    "scaffold.tool_checked",
                    tool=report.tool,
                    version=report.version or "",
                    supported=report.supported,
                    operations=report.operations,
                    points=report.points,
                    calls=report.calls,
                )
            )
        for finding in sorted(report.findings, key=_order):
            if finding.severity == "info" and not verbose:
                continue
            lines.append(
                texts.get(
                    "scaffold.line",
                    marker=texts.get(f"scaffold.marker_{finding.severity}"),
                    check=finding.check,
                    text=finding_text(finding, texts),
                )
            )
    counts = count_problems(reports)
    summary = "summary_failed" if counts["error"] else "summary_clean"
    lines.append("")
    lines.append(
        texts.get(
            f"scaffold.{summary}",
            errors=counts["error"],
            warnings=counts["warning"],
            infos=counts["info"],
        )
    )
    if counts["info"] and not verbose:
        lines.append(texts.get("scaffold.infos_hidden", count=counts["info"]))
    return "\n".join(lines) + "\n"


def check_json(reports: Sequence[ToolReport], texts: Texts) -> str:
    """Render the same report as a JSON document (``retman-scaffold-check/1``)."""
    document = {
        "schema": JSON_SCHEMA,
        "retman": __version__,
        "exit_code": exit_code(reports),
        "tools": [
            {
                "tool": report.tool,
                "status": report.status,
                "version": report.version,
                "supported": report.supported,
                "operations": report.operations,
                "points": report.points,
                "calls": report.calls,
                "findings": [
                    {
                        "check": finding.check,
                        "severity": finding.severity,
                        "operation": finding.operation,
                        "key": finding.key,
                        "args": dict(finding.args),
                        "text": finding_text(finding, texts),
                    }
                    for finding in sorted(report.findings, key=_order)
                ],
            }
            for report in reports
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

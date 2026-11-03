"""The light drift check that ``retman doctor check`` shows for the tools in use.

It is the part of ``retman scaffold check`` that a user with a newer tool in the
supported range needs: the manifest's commands exist in the installed catalog and
the tool offers no value the manifest neither offers nor excludes ("coverage gap:
kartograf 0.8.1 offers 0.3m"). It runs on a grid varied one choice at a time, with
one sample per operation, under the offline guard (ARCHITECTURE 3.2.3, 7.2).
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from retman.devtools.drift import Finding, light_findings
from retman.devtools.report import finding_text
from retman.eval.dataset import DEFAULT_COMMANDS, load_commands
from retman.exceptions import RetmanError
from retman.i18n.loader import Texts
from retman.registry.manifest import ManifestSpec

# What decides the findings of a tool: its manifest, its translation folder and its
# installed version; ``None`` when there is nothing to check against
LightCheck = Callable[[ManifestSpec, Path, str], list[Finding] | None]


@dataclass(frozen=True)
class Line:
    """One line for the doctor report: how serious, what to say, how to fix."""

    status: Literal["ok", "warning", "error"]
    text: str
    hint: str | None = None


def packaged_check(
    manifest: ManifestSpec, directory: Path, version: str
) -> list[Finding] | None:
    """Run the light check against the eval command set shipped with Retman."""
    return light_findings(
        manifest, directory, version, commands=load_commands(DEFAULT_COMMANDS)
    )


def light_lines(
    manifest: ManifestSpec,
    directory: Path,
    version: str,
    texts: Texts,
    check: LightCheck | None = None,
) -> list[Line]:
    """Return the doctor lines of one tool in use: ``ok``, or one line per finding.

    The operations that could not be checked (X10) are one line, and the hint on
    how to go further stands on the first problem only. A tool the scaffold has
    nothing to check against gives no line; a check that cannot run (an unreadable
    dataset) is a warning, never an exception.
    """
    tool = manifest["tool"]
    hint = texts.get("scaffold.doctor_hint")
    try:
        findings = (check or packaged_check)(manifest, directory, version)
    except RetmanError as error:
        text = texts.get("scaffold.doctor_failed", tool=tool, error=error)
        return [Line("warning", text, hint)]
    if findings is None:
        return []
    problems = [finding for finding in findings if finding.severity != "info"]
    unchecked = list(
        dict.fromkeys(
            finding.operation or "" for finding in problems if finding.check == "X10"
        )
    )
    lines = [
        Line(
            "error" if finding.severity == "error" else "warning",
            finding_text(finding, texts),
        )
        for finding in problems
        if finding.check != "X10"
    ]
    if unchecked:
        text = texts.get(
            "scaffold.doctor_unchecked",
            tool=tool,
            count=len(unchecked),
            operations=", ".join(unchecked),
        )
        lines.append(Line("warning", text))
    if not lines:
        return [Line("ok", texts.get("scaffold.doctor_ok", tool=tool, version=version))]
    return [replace(lines[0], hint=hint), *lines[1:]]

"""Retman's descriptions of every installed tool against what that tool accepts.

The real tools are used offline: the tool's own validation (``validate_command``)
judges every point of the manifest grid, and the catalog is read for the coverage
and effects checks (``retman scaffold check``, ARCHITECTURE 3.2.3, 3.2.7). A tool
that is not installed, or installed in a version outside its manifest's range, is
skipped; the CI runs this on the oldest and the newest supported version.
"""

import functools
import importlib.metadata
from pathlib import Path
from typing import Any

import pytest

import retman.tools
from retman.devtools.drift import ToolReport, check_tools
from retman.devtools.model import Reader, load_reader
from retman.devtools.report import finding_text
from retman.eval.dataset import DEFAULT_COMMANDS, EvalCommand, load_commands
from retman.i18n.loader import load_core_texts
from retman.registry.loader import discover_manifests, version_matches
from retman.registry.manifest import ManifestSpec

MANIFESTS: dict[str, tuple[ManifestSpec, Path]] = {
    manifest["tool"]: (manifest, folder) for manifest, folder in discover_manifests()
}
# Tools whose operations run catalog commands: the ones there is something to check
CATALOG_TOOLS = [
    tool
    for tool, (manifest, _) in MANIFESTS.items()
    if any("calls" in spec for spec in manifest["operations"])
]
OPERATIONS = [
    pytest.param(tool, spec["id"], id=f"{tool}-{spec['id']}")
    for tool in CATALOG_TOOLS
    for spec in MANIFESTS[tool][0]["operations"]
    if "calls" in spec
]
TEXTS = load_core_texts("pl")


def installed(tool: str) -> str:
    """The installed version of the tool, or skip the test."""
    manifest, _ = MANIFESTS[tool]
    pytest.importorskip(manifest["distribution"].replace("-", "_"))
    version = importlib.metadata.version(manifest["distribution"])
    if not version_matches(version, manifest["supported_versions"]):
        pytest.skip(f"{tool} {version} is outside {manifest['supported_versions']}")
    return version


@functools.cache
def reader_of(tool: str) -> Reader:
    """The tool's reader with its catalog read once for all tests of this module."""
    reader = load_reader(tool)
    assert reader is not None, f"retman.devtools.readers.{tool} is missing"
    return Reader(
        functools.cache(reader.read_catalog), reader.validate, reader.scratch_settings
    )


@pytest.mark.parametrize("tool", CATALOG_TOOLS)
def test_gate_environment_installs_the_tool_in_a_supported_version(tool: str) -> None:
    # The checks below skip a tool that is missing; the gate must not skip them
    manifest, _ = MANIFESTS[tool]
    try:
        version = importlib.metadata.version(manifest["distribution"])
    except importlib.metadata.PackageNotFoundError:
        pytest.fail(f"{manifest['distribution']} is missing from the environment")

    assert version_matches(version, manifest["supported_versions"])


@pytest.fixture(scope="module")
def rows() -> list[EvalCommand]:
    return load_commands(DEFAULT_COMMANDS)


def problems(report: ToolReport, *severities: str) -> list[str]:
    return [
        f"{finding.check} {finding_text(finding, TEXTS)}"
        for finding in report.findings
        if finding.severity in severities
    ]


def check(tool: str, rows: list[EvalCommand], **options: Any) -> ToolReport:
    installed(tool)
    (report,) = check_tools(
        [MANIFESTS[tool]],
        commands=rows,
        readers={tool: reader_of(tool)},
        **options,
    )
    assert report.status == "checked", problems(report, "error", "info")
    return report


@pytest.mark.parametrize(("tool", "operation"), OPERATIONS)
def test_operation_conforms_to_the_installed_tool(
    tool: str, operation: str, rows: list[EvalCommand]
) -> None:
    report = check(tool, rows, operations=[operation])

    # No drift (X1-X4, X6-X7); and the operation has complete rows with free values
    # in the eval command set, so that its grid could be built (X10)
    assert problems(report, "error") == []
    assert [f for f in report.findings if f.check == "X10"] == []
    assert report.points > 0


@pytest.mark.parametrize("tool", CATALOG_TOOLS)
def test_tool_as_a_whole_conforms_to_the_installed_tool(
    tool: str, rows: list[EvalCommand]
) -> None:
    # Operations are checked one by one above: here the checks that concern the
    # tool: lookups refused for commands with effects, error texts, schemas
    report = check(tool, rows, operations=[], tool_level=True)

    assert problems(report, "error") == []


@pytest.mark.parametrize("tool", CATALOG_TOOLS)
def test_reader_exemptions_name_codes_of_the_installed_registry(tool: str) -> None:
    installed(tool)

    catalog = reader_of(tool).read_catalog()

    assert catalog.commands and catalog.error_codes
    # An exemption of a code the tool no longer has would hide nothing and mislead
    assert set(catalog.unreachable_errors) <= set(catalog.error_codes)


def test_committed_translations_hold_no_draft_markers() -> None:
    folder = Path(retman.tools.__file__).resolve().parent

    marked = [
        path.relative_to(folder.parent)
        for path in sorted(folder.glob("*/pl.toml"))
        if "TODO" in path.read_text(encoding="utf-8")
        or "SPLIT_REQUIRED" in path.read_text(encoding="utf-8")
    ]

    # ``retman scaffold draft`` leaves TODO markers: nobody reviewed that text yet
    assert marked == []


def test_kartograf_unexposed_commands_are_the_ones_whose_run_has_effects(
    rows: list[EvalCommand],
) -> None:
    # X9 lists data commands only: a source listing, a store read, `sheet` or
    # `config show` (read-only in `command_schema`) is no unused data command
    report = check("kartograf", rows, operations=[], tool_level=True)

    (finding,) = [f for f in report.findings if f.check == "X9"]
    unexposed = finding.args["commands"].split(", ")
    assert "soil hsg" in unexposed and "cache clear" in unexposed
    assert not {
        "elevation list-sources",
        "elevation availability",
        "store overview",
        "sheet find",
        "config show",
        "commands list",
    } & set(unexposed)

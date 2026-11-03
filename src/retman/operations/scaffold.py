"""``scaffold check``, ``list`` and ``draft``: the descriptions of the tools.

The drift check compares Retman's descriptions of a tool with the installed tool; the
list and the draft read the catalog of a tool to help write a new operation
(ARCHITECTURE 3.2.3). Everything is offline: nothing is downloaded, and a draft is
written only below ``src/retman/tools/<tool>/_drafts/``, never over a file.
"""

import importlib.metadata
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict

from retman.adapters.catalog import PlanClient
from retman.catalog.envelope import Output
from retman.devtools.draft import build_draft, classify
from retman.devtools.drift import check_tools
from retman.devtools.model import Reader, ScaffoldError, load_reader
from retman.devtools.report import check_document, check_items, render_check
from retman.eval.dataset import DEFAULT_COMMANDS, EvalCommand, load_commands
from retman.exceptions import InvalidValueError
from retman.i18n.loader import Texts, machine_texts
from retman.operations.documents import check_targets, conflicts, targets_output
from retman.registry.loader import discover_manifests
from retman.registry.manifest import ManifestSpec

# Where ``draft --write`` puts its files: ``<tools>/<tool>/_drafts/`` (git-ignored)
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"

Manifests = Iterable[tuple[ManifestSpec, Path]]


class _Entry(TypedDict):
    """One data command of a tool catalog in the document of ``scaffold list``."""

    id: str
    group: str | None
    network: bool
    writes: bool
    operations: list[str]
    use: str


def _reader(tool: str, readers: Mapping[str, Reader] | None) -> Reader:
    reader = (
        readers[tool] if readers is not None and tool in readers else load_reader(tool)
    )
    if reader is None:
        raise ScaffoldError(
            f"No catalog reader exists for the tool {tool!r}",
            code="unsupported",
            details={"reason": "no_reader", "tool": tool},
            hint="Only tools with a reader in `retman.devtools.readers` can be read.",
        )
    return reader


def _unknown(option: str, value: str, allowed: Sequence[str]) -> InvalidValueError:
    return InvalidValueError(
        f"Unknown {option} {value!r}; known: {', '.join(allowed)}",
        details={
            "reason": "unknown_value",
            "option": option,
            "value": value,
            "allowed": list(allowed),
        },
        hint=f"Choose one of: {', '.join(allowed)}.",
    )


def scaffold_check(
    *,
    tool: list[str] | None = None,
    operation: list[str] | None = None,
    commands: str | None = None,
    require_tools: bool = False,
    include_info: bool = False,
    manifests: Manifests | None = None,
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    readers: Mapping[str, Reader] | None = None,
    clients: Mapping[str, PlanClient] | None = None,
    command_rows: Sequence[EvalCommand] | None = None,
) -> Output:
    """Compare the descriptions of the tools with the installed tools.

    Parameters
    ----------
    tool, operation : list of str, optional
        Check only these tools and operations.
    commands : str, optional
        JSONL file with the commands the grids are built from.
    require_tools : bool, optional
        A tool that is not installed is an error instead of a skipped tool.
    include_info : bool, optional
        Also list the findings of severity ``info`` in the terminal report.
    manifests, version_lookup, readers, clients, command_rows
        Injections of the caller for offline tests: the manifests, the installed
        versions, the catalog readers, the clients of the tools and the command set.

    Returns
    -------
    Output
        The ``retman-scaffold-check/1`` document; the units are the tools, ``failed``
        when a finding is an error.

    Raises
    ------
    InvalidValueError
        An unknown tool or operation is named.
    EvalDatasetError
        The command set is malformed.
    """
    available = list(manifests if manifests is not None else discover_manifests())
    known = sorted(manifest["tool"] for manifest, _ in available)
    for name in tool or ():
        if name not in known:
            raise _unknown("tool", name, known)
    selected = [
        spec["id"]
        for manifest, _ in available
        if not tool or manifest["tool"] in tool
        for spec in manifest["operations"]
    ]
    for name in operation or ():
        if name not in selected:
            raise _unknown("operation", name, selected)
    rows = (
        command_rows
        if command_rows is not None
        else load_commands(Path(commands) if commands else DEFAULT_COMMANDS)
    )
    reports = check_tools(
        available,
        commands=rows,
        version_lookup=version_lookup,
        readers=readers,
        clients=clients,
        tools=tool,
        operations=operation,
        require_tools=require_tools,
    )

    def view(texts: Texts) -> str:
        return render_check(reports, texts, verbose=include_info)

    document = check_document(reports, machine_texts())
    return Output(document, items=check_items(reports), view=view)


def _effects(texts: Texts, network: bool, writes: bool) -> str:
    names = [
        texts.get(f"scaffold.effect_{name}")
        for name, present in (("network", network), ("writes", writes))
        if present
    ]
    return ", ".join(names) if names else texts.get("scaffold.effect_none")


def scaffold_list(
    *,
    tool: str,
    manifests: Manifests | None = None,
    readers: Mapping[str, Reader] | None = None,
) -> Output:
    """List the data commands of the catalog of a tool and who uses them.

    Parameters
    ----------
    tool : str
        Name of the tool.
    manifests, readers
        Injections of the caller for offline tests.

    Returns
    -------
    Output
        The ``retman-scaffold-list/1`` document.

    Raises
    ------
    ScaffoldError
        No reader exists for the tool (``unsupported``).
    """
    available = list(manifests if manifests is not None else discover_manifests())
    catalog = _reader(tool, readers).read_catalog()
    users: dict[str, list[str]] = {}
    for manifest, _ in available:
        if manifest["tool"] == tool:
            for spec in manifest["operations"]:
                for command in spec.get("commands", []):
                    users.setdefault(command, []).append(spec["id"])
    entries: list[_Entry] = [
        {
            "id": info.id,
            "group": info.group or None,
            "network": info.network,
            "writes": info.writes,
            "operations": users.get(info.id, []),
            "use": classify(info),
        }
        for info in catalog.commands.values()
    ]

    def view(texts: Texts) -> str:
        rows = [
            (
                entry["id"],
                entry["group"] or "-",
                _effects(texts, entry["network"], entry["writes"]),
                ", ".join(entry["operations"]) or "-",
                texts.get(f"scaffold.use_{entry['use']}"),
            )
            for entry in entries
        ]
        header = (
            texts.get("scaffold.col_command"),
            texts.get("scaffold.col_group"),
            texts.get("scaffold.col_effects"),
            texts.get("scaffold.col_operations"),
            texts.get("scaffold.col_use"),
        )
        widths = [
            max(len(row[i]) for row in [header, *rows]) for i in range(len(header))
        ]
        lines = [
            texts.get(
                "scaffold.list_title",
                tool=catalog.tool,
                version=catalog.version,
                count=len(rows),
            )
        ]
        for row in [header, *rows]:
            cells = zip(row, widths, strict=True)
            lines.append("  ".join(cell.ljust(width) for cell, width in cells).rstrip())
        return "\n".join(lines) + "\n"

    return Output(
        {"tool": catalog.tool, "version": catalog.version, "commands": entries},
        view=view,
    )


def _value(text: str) -> object:
    """Parse ``true``, ``4`` and ``"x"`` as JSON, anything else as the text it is."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _fixed(items: Sequence[str]) -> dict[str, object]:
    fixed: dict[str, object] = {}
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name:
            raise InvalidValueError(
                f"Option 'fix' needs name=value, got {item!r}",
                details={"reason": "invalid_fix", "option": "fix", "value": item},
                hint="Write each fixed option as name=value, e.g. --fix resolution=1m.",
            )
        fixed[name] = _value(value)
    return fixed


def scaffold_draft(
    *,
    tool: str,
    command: str,
    fix: list[str] | None = None,
    only: list[str] | None = None,
    id: str | None = None,
    write: bool = False,
    check: bool = False,
    readers: Mapping[str, Reader] | None = None,
    tools_dir: Path | None = None,
) -> Output:
    """Draft an operation from one catalog command of a tool.

    Parameters
    ----------
    tool, command : str
        The tool and its catalog command.
    fix : list of str, optional
        Tool options fixed to a value, ``name=value``.
    only : list of str, optional
        Keep only these tool options in the draft.
    id : str, optional
        Identifier of the new operation; derived from the command by default.
    write : bool, optional
        Save the draft below ``<tools>/<tool>/_drafts/`` instead of printing it.
    check : bool, optional
        Plan the files ``write`` would create.
    readers, tools_dir
        Injections of the caller for offline tests.

    Returns
    -------
    Output
        The ``retman-scaffold-draft/1`` document (the draft as text), the files that
        were written, or the plan.

    Raises
    ------
    ScaffoldError
        No reader for the tool (``unsupported``) or a draft file exists
        (``conflict``): a draft is never overwritten.
    InvalidValueError
        ``fix`` is not ``name=value``.
    """
    fixed = _fixed(fix or [])
    names = (
        [name for chunk in only for name in chunk.split(",") if name] if only else None
    )
    reader = _reader(tool, readers)
    draft = build_draft(
        reader.read_catalog(),
        reader,
        command,
        fix=fixed,
        only=names,
        operation_id=id,
    )
    folder = (tools_dir or TOOLS_DIR) / tool / "_drafts"
    python = folder / f"{draft.operation_id}.py"
    toml = folder / f"{draft.operation_id}.toml"
    document = {
        "operation_id": draft.operation_id,
        "python": draft.python(),
        "translations": draft.translations,
    }
    if not write and not check:
        return Output(
            document,
            view=lambda texts: f"{draft.python()}\n\n{draft.translations}\n",
        )
    targets = check_targets([("write", python), ("write", toml)])
    if check:
        return targets_output(targets)
    if (failure := conflicts(targets)) is not None:
        raise ScaffoldError(
            "A draft file exists and is never overwritten",
            code="conflict",
            details=dict(failure.details),
            hint="Delete or rename the draft, or give another `id`.",
        )
    folder.mkdir(parents=True, exist_ok=True)
    python.write_text(draft.python() + "\n", encoding="utf-8", newline="\n")
    toml.write_text(draft.translations + "\n", encoding="utf-8", newline="\n")
    return Output(
        document,
        files=[python, toml],
        view=lambda texts: (
            texts.get("scaffold.draft_written", python=python, toml=toml) + "\n"
        ),
    )

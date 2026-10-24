"""``retman-scaffold``: drafts from a tool's catalog and the drift check.

    retman-scaffold list <tool>
    retman-scaffold draft <tool> "<command>" [--fix k=v] [--only a,b] [--id op]
        [--write]
    retman-scaffold --check [--tool T] [--operation OP] [--json] [--require-tools]

Exit codes: ``0`` clean, ``1`` errors found (or the command failed), ``2`` usage.
Drafts go to the standard output; ``--write`` creates files below
``src/retman/tools/<tool>/_drafts/`` and never touches a reviewed file
(ARCHITECTURE 3.2.3).
"""

import argparse
import contextlib
import importlib.metadata
import json
import os
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import NoReturn

from retman.adapters.catalog import PlanClient
from retman.devtools.draft import build_draft, classify
from retman.devtools.drift import check_tools
from retman.devtools.model import Reader, ScaffoldError, load_reader
from retman.devtools.report import check_json, exit_code, render_check
from retman.eval.dataset import DEFAULT_COMMANDS, EvalCommand, load_commands
from retman.exceptions import EvalDatasetError, RetmanError
from retman.i18n.loader import Texts, load_core_texts
from retman.registry.loader import discover_manifests
from retman.registry.manifest import ManifestSpec

# Where ``draft --write`` puts its files: ``<tools>/<tool>/_drafts/`` (git-ignored)
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"

Manifests = Iterable[tuple[ManifestSpec, Path]]


class _Usage(Exception):
    """A mistake in the command line (exit code 2)."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _Usage(message)


def _parser(texts: Texts) -> _Parser:
    parser = _Parser(prog="retman-scaffold", description=texts.get("scaffold.cli"))
    parser.add_argument(
        "--check", action="store_true", help=texts.get("scaffold.h_check")
    )
    parser.add_argument(
        "--tool", action="append", metavar="TOOL", help=texts.get("scaffold.h_tool")
    )
    parser.add_argument(
        "--operation",
        action="append",
        metavar="ID",
        help=texts.get("scaffold.h_operation"),
    )
    parser.add_argument(
        "--json", action="store_true", help=texts.get("scaffold.h_json")
    )
    parser.add_argument(
        "--require-tools",
        action="store_true",
        help=texts.get("scaffold.h_require_tools"),
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help=texts.get("scaffold.h_verbose")
    )
    parser.add_argument(
        "--commands", type=Path, metavar="FILE", help=texts.get("scaffold.h_commands")
    )
    sub = parser.add_subparsers(dest="action", metavar="{list,draft}")
    listing = sub.add_parser("list", help=texts.get("scaffold.h_list"))
    listing.add_argument("tool", help=texts.get("scaffold.h_tool_name"))
    draft = sub.add_parser("draft", help=texts.get("scaffold.h_draft"))
    draft.add_argument("tool", help=texts.get("scaffold.h_tool_name"))
    draft.add_argument("command", help=texts.get("scaffold.h_command"))
    draft.add_argument(
        "--fix",
        action="append",
        default=[],
        metavar="K=V",
        help=texts.get("scaffold.h_fix"),
    )
    draft.add_argument(
        "--only", action="append", metavar="A,B", help=texts.get("scaffold.h_only")
    )
    draft.add_argument("--id", metavar="ID", help=texts.get("scaffold.h_id"))
    draft.add_argument(
        "--write", action="store_true", help=texts.get("scaffold.h_write")
    )
    return parser


def _value(text: str) -> object:
    """``true``, ``4`` and ``"x"`` as JSON, anything else as the text it is."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _fixed(items: Sequence[str], texts: Texts) -> dict[str, object]:
    fixed: dict[str, object] = {}
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name:
            raise _Usage(texts.get("scaffold.invalid_fix", item=item))
        fixed[name] = _value(value)
    return fixed


def _reader(tool: str, readers: Mapping[str, Reader] | None, texts: Texts) -> Reader:
    reader = (
        readers[tool] if readers is not None and tool in readers else load_reader(tool)
    )
    if reader is None:
        raise ScaffoldError(texts.get("scaffold.no_reader", tool=tool))
    return reader


def _check(
    args: argparse.Namespace,
    texts: Texts,
    manifests: list[tuple[ManifestSpec, Path]],
    version_lookup: Callable[[str], str],
    readers: Mapping[str, Reader] | None,
    clients: Mapping[str, PlanClient] | None,
    commands: Sequence[EvalCommand] | None,
) -> int:
    known = sorted(manifest["tool"] for manifest, _ in manifests)
    for tool in args.tool or ():
        if tool not in known:
            raise _Usage(
                texts.get("scaffold.unknown_tool", tool=tool, known=", ".join(known))
            )
    selected = [
        spec["id"]
        for manifest, _ in manifests
        if not args.tool or manifest["tool"] in args.tool
        for spec in manifest["operations"]
    ]
    for operation in args.operation or ():
        if operation not in selected:
            raise _Usage(texts.get("scaffold.unknown_operation", operation=operation))
    rows = (
        commands
        if commands is not None
        else load_commands(args.commands or DEFAULT_COMMANDS)
    )
    reports = check_tools(
        manifests,
        commands=rows,
        version_lookup=version_lookup,
        readers=readers,
        clients=clients,
        tools=args.tool,
        operations=args.operation,
        require_tools=args.require_tools,
    )
    if args.json:
        print(check_json(reports, texts), end="")
    else:
        print(render_check(reports, texts, verbose=args.verbose), end="")
    return exit_code(reports)


def _effects(texts: Texts, network: bool, writes: bool) -> str:
    names = [
        texts.get(f"scaffold.effect_{name}")
        for name, present in (("network", network), ("writes", writes))
        if present
    ]
    return ", ".join(names) if names else texts.get("scaffold.effect_none")


def _list(
    tool: str,
    texts: Texts,
    manifests: list[tuple[ManifestSpec, Path]],
    readers: Mapping[str, Reader] | None,
) -> int:
    catalog = _reader(tool, readers, texts).read_catalog()
    users: dict[str, list[str]] = {}
    for manifest, _ in manifests:
        if manifest["tool"] == tool:
            for spec in manifest["operations"]:
                for command in spec.get("commands", []):
                    users.setdefault(command, []).append(spec["id"])
    rows = [
        (
            info.id,
            info.group or "-",
            _effects(texts, info.network, info.writes),
            ", ".join(users.get(info.id, [])) or "-",
            texts.get(f"scaffold.use_{classify(info)}"),
        )
        for info in catalog.commands.values()
    ]
    header = (
        texts.get("scaffold.col_command"),
        texts.get("scaffold.col_group"),
        texts.get("scaffold.col_effects"),
        texts.get("scaffold.col_operations"),
        texts.get("scaffold.col_use"),
    )
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
    print(
        texts.get(
            "scaffold.list_title",
            tool=catalog.tool,
            version=catalog.version,
            count=len(rows),
        )
    )
    for row in [header, *rows]:
        cells = zip(row, widths, strict=True)
        print("  ".join(cell.ljust(width) for cell, width in cells).rstrip())
    return 0


def _draft(
    args: argparse.Namespace,
    texts: Texts,
    readers: Mapping[str, Reader] | None,
    tools_dir: Path,
) -> int:
    fixed = _fixed(args.fix, texts)
    only = (
        [name for chunk in args.only for name in chunk.split(",") if name]
        if args.only
        else None
    )
    reader = _reader(args.tool, readers, texts)
    draft = build_draft(
        reader.read_catalog(),
        reader,
        args.command,
        fix=fixed,
        only=only,
        operation_id=args.id,
    )
    if not args.write:
        print(draft.python())
        print()
        print(draft.translations)
        return 0
    folder = tools_dir / args.tool / "_drafts"
    python = folder / f"{draft.operation_id}.py"
    toml = folder / f"{draft.operation_id}.toml"
    for path in (python, toml):
        if path.exists():
            raise ScaffoldError(texts.get("scaffold.draft_exists", path=path))
    folder.mkdir(parents=True, exist_ok=True)
    python.write_text(draft.python() + "\n", encoding="utf-8", newline="\n")
    toml.write_text(draft.translations + "\n", encoding="utf-8", newline="\n")
    print(texts.get("scaffold.draft_written", python=python, toml=toml))
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    manifests: Manifests | None = None,
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    readers: Mapping[str, Reader] | None = None,
    clients: Mapping[str, PlanClient] | None = None,
    commands: Sequence[EvalCommand] | None = None,
    tools_dir: Path | None = None,
) -> int:
    """Run ``retman-scaffold``; the keyword arguments are injections for offline tests.

    Returns
    -------
    int
        ``0`` clean, ``1`` errors found or the command failed, ``2`` usage.
    """
    texts = load_core_texts("pl")
    try:
        args = _parser(texts).parse_args(argv)
        if args.check == (args.action is not None):
            raise _Usage(
                texts.get(
                    "scaffold.usage_both" if args.check else "scaffold.usage_nothing"
                )
            )
        available = list(manifests if manifests is not None else discover_manifests())
        if args.check:
            return _check(
                args, texts, available, version_lookup, readers, clients, commands
            )
        if args.action == "list":
            return _list(args.tool, texts, available, readers)
        return _draft(args, texts, readers, tools_dir or TOOLS_DIR)
    except _Usage as error:
        print(texts.get("scaffold.usage_error", error=error), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(texts.get("scaffold.interrupted"), file=sys.stderr)
        return 3
    except BrokenPipeError:
        # The reader of the pipe left (``| head``): point stdout at the null device
        # so that the flush at exit stays quiet, and say nothing more
        with contextlib.suppress(OSError, ValueError, AttributeError):
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except EvalDatasetError as error:
        print(texts.get("scaffold.invalid_commands", error=error), file=sys.stderr)
    except (RetmanError, OSError) as error:
        print(texts.get("scaffold.failure", error=error), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

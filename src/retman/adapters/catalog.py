"""Command layer: how Retman calls tools that ship a command catalog.

Every catalog-backed operation is a pure *call builder* (``calls(params, ctx)
-> list[CatalogCall]``) run through one *client* per tool
(``src/retman/tools/<tool>/client.py``, named by the manifest key ``client``). The
client is split by capability so that the gate of PRD W-05/N-12 is structural:
before ``plan.confirm()`` only the offline ``PlanClient`` half exists for
planning code; ``RunClient`` (run, check, query) is reachable only inside
``execute()`` and, after a separate consent, ``Retman.check()``.

This module is standard library only and imports no tool.
"""

import hashlib
import importlib
import json
import re
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from retman.exceptions import RetmanError
from retman.i18n.loader import Texts
from retman.registry.manifest import (
    HandlerOutput,
    HandlerWarning,
    ParamSpec,
    ToolAudit,
    ToolAuditCall,
)
from retman.registry.operation import Operation

ToolDocument = Mapping[str, Any]
RunStatus = Literal["ok", "partial", "failed", "cancelled"]


@dataclass(frozen=True)
class CatalogCall:
    """One catalog command with its options, as the tool's own API takes them.

    ``options`` are JSON-form options exactly as ``validate_command`` and
    ``run_command`` take them (a bbox is four numbers plus a required
    ``bbox_crs``, a path is a string, a list is a list). Environment arguments
    (store directory, workers, cache, update) are never put here: the client
    adds them from ``[tools.<tool>]``.

    ``kind`` is the data kind of the files the call yields (the key of
    ``HandlerOutput.files``). ``params`` maps a tool option to the Retman
    parameter it came from where the names differ, e.g. ``{"sheet": "area",
    "horizontal_crs": "target_crs"}``; it routes a tool's rejection back to the
    parameter the user must answer again. An option inside another option is
    keyed by its path (``"options.years": "period"``, see ``ToolError``).
    """

    command: str
    options: Mapping[str, object]
    kind: str | None = None
    params: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolFile:
    """A file a command produced or found: path, checksum, version label, status."""

    path: Path
    sha256: str | None = None
    version: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class ToolFailure:
    """A unit (sheet, file, county) a command could not deliver."""

    unit: str
    kind: str
    detail: str


@dataclass(frozen=True)
class ToolNotice:
    """A message of the tool; ``text`` is the tool's own wording."""

    level: Literal["info", "warning", "error"]
    code: str
    text: str


@dataclass(frozen=True)
class ToolRun:
    """The outcome of one data command, mapped from the tool's JSON document."""

    command: str
    status: RunStatus
    files: tuple[ToolFile, ...] = ()
    failed: tuple[ToolFailure, ...] = ()
    notices: tuple[ToolNotice, ...] = ()
    document: ToolDocument = field(default_factory=dict)
    # The exact command line including environment arguments, for the audit
    command_line: str = ""
    # Document schema label, e.g. "kartograf-download/1"
    schema: str = ""


class ToolError(RetmanError):
    """A tool refused or failed; raised by clients instead of the tool's exceptions.

    ``code`` is the tool's stable error code (``invalid_input``, ``no_coverage``,
    ``io_error``…); ``option``/``options`` name the tool options at fault and
    ``allowed`` what the tool would accept there. An option inside the options a
    command takes of another command is named by its path (``options.years``), so
    that ``CatalogCall.params`` can route it like any other. ``detail`` and
    ``hint`` are the tool's own wording: the user sees Retman's text chosen by
    ``code`` (see ``tool_error_text``). ``call`` is the command that raised (set by
    the generic runners when the client did not).
    """

    def __init__(
        self,
        tool: str,
        code: str,
        detail: str,
        *,
        hint: str | None = None,
        option: str | None = None,
        options: Iterable[str] = (),
        allowed: Iterable[str] | None = None,
        details: Mapping[str, Any] | None = None,
        call: CatalogCall | None = None,
    ) -> None:
        self.tool = tool
        self.code = code
        self.detail = detail
        self.hint = hint
        self.option = option
        self.options = tuple(options)
        self.allowed = tuple(allowed) if allowed is not None else None
        self.details: Mapping[str, Any] = details or {}
        self.call = call
        super().__init__(f"{tool} [{code}]: {detail}")


class ToolDriftError(RetmanError):
    """The installed tool no longer accepts what the manifest asks of it.

    A programmer-level error (run ``retman doctor`` / ``retman-scaffold
    --check``): no Retman parameter can be named, so asking the user again
    would loop on the same rejection.
    """


class PlanClient(Protocol):
    """The offline half of a client; the only tool object before confirmation.

    No method may use the network or write anything.
    """

    def validate(self, call: CatalogCall) -> None:
        """The tool's own offline validation; raises ``ToolError``."""
        ...

    def command_line(self, call: CatalogCall) -> str:
        """The exact command line of ``call`` (offline), for the audit."""
        ...

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """An effects-free catalog command (no network, no writes).

        Raises ``ToolError("not_offline")`` for any other command.
        """
        ...


class RunClient(PlanClient, Protocol):
    """A full client; only inside ``execute()`` and ``Retman.check()``."""

    def run(self, call: CatalogCall) -> ToolRun:
        """Run a data command; writes the tool's store."""
        ...

    def check(self, call: CatalogCall) -> ToolDocument:
        """The tool's freshness plan for ``call``; a network step."""
        ...

    def query(self, call: CatalogCall) -> ToolDocument:
        """A read-only network query outside run/check/validate."""
        ...


class PlanView:
    """The offline half of a client and nothing else.

    Wraps a full client for planning code (call builders, previews, context
    aware extractors): ``run``, ``check`` and ``query`` do not exist on it, so a
    network step before confirmation is impossible by construction (N-12).
    """

    __slots__ = ("_client",)

    def __init__(self, client: PlanClient) -> None:
        self._client = client

    def validate(self, call: CatalogCall) -> None:
        """Offline validation by the tool."""
        self._client.validate(call)

    def command_line(self, call: CatalogCall) -> str:
        """Offline command line."""
        return self._client.command_line(call)

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Offline, effects-free lookup."""
        return self._client.lookup(call)


class NoClient:
    """Client of a tool that declares none: every use is a programmer error."""

    def __init__(self, tool: str) -> None:
        self._tool = tool

    def _fail(self, call: CatalogCall) -> Any:
        raise RetmanError(
            f"{self._tool} declares no command client; cannot use {call.command!r}"
        )

    def validate(self, call: CatalogCall) -> None:
        """Always fails."""
        self._fail(call)

    def command_line(self, call: CatalogCall) -> str:
        """Always fails."""
        return cast(str, self._fail(call))

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Always fails."""
        return cast(ToolDocument, self._fail(call))

    def run(self, call: CatalogCall) -> ToolRun:
        """Always fails."""
        return cast(ToolRun, self._fail(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """Always fails."""
        return cast(ToolDocument, self._fail(call))

    def query(self, call: CatalogCall) -> ToolDocument:
        """Always fails."""
        return cast(ToolDocument, self._fail(call))


@dataclass(frozen=True)
class ToolContext:
    """What a call builder, preview, check or handler may use of its surroundings.

    The same type for all of them. While planning (builders, previews) ``client``
    is an offline ``PlanClient``, ``output_dir`` is ``None`` (no result folder
    exists yet) and ``inputs`` are the already validated workspace inputs of the
    plan; inside ``execute()`` and ``Retman.check()`` ``client`` is a
    ``RunClient`` (read it as ``ctx.runner``). ``specs`` are the operation's
    manifest parameters, for ``tool_value`` and ``option_meta``. ``operation`` is
    the operation being planned or run, so that a handler can delegate to
    ``run_calls`` for the part of its work that is a plain catalog call (``None``
    in a context built without one).
    """

    tool: str
    settings: Mapping[str, Any]
    project_dir: Path
    output_dir: Path | None
    inputs: Mapping[str, Path]
    client: PlanClient
    specs: Mapping[str, ParamSpec] = field(default_factory=dict)
    operation: Operation | None = None

    @property
    def store_dir(self) -> Path:
        """The tool's store folder, ``[tools.<tool>] store_dir``."""
        try:
            return Path(self.settings["store_dir"])
        except KeyError:
            raise RetmanError(f"[tools.{self.tool}] has no store_dir") from None

    @property
    def runner(self) -> RunClient:
        """``client`` as a ``RunClient``; fails while planning (offline half only)."""
        client = self.client
        if isinstance(client, PlanView) or not hasattr(client, "run"):
            raise RetmanError("the network-capable client exists only after consent")
        return cast(RunClient, client)

    def tool_value(self, param: str, key: str) -> str:
        """The tool's own value of an option key (manifest ``tool_values``)."""
        return self.specs[param].get("tool_values", {}).get(key, key)

    def option_meta(self, param: str, key: str) -> Mapping[str, Any]:
        """The opaque per-option data of the manifest (``{}`` if none)."""
        return self.specs[param].get("option_meta", {}).get(key, {})


CallBuilder = Callable[[dict[str, Any], ToolContext], list[CatalogCall]]
Describe = Callable[
    [Operation, dict[str, Any], Sequence[tuple[CatalogCall, ToolRun]], ToolContext],
    HandlerOutput,
]


def load_reference(reference: str) -> Any:
    """Import ``"module:attribute"`` lazily; the tool is imported only when used."""
    module_name, attribute = reference.split(":", 1)
    return getattr(importlib.import_module(module_name), attribute)


def create_client(reference: str, settings: Mapping[str, Any]) -> RunClient:
    """Build a tool's client from the manifest key ``client``.

    The factory takes the validated ``[tools.<tool>]`` table and must not touch
    the network or write anything (the pipeline builds the client while
    planning, and gives planning code only its ``PlanView``).
    """
    return cast(RunClient, load_reference(reference)(settings))


def route_error(
    call: CatalogCall | None, err: ToolError, params: Collection[str]
) -> list[str]:
    """Retman parameters a rejection concerns, via ``call.params`` or same names.

    Empty when no tool option of the error maps to a parameter of the operation.
    """
    routed: list[str] = []
    for option in (*([err.option] if err.option else []), *err.options):
        name = call.params.get(option, option) if call is not None else option
        if name in params and name not in routed:
            routed.append(name)
    return routed


def tool_error_text(
    operation: Operation,
    texts: Texts,
    err: ToolError,
    *,
    fallback: str = "errors.tool_error",
) -> str:
    """Retman's own text for a tool error, chosen by its stable ``code``.

    The tool's ``pl.toml`` ``[errors.<code>]`` wins; otherwise the core text
    ``fallback``. Placeholders: ``{tool}``, ``{code}``, ``{detail}``, ``{hint}``,
    ``{option}``, ``{option_label}`` (the labels of the parameters the options
    route to) and ``{allowed}``. The tool's wording appears only as ``{detail}``.
    """
    names = route_error(
        err.call, err, [param["name"] for param in operation.spec["params"]]
    )
    args = {
        "tool": err.tool,
        "code": err.code,
        "detail": err.detail,
        "hint": err.hint or "",
        "option": err.option or "",
        "option_label": ", ".join(
            operation.text(f"params.{name}.label") for name in names
        ),
        "allowed": ", ".join(err.allowed or ()),
    }
    key = f"errors.{err.code}"
    if operation.texts.has(key):
        return operation.texts.get(key, **args)
    return texts.get(fallback, **args)


# Above this many warning notices of one code, a run shows the first
# NOTICES_SHOWN of them and one line counting the rest (the tool's saved
# document keeps every notice).
NOTICES_GROUPED_ABOVE = 5
NOTICES_SHOWN = 3


def notice_warnings(
    operation: Operation, tool: str, notices: Iterable[ToolNotice]
) -> list[HandlerWarning]:
    """Warnings for the tool's notices; nothing is dropped except info notices.

    A notice code with a ``[warnings.<code>]`` text in the tool's ``pl.toml`` is
    shown with that text; every other warning/error notice is shown verbatim
    behind the core ``tool_notice`` text. Info notices stay in the audit document.
    A code repeated more than ``NOTICES_GROUPED_ABOVE`` times in one run shows its
    first ``NOTICES_SHOWN`` notices and a ``tool_notices_more`` line with the
    count of the rest, which stay in the tool's document saved with the result.
    """
    shown = [notice for notice in notices if notice.level != "info"]
    counts = Counter(notice.code for notice in shown)
    seen: Counter[str] = Counter()
    warnings: list[HandlerWarning] = []
    for notice in shown:
        seen[notice.code] += 1
        grouped = counts[notice.code] > NOTICES_GROUPED_ABOVE
        if grouped and seen[notice.code] > NOTICES_SHOWN:
            if seen[notice.code] == NOTICES_SHOWN + 1:
                warnings.append(
                    {
                        "key": "tool_notices_more",
                        "args": {
                            "tool": tool,
                            "code": notice.code,
                            "count": str(counts[notice.code] - NOTICES_SHOWN),
                        },
                    }
                )
            continue
        key = (
            notice.code
            if operation.texts.has(f"warnings.{notice.code}")
            else "tool_notice"
        )
        warnings.append(
            {
                "key": key,
                "args": {"tool": tool, "code": notice.code, "text": notice.text},
            }
        )
    return warnings


def failure_warnings(failures: Iterable[ToolFailure]) -> list[HandlerWarning]:
    """Warnings for units a partial run could not deliver (tool wording as detail)."""
    return [
        {
            "key": "tool_failure",
            "args": {"unit": item.unit, "kind": item.kind, "detail": item.detail},
        }
        for item in failures
    ]


def default_describe(
    operation: Operation,
    params: dict[str, Any],
    runs: Sequence[tuple[CatalogCall, ToolRun]],
    ctx: ToolContext,
) -> HandlerOutput:
    """The generic mapping of runs to a result: files by ``call.kind``, warnings.

    A tool's ``describe`` function usually starts from this and adds ``values``.
    """
    files: dict[str, list[Path]] = {}
    warnings: list[HandlerWarning] = []
    for call, run in runs:
        if call.kind is not None:
            files.setdefault(call.kind, []).extend(item.path for item in run.files)
        warnings.extend(notice_warnings(operation, ctx.tool, run.notices))
        warnings.extend(failure_warnings(run.failed))
    return {
        "values": {
            "calls": len(runs),
            "file_count": sum(len(paths) for paths in files.values()),
        },
        "files": files,
        "warnings": warnings,
    }


def _document_name(index: int, command: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", command.lower()).strip("_")
    return f"tool_{index}_{slug}.json"


def _save_document(output_dir: Path, index: int, run: ToolRun) -> tuple[str, str]:
    """Write the tool's whole document into the result folder; name and SHA-256."""
    data = (
        json.dumps(run.document, ensure_ascii=False, indent=2, default=str) + "\n"
    ).encode("utf-8")
    name = _document_name(index, run.command)
    (output_dir / name).write_bytes(data)
    return name, hashlib.sha256(data).hexdigest()


def _audit_call(
    call: CatalogCall, run: ToolRun, document_file: str, sha256: str
) -> ToolAuditCall:
    return {
        "command": call.command,
        "options": dict(call.options),
        "command_line": run.command_line,
        "schema": run.schema,
        "status": run.status,
        "files": [
            {
                "path": str(item.path),
                "sha256": item.sha256,
                "version": item.version,
                "status": item.status,
            }
            for item in run.files
        ],
        "document_file": document_file,
        "sha256": sha256,
    }


def run_calls(
    operation: Operation,
    params: dict[str, Any],
    inputs: Mapping[str, Path],
    output_dir: Path,
    ctx: ToolContext,
) -> HandlerOutput:
    """Run the operation's catalog calls through the client (after confirmation).

    The calls are the builder's, the same as validated at plan time. The runner
    stops at the first ``failed``/``cancelled`` run and raises ``ToolError``; a
    ``partial`` run continues with warnings. Each call's whole JSON document is
    saved as ``output_dir/tool_<n>_<command>.json`` and referenced, with its
    SHA-256, from the ``tool`` audit block of the returned ``HandlerOutput``.
    The operation's ``describe`` function (or ``default_describe``) maps the runs
    to files, values and warnings.
    """
    builder: CallBuilder = load_reference(operation.spec["calls"])
    client = ctx.runner
    runs: list[tuple[CatalogCall, ToolRun]] = []
    saved: list[tuple[str, str]] = []
    for index, call in enumerate(builder(params, ctx), 1):
        try:
            run = client.run(call)
        except ToolError as err:
            if err.call is None:
                err.call = call
            raise
        runs.append((call, run))
        saved.append(_save_document(output_dir, index, run))
        if run.status in ("failed", "cancelled"):
            first = run.failed[0] if run.failed else None
            raise ToolError(
                ctx.tool,
                "cancelled"
                if run.status == "cancelled"
                else (first.kind if first else "failed"),
                first.detail if first else run.status,
                call=call,
            )
    describe: Describe = (
        load_reference(operation.spec["describe"])
        if "describe" in operation.spec
        else default_describe
    )
    output = describe(operation, params, runs, ctx)
    audit: ToolAudit = {
        "tool": ctx.tool,
        "version": operation.version,
        "calls": [
            _audit_call(call, run, name, digest)
            for (call, run), (name, digest) in zip(runs, saved, strict=True)
        ],
    }
    output["tool"] = audit
    return output

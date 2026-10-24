"""Generic adapter from a validated manifest to a tool's handlers, previews, checks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retman.adapters.catalog import (
    CallBuilder,
    ToolContext,
    ToolDriftError,
    ToolError,
    load_reference,
    route_error,
    run_calls,
    tool_error_text,
)
from retman.core.check import CheckReport, CheckStatus
from retman.core.journal import utc_now
from retman.core.result import Result
from retman.exceptions import ManifestError, error_document
from retman.i18n.loader import Texts
from retman.kinds import validate_file
from retman.registry.manifest import (
    CheckOutput,
    HandlerWarning,
    PreviewOutput,
    PreviewProblem,
)
from retman.registry.operation import Operation

_CHECK_STATUSES = ("available", "partial", "unavailable", "unknown")


@dataclass(frozen=True)
class ResolvedProblem:
    """A problem of the plan: the parameters to ask again and the text shown."""

    params: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Preview:
    """What the offline preview found out, with translated texts.

    ``values`` are audit-only, ``rows`` are ``(label, value)`` plan rows and
    ``problems`` name parameters the user must answer again.
    """

    values: dict[str, Any]
    rows: list[tuple[str, str]]
    problems: list[ResolvedProblem]


def _warning_text(operation: Operation, texts: Texts, warning: HandlerWarning) -> str:
    """Return the tool's own text of a warning, else the core's (``tool_notice``)."""
    key = f"warnings.{warning['key']}"
    source = operation.texts if operation.texts.has(key) else texts
    return source.get(key, **warning["args"])


def _summary(
    operation: Operation,
    texts: Texts,
    number: int,
    output_dir: Path,
    values: dict[str, Any],
    in_store: bool,
    ctx: ToolContext,
) -> str:
    """Build the result line: the operation's own template, else a core text."""
    label = operation.text("label")
    key = f"operations.{operation.id}.summary"
    if operation.texts.has(key):
        try:
            return operation.texts.get(
                key,
                **{
                    **values,
                    "number": number,
                    "operation": label,
                    "directory": str(output_dir),
                },
            )
        except (KeyError, IndexError, ValueError):
            # A template that does not fit the values must not turn a success
            # into a failure; the generic line below is always correct
            pass
    if in_store:
        return texts.get(
            "results.success_store",
            number=number,
            operation=label,
            store=str(ctx.settings.get("store_dir", "")),
            directory=str(output_dir),
        )
    return texts.get(
        "results.success", number=number, operation=label, directory=str(output_dir)
    )


def execute_operation(
    operation: Operation,
    params: dict[str, Any],
    inputs: dict[str, Path],
    output_dir: Path,
    number: int,
    params_audit: dict[str, dict[str, Any]],
    inputs_audit: dict[str, dict[str, Any]],
    texts: Texts,
    ctx: ToolContext,
) -> Result:
    """Run the handler (or the catalog calls), check its files, build a result.

    ``ctx`` carries the network-capable client; it exists only here. A file is
    accepted inside ``output_dir`` or inside the tool's own store
    (``[tools.<tool>] store_dir``); a tool error becomes the result's error text.
    """
    result = Result(True, number, operation.id, params_audit, inputs_audit)
    try:
        if "handler" in operation.spec:
            handler = load_reference(operation.spec["handler"])
            data = handler(params, inputs, output_dir, ctx)
        else:
            data = run_calls(operation, params, inputs, output_dir, ctx)
        roots = [output_dir.resolve()]
        if "store_dir" in ctx.settings:
            roots.append(ctx.store_dir.resolve())
        in_store = False
        for kind, paths in data["files"].items():
            if kind not in operation.spec["outputs"]:
                raise ValueError(f"undeclared output kind {kind}")
            for path in paths:
                checked = Path(path).resolve()
                if not any(checked.is_relative_to(root) for root in roots):
                    raise ValueError(f"output outside result directory: {checked}")
                in_store = in_store or not checked.is_relative_to(roots[0])
                validate_file(kind, checked)
                result.files.setdefault(kind, []).append(checked)
        result.outputs = list(result.files)
        result.values = data["values"]
        result.warnings = [
            _warning_text(operation, texts, warning) for warning in data["warnings"]
        ]
        result.tool = data.get("tool")
        result.summary = _summary(
            operation, texts, number, output_dir, result.values, in_store, ctx
        )
    except ToolError as err:
        _fail(result, texts, number, tool_error_text(operation, texts, err))
        result.error_code = err.tool_code
        result.failure = error_document(err)
    except Exception as err:
        _fail(result, texts, number, str(err))
        result.failure = error_document(err)
    return result


def _fail(result: Result, texts: Texts, number: int, error: str) -> None:
    result.ok = False
    result.outputs = []
    result.values = {}
    result.files = {}
    result.error = error
    result.summary = texts.get("results.failure", number=number, error=error)


def _problem_text(operation: Operation, texts: Texts, problem: PreviewProblem) -> str:
    key = f"problems.{problem['key']}"
    source = operation.texts if operation.texts.has(key) else texts
    return source.get(key, **problem["args"])


def preview_operation(
    operation: Operation,
    params: dict[str, Any],
    ctx: ToolContext,
    texts: Texts,
) -> Preview:
    """Offline plan-time review: the tool validates every call, then ``preview``.

    ``ctx.client`` must be the offline half of the client. A tool rejection is
    routed to the Retman parameters it names (``CatalogCall.params``, the error's
    ``option``/``options``) and becomes a problem with Retman's own text; when
    the preview function reports problems of its own they are added. The
    operation's ``preview`` function runs only when the tool accepted every call.

    Raises
    ------
    ToolDriftError
        A rejection names no parameter of the operation: the installed tool no
        longer accepts what the manifest asks, and no answer of the user helps.
    ManifestError
        A preview problem names an unknown parameter.
    """
    names = [param["name"] for param in operation.spec["params"]]
    problems: list[ResolvedProblem] = []
    if "calls" in operation.spec:
        builder: CallBuilder = load_reference(operation.spec["calls"])
        for call in builder(params, ctx):
            try:
                ctx.client.validate(call)
            except ToolError as err:
                if err.call is None:
                    err.call = call
                routed = route_error(call, err, names)
                if not routed:
                    raise ToolDriftError(
                        operation.tool,
                        operation.id,
                        err.detail,
                        texts.get(
                            "errors.tool_drift",
                            tool=operation.tool,
                            operation=operation.id,
                            detail=err.detail,
                        ),
                    ) from err
                problems.append(
                    ResolvedProblem(
                        tuple(routed),
                        tool_error_text(
                            operation, texts, err, fallback="dialog.tool_rejected"
                        ),
                    )
                )
    if problems or "preview" not in operation.spec:
        return Preview({}, [], problems)
    output: PreviewOutput = load_reference(operation.spec["preview"])(params, ctx)
    for problem in output["problems"]:
        if any(name not in names for name in problem["params"]):
            raise ManifestError(
                f"{operation.id}: preview problem {problem['key']} names "
                f"{problem['params']}, which are not parameters of the operation"
            )
        problems.append(
            ResolvedProblem(
                tuple(problem["params"]), _problem_text(operation, texts, problem)
            )
        )
    rows = [
        (
            operation.texts.get(f"preview.{row['key']}.label", **row["args"]),
            operation.texts.get(f"preview.{row['key']}.value", **row["args"]),
        )
        for row in output["rows"]
    ]
    return Preview(dict(output["values"]), rows, problems)


def _report(
    operation: Operation,
    texts: Texts,
    status: CheckStatus,
    items: list[Any],
    lines: list[str],
    error: str | None,
) -> CheckReport:
    checked_at = utc_now()
    header = texts.get(
        "check.header",
        tool=operation.tool,
        version=operation.version,
        time=checked_at[:16].replace("T", " "),
        status=texts.get(f"check.status_{status}"),
    )
    return CheckReport(
        operation.id,
        operation.tool,
        operation.version,
        checked_at,
        status,
        header,
        items,
        lines,
        error,
    )


def failed_check(operation: Operation, texts: Texts, error: str) -> CheckReport:
    """Report a check that could not run or complete: status ``unknown``."""
    return _report(
        operation,
        texts,
        "unknown",
        [],
        [texts.get("check.failed", error=error)],
        error,
    )


def run_check(
    operation: Operation,
    params: dict[str, Any],
    ctx: ToolContext,
    texts: Texts,
) -> CheckReport:
    """Run the operation's ``check`` (a network step, after its own consent).

    A failing check is a report with status ``unknown`` and the reason in
    ``error``, never an exception (``KeyboardInterrupt`` still propagates).
    """
    try:
        output: CheckOutput = load_reference(operation.spec["check"])(params, ctx)
        if output["status"] not in _CHECK_STATUSES:
            raise ValueError(f"unknown check status {output['status']!r}")
        items = list(output["items"])
        lines = [
            operation.texts.get(f"check.{item['key']}", **item["args"])
            for item in items
        ]
        return _report(operation, texts, output["status"], items, lines, None)
    except ToolError as err:
        return failed_check(operation, texts, tool_error_text(operation, texts, err))
    except Exception as err:
        return failed_check(operation, texts, str(err))

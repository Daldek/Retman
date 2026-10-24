"""``eval run``: how well the model chooses operations and values on the command set."""

import json
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

from retman.backends.base import DecisionBackend
from retman.catalog.envelope import Item, Output
from retman.config import load_config
from retman.environment import OptionValue
from retman.eval.dataset import DEFAULT_COMMANDS, load_commands, validate_commands
from retman.eval.metrics import (
    EvalRecord,
    EvaluationSummary,
    Measures,
    Ratio,
    Recommendation,
    Timing,
)
from retman.eval.report import render_report
from retman.eval.runner import filter_commands, run_evaluation
from retman.exceptions import InvalidValueError
from retman.i18n.loader import Texts, load_core_texts
from retman.operations.documents import check_targets, conflicts, targets_output
from retman.registry.operation import Operation

_RATIOS = (
    "operation",
    "operation_in_scope",
    "operation_out_of_scope",
    "parameter",
    "parameter_correct_automatic",
    "parameter_wrong_automatic",
    "parameter_asked",
    "automatic_coverage",
    "accepted_operation",
    "accepted_model_parameters",
    "accepted_extractors",
    "accepted_all",
    "silent_guesses",
    "clarification",
    "unnecessary_questions",
    "w03",
    "stability",
)


def _ratio(ratio: Ratio) -> dict[str, Any]:
    return {"count": ratio.count, "total": ratio.total, "fraction": ratio.fraction}


def _timing(timing: Timing) -> dict[str, float]:
    return {"median": timing.median, "p90": timing.p90, "maximum": timing.maximum}


def _measures(measures: Measures) -> dict[str, Any]:
    names = {field.name for field in fields(measures)}
    document: dict[str, Any] = {}
    for name in _RATIOS:
        assert name in names
        value = getattr(measures, name)
        document[name] = None if value is None else _ratio(value)
    for name in ("plan_seconds", "model_queries"):
        value = getattr(measures, name)
        document[name] = None if value is None else _timing(value)
    return document


def _recommendation(recommendation: Recommendation) -> dict[str, Any]:
    point = recommendation.point
    return {
        "threshold": None if point is None else point.threshold,
        "error": None if point is None else _ratio(point.error),
        "coverage": None if point is None else _ratio(point.coverage),
        "insufficient": recommendation.insufficient,
        "minimum_sample": recommendation.minimum_sample,
    }


def summary_document(
    summary: EvaluationSummary, *, repeat: int, target_error: float | None
) -> dict[str, Any]:
    """Return the document ``retman-eval/1`` (without its ``schema``).

    The raw record of every run is the ``output`` file; the document keeps the
    measures of the whole set, the recommended thresholds and the W-03 violations.
    """
    return {
        "commands": summary.commands,
        "runs": summary.runs,
        "repeat": repeat,
        "target_error": target_error,
        "overall": _measures(summary.overall),
        "recommendations": (
            None
            if summary.recommendations is None
            else {
                category: _recommendation(item)
                for category, item in summary.recommendations.items()
            }
        ),
        "violations": [
            {
                "id": case.id,
                "repeat": case.repeat,
                "command": case.command,
                "expected": case.expected,
                "actual": case.actual,
            }
            for case in summary.overall.violations
        ],
    }


def w03_items(records: list[EvalRecord], summary: EvaluationSummary) -> list[Item]:
    """Return the units of the result: the commands that had to be refused (W-03).

    A command is ``ok`` when Retman refused it or asked, and ``failed`` (code
    ``unsupported``, reason ``planned_out_of_scope``) when it planned an operation
    for it without asking.
    """
    violated = {case.id for case in summary.overall.violations}
    ids = dict.fromkeys(
        record["id"]
        for record in records
        if record["expected"]["operation"] == "out_of_scope"
    )
    return [
        Item(ident, "failed", "unsupported", "planned_out_of_scope")
        if ident in violated
        else Item(ident, "ok")
        for ident in ids
    ]


def eval_run(
    *,
    config: str | None = None,
    commands: str | None = None,
    operations: list[str] | None = None,
    tags: list[str] | None = None,
    repeat: int = 1,
    target_error: float | None = None,
    output: str | None = None,
    report: str | None = None,
    check: bool = False,
    force: bool = False,
    backend: DecisionBackend | None = None,
    operation_registry: dict[str, Operation] | None = None,
    overrides: Mapping[str, OptionValue] | None = None,
) -> Output:
    """Evaluate a command set without executing any operation.

    Parameters
    ----------
    config : str, optional
        The settings file; the model server must be set in it.
    commands : str, optional
        JSONL file with the commands; the set shipped with Retman by default.
    operations, tags : list of str, optional
        Keep the commands that expect one of these operations or carry one of these
        tags.
    repeat : int, optional
        Plan every command this many times.
    target_error : float, optional
        Accepted share of wrong decisions taken without asking, in (0, 1]; adds the
        recommended thresholds.
    output, report : str, optional
        Files for the raw records (JSON lines) and for the Markdown report.
    check : bool, optional
        Validate the call and plan the write of ``output`` and ``report`` only.
    force : bool, optional
        Replace ``output`` and ``report`` if they exist.
    backend, operation_registry, overrides
        Injections of the caller for offline tests: the decision backend, the
        operations instead of the discovered ones, and the settings that
        command-line options give.

    Returns
    -------
    Output
        The ``retman-eval/1`` document; the units are the commands that had to be
        refused (W-03), so ``partial`` means some were planned.

    Raises
    ------
    ConfigError
        The settings or the model server settings cannot be used.
    EvalDatasetError
        The command set is malformed or names unknown operations.
    InvalidValueError
        The filters selected no command.
    RetmanError
        An output file exists and ``force`` is not given (``conflict``).
    BackendError
        The model server failed: no partial report or record is written.
    """
    settings = load_config(Path(config) if config else None, options=overrides)
    texts = load_core_texts(settings.language)
    rows = load_commands(Path(commands) if commands else DEFAULT_COMMANDS)
    validate_commands(rows)
    rows = filter_commands(rows, operations, tags)
    if not rows:
        raise InvalidValueError(
            "The filters selected no command",
            details={"reason": "empty_selection", "option": "operations"},
            hint="Name operations and tags that the command set has.",
        )
    targets = check_targets([("output", output), ("report", report)], force=force)
    if check:
        return targets_output(targets)
    if (failure := conflicts(targets)) is not None:
        raise failure
    existing = [target["path"] for target in targets if target["action"] == "replace"]
    records, summary = run_evaluation(
        rows,
        settings,
        backend=backend,
        operations=operation_registry,
        repeat=repeat,
        target_error=target_error,
    )
    text = render_report(summary, records, texts, target_error=target_error)
    if output is not None:
        raw = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records)
        Path(output).write_text(raw, encoding="utf-8", newline="\n")
    if report is not None:
        Path(report).write_text(text, encoding="utf-8", newline="\n")

    def view(texts: Texts) -> str:
        if report is None:
            return text
        return texts.get("eval.report_written", path=report) + "\n"

    return Output(
        summary_document(summary, repeat=repeat, target_error=target_error),
        items=w03_items(records, summary),
        files=[path for path in (output, report) if path is not None],
        replaced=existing,
        view=view,
    )

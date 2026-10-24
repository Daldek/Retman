"""Domain documents built from the objects of the core, and the plan of file writes.

The documents are the ``result`` of the commands (``retman-<kind>/1``, schemas in
``src/retman/schemas/``); the envelope adds their ``schema``. Texts that the user's
language shapes (labels, questions, the summary of a result) come from the
translation files, as in the dialog.
"""

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from retman._json import to_jsonable
from retman.catalog.envelope import Notice, Output
from retman.core.dialog import Question
from retman.core.plan import Plan, PlanValue
from retman.core.result import Result
from retman.exceptions import RetmanError
from retman.i18n.loader import Texts

TARGETS_SCHEMA = "retman-targets/1"
"""Document of the plan of a ``check`` run that writes files."""


def _entry(plan: Plan, name: str, item: PlanValue) -> dict[str, Any]:
    return {
        "label": plan.labels.get(name, name),
        "value": to_jsonable(item.value),
        "display": plan.display.get(name, str(item.value)),
        "source": item.source,
        "confidence": item.confidence,
        "unverified": item.unverified,
    }


def _question(question: Question) -> dict[str, Any]:
    document: dict[str, Any] = {
        "name": question.name,
        "type": question.type,
        "text": question.text,
        "options": [
            {"key": option.key, "label": option.label} for option in question.options
        ],
    }
    for key in ("default", "example", "error"):
        value = getattr(question, key)
        if value is not None:
            document[key] = to_jsonable(value)
    return document


def decision_documents(plan: Plan) -> list[dict[str, Any]]:
    """Return the model decisions of a plan: choice, confidence, method, odds."""
    return [
        {
            "name": decision["name"],
            "key": decision["key"],
            "confidence": decision["confidence"],
            "method": decision["confidence_method"],
            "probabilities": to_jsonable(decision["probabilities"]),
        }
        for decision in plan.decisions
    ]


def plan_document(
    plan: Plan, *, result: Result | None = None, explain: bool = False
) -> dict[str, Any]:
    """Return the document ``retman-plan/1`` (without its ``schema``).

    Parameters
    ----------
    plan : Plan
        The plan as it stands: complete or with open questions.
    result : Result, optional
        The result of running the confirmed plan; it is the ``run`` of the document.
    explain : bool, optional
        Add the model decisions as ``decisions``.

    Returns
    -------
    dict
        The text of the command, the operation, ``values`` and ``inputs`` with their
        source and confidence, the ``unset`` optional parameters, the offline
        ``preview``, the open ``questions`` and ``complete`` (no question is open).
    """
    document: dict[str, Any] = {
        "text": plan.command,
        "operation": plan.operation,
        "operation_label": plan.operation_label or None,
        "operation_confidence": plan.operation_confidence,
        "operation_unverified": plan.operation_unverified,
        "complete": plan.operation is not None and not plan.questions,
        "confirmed": plan.confirmed,
        "values": {
            name: _entry(plan, name, item) for name, item in plan.values.items()
        },
        "inputs": {
            name: _entry(plan, name, item) for name, item in plan.inputs.items()
        },
        "unset": [
            {"name": name, "label": label, "meaning": meaning}
            for name, (label, meaning) in plan.unset.items()
        ],
        "preview": [
            {"label": label, "value": value} for label, value in plan.preview_rows
        ],
        "questions": [_question(question) for question in plan.questions],
    }
    if explain:
        document["decisions"] = decision_documents(plan)
    if result is not None:
        document["run"] = to_jsonable(result.to_dict())
    return document


def explain_lines(plan: Plan, texts: Texts) -> list[str]:
    """Return the lines that explain the model decisions of a plan (``--explain``)."""
    lines = []
    for decision in plan.decisions:
        confidence = decision["confidence"]
        ranked = sorted(
            decision["probabilities"].items(), key=lambda item: item[1], reverse=True
        )
        lines.append(
            texts.get(
                "cli.explain",
                name=decision["name"],
                choice=decision["key"],
                confidence="—" if confidence is None else f"{confidence:.2f}",
                method=decision["confidence_method"],
                probabilities=", ".join(f"{key} {value:.2f}" for key, value in ranked),
            )
        )
    return lines


def result_lines(result: Result, texts: Texts) -> list[str]:
    """Return the summary of a result and its warnings, as the dialog shows them."""
    return [
        result.summary,
        *(texts.get("cli.warning", text=warning) for warning in result.warnings),
    ]


# --- the plan of the commands that write files ------------------------------------


def target_action(path: Path, *, force: bool) -> str:
    """Return what writing ``path`` would do: ``write``, ``replace`` or ``conflict``."""
    if not path.exists():
        return "write"
    return "replace" if force else "conflict"


def check_targets(
    targets: Iterable[tuple[str, Path | str | None]], *, force: bool = False
) -> list[dict[str, str]]:
    """Plan the writes of the options that name a file or a folder.

    Parameters
    ----------
    targets : iterable of tuple
        ``(option, path)`` pairs; a ``None`` path is an option that was not given and
        is left out.
    force : bool, optional
        An existing file is replaced (``replace``) instead of a ``conflict``.

    Returns
    -------
    list of dict
        ``{"option", "path", "action"}`` per target, the path absolute.
    """
    return [
        {
            "option": option,
            "path": str(Path(os.path.abspath(path))),
            "action": target_action(Path(os.path.abspath(path)), force=force),
        }
        for option, path in targets
        if path is not None
    ]


def targets_output(
    targets: Sequence[Mapping[str, str]], *, notices: Sequence[Notice] = ()
) -> Output:
    """Return the plan of a ``check`` run that writes files (``retman-targets/1``).

    A plan that lists a ``conflict`` is a successful result: only the real run fails.
    """

    def view(texts: Texts) -> str:
        lines = [texts.get("targets.title")]
        for target in targets:
            lines.append(
                texts.get(
                    "targets.line",
                    action=texts.get(f"targets.action_{target['action']}"),
                    path=target["path"],
                )
            )
        return "\n".join(lines) + "\n"

    return Output(
        {"targets": [dict(target) for target in targets]},
        notices=notices,
        check=True,
        schema=TARGETS_SCHEMA,
        view=view,
    )


def conflicts(targets: Sequence[Mapping[str, str]]) -> RetmanError | None:
    """Return the error of a real run that meets existing files, or ``None``.

    Every offending path is in ``details.paths`` (DEV-19.6).
    """
    paths = [target["path"] for target in targets if target["action"] == "conflict"]
    if not paths:
        return None
    return RetmanError(
        "Existing files would be overwritten: " + ", ".join(paths),
        code="conflict",
        details={"reason": "output_exists", "paths": paths},
        hint="Give other paths, or `force` (CLI: --force) to replace them.",
    )


def sequence_view(lines: Callable[[Texts], list[str]]) -> Callable[[Texts], str]:
    """Return a view that joins the lines of ``lines`` and ends with a newline."""

    def view(texts: Texts) -> str:
        return "\n".join(lines(texts)) + "\n"

    return view

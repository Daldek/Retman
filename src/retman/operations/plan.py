"""``plan run``: recognise, plan and, once confirmed, run a Polish command.

This is the conversation of Retman without a terminal: one call recognises the
operation, fills in what the command states and returns the plan; with ``yes`` it also
confirms and runs the complete plan. Nothing is asked: an open question is an
``input_required`` error that lists the questions (AGI-3.5). The dialog of a terminal
(:mod:`retman.cli.conversation`) is the same pipeline with prompts in between.
"""

from collections.abc import Mapping
from pathlib import Path

from retman.backends.base import DecisionBackend
from retman.catalog.envelope import Notice, Output
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.core.result import Result
from retman.environment import OptionValue
from retman.exceptions import InputRequiredError, RetmanError
from retman.i18n.loader import Texts
from retman.operations.documents import (
    explain_lines,
    plan_document,
    result_lines,
)


def input_required(plan: Plan) -> InputRequiredError:
    """Build the error of a plan that needs input and cannot ask for it.

    Without a terminal nobody can answer (AGI-3.5), so the call ends with
    ``validation_error``, reason ``input_required``: ``details.questions`` lists the
    open questions, and the hint names the option that gives the missing
    confirmation (``--yes``) or shows the plan without running it (``--check``).
    """
    if plan.questions:
        return InputRequiredError(
            "The plan has open questions and nobody can answer them",
            details={
                "option": "text",
                "questions": [
                    {
                        "name": question.name,
                        "type": question.type,
                        "text": question.text,
                        "options": [option.key for option in question.options],
                    }
                    for question in plan.questions
                ],
            },
            hint="Put the missing values in the command text and repeat, or run "
            "`retman plan run` in a terminal; `--check` shows the plan.",
        )
    return InputRequiredError(
        "The plan is complete and needs a confirmation",
        details={"option": "yes"},
        hint="Give `--yes` (option `yes`) to confirm and run it, or `--check` to "
        "show the plan without running it.",
    )


def failure(result: Result) -> RetmanError:
    """Return the error of a run that failed, from the document the pipeline made.

    The failed result is saved in the project like any other; the call ends with the
    registry code and the hint of the failure (ERR-4).
    """
    document = result.failure
    if document is None:
        return RetmanError(result.error or "The operation failed")
    return RetmanError(
        document["message"],
        code=document["code"],
        details=document.get("details"),
        hint=document.get("hint"),
    )


def plan_run(
    *,
    text: str | None = None,
    check: bool = False,
    yes: bool = False,
    explain: bool = False,
    config: str | None = None,
    backend: DecisionBackend | None = None,
    project_dir: Path | None = None,
    overrides: Mapping[str, OptionValue] | None = None,
) -> Output:
    """Plan a Polish command and, with ``yes``, run it.

    Parameters
    ----------
    text : str, optional
        The command. Without it there is nothing to plan: ``input_required``.
    check : bool, optional
        Stop at the plan; open questions are part of it and no error.
    yes : bool, optional
        Confirm the complete plan and run it.
    explain : bool, optional
        Add the model decisions to the document.
    config : str, optional
        The settings file.
    backend, project_dir, overrides
        Injections of the caller: the decision backend, the project folder (the
        current one by default) and the settings that command-line options give.

    Returns
    -------
    Output
        The ``retman-plan/1`` document; with ``yes`` its ``run`` holds the result.

    Raises
    ------
    InputRequiredError
        No ``text``, an open question or a confirmation that nobody gives.
    RetmanError
        Whatever ended the recognition or the run, with its registry code.
    """
    if text is None:
        raise InputRequiredError(
            "A plan needs the command text and there is no terminal to ask for it",
            details={"option": "text"},
            hint="Give the command: `retman plan run --text '<command>'`.",
        )
    retman = Retman.from_config(
        Path(config) if config else None,
        backend=backend,
        project_dir=project_dir,
        options=overrides,
    )
    plan = retman.plan(text)
    if check:
        return _check_output(plan, explain)
    if plan.questions or plan.operation is None or not yes:
        raise input_required(plan)
    plan.confirm()
    result = retman.execute(plan)
    if not result.ok:
        raise failure(result)
    return Output(
        plan_document(plan, result=result, explain=explain),
        notices=[
            Notice("warning", "operation_warning", warning)
            for warning in result.warnings
        ],
        view=lambda texts: _view(plan, texts, explain=explain, result=result),
    )


def _check_output(plan: Plan, explain: bool) -> Output:
    notices = []
    if plan.questions:
        notices.append(
            Notice(
                "info",
                "questions_open",
                "The plan is incomplete: put the answers to the open questions "
                "into the command text and plan again.",
            )
        )
    return Output(
        plan_document(plan, explain=explain),
        notices=notices,
        check=True,
        view=lambda texts: _view(plan, texts, explain=explain),
    )


def _view(
    plan: Plan, texts: Texts, *, explain: bool, result: Result | None = None
) -> str:
    lines = [plan.summary()]
    if explain:
        lines += explain_lines(plan, texts)
    if result is not None:
        lines += result_lines(result, texts)
    return "\n".join(lines) + "\n"

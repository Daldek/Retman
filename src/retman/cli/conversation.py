"""The conversation in a terminal: questions, plan, confirmation, result.

This is ``plan run`` with a person at the keyboard (AGI-3.5 allows prompts only when
stdin is a terminal and the call is not ``--json``): the same pipeline as
:func:`retman.operations.plan_run`, with prompts in between. The user can ask for
help (``?``), change a value, have the availability checked (a separate step with its
own consent, ARCHITECTURE 6.5), decline, cancel or confirm; the words that mean
these are the ``[answers]`` of the translation file of the language.
"""

from retman.core.dialog import Question
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.exceptions import error_document
from retman.i18n.loader import Texts
from retman.operations.documents import explain_lines, result_lines
from retman.operations.plan import failure
from retman.outcomes import EXIT_CANCELLED, EXIT_OK, write_document


def _said(answer: str, key: str, texts: Texts) -> bool:
    """Whether ``answer`` is one of the words of ``[answers] <key>``, in lower case."""
    return answer.lower() in texts.lines(f"answers.{key}")


def _prompt(question: Question, texts: Texts) -> str:
    print(texts.get("cli.question", text=question.text))
    for index, option in enumerate(question.options, 1):
        print(texts.get("cli.option", number=index, label=option.label))
    if question.example:
        print(texts.get("cli.example", value=question.example))
    if question.default is not None:
        print(texts.get("cli.default", value=question.default))
    if question.error:
        print(texts.get("cli.error", error=question.error))
    return input(texts.get("cli.answer_prompt"))


def _answer_questions(retman: Retman, plan: Plan, texts: Texts) -> Plan | None:
    """Ask the open questions in turn; ``None`` when the user cancelled."""
    while plan.questions:
        question = plan.questions[0]
        answer = _prompt(question, texts)
        if _said(answer.strip(), "cancel", texts):
            retman.record_plan(plan, "cancelled")
            print(texts.get("cli.cancelled"))
            return None
        if answer.strip() == "?":
            print(question.help or texts.get("cli.help"))
            continue
        plan = plan.answer(question.name, answer.strip())
    return plan


def _execute(retman: Retman, plan: Plan, texts: Texts, command: str) -> int:
    """Confirm and run a complete plan; print the result and the warnings."""
    plan.confirm()
    result = retman.execute(plan)
    print("\n".join(result_lines(result, texts)))
    if result.ok:
        return EXIT_OK
    return write_document(error_document(failure(result), command))


def conversation(
    retman: Retman, text: str, texts: Texts, *, check: bool, yes: bool, explain: bool
) -> int:
    """Plan one command with the user and, if they confirm, run it.

    Parameters
    ----------
    retman : Retman
        The pipeline.
    text : str
        The command of the user.
    texts : Texts
        Core texts of the dialog.
    check : bool
        Stop at the plan (``--check``): nothing is confirmed or run.
    yes : bool
        Confirm a complete plan without asking (``--yes``).
    explain : bool
        Show the decisions of the model under the plan.

    Returns
    -------
    int
        ``0``, ``130`` when the user declined or cancelled, or the exit code of the
        error document of a failed run.
    """
    answered = _answer_questions(retman, retman.plan(text), texts)
    if answered is None:
        return EXIT_CANCELLED
    plan = answered
    print(plan.summary())
    if explain:
        print("\n".join(explain_lines(plan, texts)))
    if check:
        return EXIT_OK
    if yes:
        return _execute(retman, plan, texts, "plan run")
    while True:
        answer = input(
            texts.get(
                "cli.confirmation_check" if plan.can_check else "cli.confirmation"
            )
            + "\n"
            + texts.get("cli.answer_prompt")
        )
        if answer == "?":
            print(texts.get("cli.help"))
        elif _said(answer, "cancel", texts):
            retman.record_plan(plan, "cancelled")
            print(texts.get("cli.cancelled"))
            return EXIT_CANCELLED
        elif _said(answer, "no", texts):
            retman.record_plan(plan, "rejected")
            print(texts.get("cli.rejected"))
            return EXIT_CANCELLED
        elif _said(answer, "check", texts) and plan.can_check:
            # A separate step with its own notice and consent: the only network
            # use before the plan is confirmed (ARCHITECTURE 6.5)
            print(plan.check_notice())
            consent = input(
                texts.get("cli.check_confirmation")
                + "\n"
                + texts.get("cli.answer_prompt")
            )
            if not _said(consent.strip(), "yes", texts):
                retman.record_check(plan, "rejected")
                print(texts.get("cli.check_declined"))
                continue
            plan.confirm_check()
            print(texts.get("cli.checking"))
            print(retman.check(plan).summary())
        elif _said(answer, "change", texts):
            changed = _change(retman, plan, texts)
            if changed is None:
                return EXIT_CANCELLED
            plan = changed
        elif _said(answer, "yes", texts):
            return _execute(retman, plan, texts, "plan run")
        else:
            print(texts.get("cli.error", error=texts.get("dialog.invalid_choice")))


def _change(retman: Retman, plan: Plan, texts: Texts) -> Plan | None:
    """Let the user reopen one value; return the new plan, ``None`` on cancel.

    An invalid choice leaves the plan as it is.
    """
    names = [*plan.values, *plan.inputs, *plan.unset]
    print(texts.get("cli.change"))
    for index, name in enumerate(names, 1):
        label, shown = plan.unset.get(
            name, (plan.labels.get(name, name), plan.display.get(name, ""))
        )
        print(texts.get("cli.option", number=index, label=f"{label}: {shown}"))
    choice = input(texts.get("cli.answer_prompt")).strip()
    if not choice.isdecimal() or not 1 <= int(choice) <= len(names):
        print(texts.get("cli.error", error=texts.get("dialog.invalid_choice")))
        return plan
    try:
        reopened = plan.change(names[int(choice) - 1])
    except ValueError as err:
        print(texts.get("cli.error", error=err))
        return plan
    answered = _answer_questions(retman, reopened, texts)
    if answered is None:
        return None
    print(answered.summary())
    return answered

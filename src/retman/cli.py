"""Standard-library command-line conversation over the public Retman API."""

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn

from retman.backends.base import DecisionBackend
from retman.config import load_settings
from retman.config_show import get_config, render_config
from retman.core.dialog import Question
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.core.result import Result
from retman.core.workspace import Workspace
from retman.doctor import run_doctor
from retman.environment import environment
from retman.exceptions import (
    BackendConnectionError,
    ConfigError,
    InputRequiredError,
    RetmanError,
    Terminated,
    UsageError,
    error_document,
)
from retman.i18n.loader import Texts, load_core_texts, text_language
from retman.initialize import run_init
from retman.logs import configure_logging, resolve_level
from retman.outcomes import (
    EXIT_CANCELLED,
    EXIT_OK,
    report_error,
    sigterm_as_exception,
    write_document,
)

logger = logging.getLogger(__name__)


class _Parser(argparse.ArgumentParser):
    """An argument parser whose mistakes are errors of the registry (AGI-3.3)."""

    def error(self, message: str) -> NoReturn:
        raise UsageError(message, hint="Run `retman --help` for the options.")


def _config_text(texts: Texts, error: ConfigError) -> str:
    """Return the text for the user: one line per problem of the settings."""
    return "\n".join(
        texts.get(
            f"config.{problem}",
            path=error.path,
            keys=error.problem_details.get(problem, ""),
            error=error.problem_details.get("error", ""),
            backend=error.problem_details.get("backend", "basal"),
        )
        for problem in error.problems
    )


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


def _explain(plan: Plan, texts: Texts) -> None:
    for decision in plan.decisions:
        confidence = decision["confidence"]
        ranked = sorted(
            decision["probabilities"].items(), key=lambda item: item[1], reverse=True
        )
        print(
            texts.get(
                "cli.explain",
                name=decision["name"],
                choice=decision["key"],
                confidence="—" if confidence is None else f"{confidence:.2f}",
                method=decision["confidence_method"],
                probabilities=", ".join(f"{key} {value:.2f}" for key, value in ranked),
            )
        )


def _input_required(plan: Plan) -> InputRequiredError:
    """Build the error of a plan that needs input without a terminal.

    No prompt is possible when stdin is not a terminal (AGI-3.5), so the call ends
    with ``validation_error`` and the reason ``input_required``.
    """
    if plan.questions:
        return InputRequiredError(
            "The plan has open questions and stdin is not a terminal",
            details={
                "questions": [
                    {
                        "name": question.name,
                        "type": question.type,
                        "text": question.text,
                        "options": [option.key for option in question.options],
                    }
                    for question in plan.questions
                ]
            },
            hint="Put the missing values in the command text, or run it in a terminal.",
        )
    return InputRequiredError(
        "The plan needs a confirmation and stdin is not a terminal",
        hint="Run the command in a terminal; --plan-only shows the plan and stops.",
    )


def _failed(result: Result) -> int:
    """Write the error document of a failed operation; return its exit code."""
    document = result.failure or error_document(
        RetmanError(result.error or "The operation failed")
    )
    return write_document(document)


def _conversation(
    retman: Retman, command: str, texts: Texts, *, plan_only: bool, explain: bool
) -> int:
    plan = retman.plan(command)
    while plan.questions:
        if not sys.stdin.isatty():
            print(plan.summary())
            raise _input_required(plan)
        question = plan.questions[0]
        answer = _prompt(question, texts)
        if answer.strip().lower() == "anuluj":
            retman.record_plan(plan, "cancelled")
            print(texts.get("cli.cancelled"))
            return EXIT_CANCELLED
        if answer.strip() == "?":
            print(question.help or texts.get("cli.help"))
            continue
        plan = plan.answer(question.name, answer.strip())
    print(plan.summary())
    if explain:
        _explain(plan, texts)
    if plan_only:
        return EXIT_OK
    if not sys.stdin.isatty():
        raise _input_required(plan)
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
        elif answer.lower() in ("anuluj",):
            retman.record_plan(plan, "cancelled")
            print(texts.get("cli.cancelled"))
            return EXIT_CANCELLED
        elif answer.lower() == "n":
            retman.record_plan(plan, "rejected")
            print(texts.get("cli.rejected"))
            return EXIT_CANCELLED
        elif answer.lower() == "s" and plan.can_check:
            # A separate step with its own notice and consent: the only network
            # use before the plan is confirmed (ARCHITECTURE 6.5)
            print(plan.check_notice())
            consent = input(
                texts.get("cli.check_confirmation")
                + "\n"
                + texts.get("cli.answer_prompt")
            )
            if consent.strip().lower() != "t":
                retman.record_check(plan, "rejected")
                print(texts.get("cli.check_declined"))
                continue
            plan.confirm_check()
            print(texts.get("cli.checking"))
            print(retman.check(plan).summary())
        elif answer.lower() == "z":
            names = [*plan.values, *plan.inputs, *plan.unset]
            print(texts.get("cli.change"))
            for index, name in enumerate(names, 1):
                label, shown = plan.unset.get(
                    name, (plan.labels.get(name, name), plan.display.get(name, ""))
                )
                print(
                    texts.get(
                        "cli.option",
                        number=index,
                        label=f"{label}: {shown}",
                    )
                )
            choice = input(texts.get("cli.answer_prompt")).strip()
            if not choice.isdecimal() or not 1 <= int(choice) <= len(names):
                print(texts.get("cli.error", error=texts.get("dialog.invalid_choice")))
                continue
            try:
                plan = plan.change(names[int(choice) - 1])
            except ValueError as err:
                print(texts.get("cli.error", error=err))
                continue
            while plan.questions:
                question = plan.questions[0]
                answer = _prompt(question, texts)
                if answer.strip().lower() == "anuluj":
                    retman.record_plan(plan, "cancelled")
                    print(texts.get("cli.cancelled"))
                    return EXIT_CANCELLED
                if answer.strip() == "?":
                    print(question.help or texts.get("cli.help"))
                    continue
                plan = plan.answer(question.name, answer.strip())
            print(plan.summary())
        elif answer.lower() == "t":
            plan.confirm()
            result = retman.execute(plan)
            print(result.summary)
            for warning in result.warnings:
                print(texts.get("cli.warning", text=warning))
            return EXIT_OK if result.ok else _failed(result)
        else:
            print(texts.get("cli.error", error=texts.get("dialog.invalid_choice")))


def _config(args: argparse.Namespace, texts: Texts) -> int:
    """``retman config show``: the settings in force and where each comes from."""
    if args.subcommand != "show":
        raise UsageError(
            "`retman config` needs the subcommand show",
            details={"option": "subcommand", "value": args.subcommand},
            hint="Run `retman config show`.",
        )
    report = get_config(args.config)
    print(report.to_json() if args.json else render_config(report, texts), end="")
    return EXIT_OK


def _parser() -> _Parser:
    parser = _Parser(prog="retman")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("command", nargs="?")
    parser.add_argument("subcommand", nargs="?")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    backend: DecisionBackend | None = None,
    project_dir: Path | None = None,
) -> int:
    """Run one command, a session, initialization or project history listing.

    Returns
    -------
    int
        The exit code: ``0``, ``130`` when the user cancelled or declined the
        plan, or the code of the error that ended the call (``ERR`` of the Nogat
        registry; the last line of stderr is then the ``retman-error/1`` document).
    """
    texts = load_core_texts("pl")
    with sigterm_as_exception():
        try:
            args = _parser().parse_args(argv)
            env = environment(args.config)
            configure_logging(
                resolve_level(
                    verbose=args.verbose,
                    quiet=args.quiet,
                    configured=env.setting("log_level").value,
                )
            )
            texts = load_core_texts(text_language(env.setting("lang").value))
            if args.subcommand is not None and args.command != "config":
                raise UsageError(
                    f"Unexpected argument {args.subcommand!r}",
                    details={"option": "subcommand", "value": args.subcommand},
                    hint="Quote the command text: retman '<command>'.",
                )
            if args.command == "init":
                return run_init(args.config, texts)
            if args.command == "config":
                return _config(args, texts)
            if args.command == "doctor":
                report, report_texts = run_doctor(
                    args.config,
                    project_dir if project_dir is not None else Path.cwd(),
                    backend=backend,
                    deep=args.deep,
                )
                print(
                    report.to_json() if args.json else report.to_text(report_texts),
                    end="",
                )
                return report.exit_code
            config = load_settings(args.config)
            texts = load_core_texts(config.language)
            folder = project_dir if project_dir is not None else Path.cwd()
            if args.command in ("results", "log"):
                workspace = Workspace(folder, config.results_dir)
                if args.command == "results":
                    results = workspace.list_results()
                    if not results:
                        print(texts.get("cli.no_results"))
                    for item in results:
                        print(
                            texts.get(
                                "cli.results_line",
                                summary=item["summary"],
                            )
                        )
                else:
                    from retman.core.journal import Journal

                    events = Journal(
                        workspace.root, "", config.journal_commands
                    ).entries()
                    if not events:
                        print(texts.get("cli.no_events"))
                    for event in events:
                        detail = event.get(
                            "command",
                            event.get(
                                "question",
                                event.get(
                                    "answer",
                                    event.get("status", event.get("number", "")),
                                ),
                            ),
                        )
                        if event["event"] == "plan" and detail:
                            detail = texts.get(f"journal.{detail}")
                        elif event["event"] == "check":
                            detail = texts.get(f"journal.check_{event['status']}")
                        print(
                            texts.get(
                                "cli.log_line",
                                time=event["time"],
                                event=texts.get(f"journal.{event['event']}"),
                                detail=detail,
                            )
                        )
                return EXIT_OK
            retman = Retman.from_config(
                args.config, backend=backend, project_dir=folder
            )
            if args.command is not None:
                return _conversation(
                    retman,
                    args.command,
                    texts,
                    plan_only=args.plan_only,
                    explain=args.explain,
                )
            if not sys.stdin.isatty():
                raise InputRequiredError(
                    "A session needs a terminal and stdin is not one",
                    hint="Give the command as an argument: retman '<command>'.",
                )
            while True:
                try:
                    command = input(texts.get("cli.command_prompt")).strip()
                except EOFError:
                    return EXIT_OK
                if command == "koniec":
                    return EXIT_OK
                if command == "anuluj":
                    print(texts.get("cli.cancelled"))
                    return EXIT_CANCELLED
                if command:
                    outcome = _conversation(
                        retman,
                        command,
                        texts,
                        plan_only=args.plan_only,
                        explain=args.explain,
                    )
                    if outcome == EXIT_CANCELLED:
                        return EXIT_CANCELLED
        except (KeyboardInterrupt, EOFError):
            print(texts.get("cli.cancelled"))
            return EXIT_CANCELLED
        except Terminated as err:
            return report_error(err)
        except BackendConnectionError as err:
            text = texts.get("errors.backend_connection", url=err.url)
            return report_error(err, text=text)
        except ConfigError as err:
            return report_error(err, text=_config_text(texts, err))
        except RetmanError as err:
            return report_error(
                err, text=texts.get("errors.retman", error=err.text or err)
            )
        except Exception as err:  # a defect: the document says so, debug has the trace
            logger.debug("Unexpected error", exc_info=True)
            text = texts.get("errors.unexpected", error=f"{type(err).__name__}: {err}")
            return report_error(err, text=text)


if __name__ == "__main__":
    sys.exit(main())

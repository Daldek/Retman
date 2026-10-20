"""Standard-library command-line conversation over the public Retman API."""

import argparse
import sys
from pathlib import Path

from retman.backends.base import DecisionBackend
from retman.config import load_config
from retman.core.dialog import Question
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.core.workspace import Workspace
from retman.doctor import run_doctor
from retman.exceptions import BackendConnectionError, ConfigError, RetmanError
from retman.i18n.loader import Texts, load_core_texts
from retman.initialize import run_init


def _config_error(texts: Texts, error: ConfigError) -> None:
    for problem in error.problems:
        print(
            texts.get(
                f"config.{problem}",
                path=error.path,
                keys=error.details.get(problem, ""),
                error=error.details.get("error", ""),
                backend=error.details.get("backend", "basal"),
            ),
            file=sys.stderr,
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


def _conversation(
    retman: Retman, command: str, texts: Texts, *, plan_only: bool, explain: bool
) -> int:
    plan = retman.plan(command)
    while plan.questions:
        if not sys.stdin.isatty():
            print(plan.summary())
            return 2
        question = plan.questions[0]
        answer = _prompt(question, texts)
        if answer.strip().lower() == "anuluj":
            retman.record_plan(plan, "cancelled")
            print(texts.get("cli.cancelled"))
            return 3
        if answer.strip() == "?":
            print(question.help or texts.get("cli.help"))
            continue
        plan = plan.answer(question.name, answer.strip())
    print(plan.summary())
    if explain:
        _explain(plan, texts)
    if plan_only:
        return 0
    if not sys.stdin.isatty():
        return 2
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
            return 3
        elif answer.lower() == "n":
            retman.record_plan(plan, "rejected")
            print(texts.get("cli.rejected"))
            return 3
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
                    return 3
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
            return 0 if result.ok else 1
        else:
            print(texts.get("cli.error", error=texts.get("dialog.invalid_choice")))


def main(
    argv: list[str] | None = None,
    *,
    backend: DecisionBackend | None = None,
    project_dir: Path | None = None,
) -> int:
    """Run one command, a session, initialization or project history listing."""
    parser = argparse.ArgumentParser(prog="retman")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("command", nargs="?")
    args = parser.parse_args(argv)
    texts = load_core_texts("pl")
    try:
        if args.command == "init":
            return run_init(args.config, texts)
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
        config = load_config(args.config)
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

                events = Journal(workspace.root, "", config.journal_commands).entries()
                if not events:
                    print(texts.get("cli.no_events"))
                for event in events:
                    detail = event.get(
                        "command",
                        event.get(
                            "question",
                            event.get(
                                "answer", event.get("status", event.get("number", ""))
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
            return 0
        retman = Retman.from_config(args.config, backend=backend, project_dir=folder)
        if args.command is not None:
            return _conversation(
                retman,
                args.command,
                texts,
                plan_only=args.plan_only,
                explain=args.explain,
            )
        if not sys.stdin.isatty():
            return 2
        while True:
            try:
                command = input(texts.get("cli.command_prompt")).strip()
            except EOFError:
                return 0
            if command == "koniec":
                return 0
            if command == "anuluj":
                print(texts.get("cli.cancelled"))
                return 3
            if command:
                outcome = _conversation(
                    retman,
                    command,
                    texts,
                    plan_only=args.plan_only,
                    explain=args.explain,
                )
                if outcome == 3:
                    return 3
    except BackendConnectionError as err:
        print(texts.get("errors.backend_connection", url=err.url), file=sys.stderr)
    except ConfigError as err:
        _config_error(texts, err)
    except (KeyboardInterrupt, EOFError):
        print(texts.get("cli.cancelled"))
        return 3
    except RetmanError as err:
        print(texts.get("errors.retman", error=err), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

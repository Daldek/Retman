"""Isolated plan-only evaluation and the retman-eval command-line entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, NoReturn

from retman import __version__
from retman.backends import build_decision_backend
from retman.backends.base import Decision, DecisionBackend
from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.config import Config, load_config
from retman.core.pipeline import Retman
from retman.eval.dataset import (
    DEFAULT_COMMANDS,
    EvalCommand,
    load_commands,
    validate_commands,
)
from retman.eval.metrics import EvalRecord, EvaluationSummary, summarize
from retman.eval.offline import offline_clients
from retman.eval.placeholders import create_geometry_files
from retman.eval.report import render_report
from retman.exceptions import (
    BackendError,
    ConfigError,
    EvalDatasetError,
    OutOfScopeError,
    RetmanError,
)
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.operation import Operation


class CountingBackend:
    """Count backend queries, including repeated consistency-model requests."""

    def __init__(self, backend: DecisionBackend, config: Config) -> None:
        self.backend = backend
        self.config = config
        self.queries = 0
        self.first_decision: Decision | None = None

    @property
    def url(self) -> str:
        """Address of the server of the wrapped backend."""
        return self.backend.url

    @property
    def model(self) -> str:
        """Name of the model of the wrapped backend."""
        return self.backend.model

    def _count(self, result: Decision) -> None:
        if (
            isinstance(self.backend, OpenAICompatibleBackend)
            and result.confidence_method == "consistency"
        ):
            self.queries += self.config.decision.consistency_runs or 1
        else:
            self.queries += 1

    def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        """Delegate the choice to the backend and count the query."""
        result = self.backend.choose(state, question, options)
        self._count(result)
        if self.first_decision is None:
            self.first_decision = result
        return result

    def yes_no(self, state: str, question: str) -> Decision:
        """Delegate the yes/no question to the backend and count the query."""
        result = self.backend.yes_no(state, question)
        self._count(result)
        return result


def _environment(config: Config, operations: dict[str, Operation]) -> dict[str, Any]:
    return {
        "retman": __version__,
        "tools": {op.tool: op.version for op in operations.values()},
        "backend": config.decision.backend,
        "model": config.decision.model,
        "confidence": config.decision.confidence or "basal",
        "thresholds": {
            "operation": config.decision.thresholds.operation,
            "parameter": config.decision.thresholds.parameter,
        },
    }


def _decision(name: str, decision: Decision) -> dict[str, Any]:
    return {
        "name": name,
        "key": decision.key,
        "confidence": decision.confidence,
        "method": decision.confidence_method,
        "probabilities": decision.probabilities,
    }


def _portable_value(value: Any, project: Path) -> Any:
    """Keep dataset-relative free values without leaking temporary project paths.

    A geometry area is recorded as the command said it: the file, not the layer
    Retman read from the placeholder file.
    """
    if isinstance(value, dict):
        portable = {key: _portable_value(item, project) for key, item in value.items()}
        if portable.get("type") == "geometry":
            portable.pop("layer", None)
        return portable
    if isinstance(value, list):
        return [_portable_value(item, project) for item in value]
    if isinstance(value, str) and value.startswith(str(project) + "/"):
        return str(Path(value).relative_to(project))
    return value


def _applicable_parameters(
    command: EvalCommand, operation: Operation
) -> tuple[list[str], list[str]]:
    expected_values = dict(command.params)
    applicable: list[str] = []
    defaults: list[str] = []
    for spec in operation.spec["params"]:
        if not all(
            expected_values.get(parent) in options
            for parent, options in spec.get("depends_on", {}).items()
        ):
            continue
        name = spec["name"]
        applicable.append(name)
        if (
            "default" in spec
            and name not in expected_values
            and name not in command.expect_clarify
        ):
            defaults.append(name)
            expected_values[name] = spec["default"]
    return applicable, defaults


def evaluate_command(
    command: EvalCommand,
    repeat: int,
    config: Config,
    backend: DecisionBackend,
    operations: dict[str, Operation],
    *,
    temporary_dir: Path | None = None,
) -> EvalRecord:
    """Plan once in a clean project. Never confirm or execute the plan."""
    counting = CountingBackend(backend, config)
    with TemporaryDirectory(dir=temporary_dir) as folder:
        project = Path(folder)
        # A command naming a geometry file needs one: the project is empty
        create_geometry_files(command.command, project)
        # Evaluation commands are not the user's work: never collect them (ADR-010)
        retman = Retman(
            replace(config, collect_commands=False),
            counting,
            project,
            operations=operations,
            clients=offline_clients(operations, config),
        )
        start = monotonic()
        category_question: dict[str, Any] = {"asked": False, "offered": []}
        initial_question: dict[str, Any] = {"asked": False, "offered": []}
        operation_offered: bool | None = None
        plan = None
        outcome = "plan"
        refused: OutOfScopeError | None = None
        try:
            plan = retman.plan(command.command)
            question = next((q for q in plan.questions if q.name == "category"), None)
            if question is not None:
                offered = [option.key for option in question.options]
                category_question = {"asked": True, "offered": offered}
                expected_category = (
                    operations[command.operation].category
                    if command.operation in operations
                    else None
                )
                if expected_category in offered:
                    position = offered.index(expected_category) + 1
                    plan = plan.answer("category", str(position))
                else:
                    operation_offered = False
            question = next((q for q in plan.questions if q.name == "operation"), None)
            if question is not None:
                offered = [option.key for option in question.options]
                initial_question = {"asked": True, "offered": offered}
                operation_offered = command.operation in offered
                if operation_offered:
                    position = offered.index(command.operation) + 1
                    plan = plan.answer("operation", str(position))
        except OutOfScopeError as error:
            outcome = "out_of_scope"
            refused = error
            plan = None
        except BackendError:
            raise  # No partial report or raw output on a broken backend.
        except RetmanError:
            outcome = "error"
        elapsed = monotonic() - start
        if refused is not None:
            # The decision that refused the command is the record's operation
            # decision, whether it came with the category or the operation question
            decisions = [
                {
                    **item,
                    "name": "operation"
                    if index == len(refused.decisions) - 1
                    else item["name"],
                }
                for index, item in enumerate(refused.decisions)
            ]
        elif plan is not None:
            decisions = [
                {
                    "name": item["name"],
                    "key": item["key"],
                    "confidence": item["confidence"],
                    "method": item["confidence_method"],
                    "probabilities": item["probabilities"],
                }
                for item in plan.decisions
            ]
        elif counting.first_decision is not None:
            decisions = [_decision("operation", counting.first_decision)]
        else:
            decisions = []
        questions = [q for q in plan.questions if q.name != "operation"] if plan else []
        # Keep an unresolved operation question visible to both coverage and errors.
        if plan is not None and plan.operation is None:
            questions = list(plan.questions)
        applicable, defaults = (
            _applicable_parameters(command, operations[command.operation])
            if command.operation in operations
            else ([], [])
        )
        return {
            "id": command.id,
            "repeat": repeat,
            "command": command.command,
            "tags": command.tags,
            "expected": {
                "operation": command.operation,
                "params": command.params,
                "expect_clarify": command.expect_clarify,
            },
            "outcome": outcome,
            "operation": plan.operation if plan is not None else None,
            "category_question": category_question,
            "operation_question": initial_question,
            "operation_offered": operation_offered,
            "decisions": decisions,
            "values": {
                name: {
                    "value": _portable_value(item.value, project),
                    "source": item.source,
                }
                for name, item in (plan.values.items() if plan else ())
            },
            "questions": [question.name for question in questions],
            "question_details": [
                {"name": question.name, "type": question.type} for question in questions
            ],
            "default_parameters": defaults,
            "applicable_parameters": applicable,
            "plan_s": elapsed,
            "model_queries": counting.queries,
            "environment": _environment(config, operations),
        }


def run_evaluation(
    commands: Sequence[EvalCommand],
    config: Config,
    *,
    backend: DecisionBackend | None = None,
    operations: dict[str, Operation] | None = None,
    repeat: int = 1,
    target_error: float | None = None,
    temporary_dir: Path | None = None,
) -> tuple[list[EvalRecord], EvaluationSummary]:
    """Evaluate already validated commands; injections permit offline tests."""
    if repeat < 1 or target_error is not None and not 0 < target_error <= 1:
        raise ValueError("repeat must be positive and target_error in (0, 1]")
    selected_operations = (
        operations
        if operations is not None
        else load_operations(config.language, config.enabled_tools)
    )
    missing = sorted(
        {command.operation for command in commands}
        - {*selected_operations, "out_of_scope"}
    )
    if missing or not selected_operations:
        raise ValueError(", ".join(missing) if missing else "no available operations")
    texts = load_core_texts(config.language)
    decision_backend = (
        backend if backend is not None else build_decision_backend(config, texts)
    )
    try:
        records = [
            evaluate_command(
                command,
                index,
                config,
                decision_backend,
                selected_operations,
                temporary_dir=temporary_dir,
            )
            for command in commands
            for index in range(repeat)
        ]
        return records, summarize(records, repeat=repeat, target_error=target_error)
    finally:
        # The caller owns injected backends; release only the one built here.
        if backend is None and callable(
            close := getattr(decision_backend, "close", None)
        ):
            close()


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError(message)


def _filter_commands(
    commands: list[EvalCommand], operations: str | None, tags: str | None
) -> list[EvalCommand]:
    requested_ops = set(operations.split(",")) if operations is not None else None
    requested_tags = set(tags.split(",")) if tags is not None else None
    if requested_ops is not None:
        requested_ops = {item.strip() for item in requested_ops}
    if requested_tags is not None:
        requested_tags = {item.strip() for item in requested_tags}
    if "" in (requested_ops or set()) | (requested_tags or set()):
        raise ValueError("empty selection")
    return [
        command
        for command in commands
        if (requested_ops is None or command.operation in requested_ops)
        and (requested_tags is None or requested_tags.intersection(command.tags))
    ]


def main(
    argv: list[str] | None = None,
    *,
    backend: DecisionBackend | None = None,
    operations: dict[str, Operation] | None = None,
) -> int:
    """Evaluate a dataset without executing any operation; return spec exit codes."""
    texts = load_core_texts("pl")
    parser = _Parser(prog="retman-eval", description=texts.get("eval.cli_description"))
    parser.add_argument(
        "--config", required=True, type=Path, help=texts.get("eval.help_config")
    )
    parser.add_argument("--commands", type=Path, help=texts.get("eval.help_commands"))
    parser.add_argument("--operations", help=texts.get("eval.help_operations"))
    parser.add_argument("--tags", help=texts.get("eval.help_tags"))
    parser.add_argument(
        "--repeat", type=int, default=1, help=texts.get("eval.help_repeat")
    )
    parser.add_argument(
        "--target-error", type=float, help=texts.get("eval.help_target")
    )
    parser.add_argument("--output", type=Path, help=texts.get("eval.help_output"))
    parser.add_argument("--report", type=Path, help=texts.get("eval.help_report"))
    try:
        args = parser.parse_args(argv)
        if (
            args.repeat < 1
            or args.target_error is not None
            and not 0 < args.target_error <= 1
        ):
            raise ValueError(texts.get("eval.invalid_arguments"))
        config = load_config(args.config)
        texts = load_core_texts(config.language)
        commands = load_commands(args.commands or DEFAULT_COMMANDS)
        validate_commands(commands)
        commands = _filter_commands(commands, args.operations, args.tags)
        if not commands:
            raise ValueError(texts.get("eval.empty_selection"))
        records, summary = run_evaluation(
            commands,
            config,
            backend=backend,
            operations=operations,
            repeat=args.repeat,
            target_error=args.target_error,
        )
        report = render_report(summary, records, texts, target_error=args.target_error)
        raw = "".join(
            json.dumps(record, ensure_ascii=False) + "\n" for record in records
        )
        if args.output:
            args.output.write_text(raw, encoding="utf-8", newline="\n")
        if args.report:
            args.report.write_text(report, encoding="utf-8", newline="\n")
        else:
            print(report, end="")
        return 4 if summary.overall.w03.count else 0
    except (KeyboardInterrupt, EOFError):
        print(texts.get("eval.interrupted"), file=sys.stderr)
        return 3
    except ConfigError as err:
        for problem in err.problems:
            print(
                texts.get(
                    f"config.{problem}",
                    path=err.path,
                    keys=err.details.get(problem, ""),
                    error=err.details.get("error", ""),
                    backend=err.details.get("backend", ""),
                ),
                file=sys.stderr,
            )
    except (EvalDatasetError, ValueError) as err:
        print(texts.get("eval.invalid_dataset", error=err), file=sys.stderr)
    except BackendError:
        print(texts.get("eval.backend_error"), file=sys.stderr)
    except (RetmanError, OSError) as err:
        print(texts.get("eval.failure", error=err), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

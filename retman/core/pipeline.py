"""Six-step pipeline: recognize, extract, ask, confirm, execute, audit."""

import platform
import sys
import uuid
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import Any

from retman import __version__
from retman.adapters import execute_operation
from retman.backends import build_decision_backend
from retman.backends.base import Decision, DecisionBackend
from retman.config import Config, load_config
from retman.core.dialog import Option, Question
from retman.core.journal import Journal, sha256_file, utc_now
from retman.core.plan import Plan, PlanValue, Source
from retman.core.result import Result
from retman.core.workspace import Workspace, WorkspaceFile
from retman.exceptions import (
    InvalidModelAnswerError,
    KindValidationError,
    OutOfScopeError,
    PlanIncompleteError,
    PlanNotConfirmedError,
    RetmanError,
)
from retman.extractors import EXTRACTORS, VALIDATORS
from retman.extractors.base import Match, Reading
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.manifest import ParamSpec
from retman.registry.operation import Operation


class Retman:
    """Plan and execute tool operations in a project-local workspace."""

    def __init__(
        self,
        config: Config,
        backend: DecisionBackend,
        project_dir: Path,
        *,
        operations: dict[str, Operation] | None = None,
    ) -> None:
        self.config = config
        self.backend = backend
        self.texts = load_core_texts(config.language)
        self.operations = (
            operations
            if operations is not None
            else load_operations(config.language, config.enabled_tools)
        )
        self.workspace = Workspace(project_dir, config.results_dir)
        self.journal = Journal(
            self.workspace.root, str(uuid.uuid4()), config.journal_commands
        )

    @classmethod
    def from_config(
        cls,
        path: Path | None = None,
        *,
        backend: DecisionBackend | None = None,
        project_dir: Path | None = None,
    ) -> "Retman":
        """Load the central config; permit an injected offline decision backend."""
        config = load_config(path)
        texts = load_core_texts(config.language)
        return cls(
            config,
            backend if backend is not None else build_decision_backend(config, texts),
            project_dir if project_dir is not None else Path.cwd(),
        )

    def _choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        decision = self.backend.choose(state, question, options)
        if decision.key not in options:
            raise InvalidModelAnswerError(self.backend.url, decision.key)
        return decision

    @staticmethod
    def _audit_decision(name: str, question: str, decision: Decision) -> dict[str, Any]:
        return {
            "name": name,
            "question": question,
            "key": decision.key,
            "probabilities": decision.probabilities,
            "confidence": decision.confidence,
            "confidence_method": decision.confidence_method,
            "model": decision.model,
        }

    def _uncertain(self, decision: Decision, category: str) -> bool:
        threshold = getattr(self.config.decision.thresholds, category)
        return (
            decision.confidence is not None
            and isinstance(threshold, float)
            and decision.confidence < threshold
        )

    def plan(self, command: str, known: dict[str, Any] | None = None) -> Plan:
        """Choose an operation and fill what code or model can determine safely."""
        if not self.operations:
            raise RetmanError(self.texts.get("dialog.no_operations"))
        self.journal.append("command", command=command)
        options = {
            key: operation.text("description")
            for key, operation in self.operations.items()
        }
        options["out_of_scope"] = self.texts.get("dialog.out_of_scope")
        question = self.texts.get("dialog.operation")
        decision = self._choose(command, question, options)
        if decision.key == "out_of_scope":
            labels = [operation.text("label") for operation in self.operations.values()]
            raise OutOfScopeError(
                labels,
                self.texts.get(
                    "dialog.out_of_scope_message", operations=", ".join(labels)
                ),
            )
        plan = Plan(
            command,
            None,
            "",
            operation_confidence=decision.confidence,
            operation_unverified=decision.confidence is None,
            known=dict(known or {}),
            language=self.config.language,
            decisions=[self._audit_decision("operation", question, decision)],
            _owner=self,
        )
        if self._uncertain(decision, "operation"):
            likely = sorted(
                self.operations,
                key=lambda key: decision.probabilities.get(key, 0),
                reverse=True,
            )[:3]
            plan.questions.append(
                Question(
                    "operation",
                    "choice",
                    question,
                    [Option(key, self.operations[key].text("label")) for key in likely],
                    help=self.texts.get("dialog.help_fallback"),
                )
            )
            return plan
        plan.operation = decision.key
        plan.operation_label = self.operations[decision.key].text("label")
        return self._populate(plan)

    def _param_question(
        self,
        operation: Operation,
        spec: ParamSpec,
        *,
        options: list[Option] | None = None,
        error: str | None = None,
    ) -> Question:
        prefix = f"params.{spec['name']}"
        return Question(
            spec["name"],
            "choice" if spec["type"] != "free" or options else "value",
            operation.text(f"{prefix}.question"),
            options
            if options is not None
            else (
                [
                    Option(key, operation.text(f"{prefix}.options.{key}.label"))
                    for key in spec.get("options", [])
                ]
                if spec["type"] == "choice"
                else [
                    Option(key, self.texts.get(f"dialog.{key}"))
                    for key in ("yes", "no")
                ]
                if spec["type"] == "bool"
                else []
            ),
            default=spec.get("default"),
            example=operation.text(f"{prefix}.example")
            if spec["type"] == "free"
            else None,
            error=error,
            help=operation.text(f"{prefix}.help")
            if operation.texts.has(f"operations.{operation.id}.{prefix}.help")
            else self.texts.get("dialog.help_fallback"),
        )

    def _applicable(self, spec: ParamSpec, plan: Plan) -> bool | None:
        for name, options in spec.get("depends_on", {}).items():
            if name not in plan.values:
                return None
            if plan.values[name].value not in options:
                return False
        return True

    def _display(self, operation: Operation, spec: ParamSpec, value: Any) -> str:
        if spec["type"] == "choice":
            return operation.text(f"params.{spec['name']}.options.{value}.label")
        if isinstance(value, dict):
            # Area values are normalized (x = east, y = north), so the plan
            # shows how Retman read them (ARCHITECTURE 6.1, note on coordinates)
            area_type = value.get("type")
            if area_type in ("sheet", "teryt"):
                return self.texts.get(
                    f"extractors.area.{area_type}", code=value["code"]
                )
            if area_type == "geometry":
                return self.texts.get("extractors.area.geometry", path=value["path"])
            if area_type == "bbox":
                crs_key = str(value["crs"]).replace("EPSG:", "")
                return self.texts.get(
                    f"extractors.area.bbox_{crs_key}_plan",
                    **{
                        name: f"{value[name]:g}"
                        for name in ("min_x", "min_y", "max_x", "max_y")
                    },
                )
            return ", ".join(
                f"{key}={item}" for key, item in value.items() if key != "type"
            )
        return str(value)

    def _set_param(
        self,
        plan: Plan,
        operation: Operation,
        spec: ParamSpec,
        value: Any,
        source: Source,
        confidence: float | None = None,
        unverified: bool = False,
    ) -> None:
        plan.values[spec["name"]] = PlanValue(value, source, confidence, unverified)
        plan.labels[spec["name"]] = operation.text(f"params.{spec['name']}.label")
        plan.display[spec["name"]] = self._display(operation, spec, value)

    def _readings(self, spec: ParamSpec, text: str) -> list[Match]:
        matches = EXTRACTORS[spec["extractor"]](text)
        accepts = spec.get("accepts")
        if accepts:
            return [
                Match(
                    match.start,
                    match.end,
                    tuple(
                        reading
                        for reading in match.readings
                        if isinstance(reading.value, dict)
                        and reading.value.get("type") in accepts
                    ),
                )
                for match in matches
                if any(
                    isinstance(reading.value, dict)
                    and reading.value.get("type") in accepts
                    for reading in match.readings
                )
            ]
        return matches

    def _reading_label(self, reading: Reading) -> str:
        key = reading.label_key
        if not key.startswith("extractors."):
            key = f"extractors.{key}"
        return self.texts.get(key, **reading.label_args)

    def _validate_free(self, spec: ParamSpec, value: Any) -> str | None:
        values = value if spec.get("multiple") and isinstance(value, list) else [value]
        for item in values:
            accepts = spec.get("accepts")
            if accepts and (
                not isinstance(item, dict) or item.get("type") not in accepts
            ):
                return self.texts.get("dialog.invalid")
            error_key = VALIDATORS[spec["extractor"]](item)
            if error_key:
                key = (
                    error_key
                    if error_key.startswith("extractors.")
                    else f"extractors.{error_key}"
                )
                return self.texts.get(key)
            bounds = spec.get("range")
            if (
                bounds is not None
                and isinstance(item, int | float)
                and not bounds[0] <= item <= bounds[1]
            ):
                return self.texts.get(
                    "dialog.invalid_range", minimum=bounds[0], maximum=bounds[1]
                )
            if isinstance(item, dict) and item.get("type") == "geometry":
                path = (self.workspace.project_dir / item["path"]).resolve()
                if not path.is_file():
                    return self.texts.get("dialog.invalid_geometry", path=item["path"])
        return None

    def _normalize_free(self, value: Any) -> Any:
        if isinstance(value, dict) and value.get("type") == "geometry":
            return {
                **value,
                "path": str((self.workspace.project_dir / value["path"]).resolve()),
            }
        if isinstance(value, list):
            return [self._normalize_free(item) for item in value]
        return value

    def _extract_param(
        self, plan: Plan, operation: Operation, spec: ParamSpec
    ) -> Question | None:
        matches = self._readings(spec, plan.command)
        if not matches:
            if "default" in spec:
                self._set_param(plan, operation, spec, spec["default"], "default")
                return None
            return (
                self._param_question(operation, spec) if spec.get("required") else None
            )
        if any(len(match.readings) > 1 for match in matches) or (
            len(matches) > 1 and not spec.get("multiple")
        ):
            options = [
                Option(str(index), self._reading_label(reading), reading.value)
                for index, reading in enumerate(
                    (reading for match in matches for reading in match.readings), 1
                )
            ]
            return self._param_question(operation, spec, options=options)
        value: Any = (
            [match.readings[0].value for match in matches]
            if spec.get("multiple")
            else matches[0].readings[0].value
        )
        error = self._validate_free(spec, value)
        if error:
            return self._param_question(operation, spec, error=error)
        self._set_param(plan, operation, spec, self._normalize_free(value), "command")
        return None

    def _choice_param(
        self, plan: Plan, operation: Operation, spec: ParamSpec
    ) -> Question | None:
        name = spec["name"]
        prefix = f"params.{name}"
        question = operation.text(f"{prefix}.question")
        recorded = next((d for d in plan.decisions if d["name"] == name), None)
        if recorded is None:
            if spec["type"] == "bool":
                decision = self.backend.yes_no(plan.command, question)
                if decision.key not in ("yes", "no"):
                    raise InvalidModelAnswerError(self.backend.url, decision.key)
            else:
                # Labels are for the user; descriptions with synonyms and English
                # names are for the model (ARCHITECTURE 4.2)
                options = {
                    key: operation.text(f"{prefix}.options.{key}.description")
                    for key in [*spec["options"], "unspecified"]
                }
                decision = self._choose(plan.command, question, options)
            recorded = self._audit_decision(name, question, decision)
            plan.decisions.append(recorded)
        key = recorded["key"]
        # Low confidence asks even when the model says "unspecified": silently
        # falling back to a default would be a guess (ARCHITECTURE 6.1)
        if recorded["confidence"] is not None and self._uncertain(
            Decision(key, recorded["probabilities"], recorded["confidence"]),
            "parameter",
        ):
            return self._param_question(operation, spec)
        if key == "unspecified":
            if "default" in spec:
                self._set_param(plan, operation, spec, spec["default"], "default")
                return None
            return (
                self._param_question(operation, spec) if spec.get("required") else None
            )
        self._set_param(
            plan,
            operation,
            spec,
            key == "yes" if spec["type"] == "bool" else key,
            "command",
            recorded["confidence"],
            recorded["confidence"] is None,
        )
        return None

    def _input_question(
        self,
        name: str,
        kind: str,
        candidates: list[WorkspaceFile],
        *,
        error: str | None = None,
    ) -> Question:
        if candidates:
            return Question(
                name,
                "choice",
                self.texts.get("dialog.input", kind=kind),
                [
                    Option(
                        str(index),
                        item.label,
                        {"path": str(item.path), "number": item.number},
                    )
                    for index, item in enumerate(candidates, 1)
                ],
                error=error,
                help=self.texts.get("dialog.help_fallback"),
            )
        return Question(
            name,
            "value",
            self.texts.get("dialog.input_missing", kind=kind),
            example=self.texts.get("dialog.example_path"),
            error=error,
            help=self.texts.get("dialog.help_fallback"),
        )

    def _set_input(
        self,
        plan: Plan,
        name: str,
        kind: str,
        path: Path,
        number: int | None,
    ) -> str | None:
        try:
            checked = self.workspace.validate_input(path, kind)
        except (KindValidationError, OSError) as err:
            return self.texts.get("dialog.invalid_file", error=err)
        plan.inputs[name] = PlanValue(
            {"path": str(checked), "number": number, "kind": kind},
            "workspace" if number is not None else "command",
        )
        plan.labels[name] = kind
        plan.display[name] = f"#{number}: {checked.name}" if number else str(checked)
        return None

    def _resolve_input(self, plan: Plan, name: str, kind: str) -> Question | None:
        candidates = self.workspace.find_by_kind(kind)
        results = EXTRACTORS["result"](plan.command)
        paths = EXTRACTORS["path"](plan.command)
        if len(results) > 1 or len(paths) > 1 or (results and paths):
            return self._input_question(name, kind, candidates)
        if results:
            number = results[0].readings[0].value
            specific = self.workspace.resolve_result(number, kind)
            if len(specific) == 1:
                item = specific[0]
                error = self._set_input(plan, name, kind, item.path, number)
                return (
                    self._input_question(name, kind, candidates, error=error)
                    if error
                    else None
                )
            return self._input_question(
                name,
                kind,
                specific or candidates,
                error=self.texts.get("dialog.invalid_choice") if not specific else None,
            )
        if paths:
            path = Path(paths[0].readings[0].value)
            error = self._set_input(plan, name, kind, path, None)
            return (
                self._input_question(name, kind, candidates, error=error)
                if error
                else None
            )
        if len(candidates) == 1:
            item = candidates[0]
            error = self._set_input(plan, name, kind, item.path, item.number)
            return (
                self._input_question(name, kind, candidates, error=error)
                if error
                else None
            )
        return self._input_question(name, kind, candidates)

    def _populate(self, plan: Plan) -> Plan:
        assert plan.operation is not None
        operation = self.operations[plan.operation]
        questions: list[Question] = []
        for spec in operation.spec["params"]:
            name = spec["name"]
            applicable = self._applicable(spec, plan)
            if not applicable:
                continue
            if name in plan.known:
                if name not in plan.values:
                    value = plan.known[name]
                    if spec["type"] == "choice" and value not in spec["options"]:
                        raise RetmanError(self.texts.get("dialog.invalid_choice"))
                    if spec["type"] == "bool" and not isinstance(value, bool):
                        raise RetmanError(self.texts.get("dialog.invalid_choice"))
                    if spec["type"] == "free":
                        error = self._validate_free(spec, value)
                        if error:
                            raise RetmanError(error)
                        value = self._normalize_free(value)
                    self._set_param(plan, operation, spec, value, "known")
                continue
            if name in plan.values:
                continue
            if spec["type"] == "free":
                question = self._extract_param(plan, operation, spec)
            else:
                question = self._choice_param(plan, operation, spec)
            if question:
                questions.append(question)
        for input_spec in operation.spec["inputs"]:
            name, kind = input_spec["name"], input_spec["kind"]
            if name in plan.inputs:
                continue
            if name in plan.known:
                known = plan.known[name]
                if isinstance(known, int):
                    matches = self.workspace.resolve_result(known, kind)
                    if len(matches) != 1:
                        raise RetmanError(self.texts.get("dialog.invalid_choice"))
                    error = self._set_input(plan, name, kind, matches[0].path, known)
                else:
                    error = self._set_input(plan, name, kind, Path(known), None)
                if error:
                    raise RetmanError(error)
                plan.inputs[name] = replace(plan.inputs[name], source="known")
                continue
            question = self._resolve_input(plan, name, kind)
            if question:
                questions.append(question)
        plan.questions = questions
        return plan

    def answer_plan(self, plan: Plan, name: str, answer: str) -> Plan:
        """Interpret a user's number or own words, retaining invalid questions."""
        question = next(q for q in plan.questions if q.name == name)
        self.journal.append("question", name=name, question=question.text)
        self.journal.append("answer", name=name, answer=answer)
        updated = plan._updated(
            values=dict(plan.values),
            inputs=dict(plan.inputs),
            labels=dict(plan.labels),
            display=dict(plan.display),
            decisions=list(plan.decisions),
            answers={**plan.answers, name: answer},
            questions=list(plan.questions),
        )
        selection: Option | None = None
        if answer.isdecimal() and 1 <= int(answer) <= len(question.options):
            selection = question.options[int(answer) - 1]
        if not answer and question.default is not None:
            value = question.default
        elif selection is not None:
            value = selection.value if selection.value is not None else selection.key
        elif name == "operation":
            choices = {
                option.key: self.operations[option.key].text("description")
                for option in question.options
            }
            decision = self._choose(answer, question.text, choices)
            value = decision.key if not self._uncertain(decision, "operation") else None
            updated.decisions.append(
                self._audit_decision("operation_answer", question.text, decision)
            )
        elif (
            updated.operation is not None
            and (spec := self.operations[updated.operation].parameter(name)) is not None
            and spec["type"] != "free"
        ):
            choices = {
                option.key: self.operations[updated.operation].text(
                    f"params.{name}.options.{option.key}.description"
                )
                if spec["type"] == "choice"
                else option.label
                for option in question.options
            }
            decision = self._choose(answer, question.text, choices)
            value = decision.key if not self._uncertain(decision, "parameter") else None
            updated.decisions.append(
                self._audit_decision(f"{name}_answer", question.text, decision)
            )
        elif (
            updated.operation is not None
            and (spec := self.operations[updated.operation].parameter(name)) is not None
        ):
            matches = self._readings(spec, answer)
            value = (
                matches[0].readings[0].value
                if (len(matches) == 1 and len(matches[0].readings) == 1)
                else None
            )
            if (
                spec.get("multiple")
                and matches
                and all(len(m.readings) == 1 for m in matches)
            ):
                value = [m.readings[0].value for m in matches]
            if matches and value is None:
                options = [
                    Option(str(index), self._reading_label(reading), reading.value)
                    for index, reading in enumerate(
                        (reading for match in matches for reading in match.readings), 1
                    )
                ]
                updated.questions = [
                    replace(
                        q,
                        type="choice",
                        options=options,
                        error=self.texts.get("dialog.ambiguous"),
                    )
                    if q.name == name
                    else q
                    for q in updated.questions
                ]
                return updated
        else:
            value = answer
        error: str | None = None
        if value is None or value == "unspecified":
            error = self.texts.get(
                "dialog.invalid_choice" if question.options else "dialog.invalid"
            )
        elif name == "operation":
            if value not in self.operations:
                error = self.texts.get("dialog.invalid_choice")
            else:
                updated.operation = value
                updated.operation_label = self.operations[value].text("label")
                updated.operation_unverified = False
        elif (
            updated.operation is not None
            and (spec := self.operations[updated.operation].parameter(name)) is not None
        ):
            if (
                spec["type"] == "choice"
                and value not in spec["options"]
                or spec["type"] == "bool"
                and value not in (True, False, "yes", "no")
            ):
                error = self.texts.get("dialog.invalid_choice")
            elif spec["type"] == "free":
                error = self._validate_free(spec, value)
            if error is None:
                if spec["type"] == "bool":
                    value = value is True or value == "yes"
                self._set_param(
                    updated,
                    self.operations[updated.operation],
                    spec,
                    self._normalize_free(value),
                    "user",
                )
                for dependent in self.operations[updated.operation].spec["params"]:
                    if name in dependent.get("depends_on", {}):
                        updated.values.pop(dependent["name"], None)
                        updated.decisions = [
                            d
                            for d in updated.decisions
                            if d["name"] != dependent["name"]
                        ]
        else:
            assert updated.operation is not None
            input_spec = next(
                i
                for i in self.operations[updated.operation].spec["inputs"]
                if i["name"] == name
            )
            kind = input_spec["kind"]
            if isinstance(value, dict):
                path, number = Path(value["path"]), value["number"]
            else:
                result_matches = EXTRACTORS["result"](str(value))
                path_matches = EXTRACTORS["path"](str(value))
                if result_matches:
                    number = result_matches[0].readings[0].value
                    candidates = self.workspace.resolve_result(number, kind)
                    if len(candidates) != 1:
                        error = self.texts.get("dialog.invalid_choice")
                    else:
                        path = candidates[0].path
                elif len(path_matches) == 1 and len(path_matches[0].readings) == 1:
                    number, path = None, Path(path_matches[0].readings[0].value)
                else:
                    error = self.texts.get("dialog.invalid")
            if error is None:
                error = self._set_input(updated, name, kind, path, number)
                if error is None and number is None:
                    updated.inputs[name] = replace(updated.inputs[name], source="user")
        if error:
            updated.questions = [
                replace(q, error=error) if q.name == name else q
                for q in updated.questions
            ]
            return updated
        updated.questions = [q for q in updated.questions if q.name != name]
        return self._populate(updated)

    def change_plan(self, plan: Plan, name: str) -> Plan:
        """Reopen one editable parameter or input without rerunning the command."""
        if plan.operation is None:
            raise PlanIncompleteError("operation has not been selected")
        operation = self.operations[plan.operation]
        if name not in plan.values and name not in plan.inputs:
            raise ValueError(f"not a plan value: {name}")
        if name in plan.known:
            raise ValueError(f"fixed external value: {name}")
        updated = plan._updated(
            values=dict(plan.values),
            inputs=dict(plan.inputs),
            questions=list(plan.questions),
            decisions=list(plan.decisions),
        )
        if name in updated.values:
            spec = operation.parameter(name)
            assert spec is not None
            updated.values.pop(name)
            question = self._param_question(operation, spec)
        else:
            updated.inputs.pop(name)
            input_spec = next(
                item for item in operation.spec["inputs"] if item["name"] == name
            )
            question = self._input_question(
                name,
                input_spec["kind"],
                self.workspace.find_by_kind(input_spec["kind"]),
            )
        updated.questions.insert(0, question)
        self.record_plan(plan, "changed")
        return updated

    def record_plan(self, plan: Plan, status: str) -> None:
        """Record an approved, changed, rejected or cancelled plan."""
        self.journal.append(
            "plan", status=status, operation=plan.operation, plan=plan.summary()
        )

    def execute(self, plan: Plan) -> Result:
        """Run only a confirmed, complete plan and preserve an audit record."""
        if not plan.confirmed:
            raise PlanNotConfirmedError("call plan.confirm() before execute()")
        if plan.questions or plan.operation is None:
            raise PlanIncompleteError("plan still has open questions")
        operation = self.operations[plan.operation]
        number, directory = self.workspace.create_result_dir(operation.id)
        self.record_plan(plan, "approved")
        started_at = utc_now()
        start_s = monotonic()
        params = {name: value.value for name, value in plan.values.items()}
        inputs: dict[str, Path] = {}
        inputs_audit: dict[str, dict[str, Any]] = {}
        params_audit = {
            name: {
                "value": entry.value,
                "source": entry.source,
                "confidence": entry.confidence,
                "unverified": entry.unverified,
            }
            for name, entry in plan.values.items()
        }
        try:
            for name, entry in plan.inputs.items():
                value = entry.value
                path = self.workspace.validate_input(Path(value["path"]), value["kind"])
                inputs[name] = path
                inputs_audit[name] = self.workspace.describe_input(
                    path, value["kind"], value["number"]
                )
            result = execute_operation(
                operation,
                params,
                inputs,
                directory,
                number,
                params_audit,
                inputs_audit,
                self.texts,
            )
        except (OSError, KindValidationError) as err:
            result = Result(
                False,
                number,
                operation.id,
                params_audit,
                inputs_audit,
                error=str(err),
                summary=self.texts.get("results.failure", number=number, error=err),
            )
        finished_at = utc_now()
        record = result.to_dict()
        record["files"] = {
            kind: [
                {
                    "path": str(path.relative_to(self.workspace.project_dir)),
                    "sha256": sha256_file(path),
                }
                for path in paths
            ]
            for kind, paths in result.files.items()
        }
        if self.config.journal_commands:
            record["command"] = {"text": plan.command, "answers": plan.answers}
        record["decisions"] = plan.decisions
        record["environment"] = {
            "retman": __version__,
            "tools": {operation.tool: operation.version},
            "decision": {
                "backend": self.config.decision.backend,
                "model": self.backend.model,
                "url": self.backend.url,
            },
            "python": sys.version.split()[0],
            "system": platform.platform(),
        }
        record["timing"] = {
            "approval": plan.confirmed_at,
            "start": started_at,
            "end": finished_at,
            "duration_s": monotonic() - start_s,
        }
        self.workspace.save_result(directory, record)
        self.journal.append(
            "execution",
            number=number,
            operation=operation.id,
            error=result.error if not result.ok else None,
        )
        return result

"""Six-step pipeline: recognize, extract, ask, confirm, execute, audit."""

import logging
import platform
import sys
import uuid
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from time import monotonic
from typing import Any

from retman import __version__
from retman.adapters import (
    Preview,
    execute_operation,
    failed_check,
    preview_operation,
    run_check,
)
from retman.adapters.catalog import (
    NoClient,
    PlanView,
    RunClient,
    ToolContext,
    create_client,
)
from retman.backends import build_decision_backend
from retman.backends.base import Decision, DecisionBackend
from retman.config import Config, load_config
from retman.core.check import CheckReport
from retman.core.collection import Collection
from retman.core.dialog import Option, Question
from retman.core.geometry import GeometryFileError, describe_geometry, geometry_layers
from retman.core.journal import Journal, sha256_file, utc_now
from retman.core.plan import Plan, PlanValue, Source
from retman.core.result import Result
from retman.core.workspace import Workspace, WorkspaceFile
from retman.exceptions import (
    CheckNotConfirmedError,
    InvalidModelAnswerError,
    KindValidationError,
    OutOfScopeError,
    PlanIncompleteError,
    PlanNotConfirmedError,
    RetmanError,
)
from retman.extractors import (
    EXTRACTORS,
    describe_value,
    read_answer,
    read_command,
    validate_value,
)
from retman.extractors.base import ExtractionContext, Match, Reading
from retman.i18n.loader import load_core_texts
from retman.kinds import validate_file
from retman.registry.loader import load_operations
from retman.registry.manifest import ParamSpec
from retman.registry.operation import (
    Operation,
    category_groups,
    category_text,
    two_stage,
)

logger = logging.getLogger(__name__)


class Retman:
    """Plan and execute tool operations in a project-local workspace.

    ``operations`` replaces the discovered operations (tests). ``clients``
    injects the command client of a tool by tool name (tests, e.g. a
    ``FakeToolClient``); otherwise it is built lazily from the manifest key
    ``client`` and the ``[tools.<tool>]`` table. ``today`` fixes the date that
    extractors resolve relative expressions against.
    """

    def __init__(
        self,
        config: Config,
        backend: DecisionBackend,
        project_dir: Path,
        *,
        operations: dict[str, Operation] | None = None,
        clients: Mapping[str, RunClient] | None = None,
        today: date | None = None,
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
        self.collection = Collection(
            config.collect_path if config.collect_commands else None
        )
        self._clients: dict[str, RunClient] = dict(clients or {})
        self._today = today if today is not None else date.today()
        # Lookups of one planning pass (e.g. the station catalog) are read once
        self._memo: dict[str, Any] = {}

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
        started_s = monotonic()
        decision = self.backend.choose(state, question, options)
        # The state is the user's command: the technical log never holds it
        logger.debug(
            "Model chose %s among %d options in %.2f s (confidence %s)",
            decision.key,
            len(options),
            monotonic() - started_s,
            decision.confidence,
        )
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

    # --- tools: clients and contexts ----------------------------------------

    def _tool_settings(self, operation: Operation) -> Mapping[str, Any]:
        return self.config.tools.get(operation.tool, {})

    def _run_client(self, operation: Operation) -> RunClient:
        """Build the tool's full client on first use from the manifest.

        Only ``execute()`` and ``check()`` may hand it to tool code; planning code
        gets ``PlanView`` (see ``_plan_client``).
        """
        client = self._clients.get(operation.tool)
        if client is None:
            if operation.client is None:
                return NoClient(operation.tool)
            try:
                client = create_client(operation.client, self._tool_settings(operation))
            except ImportError as err:
                raise RetmanError(
                    self.texts.get("errors.tool_import", tool=operation.tool, error=err)
                ) from err
            self._clients[operation.tool] = client
        return client

    def _plan_client(self, operation: Operation) -> PlanView:
        """Return the offline half of the tool's client, usable by planning (N-12)."""
        return PlanView(self._run_client(operation))

    def _tool_context(
        self,
        operation: Operation,
        client: RunClient | PlanView,
        *,
        output_dir: Path | None = None,
        inputs: Mapping[str, Path] | None = None,
    ) -> ToolContext:
        return ToolContext(
            tool=operation.tool,
            settings=self._tool_settings(operation),
            project_dir=self.workspace.project_dir,
            output_dir=output_dir,
            inputs=inputs or {},
            client=client,
            specs={param["name"]: param for param in operation.spec["params"]},
            operation=operation,
        )

    @staticmethod
    def _plan_inputs(plan: Plan) -> dict[str, Path]:
        return {name: Path(entry.value["path"]) for name, entry in plan.inputs.items()}

    def _extraction_context(
        self, plan: Plan, operation: Operation
    ) -> ExtractionContext:
        """Offline facts for context-aware extractors; the tool is touched lazily."""
        scope: dict[str, Any] = {}
        for spec in operation.spec["params"]:
            entry = plan.values.get(spec["name"])
            if spec["type"] == "choice" and entry is not None:
                scope.update(spec.get("option_meta", {}).get(entry.value, {}))
        return ExtractionContext(
            tool=operation.tool,
            settings=self._tool_settings(operation),
            project_dir=self.workspace.project_dir,
            scope=scope,
            lookup=lambda call: self._plan_client(operation).lookup(call),
            today=self._today,
            memo=self._memo,
        )

    # --- recognition --------------------------------------------------------

    def _out_of_scope(
        self, command: str, decisions: list[dict[str, Any]]
    ) -> OutOfScopeError:
        """Record that nothing fits (W-03) and build the error to raise."""
        compact = self._compact(decisions)
        self.journal.append("out_of_scope", decisions=compact)
        self._collect(
            {"status": "out_of_scope", "command": command, "operation": None},
            decisions,
        )
        members = list(self.operations.values())
        if two_stage(self.operations):
            groups = category_groups(members)
            labels = [category_text(ops, key, "label") for key, ops in groups.items()]
        else:
            labels = [operation.text("label") for operation in members]
        return OutOfScopeError(
            labels,
            self.texts.get("dialog.out_of_scope_message", operations=", ".join(labels)),
            compact,
        )

    def plan(self, command: str, known: dict[str, Any] | None = None) -> Plan:
        """Choose an operation and fill what code or model can determine safely.

        With more operations than one question can offer, the model first
        chooses a category, then an operation of it (ARCHITECTURE 3.4).
        """
        if not self.operations:
            raise RetmanError(self.texts.get("dialog.no_operations"))
        self._memo = {}
        self.journal.append("command", command=command)
        plan = Plan(
            command,
            None,
            "",
            known=dict(known or {}),
            language=self.config.language,
            _owner=self,
        )
        if not two_stage(self.operations):
            return self._select_operation(plan, None)
        groups = category_groups(self.operations.values())
        question = self.texts.get("dialog.category")
        options = {
            key: category_text(members, key, "description")
            for key, members in groups.items()
        }
        options["out_of_scope"] = self.texts.get("dialog.out_of_scope")
        decision = self._choose(command, question, options)
        plan.decisions.append(self._audit_decision("category", question, decision))
        if decision.key == "out_of_scope":
            raise self._out_of_scope(command, plan.decisions)
        if self._uncertain(decision, "operation"):
            likely = sorted(
                groups, key=lambda key: decision.probabilities.get(key, 0), reverse=True
            )[:3]
            plan.questions.append(
                Question(
                    "category",
                    "choice",
                    question,
                    [
                        Option(key, category_text(groups[key], key, "label"))
                        for key in likely
                    ],
                    help=self.texts.get("dialog.help_fallback"),
                )
            )
            return plan
        return self._select_operation(plan, decision.key)

    def _select_operation(self, plan: Plan, category: str | None) -> Plan:
        """Ask the model which operation (of ``category``, if given) the command is."""
        members = {
            key: operation
            for key, operation in self.operations.items()
            if category is None or operation.category == category
        }
        question = self.texts.get("dialog.operation")
        options = {
            key: operation.text("description") for key, operation in members.items()
        }
        options["out_of_scope"] = self.texts.get("dialog.out_of_scope")
        decision = self._choose(plan.command, question, options)
        plan.decisions.append(self._audit_decision("operation", question, decision))
        if decision.key == "out_of_scope":
            raise self._out_of_scope(plan.command, plan.decisions)
        plan.operation_confidence = decision.confidence
        plan.operation_unverified = any(
            item["confidence"] is None for item in plan.decisions
        )
        if self._uncertain(decision, "operation"):
            likely = sorted(
                members,
                key=lambda key: decision.probabilities.get(key, 0),
                reverse=True,
            )[:3]
            plan.questions.append(
                Question(
                    "operation",
                    "choice",
                    question,
                    [Option(key, members[key].text("label")) for key in likely],
                    help=self.texts.get("dialog.help_fallback"),
                )
            )
            return plan
        plan.operation = decision.key
        plan.operation_label = members[decision.key].text("label")
        return self._populate(plan)

    # --- questions and values -----------------------------------------------

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

    def _unset(self, plan: Plan, operation: Operation) -> dict[str, tuple[str, str]]:
        """Applicable optional parameters left unset, with what that means (N-11).

        A parameter being asked about is not unset: its question is open.
        """
        asked = {question.name for question in plan.questions}
        unset: dict[str, tuple[str, str]] = {}
        for spec in operation.spec["params"]:
            name = spec["name"]
            if (
                spec.get("required")
                or "default" in spec
                or name in plan.values
                or name in asked
                or name in plan.known
                or self._applicable(spec, plan) is not True
            ):
                continue
            unset[name] = (
                operation.text(f"params.{name}.label"),
                operation.text(f"params.{name}.unset"),
            )
        return unset

    def _display_item(self, operation: Operation, spec: ParamSpec, value: Any) -> str:
        area_type = value.get("type") if isinstance(value, dict) else None
        # Area values are normalized (x = east, y = north), so the plan
        # shows how Retman read them (ARCHITECTURE 6.1, note on coordinates)
        if area_type in ("sheet", "teryt"):
            return self.texts.get(f"extractors.area.{area_type}", code=value["code"])
        if area_type == "geometry":
            shown = (
                self.texts.get(
                    "extractors.area.geometry_layer",
                    path=value["path"],
                    layer=value["layer"],
                )
                if value.get("layer") is not None
                else self.texts.get("extractors.area.geometry", path=value["path"])
            )
            note = f"operations.{operation.id}.params.{spec['name']}.geometry_note"
            return (
                f"{shown} ({operation.texts.get(note)})"
                if operation.texts.has(note)
                else shown
            )
        if area_type == "bbox":
            crs_key = str(value["crs"]).replace("EPSG:", "")
            return self.texts.get(
                f"extractors.area.bbox_{crs_key}_plan",
                **{
                    name: f"{value[name]:g}"
                    for name in ("min_x", "min_y", "max_x", "max_y")
                },
            )
        described = (
            describe_value(spec["extractor"], value, self.texts)
            if "extractor" in spec
            else None
        )
        if described is not None:
            return described
        if isinstance(value, dict):
            return ", ".join(
                f"{key}={item}" for key, item in value.items() if key != "type"
            )
        return str(value)

    def _display(self, operation: Operation, spec: ParamSpec, value: Any) -> str:
        if spec["type"] == "choice":
            return operation.text(f"params.{spec['name']}.options.{value}.label")
        if isinstance(value, list):
            return ", ".join(
                self._display_item(operation, spec, item) for item in value
            )
        return self._display_item(operation, spec, value)

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

    def _readings(
        self,
        plan: Plan,
        operation: Operation,
        spec: ParamSpec,
        text: str,
        *,
        answer: bool = False,
    ) -> list[Match]:
        """Return the readings of the parameter's extractor, narrowed by ``accepts``."""
        context = self._extraction_context(plan, operation)
        read = read_answer if answer else read_command
        matches = read(spec["extractor"], text, context)
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
                    match.confirm,
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

    def _validate_geometry(self, item: dict[str, Any]) -> str | None:
        """Why a geometry area cannot be used (file, kind, layer); None if it can."""
        path = (self.workspace.project_dir / item["path"]).resolve()
        if not path.is_file():
            return self.texts.get("dialog.invalid_geometry", path=item["path"])
        try:
            validate_file("area_geometry", path)
        except (KindValidationError, OSError) as err:
            return self.texts.get("dialog.invalid_file", error=err)
        layer = item.get("layer")
        if layer is None:
            return None
        if path.suffix.lower() != ".gpkg":
            return self.texts.get("dialog.invalid")
        try:
            known = geometry_layers(path)
        except GeometryFileError as err:
            return self.texts.get(
                "dialog.geometry_unreadable", file=path.name, error=err.reason
            )
        if layer not in known:
            return self.texts.get(
                "dialog.geometry_layer_unknown", file=path.name, layer=layer
            )
        return None

    def _validate_free(
        self, plan: Plan, operation: Operation, spec: ParamSpec, value: Any
    ) -> str | None:
        context = self._extraction_context(plan, operation)
        values = value if spec.get("multiple") and isinstance(value, list) else [value]
        for item in values:
            accepts = spec.get("accepts")
            if accepts and (
                not isinstance(item, dict) or item.get("type") not in accepts
            ):
                return self.texts.get("dialog.invalid")
            error_key = validate_value(spec["extractor"], item, context)
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
                error = self._validate_geometry(item)
                if error:
                    return error
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

    def _complete_geometry(
        self, operation: Operation, spec: ParamSpec, value: Any
    ) -> tuple[Any, Question | None]:
        """Decide the layer of a geometry area (never guessed, W-02).

        A Shapefile has none, a GeoPackage with one feature table uses it (the
        plan shows it) and with several the user chooses by number. Any other
        value is returned unchanged. The value must be validated and normalized.
        """
        if (
            not isinstance(value, dict)
            or value.get("type") != "geometry"
            or "layer" in value
        ):
            return value, None
        path = Path(value["path"])
        if path.suffix.lower() != ".gpkg":
            return {**value, "layer": None}, None
        try:
            layers = geometry_layers(path)
        except GeometryFileError as err:
            return value, self._param_question(
                operation,
                spec,
                error=self.texts.get(
                    "dialog.geometry_unreadable", file=path.name, error=err.reason
                ),
            )
        if not layers:
            return value, self._param_question(
                operation,
                spec,
                error=self.texts.get("dialog.geometry_no_layers", file=path.name),
            )
        if len(layers) == 1:
            return {**value, "layer": layers[0]}, None
        return value, Question(
            spec["name"],
            "choice",
            self.texts.get("dialog.geometry_layer", file=path.name),
            [
                Option(str(index), layer, {**value, "layer": layer})
                for index, layer in enumerate(layers, 1)
            ],
            help=self.texts.get("dialog.help_fallback"),
        )

    def _extract_param(
        self, plan: Plan, operation: Operation, spec: ParamSpec
    ) -> Question | None:
        matches = self._readings(plan, operation, spec, plan.command)
        if not matches:
            if "default" in spec:
                self._set_param(plan, operation, spec, spec["default"], "default")
                return None
            return (
                self._param_question(operation, spec) if spec.get("required") else None
            )
        if any(match.ambiguous for match in matches) or (
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
        error = self._validate_free(plan, operation, spec, value)
        if error:
            return self._param_question(operation, spec, error=error)
        value, layer_question = self._complete_geometry(
            operation, spec, self._normalize_free(value)
        )
        if layer_question is not None:
            return layer_question
        self._set_param(plan, operation, spec, value, "command")
        return None

    @staticmethod
    def _extracted_values(matches: list[Match]) -> list[Any]:
        return list(
            dict.fromkeys(
                reading.value for match in matches for reading in match.readings
            )
        )

    def _extracted_choice_error(self, spec: ParamSpec, values: list[Any]) -> str | None:
        """Why values read by code do not give one option; None if they do."""
        supported = set(spec["option_values"].values())
        if len(values) > 1:
            return self.texts.get(
                "dialog.several_values", values=", ".join(map(str, values))
            )
        if values and values[0] not in supported:
            return self.texts.get("dialog.unsupported_value", value=values[0])
        return None

    def _extracted_choice(
        self, plan: Plan, operation: Operation, spec: ParamSpec
    ) -> Question | None:
        """Read a choice by code, never by the model (ADR-009)."""
        values = self._extracted_values(
            read_command(
                spec["extractor"],
                plan.command,
                self._extraction_context(plan, operation),
            )
        )
        if len(values) == 1 and values[0] in spec["option_values"].values():
            key = next(k for k, v in spec["option_values"].items() if v == values[0])
            self._set_param(plan, operation, spec, key, "command")
            return None
        if not values and "default" in spec:
            self._set_param(plan, operation, spec, spec["default"], "default")
            return None
        if not values and not spec.get("required"):
            return None
        return self._param_question(
            operation, spec, error=self._extracted_choice_error(spec, values)
        )

    def _choice_param(
        self, plan: Plan, operation: Operation, spec: ParamSpec
    ) -> Question | None:
        name = spec["name"]
        prefix = f"params.{name}"
        # The user-facing question ("1 m or 5 m?") reads to the model as an open
        # choice; the model is asked what the command states (ARCHITECTURE 4.2)
        question = operation.text(f"{prefix}.model_question")
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
                        if spec.get("multiple") and not isinstance(value, list):
                            value = [value]
                        error = self._validate_free(plan, operation, spec, value)
                        if error:
                            raise RetmanError(error)
                        value, layer_question = self._complete_geometry(
                            operation, spec, self._normalize_free(value)
                        )
                        if layer_question is not None:
                            # A fixed value is never asked about
                            raise RetmanError(
                                layer_question.error
                                or self.texts.get(
                                    "dialog.geometry_layer_required",
                                    file=Path(value["path"]).name,
                                )
                            )
                    self._set_param(plan, operation, spec, value, "known")
                continue
            if name in plan.values:
                continue
            if name in plan.reopened:
                # The tool rejected the answer at preview: ask again, never
                # derive the value from the command a second time
                questions.append(
                    self._param_question(operation, spec, error=plan.reopened[name])
                )
                continue
            if spec["type"] == "free":
                question = self._extract_param(plan, operation, spec)
            elif spec["type"] == "choice" and "extractor" in spec:
                question = self._extracted_choice(plan, operation, spec)
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
        plan.unset = self._unset(plan, operation)
        if not questions:
            return self._review(plan, operation)
        return plan

    # --- offline review of a complete plan ----------------------------------

    def _review(self, plan: Plan, operation: Operation) -> Plan:
        """Let the tool validate the complete plan and preview it, offline (N-12).

        A rejection reopens the parameters it names as questions; the plan is
        complete, and so confirmable, only when the tool accepts it.
        """
        if "calls" not in operation.spec and "preview" not in operation.spec:
            return plan
        params = {name: entry.value for name, entry in plan.values.items()}
        context = self._tool_context(
            operation, self._plan_client(operation), inputs=self._plan_inputs(plan)
        )
        preview = preview_operation(operation, params, context, self.texts)
        if preview.problems:
            self._reopen(plan, operation, preview)
            return self._populate(plan)
        plan.preview_rows = preview.rows
        plan.preview_values = preview.values
        return plan

    def _reopen(self, plan: Plan, operation: Operation, preview: Preview) -> None:
        """Make the parameters of the problems questions again, with the reason.

        The model's decision stays in ``plan.decisions`` (a truthful audit); the
        value is dropped and ``plan.reopened`` keeps ``_populate`` from deriving
        it from the command a second time. Fixed (``known``) values and
        parameters without a value cannot be reopened; when nothing can be, the
        plan could never become confirmable, so this raises instead of looping.
        """
        reopened: dict[str, str] = {}
        for problem in preview.problems:
            for name in problem.params:
                if name in plan.values and name not in plan.known:
                    reopened.setdefault(name, problem.text)
        if not reopened:
            raise RetmanError(preview.problems[0].text)
        for name in reopened:
            plan.values.pop(name)
        plan.reopened.update(reopened)
        plan.preview_rows = []
        plan.preview_values = {}

    def answer_plan(self, plan: Plan, name: str, answer: str) -> Plan:
        """Interpret a user's number or own words, retaining invalid questions."""
        question = next(q for q in plan.questions if q.name == name)
        self._memo = {}
        self.journal.append(
            "question",
            name=name,
            question=question.text,
            **({"reason": question.error} if name in plan.reopened else {}),
        )
        self.journal.append("answer", name=name, answer=answer)
        updated = plan._updated(
            values=dict(plan.values),
            inputs=dict(plan.inputs),
            labels=dict(plan.labels),
            display=dict(plan.display),
            decisions=list(plan.decisions),
            answers={**plan.answers, name: answer},
            questions=list(plan.questions),
            reopened=dict(plan.reopened),
        )
        selection: Option | None = None
        if answer.isdecimal() and 1 <= int(answer) <= len(question.options):
            selection = question.options[int(answer) - 1]
        if not answer and question.default is not None:
            value = question.default
        elif selection is not None:
            value = selection.value if selection.value is not None else selection.key
        elif name == "category":
            groups = category_groups(self.operations.values())
            choices = {
                option.key: category_text(groups[option.key], option.key, "description")
                for option in question.options
            }
            decision = self._choose(answer, question.text, choices)
            value = decision.key if not self._uncertain(decision, "operation") else None
            updated.decisions.append(
                self._audit_decision("category_answer", question.text, decision)
            )
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
            and spec["type"] == "choice"
            and "extractor" in spec
        ):
            values = self._extracted_values(
                read_answer(
                    spec["extractor"],
                    answer,
                    self._extraction_context(
                        updated, self.operations[updated.operation]
                    ),
                )
            )
            value = next(
                (
                    key
                    for key, option_value in spec["option_values"].items()
                    if len(values) == 1 and option_value == values[0]
                ),
                None,
            )
            if value is None and (
                message := self._extracted_choice_error(spec, values)
            ):
                updated.questions = [
                    replace(q, error=message) if q.name == name else q
                    for q in updated.questions
                ]
                return updated
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
            model_question = self.operations[updated.operation].text(
                f"params.{name}.model_question"
            )
            decision = self._choose(answer, model_question, choices)
            value = decision.key if not self._uncertain(decision, "parameter") else None
            updated.decisions.append(
                self._audit_decision(f"{name}_answer", model_question, decision)
            )
        elif (
            updated.operation is not None
            and (spec := self.operations[updated.operation].parameter(name)) is not None
        ):
            matches = self._readings(
                updated, self.operations[updated.operation], spec, answer, answer=True
            )
            value = (
                matches[0].readings[0].value
                if (len(matches) == 1 and not matches[0].ambiguous)
                else None
            )
            if (
                spec.get("multiple")
                and matches
                and all(not m.ambiguous for m in matches)
            ):
                value = [m.readings[0].value for m in matches]
            if matches and value is None:
                options = [
                    Option(str(index), self._reading_label(reading), reading.value)
                    for index, reading in enumerate(
                        (reading for match in matches for reading in match.readings), 1
                    )
                ]
                confirm_only = all(
                    len(match.readings) == 1 and match.confirm for match in matches
                )
                updated.questions = [
                    replace(
                        q,
                        type="choice",
                        options=options,
                        error=self.texts.get(
                            "dialog.confirm_reading"
                            if confirm_only
                            else "dialog.ambiguous"
                        ),
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
        elif name == "category":
            groups = category_groups(self.operations.values())
            if value not in groups:
                error = self.texts.get("dialog.invalid_choice")
            else:
                updated.questions = [q for q in updated.questions if q.name != name]
                return self._select_operation(updated, value)
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
            operation = self.operations[updated.operation]
            if (
                spec["type"] == "choice"
                and value not in spec["options"]
                or spec["type"] == "bool"
                and value not in (True, False, "yes", "no")
            ):
                error = self.texts.get("dialog.invalid_choice")
            elif spec["type"] == "free":
                if spec.get("multiple") and not isinstance(value, list):
                    value = [value]
                error = self._validate_free(updated, operation, spec, value)
            if error is None:
                if spec["type"] == "bool":
                    value = value is True or value == "yes"
                value = self._normalize_free(value)
                if spec["type"] == "free":
                    value, layer_question = self._complete_geometry(
                        operation, spec, value
                    )
                    if layer_question is not None:
                        updated.questions = [
                            layer_question if q.name == name else q
                            for q in updated.questions
                        ]
                        return updated
                self._set_param(updated, operation, spec, value, "user")
                updated.reopened.pop(name, None)
                for dependent in operation.spec["params"]:
                    if name in dependent.get("depends_on", {}):
                        updated.values.pop(dependent["name"], None)
                        updated.reopened.pop(dependent["name"], None)
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
        if (
            name not in plan.values
            and name not in plan.inputs
            and name not in plan.unset
        ):
            raise ValueError(f"not a plan value: {name}")
        if name in plan.known:
            raise ValueError(f"fixed external value: {name}")
        updated = plan._updated(
            values=dict(plan.values),
            inputs=dict(plan.inputs),
            questions=list(plan.questions),
            decisions=list(plan.decisions),
            reopened=dict(plan.reopened),
        )
        if name in updated.values or name in plan.unset:
            spec = operation.parameter(name)
            assert spec is not None
            updated.values.pop(name, None)
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
        self.record_plan(plan, "changed", changed=name)
        return updated

    @staticmethod
    def _compact(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Model decisions without question texts, for journal and collection."""
        return [
            {
                "name": d["name"],
                "key": d["key"],
                "confidence": d["confidence"],
                "method": d["confidence_method"],
                "probabilities": d["probabilities"],
            }
            for d in decisions
        ]

    @staticmethod
    def _portable(value: Any) -> Any:
        """Plan value without local paths: a geometry file keeps only its name."""
        if isinstance(value, dict) and value.get("type") == "geometry":
            return {**value, "path": Path(value["path"]).name}
        if isinstance(value, list):
            return [Retman._portable(item) for item in value]
        return value

    def _plan_data(self, plan: Plan) -> dict[str, Any]:
        """Collect what Retman understood: values with sources, questions, decisions."""
        return {
            "operation": plan.operation,
            "values": {
                name: {"value": self._portable(entry.value), "source": entry.source}
                for name, entry in plan.values.items()
            },
            "inputs": {
                name: {"number": entry.value.get("number"), "source": entry.source}
                for name, entry in plan.inputs.items()
            },
            "questions": [question.name for question in plan.questions],
            "decisions": self._compact(plan.decisions),
        }

    def _collect(self, record: dict[str, Any], decisions: list[dict[str, Any]]) -> None:
        if not self.collection.enabled:
            return
        operation = self.operations.get(record.get("operation") or "")
        self.collection.append(
            {
                **record,
                "session_id": self.journal.session_id,
                "decisions": self._compact(decisions),
                "environment": {
                    "retman": __version__,
                    "tools": {operation.tool: operation.version} if operation else {},
                    "backend": self.config.decision.backend,
                    "model": self.backend.model,
                },
            }
        )

    def _collect_plan(
        self,
        plan: Plan,
        status: str,
        *,
        changed: str | None = None,
        result: Result | None = None,
    ) -> None:
        data = self._plan_data(plan)
        del data["decisions"]
        record: dict[str, Any] = {
            "status": status,
            "command": plan.command,
            "answers": plan.answers,
            **data,
        }
        if changed:
            record["changed"] = changed
        if result is not None:
            record["result"] = {"ok": result.ok, "error": result.error}
        self._collect(record, plan.decisions)

    def record_plan(
        self, plan: Plan, status: str, *, changed: str | None = None
    ) -> None:
        """Record an approved, changed, rejected or cancelled plan.

        The journal gets the shown plan and the structured data behind it; the
        optional collection (ADR-010) also gets the command and the answers —
        for an approved plan only after execution, with its outcome.
        """
        self.journal.append(
            "plan",
            status=status,
            plan=plan.summary(),
            **({"changed": changed} if changed else {}),
            **self._plan_data(plan),
        )
        if status != "approved":
            self._collect_plan(plan, status, changed=changed)

    # --- availability check (a separate, consented network step) -------------

    def _checkable(self, plan: Plan) -> Operation:
        if plan.operation is None or plan.questions:
            raise PlanIncompleteError("plan still has open questions")
        operation = self.operations[plan.operation]
        if "check" not in operation.spec:
            raise PlanIncompleteError("this operation offers no availability check")
        return operation

    def check_notice(self, plan: Plan) -> str:
        """Describe what the availability check contacts and sends, before consent."""
        operation = self._checkable(plan)
        return self.texts.get("check.notice", operation=operation.text("check.notice"))

    def check(self, plan: Plan) -> CheckReport:
        """Ask the tool's data services what exists for a complete plan.

        The only network entry point besides ``execute()``: it needs its own,
        single-use consent (``plan.confirm_check()``), creates no result and
        writes nothing in the workspace, and never changes the plan's values.
        The plan's approval is withdrawn: the user must confirm after reading the
        report. A failed check is a report with status ``unknown``;
        ``KeyboardInterrupt`` propagates (the journal still records the attempt).

        Raises
        ------
        CheckNotConfirmedError
            ``plan.confirm_check()`` was not called since the last change or check.
        """
        if not plan.check_confirmed:
            raise CheckNotConfirmedError("call plan.confirm_check() before check()")
        plan.check_confirmed = False
        operation = self._checkable(plan)
        plan.confirmed = False
        plan.confirmed_at = None
        params = {name: entry.value for name, entry in plan.values.items()}
        report: CheckReport | None = None
        try:
            try:
                context = self._tool_context(
                    operation,
                    self._run_client(operation),
                    inputs=self._plan_inputs(plan),
                )
            except (OSError, ImportError, RetmanError) as err:
                logger.warning(
                    "Availability check of %s could not run: %s",
                    operation.id,
                    type(err).__name__,
                )
                report = failed_check(operation, self.texts, str(err))
            else:
                report = run_check(operation, params, context, self.texts)
                logger.info(
                    "Availability check of %s finished: %s", operation.id, report.status
                )
        finally:
            self.journal.append(
                "check",
                status="approved",
                result=report.status if report else None,
                error=report.error if report else None,
                tool=operation.tool,
                version=operation.version,
                lines=report.lines if report else [],
                **self._plan_data(plan),
            )
        plan.checks = [*plan.checks, report]
        return report

    def record_check(self, plan: Plan, status: str) -> None:
        """Journal a declined availability check (no network was used)."""
        operation = self._checkable(plan)
        self.journal.append(
            "check",
            status=status,
            result=None,
            error=None,
            tool=operation.tool,
            version=operation.version,
            lines=[],
            **self._plan_data(plan),
        )

    # --- execution -----------------------------------------------------------

    def _file_record(self, operation: Operation, path: Path) -> dict[str, str]:
        """Describe a result file for ``result.json``: project-relative or stored."""
        try:
            entry = {"path": str(path.relative_to(self.workspace.project_dir))}
        except ValueError:
            entry = {"path": str(path), "store": operation.tool}
        entry["sha256"] = sha256_file(path)
        return entry

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
            for name, entry in plan.values.items():
                if (
                    isinstance(entry.value, dict)
                    and entry.value.get("type") == "geometry"
                ):
                    params_audit[name]["files"] = describe_geometry(
                        Path(entry.value["path"])
                    )
            for name, entry in plan.inputs.items():
                value = entry.value
                path = self.workspace.validate_input(Path(value["path"]), value["kind"])
                inputs[name] = path
                inputs_audit[name] = self.workspace.describe_input(
                    path, value["kind"], value["number"]
                )
            context = self._tool_context(
                operation,
                self._run_client(operation),
                output_dir=directory,
                inputs=inputs,
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
                context,
            )
        except (OSError, ImportError, RetmanError) as err:
            logger.warning("Operation %s failed: %s", operation.id, type(err).__name__)
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
        logger.info(
            "Operation %s finished as result #%d (ok=%s) in %.2f s",
            operation.id,
            number,
            result.ok,
            monotonic() - start_s,
        )
        record = result.to_dict()
        record["files"] = {
            kind: [self._file_record(operation, path) for path in paths]
            for kind, paths in result.files.items()
        }
        if self.config.journal_commands:
            record["command"] = {"text": plan.command, "answers": plan.answers}
        record["decisions"] = plan.decisions
        if plan.unset:
            record["unset"] = {name: text for name, (_, text) in plan.unset.items()}
        if plan.preview_values:
            record["preview"] = plan.preview_values
        if plan.checks:
            record["checks"] = [report.to_dict() for report in plan.checks]
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
        self._collect_plan(plan, "approved", result=result)
        return result

"""Consumer-visible planning metrics and confidence threshold analysis."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import ceil
from statistics import median
from typing import Any

EvalRecord = dict[str, Any]


@dataclass(frozen=True)
class Ratio:
    """Numerator and denominator kept alongside the displayed fraction."""

    count: int = 0
    total: int = 0

    @property
    def fraction(self) -> float | None:
        return self.count / self.total if self.total else None


@dataclass(frozen=True)
class Timing:
    median: float
    p90: float
    maximum: float


@dataclass(frozen=True)
class ErrorCase:
    id: str
    repeat: int
    command: str
    field: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ThresholdPoint:
    threshold: float
    error: Ratio
    coverage: Ratio


@dataclass(frozen=True)
class Recommendation:
    point: ThresholdPoint | None
    insufficient: bool
    minimum_sample: int


@dataclass
class Measures:
    """One set of metrics, usable globally or for one operation/tag."""

    operation: Ratio = Ratio()
    operation_in_scope: Ratio = Ratio()
    operation_out_of_scope: Ratio = Ratio()
    parameter: Ratio = Ratio()
    parameter_correct_automatic: Ratio = Ratio()
    parameter_wrong_automatic: Ratio = Ratio()
    parameter_asked: Ratio = Ratio()
    automatic_coverage: Ratio = Ratio()
    accepted_operation: Ratio = Ratio()
    accepted_model_parameters: Ratio = Ratio()
    accepted_extractors: Ratio = Ratio()
    accepted_all: Ratio = Ratio()
    silent_guesses: Ratio = Ratio()
    clarification: Ratio = Ratio()
    unnecessary_questions: Ratio = Ratio()
    w03: Ratio = Ratio()
    stability: Ratio | None = None
    plan_seconds: Timing | None = None
    model_queries: Timing | None = None
    errors: list[ErrorCase] = field(default_factory=list)
    violations: list[ErrorCase] = field(default_factory=list)


@dataclass
class EvaluationSummary:
    overall: Measures
    by_operation: dict[str, Measures]
    by_tag: dict[str, Measures]
    curves: dict[str, list[ThresholdPoint]]
    recommendations: dict[str, Recommendation] | None
    command_counts: dict[str, int]
    tag_counts: dict[str, int]
    runs: int
    commands: int


def _ratio_add(ratio: Ratio, count: int = 0, total: int = 0) -> Ratio:
    return Ratio(ratio.count + count, ratio.total + total)


def _timing(values: list[float]) -> Timing | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile: the 90th observation for a set of 100.
    return Timing(median(ordered), ordered[ceil(0.9 * len(ordered)) - 1], ordered[-1])


def _correct_key(decision: dict[str, Any], expected: Any) -> bool:
    key = decision["key"]
    if isinstance(expected, bool):
        return key == ("yes" if expected else "no")
    return key == expected


def _issue(record: EvalRecord, field: str, expected: Any, actual: Any) -> ErrorCase:
    return ErrorCase(
        record["id"], record["repeat"], record["command"], field, expected, actual
    )


def _measure(records: Sequence[EvalRecord], repeat: int) -> Measures:
    measures = Measures()
    timings: list[float] = []
    queries: list[float] = []
    repeats: dict[str, list[tuple[tuple[str, str], ...]]] = defaultdict(list)
    for record in records:
        expected = record["expected"]
        expected_operation = expected["operation"]
        decisions = {item["name"]: item for item in record["decisions"]}
        questions = set(record["questions"])
        op_asked = (
            record["operation_question"]["asked"]
            or record["category_question"]["asked"]
        )
        op_decision = decisions.get("operation")
        op_correct = op_decision is not None and _correct_key(
            op_decision, expected_operation
        )
        measures.operation = _ratio_add(measures.operation, int(op_correct), 1)
        group = (
            "operation_out_of_scope"
            if expected_operation == "out_of_scope"
            else "operation_in_scope"
        )
        setattr(
            measures, group, _ratio_add(getattr(measures, group), int(op_correct), 1)
        )
        if not op_correct:
            measures.errors.append(
                _issue(record, "operation", expected_operation, op_decision)
            )
        if op_decision is not None and not op_asked:
            measures.accepted_operation = _ratio_add(
                measures.accepted_operation, int(not op_correct), 1
            )
        if expected_operation == "out_of_scope":
            violation = (
                record["outcome"] == "plan"
                and not op_asked
                and bool(record.get("operation"))
            )
            measures.w03 = _ratio_add(measures.w03, int(violation), 1)
            if violation:
                measures.violations.append(
                    _issue(record, "W-03", "out_of_scope", record.get("operation"))
                )
        if "complete" in record["tags"] and not expected["expect_clarify"]:
            measures.automatic_coverage = _ratio_add(
                measures.automatic_coverage, int(not questions and not op_asked), 1
            )
        # A question about an unrelated operation cannot test the expected parameters.
        if (
            expected_operation != "out_of_scope"
            and record.get("operation") == expected_operation
        ):
            _parameters(measures, record, decisions, questions)
        if record["outcome"] != "error":
            timings.append(record["plan_s"])
            queries.append(record["model_queries"])
        repeats[record["id"]].append(
            tuple(sorted((item["name"], item["key"]) for item in record["decisions"]))
        )
    measures.unnecessary_questions = Ratio(
        measures.unnecessary_questions.count, len(records)
    )
    for metric_name in (
        "parameter_correct_automatic",
        "parameter_wrong_automatic",
        "parameter_asked",
    ):
        ratio = getattr(measures, metric_name)
        setattr(measures, metric_name, Ratio(ratio.count, measures.parameter.total))
    measures.accepted_all = Ratio(
        measures.accepted_operation.count
        + measures.accepted_model_parameters.count
        + measures.accepted_extractors.count,
        measures.accepted_operation.total
        + measures.accepted_model_parameters.total
        + measures.accepted_extractors.total,
    )
    measures.plan_seconds = _timing(timings)
    measures.model_queries = _timing(queries)
    if repeat > 1:
        measures.stability = Ratio(
            sum(
                len(group) == repeat and len(set(group)) == 1
                for group in repeats.values()
            ),
            len(repeats),
        )
    return measures


def _parameters(
    measures: Measures,
    record: EvalRecord,
    decisions: dict[str, dict[str, Any]],
    questions: set[str],
) -> None:
    expected = record["expected"]
    values = record["values"]
    params = expected["params"]
    clarify = expected["expect_clarify"]
    applicable = set(record.get("applicable_parameters", [*params, *clarify]))
    for name, expected_value in params.items():
        actual = values.get(name)
        asked = name in questions
        correct = actual is not None and actual["value"] == expected_value
        measures.parameter = _ratio_add(measures.parameter, int(correct), 1)
        field = (
            "parameter_asked"
            if asked
            else "parameter_correct_automatic"
            if correct
            else "parameter_wrong_automatic"
        )
        measures_value = getattr(measures, field)
        setattr(measures, field, _ratio_add(measures_value, 1))
        # Listed only when a wrong value was set: an asked value is a cost
        # (unnecessary question), and a missing one follows from a wrong
        # operation or an unresolved controlling parameter (``depends_on``)
        if actual is not None and not correct and not asked:
            measures.errors.append(_issue(record, name, expected_value, actual))
    measures.clarification = _ratio_add(
        measures.clarification, len(questions.intersection(clarify)), len(clarify)
    )
    for name in clarify:
        # Same rule: only a value accepted without the expected question is listed
        if name not in questions and values.get(name) is not None:
            measures.errors.append(_issue(record, name, "question", values[name]))
    unnecessary = questions.intersection(params)
    # A default only applies to a parameter absent from both expectation fields.
    unnecessary.update(
        name for name in questions if name in record.get("default_parameters", [])
    )
    measures.unnecessary_questions = _ratio_add(
        measures.unnecessary_questions, len(unnecessary.intersection(applicable))
    )

    for name, decision in decisions.items():
        if name in ("operation", "operation_answer"):
            continue
        if name not in applicable:
            continue
        # A low-confidence decision is not accepted if the pipeline asks.
        if name in questions:
            continue
        expected_key = params.get(name, "unspecified")
        correct = _correct_key(decision, expected_key)
        measures.accepted_model_parameters = _ratio_add(
            measures.accepted_model_parameters, int(not correct), 1
        )
        if name not in params:
            guessed = decision["key"] != "unspecified"
            measures.silent_guesses = _ratio_add(
                measures.silent_guesses, int(guessed), 1
            )
            if guessed:
                measures.errors.append(
                    _issue(record, name, "unspecified", decision["key"])
                )
        elif not correct:
            measures.errors.append(_issue(record, name, expected_key, decision["key"]))
    for name, value in values.items():
        if (
            name not in applicable
            or name in decisions
            or name in questions
            or value["source"] != "command"
        ):
            continue
        # Only extractor values (not defaults) contribute to this category.
        correct = name in params and value["value"] == params[name]
        measures.accepted_extractors = _ratio_add(
            measures.accepted_extractors, int(not correct), 1
        )
        if not correct and name not in params:
            measures.errors.append(_issue(record, name, "unspecified", value["value"]))


def threshold_curve(
    records: Sequence[EvalRecord], category: str
) -> list[ThresholdPoint]:
    """Error and coverage at every observed model confidence, without new calls."""
    observed: list[tuple[float, bool]] = []
    for record in records:
        expected = record["expected"]
        for decision in record["decisions"]:
            name = decision["name"]
            if (
                (category == "operation" and name != "operation")
                or (
                    category == "parameter"
                    and name in ("operation", "operation_answer")
                )
                or decision["confidence"] is None
            ):
                continue
            if category == "parameter" and (
                record.get("operation") != expected["operation"]
                or name
                not in record.get(
                    "applicable_parameters",
                    [*expected["params"], *expected["expect_clarify"]],
                )
            ):
                continue
            value = (
                expected["operation"]
                if category == "operation"
                else expected["params"].get(name, "unspecified")
            )
            observed.append((decision["confidence"], _correct_key(decision, value)))
    return [
        ThresholdPoint(
            threshold,
            Ratio(
                sum(
                    not correct
                    for confidence, correct in observed
                    if confidence >= threshold
                ),
                sum(confidence >= threshold for confidence, _ in observed),
            ),
            Ratio(
                sum(confidence >= threshold for confidence, _ in observed),
                len(observed),
            ),
        )
        for threshold in sorted({confidence for confidence, _ in observed})
    ]


def recommend_threshold(
    curve: Sequence[ThresholdPoint], target_error: float
) -> Recommendation:
    """Pick the smallest observed threshold satisfying the target error."""
    minimum_sample = ceil(1 / target_error)
    point = next(
        (
            point
            for point in curve
            if point.error.fraction is not None and point.error.fraction <= target_error
        ),
        None,
    )
    return Recommendation(
        point,
        point is not None and point.error.total < 1 / target_error,
        minimum_sample,
    )


def summarize(
    records: Sequence[EvalRecord], *, repeat: int = 1, target_error: float | None = None
) -> EvaluationSummary:
    """Aggregate all evaluated runs, plus breakdowns and optional recommendations."""
    by_operation: dict[str, list[EvalRecord]] = defaultdict(list)
    by_tag: dict[str, list[EvalRecord]] = defaultdict(list)
    ids_by_operation: dict[str, set[str]] = defaultdict(set)
    ids_by_tag: dict[str, set[str]] = defaultdict(set)
    for record in records:
        operation = record["expected"]["operation"]
        by_operation[operation].append(record)
        ids_by_operation[operation].add(record["id"])
        for tag in record["tags"]:
            by_tag[tag].append(record)
            ids_by_tag[tag].add(record["id"])
    curves = {
        category: threshold_curve(records, category)
        for category in ("operation", "parameter")
    }
    recommendations = (
        {
            category: recommend_threshold(points, target_error)
            for category, points in curves.items()
        }
        if target_error is not None
        else None
    )
    return EvaluationSummary(
        overall=_measure(records, repeat),
        by_operation={
            key: _measure(group, repeat) for key, group in sorted(by_operation.items())
        },
        by_tag={key: _measure(group, repeat) for key, group in sorted(by_tag.items())},
        curves=curves,
        recommendations=recommendations,
        command_counts={key: len(ids) for key, ids in sorted(ids_by_operation.items())},
        tag_counts={key: len(ids) for key, ids in sorted(ids_by_tag.items())},
        runs=len(records),
        commands=len({record["id"] for record in records}),
    )

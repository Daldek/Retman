"""Polish-language Markdown reporting of planning evaluations."""

import json
from collections.abc import Callable, Sequence
from typing import Any

from retman.eval.metrics import (
    ErrorCase,
    EvalRecord,
    EvaluationSummary,
    Measures,
    Ratio,
    Timing,
)
from retman.i18n.loader import Texts

_METRICS = (
    ("operation", "operation"),
    ("operation_in_scope", "operation_in_scope"),
    ("operation_out_of_scope", "operation_out_of_scope"),
    ("parameter", "parameter"),
    ("parameter_correct_automatic", "parameter_correct_automatic"),
    ("parameter_wrong_automatic", "parameter_wrong_automatic"),
    ("parameter_asked", "parameter_asked"),
    ("automatic_coverage", "automatic_coverage"),
    ("accepted_all", "accepted_all"),
    ("accepted_operation", "accepted_operation"),
    ("accepted_model_parameters", "accepted_model_parameters"),
    ("accepted_extractors", "accepted_extractors"),
    ("silent_guesses", "silent_guesses"),
    ("clarification", "clarification"),
    ("unnecessary_questions", "unnecessary_questions"),
    ("w03", "w03"),
    ("stability", "stability"),
)


def _number(number: int | float) -> str:
    return f"{number:.12g}".replace(".", ",")


def _rounded(number: float) -> str:
    """Fractions and seconds: two decimals are enough at tens of commands."""
    return f"{number:.2f}".replace(".", ",")


def _ratio(ratio: Ratio | None, texts: Texts) -> str:
    if ratio is None:
        return texts.get("eval.not_applicable")
    if ratio.fraction is None:
        return texts.get("eval.no_sample", count=ratio.count, total=ratio.total)
    return texts.get(
        "eval.fraction",
        fraction=_rounded(ratio.fraction),
        count=ratio.count,
        total=ratio.total,
    )


def _cell(value: Any) -> str:
    """Render a single Markdown table cell without breaking table layout."""
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return [
        "| " + " | ".join(map(_cell, headers)) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(_cell, row)) + " |" for row in rows),
    ]


def _measure_rows(measures: Measures, texts: Texts) -> list[list[str]]:
    return [
        [texts.get(f"eval.metric_{key}"), _ratio(getattr(measures, field), texts)]
        for key, field in _METRICS
        if field != "stability" or measures.stability is not None
    ]


def _group_rows(groups: dict[str, Measures], texts: Texts) -> list[list[str]]:
    return [
        [group, *row]
        for group, measures in groups.items()
        for row in _measure_rows(measures, texts)
    ]


def _timing(
    timing: Timing | None, texts: Texts, render: Callable[[float], str]
) -> list[str]:
    if timing is None:
        return [texts.get("eval.not_applicable")] * 3
    return [render(timing.median), render(timing.p90), render(timing.maximum)]


def _errors(errors: list[ErrorCase], texts: Texts) -> list[str]:
    if not errors:
        return [texts.get("eval.no_errors")]
    return [
        texts.get(
            "eval.error_line",
            id=_cell(error.id),
            repeat=error.repeat,
            command=_cell(error.command),
            field=_cell(error.field),
            expected=_cell(json.dumps(error.expected, ensure_ascii=False)),
            actual=_cell(json.dumps(error.actual, ensure_ascii=False)),
        )
        for error in errors
    ]


def render_report(
    summary: EvaluationSummary,
    records: Sequence[EvalRecord],
    texts: Texts,
    *,
    target_error: float | None = None,
) -> str:
    """Render a complete Markdown report without configuration paths or server URL."""
    environment = records[0]["environment"] if records else {}
    lines = [
        texts.get("eval.title"),
        "",
        texts.get("eval.configuration"),
        "",
        texts.get("eval.version", value=environment.get("retman", "")),
        texts.get(
            "eval.tools",
            value=", ".join(
                f"{name} {version}"
                for name, version in environment.get("tools", {}).items()
            ),
        ),
        texts.get("eval.backend", value=environment.get("backend", "")),
        texts.get("eval.model", value=environment.get("model", "")),
        texts.get("eval.confidence", value=environment.get("confidence", "")),
        texts.get(
            "eval.thresholds",
            operation=environment.get("thresholds", {}).get("operation", ""),
            parameter=environment.get("thresholds", {}).get("parameter", ""),
        ),
        "",
        texts.get("eval.dataset"),
        "",
        texts.get("eval.dataset_counts", commands=summary.commands, runs=summary.runs),
        "",
        texts.get("eval.dataset_operations"),
        *_table(
            [texts.get("eval.operation_column"), texts.get("eval.count_column")],
            [[key, str(count)] for key, count in summary.command_counts.items()],
        ),
        "",
        texts.get("eval.dataset_tags"),
        *_table(
            [texts.get("eval.tag_column"), texts.get("eval.count_column")],
            [[key, str(count)] for key, count in summary.tag_counts.items()],
        ),
        "",
        texts.get("eval.measures"),
        *_table(
            [texts.get("eval.metric_column"), texts.get("eval.value_column")],
            _measure_rows(summary.overall, texts),
        ),
        "",
        texts.get("eval.by_operation"),
        *_table(
            [
                texts.get("eval.operation_column"),
                texts.get("eval.metric_column"),
                texts.get("eval.value_column"),
            ],
            _group_rows(summary.by_operation, texts),
        ),
        "",
        texts.get("eval.by_tag"),
        *_table(
            [
                texts.get("eval.tag_column"),
                texts.get("eval.metric_column"),
                texts.get("eval.value_column"),
            ],
            _group_rows(summary.by_tag, texts),
        ),
        "",
        texts.get("eval.curves"),
    ]
    for category, curve in summary.curves.items():
        lines.extend(["", texts.get(f"eval.curve_{category}")])
        if curve:
            lines.extend(
                _table(
                    [
                        texts.get("eval.threshold_column"),
                        texts.get("eval.error_column"),
                        texts.get("eval.coverage_column"),
                    ],
                    [
                        [
                            _number(point.threshold),
                            _ratio(point.error, texts),
                            _ratio(point.coverage, texts),
                        ]
                        for point in curve
                    ],
                )
            )
        else:
            lines.append(texts.get("eval.no_confidences"))
    if target_error is not None and summary.recommendations is not None:
        lines.extend(
            ["", texts.get("eval.recommendations", target=_number(target_error))]
        )
        for category, recommendation in summary.recommendations.items():
            if recommendation.point is None:
                lines.append(
                    texts.get(
                        "eval.no_recommendation",
                        category=texts.get(f"eval.category_{category}"),
                    )
                )
            else:
                point = recommendation.point
                lines.append(
                    texts.get(
                        "eval.recommendation",
                        category=texts.get(f"eval.category_{category}"),
                        threshold=_number(point.threshold),
                        accepted=point.error.total,
                        total=point.coverage.total,
                        error=_ratio(point.error, texts),
                    )
                )
                if recommendation.insufficient:
                    lines.append(
                        texts.get(
                            "eval.small_sample",
                            category=texts.get(f"eval.category_{category}"),
                            accepted=point.error.total,
                            minimum=recommendation.minimum_sample,
                            target=_number(target_error),
                        )
                    )
    lines.extend(
        [
            "",
            texts.get("eval.errors"),
            *_errors(summary.overall.errors, texts),
            "",
            texts.get("eval.violations"),
            *_errors(summary.overall.violations, texts),
            "",
            texts.get("eval.timings"),
            *_table(
                [
                    texts.get("eval.group_column"),
                    texts.get("eval.plan_median_column"),
                    texts.get("eval.plan_p90_column"),
                    texts.get("eval.plan_max_column"),
                    texts.get("eval.queries_median_column"),
                    texts.get("eval.queries_p90_column"),
                    texts.get("eval.queries_max_column"),
                ],
                [
                    [
                        group,
                        *_timing(measures.plan_seconds, texts, _rounded),
                        *_timing(measures.model_queries, texts, _number),
                    ]
                    for group, measures in [
                        (texts.get("eval.all_group"), summary.overall),
                        *summary.by_operation.items(),
                        *summary.by_tag.items(),
                    ]
                ],
            ),
        ]
    )
    return "\n".join(lines) + "\n"

"""Consumer-visible plan-only evaluation, metrics and report behavior."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from error_documents import last_line_document

from retman.backends.base import Decision
from retman.config import Thresholds, init_config, load_config
from retman.eval.dataset import EvalCommand
from retman.eval.metrics import recommend_threshold, summarize, threshold_curve
from retman.eval.report import render_report
from retman.eval.runner import main, run_evaluation
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend

SHEET = "N-34-130-D-d-2-4"
AREA = {"type": "sheet", "code": SHEET}


def command(
    id: str,
    *,
    text: str | None = None,
    operation: str = "make_dem",
    params: dict[str, object] | None = None,
    clarify: list[str] | None = None,
    tags: list[str] | None = None,
) -> EvalCommand:
    return EvalCommand(
        id,
        text or f"Zrób NMT dla arkusza {SHEET}",
        operation,
        params if params is not None else {"area": AREA, "style": "raw"},
        clarify or [],
        tags or ["formal", "complete"],
        None,
    )


@pytest.fixture
def context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    monkeypatch.syspath_prepend(str(fixtures))
    from dummy_tool.manifest import MANIFEST

    operations = load_operations(
        "pl",
        manifests=[(MANIFEST, fixtures / "dummy_tool")],
        version_lookup=lambda _: "1.2.0",
    )
    config = load_config(init_config(tmp_path / "config.toml"))
    config = replace(
        config,
        decision=replace(
            config.decision,
            url="https://private.example.invalid/v1",
            model="fake-model",
            thresholds=Thresholds(0.8, 0.8),
        ),
    )
    return config, operations


def run_one(
    context, entry: EvalCommand, rules: dict[str, str | Decision], tmp_path: Path
):
    config, operations = context
    records, _ = run_evaluation(
        [entry],
        config,
        backend=FakeDecisionBackend(rules),
        operations=operations,
        temporary_dir=tmp_path,
    )
    return records[0]


def test_metrics_measure_decisions_values_questions_and_w03(context, tmp_path: Path):
    complete = run_one(
        context,
        command("correct"),
        {"make_dem": "make_dem", "raw": "raw"},
        tmp_path,
    )
    incomplete = run_one(
        context,
        command(
            "missing", params={"area": AREA}, clarify=["style"], tags=["incomplete"]
        ),
        {"make_dem": "make_dem"},
        tmp_path,
    )
    guess = run_one(
        context,
        command("guess", params={"area": AREA}, clarify=["style"], tags=["incomplete"]),
        {"make_dem": "make_dem", "raw": "raw"},
        tmp_path,
    )
    wrong = run_one(
        context,
        command("wrong"),
        {"make_dem": "make_dem", "smooth": "smooth"},
        tmp_path,
    )
    uncertain = run_one(
        context,
        command("uncertain"),
        {
            "make_dem": "make_dem",
            "smooth": Decision("smooth", {"smooth": 0.5}, 0.5, "logprobs"),
        },
        tmp_path,
    )
    violation = run_one(
        context,
        command(
            "violation", operation="out_of_scope", params={}, tags=["out_of_scope"]
        ),
        {"make_dem": "make_dem", "raw": "raw"},
        tmp_path,
    )
    rejected = run_one(
        context,
        command(
            "rejected",
            text="Czy jutro będzie padać?",
            operation="out_of_scope",
            params={},
            tags=["out_of_scope"],
        ),
        {},
        tmp_path,
    )
    records = [complete, incomplete, guess, wrong, uncertain, violation, rejected]
    measures = summarize(records).overall
    assert measures.operation == (type(measures.operation))(6, 7)
    assert measures.operation_in_scope == (type(measures.operation))(5, 5)
    assert measures.operation_out_of_scope == (type(measures.operation))(1, 2)
    assert measures.parameter == (type(measures.parameter))(6, 8)
    assert measures.automatic_coverage == (type(measures.automatic_coverage))(2, 3)
    assert measures.clarification == (type(measures.clarification))(1, 2)
    assert measures.unnecessary_questions == (type(measures.unnecessary_questions))(
        1, 7
    )
    assert measures.silent_guesses == (type(measures.silent_guesses))(1, 1)
    assert measures.w03 == (type(measures.w03))(1, 2)
    assert measures.accepted_operation == (type(measures.accepted_operation))(1, 7)
    assert measures.accepted_model_parameters == (
        type(measures.accepted_model_parameters)
    )(2, 3)
    assert measures.accepted_extractors == (type(measures.accepted_extractors))(0, 5)
    assert measures.accepted_all == (type(measures.accepted_all))(3, 15)
    assert {case.id for case in measures.violations} == {"violation"}
    # An uncertain value that Retman asked about is a cost, not an error case
    assert {case.id for case in measures.errors} == {"guess", "wrong", "violation"}
    assert measures.model_queries is not None and measures.model_queries.median == 2
    assert measures.plan_seconds is not None and measures.plan_seconds.maximum >= 0
    assert summarize(records).by_tag["out_of_scope"].w03.count == 1
    assert summarize(records).by_operation["make_dem"].silent_guesses.count == 1


def test_operation_question_answered_by_number_without_answering_parameters(
    context, tmp_path: Path
):
    unsure = Decision(
        "make_dem",
        {"make_dem": 0.4, "copy_dem": 0.3, "broken_dem": 0.2},
        0.4,
        "logprobs",
    )
    result = run_one(
        context,
        command(
            "question", params={"area": AREA}, clarify=["style"], tags=["incomplete"]
        ),
        {"make_dem": unsure},
        tmp_path,
    )
    assert result["operation_question"]["asked"]
    assert "make_dem" in result["operation_question"]["offered"]
    assert result["operation_offered"] is True
    assert result["operation"] == "make_dem"
    assert result["questions"] == ["style"]
    assert result["question_details"] == [{"name": "style", "type": "choice"}]
    assert result["model_queries"] == 2
    assert result["values"]["area"] == {"value": AREA, "source": "command"}
    assert summarize([result]).overall.accepted_operation.total == 0

    not_offered = Decision(
        "copy_dem",
        {"copy_dem": 0.4, "broken_dem": 0.3, "escape_dem": 0.2},
        0.4,
        "logprobs",
    )
    missing = run_one(
        context, command("not-offered"), {"copy_dem": not_offered}, tmp_path
    )
    assert missing["operation_offered"] is False
    assert missing["operation"] is None
    assert missing["questions"] == ["operation"]
    assert missing["model_queries"] == 1
    assert summarize([missing]).overall.parameter.total == 0

    # Asking about the operation makes an otherwise complete plan nonautomatic.
    answered_complete = {
        **result,
        "expected": {
            "operation": "make_dem",
            "params": {"area": AREA},
            "expect_clarify": [],
        },
        "tags": ["complete"],
        "questions": [],
    }
    assert summarize([answered_complete]).overall.automatic_coverage.fraction == 0


def test_default_parameter_question_is_unnecessary(context, tmp_path: Path):
    record = run_one(
        context,
        command("default", params={"area": AREA, "style": "smooth"}),
        {
            "make_dem": "make_dem",
            "smooth": "smooth",
            "unspecified": Decision(
                "unspecified", {"unspecified": 0.5}, 0.5, "logprobs"
            ),
        },
        tmp_path,
    )
    assert record["questions"] == ["detail"]
    assert summarize([record]).overall.unnecessary_questions.count == 1

    accepted = run_one(
        context,
        command("default-accepted", params={"area": AREA, "style": "smooth"}),
        {"make_dem": "make_dem", "smooth": "smooth"},
        tmp_path,
    )
    assert accepted["values"]["detail"] == {"value": "high", "source": "default"}
    assert accepted["questions"] == []
    assert summarize([accepted]).overall.accepted_model_parameters.count == 0


def test_confidence_curve_recommendation_stability_and_timing(context, tmp_path: Path):
    config, operations = context
    entries = [command("repeat"), command("other", text="NMT z arkusza " + SHEET)]
    backend = FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"})
    records, summary = run_evaluation(
        entries,
        config,
        backend=backend,
        operations=operations,
        repeat=2,
        target_error=0.01,
        temporary_dir=tmp_path,
    )
    assert [record["repeat"] for record in records] == [0, 1, 0, 1]
    assert summary.overall.stability is not None
    assert summary.overall.stability.fraction == 1
    assert summary.recommendations is not None
    assert summary.recommendations["operation"].insufficient
    assert summary.recommendations["operation"].minimum_sample == 100
    # Build known confidences and decisions, then confirm the full threshold curve.
    scored = [
        {
            **records[0],
            "decisions": [
                {
                    "name": "operation",
                    "key": "make_dem",
                    "confidence": 0.5,
                    "method": "logprobs",
                    "probabilities": {"make_dem": 0.5},
                },
                {
                    "name": "style",
                    "key": "raw",
                    "confidence": 0.7,
                    "method": "logprobs",
                    "probabilities": {"raw": 0.7},
                },
            ],
        },
        {
            **records[1],
            "decisions": [
                {
                    "name": "operation",
                    "key": "copy_dem",
                    "confidence": 0.6,
                    "method": "logprobs",
                    "probabilities": {"copy_dem": 0.6},
                },
                {
                    "name": "style",
                    "key": "smooth",
                    "confidence": 0.9,
                    "method": "logprobs",
                    "probabilities": {"smooth": 0.9},
                },
            ],
        },
        {
            **records[2],
            "decisions": [
                {
                    "name": "operation",
                    "key": "make_dem",
                    "confidence": 0.9,
                    "method": "logprobs",
                    "probabilities": {"make_dem": 0.9},
                },
            ],
        },
    ]
    curve = threshold_curve(scored, "operation")
    assert [
        (p.threshold, p.error.count, p.error.total, p.coverage.total) for p in curve
    ] == [(0.5, 1, 3, 3), (0.6, 1, 2, 3), (0.9, 0, 1, 3)]
    recommendation = recommend_threshold(curve, 0.01)
    assert recommendation.point is not None
    assert recommendation.point.threshold == 0.9
    assert recommendation.insufficient
    param_curve = threshold_curve(scored, "parameter")
    assert [(p.threshold, p.error.count, p.error.total) for p in param_curve] == [
        (0.7, 1, 2),
        (0.9, 1, 1),
    ]
    assert recommend_threshold(param_curve, 0.01).point is None
    assert summary.overall.model_queries is not None
    assert summary.overall.model_queries.p90 == 2
    changing = [
        records[0],
        {
            **records[1],
            "decisions": [
                {**records[1]["decisions"][0], "key": "copy_dem"},
                *records[1]["decisions"][1:],
            ],
        },
    ]
    stability = summarize(changing, repeat=2).overall.stability
    assert stability is not None and stability.fraction == 0


def test_metric_breakdown_marks_wrong_extractor_and_bool_decisions(
    context, tmp_path: Path
):
    good = run_one(
        context,
        command("synthetic"),
        {"make_dem": "make_dem", "raw": "raw"},
        tmp_path,
    )
    wrong = {
        **good,
        "expected": {
            "operation": "make_dem",
            "params": {"area": AREA, "style": True},
            "expect_clarify": [],
        },
        "values": {
            "area": {
                "value": {**AREA, "code": "N-34-130-D-d-2-3"},
                "source": "command",
            },
            "style": {"value": False, "source": "command"},
        },
        "decisions": [
            good["decisions"][0],
            {**good["decisions"][1], "key": "no", "confidence": 0.6},
        ],
    }
    measures = summarize([wrong]).overall
    assert measures.parameter.fraction == 0
    assert measures.accepted_operation.count == 0
    assert measures.accepted_model_parameters.count == 1
    assert measures.accepted_extractors.count == 1
    assert measures.accepted_all.fraction == 2 / 3
    assert {case.field for case in measures.errors} == {"area", "style"}


def test_isolation_report_privacy_and_no_handler_calls(
    context, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from dummy_tool import handlers

    monkeypatch.setattr(
        handlers, "make_dem", lambda *args, **kwargs: pytest.fail("handler called")
    )
    config, operations = context
    output = tmp_path / "temp-projects"
    output.mkdir()
    before = set(tmp_path.iterdir())
    records, summary = run_evaluation(
        [command("isolation")],
        config,
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        operations=operations,
        target_error=0.01,
        temporary_dir=output,
    )
    assert set(tmp_path.iterdir()) == before
    assert list(output.iterdir()) == []
    assert records[0]["outcome"] == "plan"
    report = render_report(summary, records, load_core_texts("pl"), target_error=0.01)
    raw = json.dumps(records, ensure_ascii=False)
    for content in (raw, report):
        assert config.decision.url not in content
        assert str(tmp_path) not in content
    assert "## Miary" in report
    assert "## Krzywe progów" in report
    assert "zbiór jest za mały" in report
    assert "2/2" in report


def test_cli_invalid_config_and_args_exit_with_registry_codes_and_no_partial_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    output = tmp_path / "raw.jsonl"
    assert (
        main(["--config", str(tmp_path / "absent.toml"), "--output", str(output)]) == 3
    )
    assert not output.exists()
    assert main([]) == 2
    assert main(["--config", "x", "--repeat", "0"]) == 2
    assert main(["--config", "x", "--bad-option"]) == 2
    captured = capsys.readouterr()
    assert "Błąd" not in captured.out
    document = last_line_document(captured.err)
    assert (document["code"], document["details"]["reason"]) == (
        "validation_error",
        "usage",
    )


@pytest.fixture
def crowded_context(context):
    """Twelve operations in three categories: recognition needs two questions."""
    from dummy_tool.crowded import crowded_operations

    config, operations = context
    layout = {"a": 3, "b": 3, "c": 3, "d": 3}
    return config, crowded_operations(operations["broken_dem"], layout)


def test_two_stage_recognition_records_both_decisions(crowded_context, tmp_path: Path):
    entry = command("two-stage", operation="b_2", params={})

    record = run_one(crowded_context, entry, {"b": "b", "b_2": "b_2"}, tmp_path)

    assert record["operation"] == "b_2"
    assert [d["name"] for d in record["decisions"]] == ["category", "operation"]
    assert record["model_queries"] == 2
    assert not record["category_question"]["asked"]
    measures = summarize([record]).overall
    assert measures.operation.count == 1 and measures.accepted_operation.count == 0


def test_unsure_category_is_answered_with_the_expected_operations_group(
    crowded_context, tmp_path: Path
):
    unsure = Decision("c", {"c": 0.4, "b": 0.3, "a": 0.2}, 0.4, "logprobs")
    entry = command("category-question", operation="b_2", params={})

    record = run_one(crowded_context, entry, {"c": unsure, "b_2": "b_2"}, tmp_path)

    assert record["category_question"] == {"asked": True, "offered": ["c", "b", "a"]}
    assert record["operation"] == "b_2" and record["operation_offered"] is None
    # The user was asked, so nothing was accepted without asking (W-02)
    assert summarize([record]).overall.accepted_operation.total == 0

    not_offered = Decision("c", {"c": 0.4, "a": 0.3, "d": 0.2}, 0.4, "logprobs")
    entry = command("category-missing", operation="b_2", params={})
    missing = run_one(crowded_context, entry, {"c": not_offered}, tmp_path)

    assert missing["category_question"]["asked"]
    assert missing["operation_offered"] is False and missing["operation"] is None
    assert missing["questions"] == ["category"]


def test_command_refused_after_the_category_still_counts_as_out_of_scope(
    crowded_context, tmp_path: Path
):
    entry = command(
        "refused", operation="out_of_scope", params={}, tags=["out_of_scope"]
    )

    record = run_one(
        crowded_context, entry, {"b": "b", "out_of_scope": "out_of_scope"}, tmp_path
    )

    assert record["outcome"] == "out_of_scope"
    assert [(d["name"], d["key"]) for d in record["decisions"]] == [
        ("category", "b"),
        ("operation", "out_of_scope"),
    ]
    measures = summarize([record]).overall
    assert measures.operation_out_of_scope.count == 1 and measures.w03.count == 0

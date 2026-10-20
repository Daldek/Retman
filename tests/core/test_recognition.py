"""Recognition by category, then operation, when one question cannot offer all."""

import pytest

from retman.backends.base import Decision
from retman.config import Thresholds
from retman.exceptions import OutOfScopeError


@pytest.fixture
def crowded(create_app):
    """Twelve operations without parameters in three categories of four."""
    from dummy_tool.crowded import crowded_operations

    template = create_app().operations["broken_dem"]
    return crowded_operations(template, {"a": 4, "b": 4, "c": 4})


def test_model_chooses_a_category_then_an_operation_of_it(create_app, crowded):
    app = create_app({"b": "b", "b_2": "b_2"}, operations_override=crowded)

    plan = app.plan("Zrób coś z grupy b")

    assert plan.operation == "b_2" and plan.operation_label == "Operacja b_2"
    first, second = app.backend.calls
    # Each question offers few options: the categories, then the category's own
    assert first[2] == {
        "a": "Opis grupy a",
        "b": "Opis grupy b",
        "c": "Opis grupy c",
        "out_of_scope": "Żadna z dostępnych operacji",
    }
    assert list(second[2]) == ["b_0", "b_1", "b_2", "b_3", "out_of_scope"]
    assert [d["name"] for d in plan.decisions] == ["category", "operation"]
    assert not plan.questions


def test_a_command_outside_every_category_is_out_of_scope_at_once(create_app, crowded):
    app = create_app({"out_of_scope": "out_of_scope"}, operations_override=crowded)

    with pytest.raises(OutOfScopeError) as error:
        app.plan("Jaka będzie pogoda?")

    # The user is told what groups exist; no second question was spent
    assert error.value.operations == ["Grupa a", "Grupa b", "Grupa c"]
    assert [d["name"] for d in error.value.decisions] == ["category"]
    assert len(app.backend.calls) == 1
    event = app.journal.entries()[-1]
    assert (
        event["event"] == "out_of_scope"
        and event["decisions"][0]["key"] == "out_of_scope"
    )


def test_out_of_scope_stays_possible_inside_the_category(create_app, crowded):
    # The model sees a group it likes but none of its operations fits
    app = create_app(
        {"b": "b", "out_of_scope": "out_of_scope"}, operations_override=crowded
    )

    with pytest.raises(OutOfScopeError) as error:
        app.plan("Prawie grupa b, ale nie to")

    assert [(d["name"], d["key"]) for d in error.value.decisions] == [
        ("category", "b"),
        ("operation", "out_of_scope"),
    ]


def test_unsure_category_asks_the_user_and_then_decides_the_operation(
    create_app, crowded
):
    unsure = Decision("b", {"b": 0.4, "c": 0.3, "a": 0.2}, 0.4, "logprobs")
    app = create_app(
        {"b": unsure, "b_2": "b_2"},
        thresholds=Thresholds(operation=0.8, parameter=0.8),
        operations_override=crowded,
    )

    plan = app.plan("Coś z grupy b albo c")
    (question,) = plan.questions
    chosen = plan.answer("category", "1")

    assert question.name == "category"
    assert [option.label for option in question.options] == [
        "Grupa b",
        "Grupa c",
        "Grupa a",
    ]
    # The operation is then decided among the chosen category's operations only
    assert chosen.operation == "b_2" and chosen.questions == []
    assert list(app.backend.calls[-1][2]) == [
        "b_0",
        "b_1",
        "b_2",
        "b_3",
        "out_of_scope",
    ]


def test_unsure_operation_offers_candidates_of_the_category_only(create_app, crowded):
    app = create_app(
        {"b": "b", "b_1": "b_1"},
        confidence=0.3,
        thresholds=Thresholds(operation=0.8, parameter=0.8),
        operations_override=crowded,
    )

    plan = app.plan("Coś z grupy b")
    by_category = plan.answer("category", "1")
    final = by_category.answer("operation", "1")

    assert [q.name for q in plan.questions] == ["category"]
    (question,) = by_category.questions
    assert question.name == "operation"
    assert {option.key for option in question.options} <= {"b_0", "b_1", "b_2", "b_3"}
    assert final.operation is not None and final.operation.startswith("b_")
    assert final.questions == []


def test_few_operations_are_recognized_in_one_question(create_app):
    app = create_app({"make_dem": "make_dem"})

    plan = app.plan("Zrób NMT")

    # All operations (and "out of scope") in the first and only recognition question
    assert plan.decisions[0]["name"] == "operation"
    assert "category" not in [d["name"] for d in plan.decisions]
    assert len(app.backend.calls[0][2]) == len(app.operations) + 1

"""Behavioral tests for the offline decision backend."""

import pytest

from retman.backends.base import Decision
from retman.testing import FakeDecisionBackend


def test_choose_follows_rule_insertion_order_not_option_order():
    # Arrange
    fake = FakeDecisionBackend({"second": "second", "first": "first"}, confidence=0.4)
    options = {"first": "Pierwsza", "second": "Druga"}

    # Act
    decision = fake.choose("Pobierz NMT", "Która operacja?", options)

    # Assert
    assert decision.key == "second"
    assert decision.confidence == 0.4
    assert decision.probabilities == {"second": 0.4}
    assert decision.confidence_method == "basal"
    assert fake.calls == [("Pobierz NMT", "Która operacja?", options)]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (
            {"unknown": "Nieznane", "unspecified": "Brak", "out_of_scope": "Poza"},
            "unspecified",
        ),
        ({"unknown": "Nieznane", "out_of_scope": "Poza"}, "out_of_scope"),
    ],
)
def test_choose_uses_explicit_fallback_only_if_offered(
    options: dict[str, str], expected: str
):
    fake = FakeDecisionBackend()
    decision = fake.choose("polecenie", "pytanie", options)
    assert decision.key == expected


def test_choose_rejects_unmatched_options_without_fallback():
    fake = FakeDecisionBackend()
    with pytest.raises(AssertionError):
        fake.choose("polecenie", "pytanie", {"sheet": "Arkusz"})


def test_choose_preserves_preconfigured_low_confidence_decision():
    # Arrange
    provided = Decision(
        "cutout",
        probabilities={"cutout": 0.35, "sheet": 0.65},
        confidence=0.35,
        confidence_method="consistency",
        model="configured",
    )
    fake = FakeDecisionBackend({"cutout": provided})

    # Act
    result = fake.choose(
        "polecenie", "pytanie", {"cutout": "Wycinek", "sheet": "Arkusz"}
    )

    # Assert
    assert result is provided


def test_yes_no_uses_first_matching_question_substring_and_defaults_to_no():
    fake = FakeDecisionBackend(
        {"unused": "unused"}, yes_no={"NMT": "yes", "arkusz": "no"}
    )
    selected = fake.yes_no("polecenie", "Czy NMT dotyczy arkusza?")
    absent = fake.yes_no("polecenie", "Czy chodzi o dane?")
    assert selected.key == "yes"
    assert absent.key == "no"
    assert fake.calls == [
        ("polecenie", "Czy NMT dotyczy arkusza?", {"yes": "yes", "no": "no"}),
        ("polecenie", "Czy chodzi o dane?", {"yes": "yes", "no": "no"}),
    ]

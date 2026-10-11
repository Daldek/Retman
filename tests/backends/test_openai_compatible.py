"""Offline replay tests for the OpenAI-compatible decision backend."""

import json
import math
from pathlib import Path

import httpx
import pytest

from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.config import ConfidenceSetting, DecisionConfig, Thresholds
from retman.exceptions import (
    BackendConnectionError,
    BackendError,
    InvalidModelAnswerError,
)
from retman.i18n.loader import load_core_texts

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "openai_compatible"
OPTIONS = {
    "a_sheet": "Pobierz NMT dla arkusza mapy",
    "b_cutout": "Pobierz wycinek NMT dla prostokąta",
    "c_out_of_scope": "Żadna z powyższych operacji",
}


def _response(name: str) -> httpx.Response:
    return httpx.Response(200, content=(FIXTURES / name).read_bytes())


def _config(
    confidence: ConfidenceSetting = "auto",
    consistency_runs: int = 3,
    api_key_env: str | None = None,
) -> DecisionConfig:
    return DecisionConfig(
        backend="openai_compatible",
        url="http://127.0.0.1:1234/v1",
        model="bielik-11b-v3.0-instruct-mlx",
        timeout_s=7,
        thresholds=Thresholds(operation=0.6, parameter=0.6),
        api_key_env=api_key_env,
        confidence=confidence,
        consistency_runs=consistency_runs,
    )


def test_choose_logprobs_normalizes_option_token_scores():
    # Arrange
    requests: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response("bielik_11b_enum_logprobs.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("logprobs"), load_core_texts("pl"), client
        )
        # Act
        decision = backend.choose(
            "Pobierz NMT dla arkusza N-34-130-D-d-2-4", "Co zrobić?", OPTIONS
        )

    # Assert: the fixture contains scores -0.011894..., -4.511894..., -7.074394...
    assert decision.key == "a_sheet"
    assert decision.confidence_method == "logprobs"
    assert decision.model == "bielik-11b-v3.0-instruct-mlx"
    assert math.isclose(sum(decision.probabilities.values()), 1.0)
    assert decision.confidence is not None
    assert math.isclose(
        decision.confidence,
        1 / (1 + math.exp(-4.5) + math.exp(-7.0625)),
        rel_tol=1e-6,
    )
    assert decision.probabilities["a_sheet"] > decision.probabilities["b_cutout"]
    payload = json.loads(requests[0].content)
    assert payload["response_format"]["json_schema"]["schema"]["enum"] == [
        "A",
        "B",
        "C",
    ]
    assert payload["top_logprobs"] == len(OPTIONS)
    assert requests[0].extensions["timeout"]["read"] == 7


def test_choose_logprobs_picks_most_probable_option_not_sampled_token():
    # Arrange: the server sampled the unlikely "B" while "A" dominates the
    # distribution (seen live with LM Studio's default temperature).
    body = json.loads((FIXTURES / "bielik_11b_enum_logprobs.json").read_text())
    choice = body["choices"][0]
    choice["message"]["content"] = "B"
    token = choice["logprobs"]["content"][0]
    token["token"], token["logprob"], token["bytes"] = "B", -4.511894226074219, [66]
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=body))

    with httpx.Client(transport=transport) as client:
        backend = OpenAICompatibleBackend(
            _config("logprobs"), load_core_texts("pl"), client
        )
        # Act
        decision = backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)

    # Assert: key and confidence describe the same, most probable option
    assert decision.key == "a_sheet"
    assert decision.confidence == max(decision.probabilities.values())


def test_choose_logprobs_rejects_incomplete_option_scores():
    # Arrange: the saved answer is valid, but one alternative is missing.
    body = json.loads((FIXTURES / "bielik_11b_enum_logprobs.json").read_text())
    alternatives = body["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    body["choices"][0]["logprobs"]["content"][0]["top_logprobs"] = alternatives[:-1]
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=body))

    with httpx.Client(transport=transport) as client:
        backend = OpenAICompatibleBackend(
            _config("logprobs"), load_core_texts("pl"), client
        )
        # Act / Assert: do not silently assign probability zero to an unseen option.
        with pytest.raises(BackendError, match="option token logprobs"):
            backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)


def test_choose_consistency_votes_for_majority_across_shuffled_options():
    # Arrange: both the A and B samples were captured from live Bielik responses.
    replies = iter(
        ("bielik_11b_enum.json", "bielik_4_5b_enum.json", "bielik_11b_enum.json")
    )
    sent: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return _response(next(replies))

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("consistency"), load_core_texts("pl"), client
        )
        # Act
        decision = backend.choose(
            "Pobierz NMT dla arkusza",
            "Która operacja?",
            dict(reversed(list(OPTIONS.items()))),
        )

    # Assert
    assert decision.key == "a_sheet"
    assert decision.confidence_method == "consistency"
    assert decision.confidence == pytest.approx(2 / 3)
    assert decision.probabilities == {
        "a_sheet": pytest.approx(2 / 3),
        "b_cutout": pytest.approx(1 / 3),
        "c_out_of_scope": 0.0,
    }
    assert len(sent) == 3
    user_prompt = json.loads(sent[0].content)["messages"][1]["content"]
    assert user_prompt.index("A — a_sheet") < user_prompt.index("B — b_cutout")


def test_choose_auto_falls_back_to_configured_consistency_when_logprobs_missing():
    # Arrange
    sent: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return _response("bielik_11b_enum.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("auto", consistency_runs=3), load_core_texts("pl"), client
        )
        # Act
        decision = backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)

    # Assert: first answer is also the first vote, not a discarded probe.
    assert decision.key == "a_sheet"
    assert decision.confidence_method == "consistency"
    assert decision.confidence == 1.0
    assert len(sent) == 3
    assert "logprobs" in json.loads(sent[0].content)
    assert all("logprobs" not in json.loads(request.content) for request in sent[1:])


def test_choose_none_does_not_report_a_fake_confidence():
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: _response("bielik_11b_enum.json"))
    ) as client:
        backend = OpenAICompatibleBackend(
            _config("none"), load_core_texts("pl"), client
        )
        decision = backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)
    assert decision.key == "a_sheet"
    assert decision.confidence is None
    assert decision.probabilities == {}
    assert decision.confidence_method == "none"


def test_choose_rejects_malformed_structured_answer_without_hidden_retry():
    sent: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return _response("bielik_11b_both.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("logprobs"), load_core_texts("pl"), client
        )
        with pytest.raises(InvalidModelAnswerError):
            backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)
    assert len(sent) == 1


def test_choose_wraps_timeout_and_preserves_exception_chain():
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("expired", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as client:
        backend = OpenAICompatibleBackend(_config(), load_core_texts("pl"), client)
        with pytest.raises(BackendConnectionError) as caught:
            backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)
    assert isinstance(caught.value.__cause__, httpx.ReadTimeout)
    assert caught.value.url == backend.url


def test_choose_uses_api_key_from_environment(monkeypatch: pytest.MonkeyPatch):
    # Arrange
    monkeypatch.setenv("RETMAN_TEST_MODEL_TOKEN", "secret-in-environment")
    observed: list[str | None] = []

    def replay(request: httpx.Request) -> httpx.Response:
        observed.append(request.headers.get("Authorization"))
        return _response("bielik_11b_enum.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("none", api_key_env="RETMAN_TEST_MODEL_TOKEN"),
            load_core_texts("pl"),
            client,
        )
        # Act
        backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)

    # Assert
    assert observed == ["Bearer secret-in-environment"]


def test_choose_falls_back_to_validated_plain_text_if_schema_unsupported():
    # Arrange
    sent: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if len(sent) == 1:
            return httpx.Response(
                400,
                json={"error": {"param": "response_format", "message": "Unsupported"}},
            )
        return _response("bielik_11b_plain.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("none"), load_core_texts("pl"), client
        )
        # Act
        decision = backend.choose("Pobierz NMT", "Która operacja?", OPTIONS)

    # Assert
    assert decision.key == "a_sheet"
    assert "response_format" in json.loads(sent[0].content)
    assert "response_format" not in json.loads(sent[1].content)


def test_yes_no_uses_translated_options_from_core_texts():
    sent: list[httpx.Request] = []

    def replay(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return _response("bielik_11b_enum.json")

    with httpx.Client(transport=httpx.MockTransport(replay)) as client:
        backend = OpenAICompatibleBackend(
            _config("none"), load_core_texts("pl"), client
        )
        decision = backend.yes_no("Pobierz NMT", "Czy chodzi o arkusz?")
    assert decision.key == "no"  # canonical order: A = no, B = yes
    prompt = json.loads(sent[0].content)["messages"][1]["content"]
    assert "A — no: Nie" in prompt
    assert "B — yes: Tak" in prompt

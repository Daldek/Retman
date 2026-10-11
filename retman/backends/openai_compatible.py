"""Decision backend for servers implementing the OpenAI chat completions API."""

import json
import math
import os
from collections import Counter
from typing import Any

import httpx

from retman.backends.base import Decision
from retman.config import DecisionConfig
from retman.exceptions import (
    BackendConnectionError,
    BackendError,
    InvalidModelAnswerError,
)
from retman.i18n.loader import Texts


class OpenAICompatibleBackend:
    """Choose from a closed set of options through an OpenAI-compatible server.

    Parameters
    ----------
    config : DecisionConfig
        Decision model, server address, timeout and confidence method.
    texts : Texts
        Model-facing questions and instructions in the command language.
    client : httpx.Client | None, optional
        Shared HTTP client; useful for offline tests with ``MockTransport``.
    """

    def __init__(
        self,
        config: DecisionConfig,
        texts: Texts,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._texts = texts
        self._client = client if client is not None else httpx.Client()
        self._owns_client = client is None
        self._schema_supported: bool | None = None
        self._logprobs_supported: bool | None = None

    @property
    def url(self) -> str:
        """Configured base URL of the model server."""
        return self._config.url

    @property
    def model(self) -> str:
        """Configured model identifier."""
        return self._config.model

    def close(self) -> None:
        """Close the HTTP client when this backend created it."""
        if self._owns_client:
            self._client.close()

    def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        """Choose one option and estimate its confidence as configured.

        Parameters
        ----------
        state : str
            User command and context.
        question : str
            Question translated into the user's language.
        options : dict[str, str]
            Allowed identifiers and translated descriptions.

        Returns
        -------
        Decision
            Chosen identifier and optionally normalized probabilities.
        """
        if not options:
            raise ValueError("options must not be empty")
        if len(options) > 10:
            raise ValueError("choose supports at most ten options")
        if self._config.confidence is None or self._config.consistency_runs is None:
            raise ValueError(
                "openai_compatible requires confidence and consistency_runs"
            )

        # A stable key-to-letter mapping makes shuffled input dictionaries equivalent.
        keys = sorted(options)
        letters = {chr(ord("A") + i): key for i, key in enumerate(keys)}
        option_lines = "\n".join(
            f"{letter} — {key}: {options[key]}" for letter, key in letters.items()
        )
        messages = [
            {"role": "system", "content": self._texts.get("backends.system")},
            {
                "role": "user",
                "content": self._texts.get(
                    "backends.decision",
                    state=state,
                    question=question,
                    options=option_lines,
                ),
            },
        ]
        method = self._config.confidence
        first_letter, first_response = self._request(
            messages, letters, method in ("auto", "logprobs")
        )
        selected = letters[first_letter]
        model = first_response.get("model")
        reported_model = model if isinstance(model, str) else self.model

        if method == "none":
            return Decision(selected, model=reported_model)

        if method in ("logprobs", "auto"):
            scores = _letter_probabilities(first_response, first_letter, letters)
            if scores is not None:
                probabilities = {
                    letters[letter]: share for letter, share in scores.items()
                }
                # The server samples the answer token; the decision is the most
                # probable option, so the reported key and confidence agree
                best = max(probabilities, key=lambda key: probabilities[key])
                return Decision(
                    best,
                    probabilities=probabilities,
                    confidence=probabilities[best],
                    confidence_method="logprobs",
                    model=reported_model,
                )
            self._logprobs_supported = False
            if method == "logprobs":
                raise BackendError(
                    self.url, "model did not return option token logprobs"
                )

        votes = Counter([first_letter])
        for _ in range(self._config.consistency_runs - 1):
            letter, _ = self._request(messages, letters, want_logprobs=False)
            votes[letter] += 1
        # If votes tie, preserve the first answer and its low confidence for the caller.
        winner = max(
            letters, key=lambda letter: (votes[letter], letter == first_letter)
        )
        probabilities = {
            key: votes[letter] / self._config.consistency_runs
            for letter, key in letters.items()
        }
        return Decision(
            letters[winner],
            probabilities=probabilities,
            confidence=probabilities[letters[winner]],
            confidence_method="consistency",
            model=reported_model,
        )

    def yes_no(self, state: str, question: str) -> Decision:
        """Choose between translated yes and no descriptions."""
        return self.choose(
            state,
            question,
            {
                "yes": self._texts.get("backends.yes"),
                "no": self._texts.get("backends.no"),
            },
        )

    def _request(
        self,
        messages: list[dict[str, str]],
        letters: dict[str, str],
        want_logprobs: bool,
    ) -> tuple[str, dict[str, Any]]:
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "decision_key",
                "strict": True,
                "schema": {"type": "string", "enum": list(letters)},
            },
        }
        use_schema = self._schema_supported is not False
        use_logprobs = want_logprobs and self._logprobs_supported is not False
        while True:
            payload: dict[str, Any] = {"model": self.model, "messages": messages}
            if use_schema:
                payload["response_format"] = schema
            if use_logprobs:
                payload["logprobs"] = True
                payload["top_logprobs"] = len(letters)
            headers: dict[str, str] = {}
            if self._config.api_key_env:
                api_key = os.environ.get(self._config.api_key_env)
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            endpoint = f"{self.url.rstrip('/')}/chat/completions"
            try:
                response = self._client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._config.timeout_s,
                )
            except httpx.RequestError as err:
                raise BackendConnectionError(self.url) from err
            if response.status_code in (400, 422):
                if use_schema and _unsupported_field(
                    response, "response_format", "json_schema"
                ):
                    self._schema_supported = False
                    use_schema = False
                    continue
                if use_logprobs and _unsupported_field(response, "logprobs"):
                    self._logprobs_supported = False
                    if self._config.confidence == "logprobs":
                        raise BackendError(self.url, "server does not support logprobs")
                    use_logprobs = False
                    continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as err:
                raise BackendError(self.url, f"HTTP {response.status_code}") from err
            try:
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                content = message["content"]
            except (ValueError, KeyError, IndexError, TypeError) as err:
                raise InvalidModelAnswerError(self.url) from err
            if not isinstance(content, str):
                raise InvalidModelAnswerError(self.url)
            answer = content.strip()
            if answer not in letters:
                try:
                    parsed = json.loads(answer)
                except ValueError as err:
                    raise InvalidModelAnswerError(self.url) from err
                if not isinstance(parsed, str) or parsed not in letters:
                    raise InvalidModelAnswerError(self.url)
                answer = parsed
            if not isinstance(data, dict):
                raise InvalidModelAnswerError(self.url)
            return answer, data


def _unsupported_field(response: httpx.Response, *field_names: str) -> bool:
    """Distinguish a missing server feature from unrelated 400 responses."""
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        return False
    if not isinstance(error, dict):
        return False
    detail = f"{error.get('param', '')} {error.get('message', '')}".lower()
    return any(name in detail for name in field_names)


def _letter_probabilities(
    response: dict[str, Any], chosen: str, letters: dict[str, str]
) -> dict[str, float] | None:
    """Normalize scores only if every option has a scored single-token alternative."""
    try:
        tokens = response["choices"][0]["logprobs"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(tokens, list):
        return None
    relevant = [
        token
        for token in tokens
        if isinstance(token, dict) and _letter_token(token.get("token")) == chosen
    ]
    if len(relevant) != 1:
        return None
    token = relevant[0]
    log_scores: dict[str, float] = {}
    for alternative in token.get("top_logprobs") or []:
        if not isinstance(alternative, dict):
            continue
        letter = _letter_token(alternative.get("token"))
        score = alternative.get("logprob")
        if (
            letter in letters
            and isinstance(score, (float, int))
            and math.isfinite(score)
        ):
            log_scores[letter] = max(log_scores.get(letter, -math.inf), score)
    chosen_score = token.get("logprob")
    if isinstance(chosen_score, (float, int)) and math.isfinite(chosen_score):
        log_scores[chosen] = chosen_score
    if set(log_scores) != set(letters):
        return None
    max_score = max(log_scores.values())
    weights = {
        letter: math.exp(score - max_score) for letter, score in log_scores.items()
    }
    total = sum(weights.values())
    return {letter: weights.get(letter, 0.0) / total for letter in letters}


def _letter_token(value: Any) -> str | None:
    """Read a single response option from its token, with optional JSON quotes."""
    if not isinstance(value, str):
        return None
    return value.strip(' \t\r\n"')

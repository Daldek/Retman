"""Deterministic backend for offline Retman tests."""

from retman.backends.base import Decision


class FakeDecisionBackend:
    """Return programmed decisions without a model service.

    Parameters
    ----------
    rules : dict[str, str | Decision] | None, optional
        Ordered candidate option keys. The first key present in ``options`` wins;
        a supplied ``Decision`` is returned unchanged.
    yes_no : dict[str, str] | None, optional
        Question substrings mapped to ``"yes"`` or ``"no"``, in insertion order.
    confidence : float, optional
        Confidence used for synthesized choices, by default 1.0.
    """

    url = "fake://"
    model = "fake"

    def __init__(
        self,
        rules: dict[str, str | Decision] | None = None,
        yes_no: dict[str, str] | None = None,
        confidence: float = 1.0,
    ) -> None:
        self.rules = rules or {}
        self.yes_no_rules = yes_no or {}
        self.confidence = confidence
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        """Take the first programmed option key, or an explicit fallback option."""
        self.calls.append((state, question, dict(options)))
        for key, decision in self.rules.items():
            if key in options:
                if isinstance(decision, Decision):
                    return decision
                return self._decision(key)
        for fallback in ("unspecified", "out_of_scope"):
            if fallback in options:
                return self._decision(fallback)
        raise AssertionError("No fake rule matched the offered options")

    def yes_no(self, state: str, question: str) -> Decision:
        """Match a question substring and return a yes/no decision, defaulting to no."""
        options = {"yes": "yes", "no": "no"}
        self.calls.append((state, question, options))
        for fragment, key in self.yes_no_rules.items():
            if fragment in question:
                if key not in options:
                    raise AssertionError(f"Invalid fake yes/no choice: {key}")
                return self._decision(key)
        return self._decision("no")

    def _decision(self, key: str) -> Decision:
        return Decision(
            key,
            probabilities={key: self.confidence},
            confidence=self.confidence,
            confidence_method="basal",
            model=self.model,
        )

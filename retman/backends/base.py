"""Interfaces of model backends (ARCHITECTURE 3.3.1)."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

ConfidenceMethod = Literal["basal", "logprobs", "consistency", "none"]


@dataclass(frozen=True)
class Decision:
    """
    A model decision: the chosen option and how sure the model is.

    Parameters
    ----------
    key : str
        Chosen option key; always one of the keys passed to the backend.
    probabilities : dict[str, float]
        Probability of every option key (empty with ``confidence_method="none"``).
    confidence : float | None
        Confidence of ``key`` in [0, 1]; ``None`` when the method is ``"none"``.
    confidence_method : ConfidenceMethod
        Where the confidence comes from (ARCHITECTURE 3.3.3, 5.4).
    model : str
        Model name reported by the backend (audit trail).
    """

    key: str
    probabilities: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None
    confidence_method: ConfidenceMethod = "none"
    model: str = ""


class DecisionBackend(Protocol):
    """A model that picks one of the given options and reports its confidence."""

    @property
    def url(self) -> str:
        """Server address (shown in the plan audit and by ``retman doctor``)."""
        ...

    @property
    def model(self) -> str:
        """Configured model name."""
        ...

    def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        """
        Pick one option.

        Parameters
        ----------
        state : str
            The user's command (plus optional context).
        question : str
            Question text in the user's language (from translation files).
        options : dict[str, str]
            ``{key: description}``; at most 10 options (ARCHITECTURE 3.4).

        Returns
        -------
        Decision
            ``Decision.key`` is always a key of ``options``.

        Raises
        ------
        BackendConnectionError
            The server did not respond within the configured timeout.
        InvalidModelAnswerError
            The model kept answering outside ``options``.
        """
        ...

    def yes_no(self, state: str, question: str) -> Decision:
        """A yes/no question; ``Decision.key`` is ``"yes"`` or ``"no"``."""
        ...


class TextBackend(Protocol):
    """A model that writes text — used only to describe results (v0.2)."""

    def describe(self, result_summary: dict[str, object], language: str) -> str:
        """Describe a result in the given language."""
        ...

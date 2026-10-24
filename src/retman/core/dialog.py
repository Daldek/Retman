"""Interface-independent questions presented by the CLI or Python callers."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Option:
    """One labelled answer to a choice or ambiguous-value question."""

    key: str
    label: str
    value: Any = None


@dataclass(frozen=True)
class Question:
    """An unresolved operation, parameter or input and its latest validation error."""

    name: str
    type: Literal["choice", "value", "confirm"]
    text: str
    options: list[Option] = field(default_factory=list)
    default: Any = None
    example: str | None = None
    error: str | None = None
    help: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Encode this question as JSON-compatible data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, state: dict[str, Any]) -> "Question":
        """Reconstitute a question from a saved plan."""
        return cls(
            **{**state, "options": [Option(**item) for item in state["options"]]}
        )

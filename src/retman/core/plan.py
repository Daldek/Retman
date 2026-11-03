"""Public plan: explicit questions, provenance, confirmation and serialization."""

from dataclasses import asdict, dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal

from retman.core.check import CheckReport
from retman.core.dialog import Question
from retman.core.journal import utc_now
from retman.exceptions import InvalidValueError, PlanIncompleteError, RetmanError
from retman.i18n.loader import load_core_texts

if TYPE_CHECKING:
    from retman.core.pipeline import Retman

Source = Literal["command", "default", "workspace", "known", "user"]


def _detached() -> RetmanError:
    """Build the error of a plan that has no Retman to answer it (a restored copy)."""
    return RetmanError(
        "The plan is not attached to a Retman",
        code="conflict",
        details={"reason": "plan_detached"},
        hint="Restore it with Plan.from_dict(state, retman=retman).",
    )


@dataclass(frozen=True)
class PlanValue:
    """A normalized parameter and its visible source and confidence."""

    value: Any
    source: Source
    confidence: float | None = None
    unverified: bool = False


@dataclass
class Plan:
    """One proposed operation; ``confirm()`` is mandatory before execution.

    ``reopened`` maps parameters the tool rejected after the user answered (an
    offline preview found a problem) to the text shown with the repeated
    question. ``unset`` maps the applicable optional parameters the command left
    unset to their label and the operation's text for "not set" (N-11: the plan
    says what an unset value means). ``preview_rows`` and ``preview_values`` are
    what the offline preview found out about the plan (rows shown, values only
    audited). ``checks`` are the availability checks run on exactly this plan
    state; the consent for the next one (``check_confirmed``) is single-use and
    never serialized.
    """

    command: str
    operation: str | None
    operation_label: str
    operation_confidence: float | None = None
    operation_unverified: bool = False
    values: dict[str, PlanValue] = field(default_factory=dict)
    inputs: dict[str, PlanValue] = field(default_factory=dict)
    questions: list[Question] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    display: dict[str, str] = field(default_factory=dict)
    known: dict[str, Any] = field(default_factory=dict)
    language: str = "pl"
    confirmed: bool = False
    confirmed_at: str | None = None
    reopened: dict[str, str] = field(default_factory=dict)
    unset: dict[str, tuple[str, str]] = field(default_factory=dict)
    preview_rows: list[tuple[str, str]] = field(default_factory=list)
    preview_values: dict[str, Any] = field(default_factory=dict)
    checks: list[CheckReport] = field(default_factory=list)
    check_confirmed: bool = False
    _owner: "Retman | None" = field(default=None, repr=False, compare=False)

    def answer(self, name: str, answer: str) -> "Plan":
        """Return a new plan after interpreting an answer through the same rules."""
        names = [question.name for question in self.questions]
        if name not in names:
            raise InvalidValueError(
                f"{name!r} is not an open question",
                details={"option": "name", "value": name, "allowed": names},
            )
        if self._owner is None:
            raise _detached()
        return self._owner.answer_plan(self, name, answer)

    def change(self, name: str) -> "Plan":
        """Reopen a displayed value for correction before confirmation."""
        if self._owner is None:
            raise _detached()
        return self._owner.change_plan(self, name)

    def confirm(self) -> "Plan":
        """Explicitly approve a complete plan; never approve open questions."""
        if self.questions or self.operation is None:
            raise PlanIncompleteError("plan still has open questions")
        self.confirmed = True
        self.confirmed_at = utc_now()
        return self

    @property
    def can_check(self) -> bool:
        """Whether the operation offers an availability check for this plan.

        True for a complete plan of an operation that declares ``check``.
        """
        return (
            self._owner is not None
            and self.operation is not None
            and not self.questions
            and "check" in self._owner.operations[self.operation].spec
        )

    def check_notice(self) -> str:
        """Describe what the availability check contacts and sends, before consent."""
        if not self.can_check or self._owner is None:
            raise PlanIncompleteError(
                "this plan offers no availability check",
                code="unsupported",
                details={"reason": "no_check"},
            )
        return self._owner.check_notice(self)

    def confirm_check(self) -> "Plan":
        """Consent to one availability check; it does not confirm the plan.

        The consent is single-use: ``Retman.check()`` consumes it, and any change
        of the plan withdraws it.
        """
        if not self.can_check:
            raise PlanIncompleteError(
                "this plan offers no availability check",
                code="unsupported",
                details={"reason": "no_check"},
            )
        self.check_confirmed = True
        return self

    def summary(self) -> str:
        """Show all selected values, provenance and unverified model choices."""
        texts = load_core_texts(self.language)
        rows = [texts.get("plan.title")]
        if self.operation is not None:
            marker = (
                texts.get("plan.unverified_marker") if self.operation_unverified else ""
            )
            rows.append(
                texts.get("plan.operation", value=self.operation_label) + marker
            )
        for name, entry in (*self.values.items(), *self.inputs.items()):
            marker = ""
            if entry.source == "default":
                marker += texts.get("plan.default_marker")
            if entry.source == "workspace":
                marker += texts.get("plan.workspace_marker")
            if entry.unverified:
                marker += texts.get("plan.unverified_marker")
            rows.append(
                texts.get(
                    "plan.parameter",
                    label=self.labels.get(name, name),
                    value=self.display.get(name, str(entry.value)),
                    marker=marker,
                )
            )
        for label, value in self.unset.values():
            rows.append(
                texts.get(
                    "plan.parameter",
                    label=label,
                    value=value,
                    marker=texts.get("plan.unset_marker"),
                )
            )
        for label, value in self.preview_rows:
            rows.append(
                texts.get(
                    "plan.parameter",
                    label=label,
                    value=value,
                    marker=texts.get("plan.preview_marker"),
                )
            )
        if self.checks:
            last = self.checks[-1]
            rows.append(
                texts.get(
                    "plan.check",
                    status=texts.get(f"check.status_{last.status}"),
                    time=last.time_label,
                )
            )
        if self.questions:
            rows.append(
                texts.get(
                    "plan.missing",
                    questions=", ".join(question.text for question in self.questions),
                )
            )
        return "\n".join(rows)

    def to_dict(self) -> dict[str, Any]:
        """Export the complete plan state as JSON-compatible data.

        Consent for an availability check is not part of the state.
        """
        return {
            "command": self.command,
            "operation": self.operation,
            "operation_label": self.operation_label,
            "operation_confidence": self.operation_confidence,
            "operation_unverified": self.operation_unverified,
            "values": {name: asdict(item) for name, item in self.values.items()},
            "inputs": {name: asdict(item) for name, item in self.inputs.items()},
            "questions": [item.to_dict() for item in self.questions],
            "decisions": self.decisions,
            "answers": self.answers,
            "labels": self.labels,
            "display": self.display,
            "known": self.known,
            "language": self.language,
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at,
            "reopened": self.reopened,
            "unset": {name: list(row) for name, row in self.unset.items()},
            "preview_rows": [list(row) for row in self.preview_rows],
            "preview_values": self.preview_values,
            "checks": [report.to_dict() for report in self.checks],
        }

    @classmethod
    def from_dict(
        cls, state: dict[str, Any], *, retman: "Retman | None" = None
    ) -> "Plan":
        """Load a saved plan; provide ``retman`` to answer remaining questions.

        Approvals are never restored (W-05): a loaded plan is always unconfirmed,
        whatever the saved state says, and must be confirmed again.
        """
        return cls(
            command=state["command"],
            operation=state["operation"],
            operation_label=state["operation_label"],
            operation_confidence=state["operation_confidence"],
            operation_unverified=state["operation_unverified"],
            values={key: PlanValue(**entry) for key, entry in state["values"].items()},
            inputs={key: PlanValue(**entry) for key, entry in state["inputs"].items()},
            questions=[Question.from_dict(entry) for entry in state["questions"]],
            decisions=state["decisions"],
            answers=state["answers"],
            labels=state["labels"],
            display=state["display"],
            known=state["known"],
            language=state["language"],
            reopened=state["reopened"],
            unset={
                name: (label, text) for name, (label, text) in state["unset"].items()
            },
            preview_rows=[(label, value) for label, value in state["preview_rows"]],
            preview_values=state["preview_values"],
            checks=[CheckReport.from_dict(entry) for entry in state["checks"]],
            _owner=retman,
        )

    def _updated(self, **changes: Any) -> "Plan":
        """Return a changed copy: approvals, preview and checks belonged to the old."""
        return replace(
            self,
            confirmed=False,
            confirmed_at=None,
            check_confirmed=False,
            checks=[],
            preview_rows=[],
            preview_values={},
            **changes,
        )

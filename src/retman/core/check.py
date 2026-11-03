"""The optional availability check, a separate consented network step (ARCH 6.5)."""

from dataclasses import dataclass
from typing import Any, Literal

from retman.registry.manifest import CheckItem

CheckStatus = Literal["available", "partial", "unavailable", "unknown"]


@dataclass(frozen=True)
class CheckReport:
    """What one availability check found, exactly as it was shown.

    A check never changes the plan: it informs, the user decides. ``items`` are
    the machine-readable facts the tool reported, ``lines`` the translated lines
    shown to the user and ``header`` the translated heading line. A failed check
    (no network, a service error) is a report with status ``unknown`` and the
    reason in ``error``, not an exception.
    """

    operation: str
    tool: str
    version: str
    checked_at: str
    status: CheckStatus
    header: str
    items: list[CheckItem]
    lines: list[str]
    error: str | None = None

    @property
    def time_label(self) -> str:
        """``checked_at`` to the minute, e.g. ``2026-10-19 16:12``."""
        return self.checked_at[:16].replace("T", " ")

    def summary(self) -> str:
        """Render the report as shown to the user: heading and lines."""
        return "\n".join([self.header, *self.lines])

    def to_dict(self) -> dict[str, Any]:
        """Return the report as JSON-compatible data."""
        return {
            "operation": self.operation,
            "tool": self.tool,
            "version": self.version,
            "checked_at": self.checked_at,
            "status": self.status,
            "header": self.header,
            "items": self.items,
            "lines": self.lines,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, state: dict[str, Any]) -> "CheckReport":
        """Load a report saved with ``to_dict``."""
        return cls(
            operation=state["operation"],
            tool=state["tool"],
            version=state["version"],
            checked_at=state["checked_at"],
            status=state["status"],
            header=state["header"],
            items=state["items"],
            lines=state["lines"],
            error=state["error"],
        )

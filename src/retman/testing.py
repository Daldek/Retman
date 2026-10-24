"""Deterministic backend and tool client for offline Retman tests."""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from retman.adapters.catalog import (
    CatalogCall,
    PlanClient,
    ToolContext,
    ToolDocument,
    ToolError,
    ToolRun,
)
from retman.backends.base import Decision
from retman.registry.operation import Operation


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


class FakeToolClient:
    """A programmed command client for offline tests that records every call.

    It satisfies the ``RunClient`` protocol without importing any tool.
    ``calls`` holds ``(method, call)`` in order, ``network_calls`` those of
    ``run``, ``check`` and ``query`` — what must stay empty before confirmation
    (N-12).

    Parameters
    ----------
    validation : Mapping[str, ToolError | Callable[[CatalogCall], ToolError | None]]
        What ``validate`` raises per command (a callable may return ``None`` to
        accept the call). Calls of other commands are accepted.
    runs : Mapping[str, ToolRun | Callable[[CatalogCall], ToolRun]]
        What ``run`` returns per command; a callable may write the files it
        reports or raise ``ToolError``. A command without an entry yields an
        ``ok`` run without files.
    documents : Mapping[str, ToolDocument | Callable[[CatalogCall], ToolDocument]]
        What ``lookup``, ``check`` and ``query`` return, by command, or by
        ``"<method>:<command>"`` to tell the methods apart. ``lookup`` of a
        command without an entry raises ``ToolError("not_offline")``; ``check``
        and ``query`` return an empty document.
    """

    def __init__(
        self,
        *,
        validation: Mapping[str, ToolError | Callable[[CatalogCall], ToolError | None]]
        | None = None,
        runs: Mapping[str, ToolRun | Callable[[CatalogCall], ToolRun]] | None = None,
        documents: Mapping[str, ToolDocument | Callable[[CatalogCall], ToolDocument]]
        | None = None,
    ) -> None:
        self.validation = validation or {}
        self.runs = runs or {}
        self.documents = documents or {}
        self.calls: list[tuple[str, CatalogCall]] = []

    @property
    def network_calls(self) -> list[tuple[str, CatalogCall]]:
        """Calls of the methods that may use the network or write: run, check, query."""
        return [item for item in self.calls if item[0] in ("run", "check", "query")]

    def validate(self, call: CatalogCall) -> None:
        """Record the call; raise the programmed rejection, if any."""
        self.calls.append(("validate", call))
        programmed = self.validation.get(call.command)
        error = programmed(call) if callable(programmed) else programmed
        if error is not None:
            raise error

    def command_line(self, call: CatalogCall) -> str:
        """Record the call; a deterministic stand-in for the tool's command line."""
        self.calls.append(("command_line", call))
        options = " ".join(
            f"--{key}={call.options[key]}" for key in sorted(call.options)
        )
        return f"fake {call.command} {options}".strip()

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Record the call; the programmed document or ``ToolError("not_offline")``."""
        self.calls.append(("lookup", call))
        document = self._document("lookup", call)
        if document is None:
            raise ToolError("fake", "not_offline", call.command, call=call)
        return document

    def run(self, call: CatalogCall) -> ToolRun:
        """Record the call; the programmed run (default: ``ok`` without files)."""
        self.calls.append(("run", call))
        programmed = self.runs.get(call.command)
        if programmed is None:
            return ToolRun(call.command, "ok", schema="fake/1")
        return programmed(call) if callable(programmed) else programmed

    def check(self, call: CatalogCall) -> ToolDocument:
        """Record the call; the programmed document or an empty one."""
        self.calls.append(("check", call))
        return self._document("check", call) or {}

    def query(self, call: CatalogCall) -> ToolDocument:
        """Record the call; the programmed document or an empty one."""
        self.calls.append(("query", call))
        return self._document("query", call) or {}

    def _document(self, method: str, call: CatalogCall) -> ToolDocument | None:
        programmed = self.documents.get(
            f"{method}:{call.command}", self.documents.get(call.command)
        )
        return programmed(call) if callable(programmed) else programmed


def tool_context(
    operation: Operation,
    *,
    client: PlanClient | None = None,
    settings: Mapping[str, Any] | None = None,
    project_dir: Path | None = None,
    output_dir: Path | None = None,
    inputs: Mapping[str, Path] | None = None,
) -> ToolContext:
    """A ``ToolContext`` for testing call builders, previews and checks.

    Defaults to a ``FakeToolClient``, empty settings and no output folder (the
    state while planning).
    """
    return ToolContext(
        tool=operation.tool,
        settings=settings or {},
        project_dir=project_dir or Path.cwd(),
        output_dir=output_dir,
        inputs=inputs or {},
        client=client if client is not None else FakeToolClient(),
        specs={param["name"]: param for param in operation.spec["params"]},
        operation=operation,
    )

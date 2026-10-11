"""Validated operation descriptions used by the planning pipeline."""

from dataclasses import dataclass

from retman.i18n.loader import Texts
from retman.registry.manifest import OperationSpec, ParamSpec


@dataclass(frozen=True)
class Operation:
    """An available operation, its texts and the installed tool version."""

    spec: OperationSpec
    tool: str
    version: str
    texts: Texts

    @property
    def id(self) -> str:
        """Globally unique operation identifier."""
        return self.spec["id"]

    def parameter(self, name: str) -> ParamSpec | None:
        """Return the manifest entry for a named parameter."""
        return next(
            (param for param in self.spec["params"] if param["name"] == name), None
        )

    def text(self, suffix: str) -> str:
        """Look up a translated operation or parameter text."""
        return self.texts.get(f"operations.{self.id}.{suffix}")

"""Validated operation descriptions used by the planning pipeline."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from retman.exceptions import ManifestError
from retman.i18n.loader import Texts
from retman.registry.manifest import OperationSpec, ParamSpec

# The decision model is offered at most this many real options (plus one more
# for "out of scope"/"unspecified"): ARCHITECTURE 3.4, point 1.
MAX_OPTIONS = 9


@dataclass(frozen=True)
class Operation:
    """An available operation, its texts and the installed tool version.

    ``client`` is the tool-level ``"module:factory"`` reference of the tool's
    command client (manifest key ``client``), ``None`` for a tool without one.
    """

    spec: OperationSpec
    tool: str
    version: str
    texts: Texts
    client: str | None = None

    @property
    def id(self) -> str:
        """Globally unique operation identifier."""
        return self.spec["id"]

    @property
    def category(self) -> str:
        """Category of the operation, the first stage of recognition."""
        return self.spec["category"]

    def parameter(self, name: str) -> ParamSpec | None:
        """Return the manifest entry for a named parameter."""
        return next(
            (param for param in self.spec["params"] if param["name"] == name), None
        )

    def text(self, suffix: str) -> str:
        """Look up a translated operation or parameter text."""
        return self.texts.get(f"operations.{self.id}.{suffix}")


def two_stage(operations: Mapping[str, Operation]) -> bool:
    """Whether one question cannot offer all operations (plus "out of scope")."""
    return len(operations) > MAX_OPTIONS


def category_groups(
    operations: Iterable[Operation],
) -> dict[str, list[Operation]]:
    """Operations by category, in registry order."""
    groups: dict[str, list[Operation]] = {}
    for operation in operations:
        groups.setdefault(operation.category, []).append(operation)
    return groups


def category_text(members: Sequence[Operation], category: str, suffix: str) -> str:
    """Label or description of a category from the first tool that describes it.

    Raises
    ------
    ManifestError
        No tool of ``members`` has ``categories.<category>.<suffix>``.
    """
    for operation in members:
        key = f"categories.{category}.{suffix}"
        if operation.texts.has(key):
            return operation.texts.get(key)
    raise ManifestError(f"missing category text categories.{category}.{suffix}")

"""Optional collection of commands from all projects in one file (ADR-010).

Unlike the project journal (the user's record of work, kept in the project),
the collection gathers planning outcomes from every project in one place, to
build and tune the test set. It is written only when the user explicitly
enabled ``[privacy] collect_commands``; nothing is ever sent anywhere
(ARCHITECTURE rozdz. 10).
"""

import json
from pathlib import Path
from typing import Any

from retman.core.journal import utc_now


class Collection:
    """Append planning outcomes to the central file, or do nothing when disabled.

    Parameters
    ----------
    path : Path | None
        Collection file; ``None`` when collecting is disabled.
    """

    def __init__(self, path: Path | None) -> None:
        self.path = path

    @property
    def enabled(self) -> bool:
        """Whether collection is switched on (a path is configured)."""
        return self.path is not None

    def append(self, record: dict[str, Any]) -> None:
        """Append one outcome as a JSON line (no-op when disabled)."""
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            line = json.dumps({"time": utc_now(), **record}, ensure_ascii=False)
            handle.write(line + "\n")

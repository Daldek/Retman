"""Project-local append-only event journal and file integrity helpers."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    """Get a timezone-qualified audit timestamp."""
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    """Hash a file without loading its entire contents in memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Journal:
    """Append events without changing existing project history."""

    def __init__(self, root: Path, session_id: str, include_commands: bool) -> None:
        self.path = root / "journal.jsonl"
        self.session_id = session_id
        self.include_commands = include_commands

    def append(self, event: str, **fields: Any) -> None:
        """Append one JSON event; omit texts shown to the user when opted out.

        Without ``include_commands`` the raw command and answer, the shown plan,
        the reason a question was asked again and the lines of an availability
        report are left out: they may quote the user's own words or paths.
        """
        if not self.include_commands:
            for name in ("command", "answer", "plan", "reason", "lines"):
                fields.pop(name, None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "time": utc_now(),
            "session_id": self.session_id,
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def entries(self) -> list[dict[str, Any]]:
        """Read events for the current project, in append order."""
        if not self.path.is_file():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

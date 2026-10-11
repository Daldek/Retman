"""Numbered project results and validated input selection."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from retman.core.journal import sha256_file
from retman.kinds import validate_file


@dataclass(frozen=True)
class WorkspaceFile:
    """One existing file for a required input kind."""

    path: Path
    number: int
    summary: str
    time: str
    kind: str

    @property
    def label(self) -> str:
        """Human-friendly identifier, with the summary and timestamp."""
        return f"#{self.number} {self.summary} ({self.time})"


class Workspace:
    """Results in the configured subdirectory of one project folder."""

    def __init__(self, project_dir: Path, results_dir: str) -> None:
        self.project_dir = project_dir.resolve()
        self.root = self.project_dir / results_dir

    def list_results(self) -> list[dict[str, Any]]:
        """Read the saved results in numeric order, without changing the project."""
        if not self.root.is_dir():
            return []
        found: list[dict[str, Any]] = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or not folder.name.split("_", 1)[0].isdigit():
                continue
            info = folder / "result.json"
            if info.is_file():
                with info.open(encoding="utf-8") as handle:
                    found.append(json.load(handle))
        return sorted(found, key=lambda item: item["number"])

    def create_result_dir(self, operation: str) -> tuple[int, Path]:
        """Reserve the next number without overwriting any existing result."""
        self.root.mkdir(parents=True, exist_ok=True)
        existing = [
            int(folder.name.split("_", 1)[0])
            for folder in self.root.iterdir()
            if folder.is_dir() and folder.name.split("_", 1)[0].isdigit()
        ]
        number = max(existing, default=0) + 1
        while True:
            directory = self.root / f"{number:03d}_{operation}"
            try:
                directory.mkdir()
                return number, directory
            except FileExistsError:
                number += 1

    def find_by_kind(self, kind: str) -> list[WorkspaceFile]:
        """Find files in successful results without selecting the newest."""
        candidates: list[WorkspaceFile] = []
        for record in self.list_results():
            if not record["ok"]:
                continue
            for file_info in record.get("files", {}).get(kind, []):
                path = self.project_dir / file_info["path"]
                candidates.append(
                    WorkspaceFile(
                        path,
                        record["number"],
                        record["summary"],
                        record["timing"]["end"],
                        kind,
                    )
                )
        return candidates

    def resolve_result(self, number: int, kind: str) -> list[WorkspaceFile]:
        """Return every file of a kind in a specifically numbered result."""
        return [item for item in self.find_by_kind(kind) if item.number == number]

    def validate_input(self, path: Path, kind: str) -> Path:
        """Resolve and validate an explicit or previously saved input file."""
        resolved = (self.project_dir / path).resolve()
        validate_file(kind, resolved)
        return resolved

    def describe_input(
        self, path: Path, kind: str, number: int | None = None
    ) -> dict[str, Any]:
        """Record provenance and a checksum before the handler runs."""
        return {
            "kind": kind,
            "source": "workspace" if number is not None else "file",
            "number": number,
            "path": str(path),
            "sha256": sha256_file(path),
        }

    def save_result(self, directory: Path, record: dict[str, Any]) -> None:
        """Write the full audit record in the numbered result directory."""
        with (directory / "result.json").open(
            "w", encoding="utf-8", newline="\n"
        ) as out:
            json.dump(record, out, ensure_ascii=False, indent=2, default=str)
            out.write("\n")

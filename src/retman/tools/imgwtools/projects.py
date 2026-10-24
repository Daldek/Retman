"""The project manifest ``imgw-project.json``, read for previews (never written here).

IMGWTools owns the manifest: it is created and changed only by the tool's own
commands. Retman reads it with the standard library to say, before anything is
confirmed, which project and which store an operation concerns, which tasks
exist and whether they are pinned.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

MANIFEST_FILE: Final = "imgw-project.json"
MANIFEST_SCHEMA: Final = "imgw-project/1"


@dataclass(frozen=True)
class ManifestTask:
    """A task of the manifest: its name, catalog command and whether it is pinned."""

    name: str
    command: str
    pinned: bool


@dataclass(frozen=True)
class Manifest:
    """What the project folder's manifest says.

    ``state`` is ``missing`` (no file), ``invalid`` (``detail`` says why) or
    ``ready``; ``store`` is the absolute store folder the manifest points at.
    """

    state: Literal["missing", "invalid", "ready"]
    path: Path
    store: Path | None = None
    tasks: tuple[ManifestTask, ...] = ()
    detail: str = ""

    @property
    def names(self) -> list[str]:
        """The task names, in manifest order."""
        return [task.name for task in self.tasks]


def load_manifest(project_dir: Path) -> Manifest:
    """Read the manifest of ``project_dir``; a bad file is ``invalid``, not an error."""
    path = project_dir / MANIFEST_FILE
    if not path.is_file():
        return Manifest("missing", path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document["schema"] != MANIFEST_SCHEMA:
            return Manifest("invalid", path, detail=f"schema {document['schema']!r}")
        text = document["store_dir"]
        tasks = tuple(
            ManifestTask(
                str(task["name"]),
                str(task["command"]),
                task.get("pinned_at") is not None,
            )
            for task in document["tasks"]
        )
        if not isinstance(text, str) or not text:
            raise ValueError("store_dir")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return Manifest("invalid", path, detail=f"{type(error).__name__}: {error}")
    # A relative store path is relative to the project folder (as the tool reads it)
    store = Path(os.path.normpath(project_dir / text))
    return Manifest("ready", path, store, tasks)

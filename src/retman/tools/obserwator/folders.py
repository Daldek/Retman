"""Folder comparisons of the previews: pure path arithmetic, no file is changed."""

import os
from pathlib import Path


def same_folder(first: object, second: object) -> bool:
    """Whether two paths name the same folder (absolute and normalised)."""
    return os.path.abspath(str(first)) == os.path.abspath(str(second))


def inside(folder: Path, path: Path) -> bool:
    """Whether ``path`` is ``folder`` or lies below it (resolved, so ``..`` counts)."""
    resolved, base = path.resolve(), folder.resolve()
    return resolved == base or base in resolved.parents

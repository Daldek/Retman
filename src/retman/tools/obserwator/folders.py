"""Folder comparisons of the previews: pure path arithmetic, no file is changed."""

import os


def same_folder(first: object, second: object) -> bool:
    """Whether two paths name the same folder (absolute and normalised)."""
    return os.path.abspath(str(first)) == os.path.abspath(str(second))

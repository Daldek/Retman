"""The command line of Retman: ``retman <group> <verb>`` (AGI §3).

:func:`main` is the one entry point (``[project.scripts] retman``); the parser, the
dialog of a terminal and the dispatch live in the modules of this package and are no
public API.
"""

from retman.cli.main import main

__all__ = ["main"]

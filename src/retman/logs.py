"""Logging of the command line: level, handler and the technical log (DEV-12).

The library only creates loggers (``logging.getLogger(__name__)``); this module is
the one place that configures a handler, and only the command line calls it. The
technical log goes to stderr, never holds the text of a command or an answer
(ARCHITECTURE 5.4) and never a secret.
"""

import logging
import sys
from typing import TextIO

from retman.exceptions import UsageError

LOG_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}
DEFAULT_LEVEL = "warning"
VERBOSE_LEVEL = "debug"
QUIET_LEVEL = "error"

_LOGGER_NAME = "retman"
_FORMAT = "%(levelname)s %(name)s: %(message)s"


def resolve_level(*, verbose: bool, quiet: bool, configured: str | None = None) -> str:
    """Return the log level by the precedence of DEV-18.1.

    Parameters
    ----------
    verbose, quiet : bool
        The command-line options ``--verbose`` (``debug``) and ``--quiet``
        (``error``); they exclude each other.
    configured : str | None, optional
        The setting ``log_level``: ``RETMAN_LOG_LEVEL``, ``NOGAT_LOG_LEVEL``, the
        settings file or the default (see :mod:`retman.environment`).

    Returns
    -------
    str
        A key of ``LOG_LEVELS``; ``warning`` when nothing sets it.

    Raises
    ------
    UsageError
        Both options are given.
    """
    if verbose and quiet:
        raise UsageError(
            "--verbose and --quiet exclude each other",
            details={"reason": "exclusive_options", "options": ["verbose", "quiet"]},
            hint="Give --verbose or --quiet, not both.",
        )
    if verbose:
        return VERBOSE_LEVEL
    if quiet:
        return QUIET_LEVEL
    return configured or DEFAULT_LEVEL


def configure_logging(level: str, stream: TextIO | None = None) -> None:
    """Send the logs of Retman to ``stream`` (stderr by default) at ``level``.

    Calling it again replaces the handler and the level, so a process that runs the
    command line several times (tests, a session) keeps one handler.

    Parameters
    ----------
    level : str
        A key of ``LOG_LEVELS``.
    stream : TextIO | None, optional
        Where the lines go; stderr when ``None``.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(LOG_LEVELS[level])
    # The command line owns the output: nothing may reach a root handler twice
    logger.propagate = False

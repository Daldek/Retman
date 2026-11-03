"""Logging of the command line: handler and the technical log (DEV-12).

The library only creates loggers (``logging.getLogger(__name__)``); this module is
the one place that configures a handler, and only the command line calls it. The
level is the setting ``log_level`` (:mod:`retman.environment`: ``--verbose``,
``--quiet``, the variables, the settings file). The technical log goes to stderr,
never holds the text of a command or an answer (ARCHITECTURE 5.4) and never a
secret.
"""

import logging
import sys
from typing import TextIO

LOG_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

_LOGGER_NAME = "retman"
_FORMAT = "%(levelname)s %(name)s: %(message)s"


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

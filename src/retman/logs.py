"""Logging of the command line: level, handler and the technical log (DEV-12).

The library only creates loggers (``logging.getLogger(__name__)``); this module is
the one place that configures a handler, and only the command line calls it. The
technical log goes to stderr, never holds the text of a command or an answer
(ARCHITECTURE 5.4) and never a secret.
"""

import logging
import sys
from collections.abc import Mapping
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
# The variable of the tool comes before the one shared by the Nogat tools (DEV-18.1)
ENVIRONMENT_VARIABLES: tuple[str, ...] = ("RETMAN_LOG_LEVEL", "NOGAT_LOG_LEVEL")

_LOGGER_NAME = "retman"
_FORMAT = "%(levelname)s %(name)s: %(message)s"


def level_from_environment(environ: Mapping[str, str]) -> str | None:
    """Return the log level named by the environment, or ``None``.

    Parameters
    ----------
    environ : Mapping[str, str]
        The process environment.

    Returns
    -------
    str | None
        The value of ``RETMAN_LOG_LEVEL`` or else ``NOGAT_LOG_LEVEL``, in lower case;
        ``None`` when neither is set (or both are empty).

    Raises
    ------
    UsageError
        The variable holds something other than ``debug``, ``info``, ``warning`` or
        ``error``.
    """
    for name in ENVIRONMENT_VARIABLES:
        value = environ.get(name, "").strip().lower()
        if not value:
            continue
        if value not in LOG_LEVELS:
            raise UsageError(
                f"{name}={value!r} is not a log level; "
                f"allowed: {', '.join(LOG_LEVELS)}",
                details={
                    "option": name,
                    "value": value,
                    "allowed": list(LOG_LEVELS),
                },
                hint=f"Set {name} to one of: {', '.join(LOG_LEVELS)}.",
            )
        return value
    return None


def resolve_level(
    *,
    verbose: bool,
    quiet: bool,
    environ: Mapping[str, str],
    configured: str | None = None,
) -> str:
    """Return the log level by the precedence of DEV-18.1.

    Parameters
    ----------
    verbose, quiet : bool
        The command-line options ``--verbose`` (``debug``) and ``--quiet``
        (``error``); they exclude each other.
    environ : Mapping[str, str]
        The process environment (``RETMAN_LOG_LEVEL``, then ``NOGAT_LOG_LEVEL``).
    configured : str | None, optional
        The level of the config file (``[log] diagnostic_level``), if it is known.

    Returns
    -------
    str
        A key of ``LOG_LEVELS``; ``warning`` when nothing sets it.

    Raises
    ------
    UsageError
        Both options are given, or the environment holds an invalid level.
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
    return level_from_environment(environ) or configured or DEFAULT_LEVEL


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

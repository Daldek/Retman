"""Retman: natural-language commands (Polish) for hydrological tools.

The public API is exactly :data:`__all__` (AGI-7.1): the conversation classes
(:class:`Retman`, :class:`Plan`, :class:`Result`, :class:`CheckReport`), the error
classes with the error registry, and the five functions that drive any command of the
catalog (AGI-2.1) -- :func:`list_commands`, :func:`command_schema`,
:func:`validate_command`, :func:`check_command` and :func:`run_command`. The operation
of each command is in :mod:`retman.operations`.

Importing the package reads no files and uses no network: the five functions import
the catalog when they are first called.
"""

__version__ = "0.1.0.dev0"

from typing import TYPE_CHECKING, Any

from retman.core.check import CheckReport
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.core.result import Result
from retman.exceptions import (
    ERROR_CODES,
    BackendConnectionError,
    BackendError,
    CheckNotConfirmedError,
    CommandNotFoundError,
    ConfigError,
    EvalDatasetError,
    InputRequiredError,
    InvalidModelAnswerError,
    InvalidValueError,
    KindValidationError,
    ManifestError,
    OutOfScopeError,
    PlanIncompleteError,
    PlanNotConfirmedError,
    RetmanError,
    TranslationError,
    UsageError,
    error_document,
)

if TYPE_CHECKING:
    from retman.catalog import CommandResult, Document

__all__ = [
    "ERROR_CODES",
    "BackendConnectionError",
    "BackendError",
    "CheckNotConfirmedError",
    "CheckReport",
    "CommandNotFoundError",
    "ConfigError",
    "EvalDatasetError",
    "InputRequiredError",
    "InvalidModelAnswerError",
    "InvalidValueError",
    "KindValidationError",
    "ManifestError",
    "OutOfScopeError",
    "Plan",
    "PlanIncompleteError",
    "PlanNotConfirmedError",
    "Result",
    "Retman",
    "RetmanError",
    "TranslationError",
    "UsageError",
    "__version__",
    "check_command",
    "command_schema",
    "error_document",
    "list_commands",
    "run_command",
    "validate_command",
]


def list_commands(*, limit: int | None = None, cursor: str | None = None) -> "Document":
    """List the commands of the catalog.

    Parameters
    ----------
    limit : int, optional
        Commands per page; ``None`` lists all of them.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.

    Returns
    -------
    Document
        The ``retman-command-list/1`` document (``to_dict()``, ``to_json()``).

    Raises
    ------
    InvalidValueError
        ``limit`` or ``cursor`` is invalid.

    Examples
    --------
    >>> import retman
    >>> retman.list_commands().to_dict()["schema"]
    'retman-command-list/1'
    """
    from retman.catalog import list_commands as _list_commands

    return _list_commands(limit=limit, cursor=cursor)


def command_schema(command: str, /) -> "Document":
    """Describe one command: options, result, effects, rules, examples and errors.

    Parameters
    ----------
    command : str
        Command name (``"plan run"``) or ``operation_id`` (``"retman_plan_run"``).

    Returns
    -------
    Document
        The ``retman-commands/1`` document holding that command.

    Raises
    ------
    CommandNotFoundError
        The command does not exist; ``details.suggestions`` lists similar names.

    Examples
    --------
    >>> import retman
    >>> retman.command_schema("plan run").to_dict()["commands"][0]["name"]
    'plan run'
    """
    from retman.catalog import command_schema as _command_schema

    return _command_schema(command)


def validate_command(command: str, /, **options: Any) -> dict[str, Any]:
    """Validate the options of a command and fill in the defaults, without effects.

    Parameters
    ----------
    command : str
        Command name or ``operation_id``.
    **options
        The options of the command, named as in its catalog entry.

    Returns
    -------
    dict
        The normalized options with the defaults applied.

    Raises
    ------
    CommandNotFoundError
        The command does not exist.
    InvalidValueError
        An option is unknown, missing, of the wrong type or out of range
        (``details.option`` and ``details.reason`` say which).

    Examples
    --------
    >>> import retman
    >>> retman.validate_command("results list", limit=5)["limit"]
    5
    """
    from retman.catalog import validate_command as _validate_command

    return _validate_command(command, options)


def check_command(command: str, /, **options: Any) -> "CommandResult":
    """Plan a command that writes without effects (the plan of ``--check``).

    Parameters
    ----------
    command : str
        Command name or ``operation_id`` of a command that has a ``check`` option.
    **options
        The options of the command.

    Returns
    -------
    CommandResult
        The result envelope with ``check`` true: for ``plan run`` the plan with its
        open questions, for a command that writes files the targets with their
        actions (``write``, ``replace`` or ``conflict``).

    Raises
    ------
    InvalidValueError
        The command has no plan (``details.reason`` ``no_check``) or the options
        are invalid.
    """
    from retman.catalog import check_command as _check_command

    return _check_command(command, options)


def run_command(command: str, /, **options: Any) -> "CommandResult":
    """Run a command of the catalog and return its result envelope.

    Parameters
    ----------
    command : str
        Command name or ``operation_id``.
    **options
        The options of the command, named as in its catalog entry.

    Returns
    -------
    CommandResult
        The ``retman-result/1`` envelope (``to_dict()``, ``to_json()``): the document
        in ``result``, the units of a batch in ``items``, the ``notices``.

    Raises
    ------
    RetmanError
        The error of the command, with ``code``, ``details`` and ``hint``.

    Examples
    --------
    >>> import retman
    >>> retman.run_command("commands list").to_dict()["status"]
    'ok'
    """
    from retman.catalog import run_command as _run_command

    return _run_command(command, options)

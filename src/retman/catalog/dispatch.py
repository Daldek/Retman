"""Lookup, validation, catalog documents and execution of catalog commands (AGI-2.1).

The entry points are re-exported by :mod:`retman.catalog`; the top-level package
exposes the five of AGI-2.1 with keyword options (:func:`retman.run_command`...):

* :func:`data_commands` and :func:`get_command` -- the catalog and its lookup;
* :func:`list_commands` and :func:`command_schema` -- the command list and the
  ``retman-commands/1`` document of one command;
* :func:`validate_command` -- validation and normalization of option values;
* :func:`check_command` and :func:`run_command` -- validation, execution and the
  result envelope; :func:`execute` is the same with the injections of the CLI.

Validation errors
-----------------
All validation failures are :class:`~retman.exceptions.InvalidValueError`
(``validation_error``) whose ``details`` hold ``option`` and a machine-readable
``reason``:

=====================  ============================================================
reason                 meaning (extra ``details`` keys)
=====================  ============================================================
``unknown_option``     option not declared by the command (``allowed``)
``required``           required option missing
``one_of``             several options of one exclusion group (``group``, ``given``)
``type``               wrong JSON type (``expected``, ``value``, ``got``; ``index``
                       inside lists)
``not_finite``         NaN or infinity where a finite number is required
``minimum``,           bound violated (``minimum``/``maximum``/``exclusive_minimum``,
``maximum``,           ``value``)
``exclusive_minimum``
``choice``             value not among the choices (``allowed``, ``value``)
``empty``              empty string, path or list
``invalid_path``       path that cannot be used (NUL character)
``invalid_cursor``     ``cursor`` that no page returned
``no_check``           ``check_command`` of a command without a ``check`` mode
=====================  ============================================================

A command that does not exist is a :class:`~retman.exceptions.CommandNotFoundError`.
"""

import difflib
import importlib
import inspect
from collections.abc import Callable, Mapping
from typing import Any, cast

from retman.catalog.document import (
    Document,
    catalog_document,
    command_list,
    paginate,
)
from retman.catalog.envelope import CommandResult, Output
from retman.catalog.spec import Command, Option
from retman.exceptions import (
    CommandNotFoundError,
    InvalidValueError,
    RetmanError,
)

# --- catalog --------------------------------------------------------------------------


def data_commands() -> tuple[Command, ...]:
    """Return the catalog.

    Returns
    -------
    tuple of Command
        All commands, ordered by group and verb as the CLI lists them.
    """
    from retman.catalog.commands import COMMANDS

    return COMMANDS


def get_command(name_or_operation_id: str) -> Command:
    """Find a command by name or by ``operation_id``.

    Parameters
    ----------
    name_or_operation_id : str
        ``"plan run"`` or ``"retman_plan_run"``; surrounding and repeated whitespace
        is ignored.

    Returns
    -------
    Command
        The declaration.

    Raises
    ------
    CommandNotFoundError
        No command has this name; ``details.suggestions`` lists similar names.
    InvalidValueError
        The argument is not a string.
    """
    if not isinstance(name_or_operation_id, str):
        raise InvalidValueError(
            f"Command name must be a string, got {type(name_or_operation_id).__name__}",
            details={"option": "command", "reason": "type", "expected": "string"},
        )
    key = " ".join(name_or_operation_id.split())
    commands = data_commands()
    for command in commands:
        if key in (command.name, command.operation_id):
            return command
    candidates = {
        label: command.name
        for command in commands
        for label in (command.name, command.operation_id)
    }
    close = difflib.get_close_matches(key, list(candidates), n=5, cutoff=0.6)
    suggestions = list(dict.fromkeys(candidates[label] for label in close))[:3]
    hint = "Run `retman commands list` to see all commands."
    if suggestions:
        hint = f"Did you mean: {', '.join(suggestions)}? " + hint
    raise CommandNotFoundError(
        f"Unknown command {name_or_operation_id!r}",
        details={"command": name_or_operation_id, "suggestions": suggestions},
        hint=hint,
    )


def _resolve(command: str | Command) -> Command:
    return command if isinstance(command, Command) else get_command(command)


# --- validation -----------------------------------------------------------------------


def _is_given(option: Option, value: object) -> bool:
    """Whether a value counts as given: ``None`` and a ``False`` flag do not."""
    return value is not None and not (option.type == "boolean" and value is False)


def _check_one_of(command: Command, normalized: Mapping[str, Any]) -> None:
    """Allow at most one option of each exclusion group (AGI-2.3)."""
    groups: dict[str, list[str]] = {}
    for option in command.options:
        if option.one_of is not None and _is_given(option, normalized.get(option.name)):
            groups.setdefault(option.one_of, []).append(option.name)
    for group, given in groups.items():
        if len(given) > 1:
            members = [o.name for o in command.options if o.one_of == group]
            raise InvalidValueError(
                f"Command {command.name!r} takes at most one of: {', '.join(members)}; "
                f"given: {', '.join(given)}",
                details={
                    "reason": "one_of",
                    "option": given[1],
                    "group": group,
                    "given": given,
                    "allowed": members,
                },
                hint=f"Give only one of: {', '.join(members)}.",
            )


def validate_command(
    name: str | Command, options: Mapping[str, object] | None = None
) -> dict[str, Any]:
    """Validate option values against the declaration of a command.

    Values must be JSON-native (numbers, strings, booleans, lists); text such as
    ``"12.5"`` is not converted to a number -- the CLI does that before calling.
    ``None`` counts as "not given". Defaults are applied for the options that have
    one; paths are kept as given.

    Parameters
    ----------
    name : str or Command
        Command name or ``operation_id`` (or a :class:`Command` instance).
    options : Mapping[str, object], optional
        Option values by option name.

    Returns
    -------
    dict
        Normalized options in catalog order, including defaults.

    Raises
    ------
    CommandNotFoundError
        The command does not exist.
    InvalidValueError
        ``options`` is not a mapping, an option is unknown, required but missing, of
        the wrong type or outside its bounds or choices, or an exclusion group has
        several members; see the module docstring for ``details``.
    """
    command = _resolve(name)
    given_options: Mapping[str, object] = {} if options is None else options
    if not isinstance(given_options, Mapping):
        raise InvalidValueError(
            f"Options of command {command.name!r} must be a mapping name -> value, "
            f"got {type(given_options).__name__}",
            details={"option": "options", "reason": "type", "expected": "object"},
        )
    known = [option.name for option in command.options]
    for key in given_options:
        if key not in known:
            close = difflib.get_close_matches(str(key), known, n=1, cutoff=0.6)
            hint = f"Allowed options: {', '.join(known)}." if known else None
            if close:
                hint = f"Did you mean {close[0]!r}? " + (hint or "")
            raise InvalidValueError(
                f"Unknown option {str(key)!r} for command {command.name!r}",
                details={
                    "reason": "unknown_option",
                    "option": str(key),
                    "allowed": known,
                },
                hint=hint or "This command takes no options.",
            )
    normalized: dict[str, Any] = {}
    for option in command.options:
        raw = given_options.get(option.name)
        if raw is not None:
            normalized[option.name] = option.normalize(raw)
    for option in command.options:
        if option.required and option.name not in normalized:
            raise InvalidValueError(
                f"Option {option.name!r} is required by command {command.name!r}",
                details={"reason": "required", "option": option.name},
                hint=(
                    f"Give '{option.name}' (CLI: {option.flag}); "
                    "`retman commands schema` lists all options."
                ),
            )
    _check_one_of(command, normalized)
    result: dict[str, Any] = {}
    for option in command.options:
        if option.name in normalized:
            result[option.name] = normalized[option.name]
        elif option.default is not None:
            result[option.name] = option.normalize(option.default)
    return result


# --- catalog documents ----------------------------------------------------------------


def command_schema(command: str | Command) -> Document:
    """Describe one command as a ``retman-commands/1`` document (AGI-2.1).

    Parameters
    ----------
    command : str or Command
        Command name (``"plan run"``) or ``operation_id`` (``"retman_plan_run"``), or
        a :class:`Command` instance.

    Returns
    -------
    Document
        The catalog document holding that one command: options with types, units,
        bounds, enum meanings and ``path_role``, result schema, effects, rules,
        examples, errors and the Polish texts (``i18n.pl``).

    Raises
    ------
    CommandNotFoundError
        ``command`` does not exist.
    """
    return Document(catalog_document((_resolve(command),)))


def list_commands(*, limit: int | None = None, cursor: str | None = None) -> Document:
    """List the catalog commands as a ``retman-command-list/1`` document (AGI-2.1).

    Parameters
    ----------
    limit : int, optional
        Commands per page; ``None`` (default) lists all.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.

    Returns
    -------
    Document
        ``commands`` with ``name``, ``operation_id``, ``summary`` and ``read_only`` of
        each command; with ``limit`` also ``page``.

    Raises
    ------
    InvalidValueError
        ``limit`` is not positive or ``cursor`` is invalid.
    """
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise InvalidValueError(
            f"Option 'limit': must be an integer >= 1, got {limit!r}",
            details={"reason": "minimum", "option": "limit", "minimum": 1},
        )
    selected, page = paginate(data_commands(), limit, cursor)
    document = command_list(selected)
    if page is not None:
        document["page"] = page
    return Document(document)


# --- execution ------------------------------------------------------------------------


def _load_function(path: str) -> Callable[..., Any]:
    """Import the function at the dotted path ``"package.module.function"``."""
    module_name, _, attribute = path.rpartition(".")
    try:
        function = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as error:
        raise RetmanError(
            f"Operation {path!r} cannot be imported: {error}",
            details={"reason": "operation_not_importable", "function": path},
        ) from error
    if not callable(function):
        raise RetmanError(
            f"Operation {path!r} is not callable",
            details={"reason": "operation_not_importable", "function": path},
        )
    return cast(Callable[..., Any], function)


def _accepted(
    function: Callable[..., Any], command: Command, injections: Mapping[str, object]
) -> dict[str, object]:
    """Return the injections that ``function`` declares and that are no options.

    An option is set by the caller of the command, never by an injection, so a name
    that the catalog declares as an option is left out.
    """
    parameters = inspect.signature(function).parameters
    options = {option.name for option in command.options}
    return {
        name: value
        for name, value in injections.items()
        if name in parameters and name not in options
    }


def execute(
    name: str | Command,
    options: Mapping[str, object] | None = None,
    injections: Mapping[str, object] | None = None,
) -> CommandResult:
    """Validate and run a catalog command with the injections of a caller.

    This is :func:`run_command` for the CLI and for tests: ``injections`` are
    keyword arguments for the parts of an operation that a caller replaces (a
    decision backend, the project folder, the discovered tools). An operation takes
    the ones it declares and ignores the others; no option of the catalog can be set
    this way.

    Parameters
    ----------
    name : str or Command
        Command name or ``operation_id`` (or a :class:`Command` instance).
    options : Mapping[str, object], optional
        Option values by option name (JSON-native).
    injections : Mapping[str, object], optional
        Keyword arguments of the operation that are not options.

    Returns
    -------
    CommandResult
        The envelope of the run.

    Raises
    ------
    CommandNotFoundError
        The command does not exist.
    InvalidValueError
        The options are invalid (see :func:`validate_command`).
    RetmanError
        Any error of the operation itself is propagated unchanged.
    """
    command = _resolve(name)
    normalized = validate_command(command, options)
    function = _load_function(command.function)
    output = function(**normalized, **_accepted(function, command, injections or {}))
    if not isinstance(output, Output):
        raise RetmanError(
            f"Operation {command.function!r} returned {type(output).__name__}, "
            "not an Output",
            details={
                "reason": "invalid_operation_output",
                "function": command.function,
            },
        )
    return CommandResult(command.name, command.result_schema, output)


def check_command(
    name: str | Command,
    options: Mapping[str, object] | None = None,
    injections: Mapping[str, object] | None = None,
) -> CommandResult:
    """Plan a command without effects: :func:`run_command` with ``check`` (AGI-2.1).

    Parameters
    ----------
    name : str or Command
        Command name or ``operation_id`` (or a :class:`Command` instance).
    options : Mapping[str, object], optional
        Option values by option name; ``check`` is added.
    injections : Mapping[str, object], optional
        As in :func:`execute`.

    Returns
    -------
    CommandResult
        Envelope with ``check`` true. Its ``result`` is the plan: for ``plan run`` the
        ``retman-plan/1`` document, for a command that writes files the
        ``retman-targets/1`` document (each target with its action ``write``,
        ``replace`` or ``conflict``). A plan that lists a conflict is a successful
        result.

    Raises
    ------
    CommandNotFoundError
        The command does not exist.
    InvalidValueError
        The command has no ``check`` mode (``details.reason`` ``no_check``) or the
        options are invalid.
    """
    command = _resolve(name)
    if not command.check:
        raise InvalidValueError(
            f"Command {command.name!r} has no check mode: it writes nothing",
            details={"reason": "no_check", "option": "check", "command": command.name},
            hint="Run it directly; only commands that write have a plan.",
        )
    return execute(command, {**(options or {}), "check": True}, injections)


def run_command(
    name: str | Command, options: Mapping[str, object] | None = None
) -> CommandResult:
    """Validate and run a catalog command.

    Parameters
    ----------
    name : str or Command
        Command name or ``operation_id`` (or a :class:`Command` instance).
    options : Mapping[str, object], optional
        Option values by option name (JSON-native).

    Returns
    -------
    CommandResult
        The ``retman-result/1`` envelope: the document in ``result``, the per-unit
        ``items`` of a batch, ``notices`` and the written files.

    Raises
    ------
    CommandNotFoundError
        The command does not exist.
    InvalidValueError
        The options are invalid (see :func:`validate_command`).
    RetmanError
        Any error of the operation itself is propagated unchanged.
    """
    return execute(name, options)

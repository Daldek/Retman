"""Declarations of the Retman command catalog (AGI-2.2, AGI-2.3).

A :class:`Command` is one entry of the catalog ``retman-commands/1``: its name
(``<group> <verb>``, the words typed in the CLI), its :class:`Option` list, what it
does to the outside world (:class:`Effects`), the document it returns and the
examples that show it. The CLI, the five catalog functions (:mod:`retman.catalog`),
the schemas of the documents, ``AGENTS.md`` and ``llms.txt`` are all generated from or
tested against these declarations (AGI-1.1).

The texts of a declaration are English (AGI-9.1); the Polish translations are in
``src/retman/i18n/pl.toml`` under ``[catalog.<operation_id>]`` and are used for the
human-readable output and the ``i18n.pl`` fields of the catalog document.

Option types
------------
===============  ==============================================  ====================
``type``         accepted value (JSON-native)                    normalized value
===============  ==============================================  ====================
``string``       non-empty text                                  ``str``
``integer``      a whole number                                  ``int``
``number``       a finite number                                 ``float``
``boolean``      ``true`` or ``false``                           ``bool``
``choice``       one of ``choices``                              ``str``
``path``         text or path-like object                        ``str`` (as given)
``string_list``  a non-empty list of non-empty texts             ``list[str]``
===============  ==============================================  ====================
"""

import keyword
import math
import numbers
import os
import re
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, NoReturn, get_args

from retman._errors import CODES
from retman.exceptions import InvalidValueError

OptionType = Literal[
    "string", "integer", "number", "boolean", "choice", "path", "string_list"
]
PathRole = Literal["input", "output", "root"]
Cardinality = Literal["single", "bounded", "unbounded"]
Writes = Literal["none", "add", "replace", "delete"]

OPTION_TYPES: Final[tuple[str, ...]] = get_args(OptionType)
"""Allowed values of :attr:`Option.type`."""
TOOL: Final = "retman"
"""Name of the tool: the prefix of every ``operation_id`` (AGI-2.2)."""
SUMMARY_MAX_CHARS: Final = 100
"""Maximum length of :attr:`Command.summary` (DOC-1.7)."""
DESCRIPTION_MAX_CHARS: Final = 600
"""Maximum length of summary, description and rules together (DOC-1.7, AGI-2.2)."""
OPERATION_ID_MAX_CHARS: Final = 48
"""Maximum length of an ``operation_id`` (AGI-5.2)."""
ERROR_CODE_NAMES: Final[tuple[str, ...]] = tuple(
    entry.code for entry in CODES if entry.exit_code is not None
)
"""Registry codes a command can declare in :attr:`Command.errors`."""

_NUMERIC_TYPES: Final = ("number", "integer")
_OPTION_NAME = re.compile(r"[a-z][a-z0-9_]*")
_COMMAND_NAME = re.compile(r"[a-z][a-z0-9]* [a-z][a-z0-9]*(?:-[a-z0-9]+)*")
_RESULT_SCHEMA = re.compile(r"retman-[a-z][a-z0-9-]*/[1-9][0-9]*")
_FUNCTION_PATH = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
_SHOWN_MAX_CHARS = 200

_EXPECTED: Final[Mapping[str, str]] = {
    "number": "number",
    "integer": "integer",
    "string": "string",
    "boolean": "boolean",
    "choice": "string",
    "string_list": "array of strings",
    "path": "string (path)",
}


# --- validation helpers ---------------------------------------------------------------


def _shown(value: object) -> object:
    """Return a JSON-compatible, bounded rendering of an offending value."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        return number if math.isfinite(number) else str(number)
    if isinstance(value, str):
        if len(value) > _SHOWN_MAX_CHARS:
            return value[: _SHOWN_MAX_CHARS - 1] + "…"
        return value
    return f"<{type(value).__name__}>"


def _text(value: object) -> str:
    """Return the value for a message: ``repr`` of scalars, else the type name."""
    if value is None or isinstance(value, bool | str | numbers.Real):
        return repr(_shown(value))
    return f"a value of type {type(value).__name__}"


def _label(option: "Option", index: int | None) -> str:
    return option.name if index is None else f"{option.name}[{index}]"


def _fail(
    option: "Option",
    index: int | None,
    reason: str,
    message: str,
    *,
    hint: str | None = None,
    **details: object,
) -> NoReturn:
    """Raise the ``validation_error`` of an option value."""
    payload: dict[str, object] = {"reason": reason, "option": option.name}
    if index is not None:
        payload["index"] = index
    payload.update(details)
    raise InvalidValueError(
        f"Option {_label(option, index)!r}: {message}", details=payload, hint=hint
    )


def _fail_type(option: "Option", value: object, index: int | None = None) -> NoReturn:
    expected = _EXPECTED[option.type] if index is None else "string"
    _fail(
        option,
        index,
        "type",
        f"expected {expected}, got {_text(value)}",
        expected=expected,
        value=_shown(value),
        got=type(value).__name__,
    )


def _check_bounds(option: "Option", number: float) -> None:
    if option.minimum is not None and number < option.minimum:
        _fail(
            option,
            None,
            "minimum",
            f"must be >= {option.minimum:g}, got {number:g}",
            minimum=option.minimum,
            value=number,
        )
    if option.maximum is not None and number > option.maximum:
        _fail(
            option,
            None,
            "maximum",
            f"must be <= {option.maximum:g}, got {number:g}",
            maximum=option.maximum,
            value=number,
        )
    if option.exclusive_minimum is not None and number <= option.exclusive_minimum:
        _fail(
            option,
            None,
            "exclusive_minimum",
            f"must be > {option.exclusive_minimum:g}, got {number:g}",
            exclusive_minimum=option.exclusive_minimum,
            value=number,
        )


def _number(option: "Option", value: object, index: int | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        _fail_type(option, value, index)
    number = float(value)
    if not math.isfinite(number):
        _fail(
            option,
            index,
            "not_finite",
            f"must be a finite number, got {number}",
            value=str(number),
        )
    _check_bounds(option, number)
    return number


def _integer(option: "Option", value: object, index: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        _fail_type(option, value, index)
    if isinstance(value, numbers.Integral):
        number = int(value)
    else:
        real = float(value)
        if not math.isfinite(real) or not real.is_integer():
            _fail_type(option, value, index)
        number = int(real)
    _check_bounds(option, number)
    return number


def _string(option: "Option", value: object, index: int | None = None) -> str:
    if not isinstance(value, str):
        _fail_type(option, value, index)
    if not value.strip():
        _fail(option, index, "empty", "must not be empty", value=value)
    return value


def _boolean(option: "Option", value: object, index: int | None = None) -> bool:
    if not isinstance(value, bool):
        _fail_type(option, value, index)
    return value


def _choice(option: "Option", value: object, index: int | None = None) -> str:
    if not isinstance(value, str):
        _fail_type(option, value, index)
    if value not in option.choices:
        allowed = ", ".join(option.choices)
        _fail(
            option,
            index,
            "choice",
            f"{value!r} is not one of: {allowed}",
            hint=f"Allowed values: {allowed}.",
            allowed=list(option.choices),
            value=_shown(value),
        )
    return value


def _path(option: "Option", value: object, index: int | None = None) -> str:
    text = os.fspath(value) if isinstance(value, str | os.PathLike) else None
    if not isinstance(text, str):
        _fail_type(option, value, index)
    if not text.strip():
        _fail(option, index, "empty", "must not be empty", value=text)
    if "\0" in text:
        _fail(option, index, "invalid_path", "must not contain a NUL character")
    return text


def _string_list(
    option: "Option", value: object, index: int | None = None
) -> list[str]:
    if not isinstance(value, list | tuple):
        _fail_type(option, value)
    if not value:
        _fail(option, None, "empty", "must not be an empty list")
    return [_string(option, item, number) for number, item in enumerate(value)]


_NORMALIZERS: Final[Mapping[str, Callable[..., Any]]] = {
    "number": _number,
    "integer": _integer,
    "string": _string,
    "boolean": _boolean,
    "choice": _choice,
    "path": _path,
    "string_list": _string_list,
}


# --- declarations ---------------------------------------------------------------------


@dataclass(frozen=True)
class Effects:
    """What a command does to the outside world (AGI-2.2 ``effects``).

    Attributes
    ----------
    read_only : bool
        The command changes nothing.
    writes : {"none", "add", "replace", "delete"}
        Kind of write: ``"add"`` creates files and never replaces one, ``"replace"``
        can replace an existing file (with ``force``).
    idempotent : bool
        Calling it again with the same options gives the same state.
    network : bool
        The command uses the network (the model server, a tool's data service).
    destructive : bool
        The command can replace or delete existing data.
    """

    read_only: bool
    writes: Writes
    idempotent: bool
    network: bool
    destructive: bool

    def __post_init__(self) -> None:
        """Validate that ``read_only`` agrees with the other fields."""
        if self.read_only and (self.writes != "none" or self.destructive):
            raise ValueError("A read-only command writes nothing and destroys nothing")
        if not self.read_only and self.writes == "none":
            raise ValueError("A command that is not read-only declares what it writes")


@dataclass(frozen=True)
class Option:
    """One option of a command: a keyword argument of its operation.

    The same ``name`` is used in Python, in JSON input and, as ``--kebab-case``
    (:attr:`flag`), on the command line.

    Parameters
    ----------
    name : str
        ``snake_case`` name; a valid Python identifier and no keyword.
    type : OptionType
        Value type (see the module docstring).
    description : str
        English description, for people and agents.
    required : bool, optional
        The option must be given; incompatible with ``default``.
    default : object, optional
        Default value; ``None`` means "no default" (the operation applies its own).
    choices : tuple of str, optional
        Allowed values; required for ``choice`` and forbidden for other types.
    meanings : Mapping of str to str, optional
        One-line meaning of every allowed value of a ``choice`` option; the keys are
        exactly ``choices``.
    minimum, maximum : float, optional
        Inclusive bounds of ``number`` and ``integer``.
    exclusive_minimum : float, optional
        Exclusive lower bound; not combinable with ``minimum``.
    unit : str, optional
        Unit of the value.
    path_role : {"input", "output", "root"}, optional
        Role of a ``path`` option, required for it and forbidden for other types:
        ``"input"`` is read, ``"output"`` is written (a file or a folder).
    one_of : str, optional
        Name of the exclusion group: at most one option of a group may be given.

    Raises
    ------
    ValueError
        If the declaration is inconsistent.
    """

    name: str
    type: OptionType
    description: str
    required: bool = False
    default: object = None
    choices: tuple[str, ...] = ()
    meanings: Mapping[str, str] = field(default_factory=dict)
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = None
    unit: str | None = None
    path_role: PathRole | None = None
    one_of: str | None = None

    def __post_init__(self) -> None:
        """Validate the field values."""
        name = self.name
        if (
            not isinstance(name, str)
            or not _OPTION_NAME.fullmatch(name)
            or keyword.iskeyword(name)
        ):
            raise ValueError(
                f"Option name {name!r} must be snake_case and not a Python keyword"
            )
        self._check_declaration()
        if self.default is not None:
            try:
                self.normalize(self.default)
            except InvalidValueError as error:
                raise ValueError(
                    f"Option {name!r}: invalid default {self.default!r}: {error}"
                ) from error

    def _check_declaration(self) -> None:
        def bad(problem: str) -> ValueError:
            return ValueError(f"Option {self.name!r}: {problem}")

        if self.type not in OPTION_TYPES:
            raise bad(f"unknown type {self.type!r}; allowed: {', '.join(OPTION_TYPES)}")
        if not isinstance(self.description, str) or not self.description.strip():
            raise bad("description must be a non-empty string")
        if self.required and self.default is not None:
            raise bad("a required option cannot have a default")
        if self.type == "choice":
            if not self.choices or not all(
                isinstance(c, str) and c for c in self.choices
            ):
                raise bad("a choice option needs a tuple of non-empty choices")
            if len(set(self.choices)) != len(self.choices):
                raise bad("choices must be unique")
            if set(self.meanings) != set(self.choices) or not all(
                isinstance(text, str) and text.strip()
                for text in self.meanings.values()
            ):
                raise bad("meanings must give a non-empty meaning for every choice")
        elif self.choices or self.meanings:
            raise bad("choices and meanings are allowed only for type 'choice'")
        bounds = {
            "minimum": self.minimum,
            "maximum": self.maximum,
            "exclusive_minimum": self.exclusive_minimum,
        }
        given = {key: value for key, value in bounds.items() if value is not None}
        if given and self.type not in _NUMERIC_TYPES:
            raise bad(f"{', '.join(given)} are allowed only for numeric types")
        if any(
            isinstance(value, bool) or not math.isfinite(value)
            for value in given.values()
        ):
            raise bad("bounds must be finite numbers")
        if self.minimum is not None and self.exclusive_minimum is not None:
            raise bad("minimum and exclusive_minimum are mutually exclusive")
        lower = self.minimum if self.minimum is not None else self.exclusive_minimum
        if lower is not None and self.maximum is not None and lower > self.maximum:
            raise bad("the lower bound exceeds maximum")
        if self.type == "path":
            if self.path_role not in get_args(PathRole):
                raise bad("a path option needs path_role input, output or root")
        elif self.path_role is not None:
            raise bad("path_role is allowed only for type 'path'")
        if self.unit is not None and not self.unit:
            raise bad("unit must be a non-empty string")
        if self.one_of is not None and not _OPTION_NAME.fullmatch(self.one_of):
            raise bad("one_of must be a snake_case group name")

    @property
    def flag(self) -> str:
        """str: command-line flag, ``--kebab-case`` of :attr:`name` (AGI-3.1)."""
        return "--" + self.name.replace("_", "-")

    @property
    def writes(self) -> bool:
        """bool: the option names something the command writes (an output path)."""
        return self.path_role == "output"

    def normalize(self, value: object) -> Any:
        """Validate one value and return its normalized form.

        Parameters
        ----------
        value : object
            JSON-native value of the option (``None`` is handled by the caller).

        Returns
        -------
        object
            Normalized value (see the module docstring for the type table).

        Raises
        ------
        InvalidValueError
            The value has the wrong type or violates a bound, the choices or an
            emptiness rule. ``details`` hold ``option``, ``reason`` (``type``,
            ``not_finite``, ``minimum``, ``maximum``, ``exclusive_minimum``,
            ``choice``, ``empty``, ``invalid_path``), the offending ``value`` and,
            for list items, the ``index``.
        """
        return _NORMALIZERS[self.type](self, value)


@dataclass(frozen=True)
class Command:
    """One catalog command: a function of :mod:`retman.operations`.

    Parameters
    ----------
    name : str
        ``"<group> <verb>"`` in lowercase, e.g. ``"plan run"``.
    operation_id : str
        ``retman_`` followed by ``name`` with spaces and hyphens replaced by
        underscores (``"retman_plan_run"``); at most 48 characters.
    summary : str
        One sentence that starts with a verb, at most 100 characters (DOC-1.7).
    description : str
        What it does, when to use it, when not to use it and what instead.
    function : str
        Dotted path of the operation, e.g. ``"retman.operations.plan_run"``; imported
        when the command runs and called with keyword arguments named like the
        options.
    options : tuple of Option
        Options in catalog order; names are unique.
    result_schema : str
        Id of the domain document in the ``result`` of the envelope
        (``"retman-plan/1"``).
    effects : Effects
        What the command does to the outside world.
    cardinality : {"single", "bounded", "unbounded"}, optional
        Size class of the result (AGI-2.2).
    check : bool, optional
        The command has the option ``check`` (a plan without effects, AGI-1.3).
    rules : tuple of str, optional
        Short imperative rules for agents.
    errors : tuple of str, optional
        Registry codes the command can raise besides ``internal_error``.
    examples : tuple of Mapping, optional
        Example option sets (valid inputs of the command); at least one.
    example_results : tuple of Mapping, optional
        Excerpt of the result of each example, in the order of ``examples``.

    Raises
    ------
    ValueError
        If the declaration is inconsistent.
    """

    name: str
    operation_id: str
    summary: str
    description: str
    function: str
    options: tuple[Option, ...]
    result_schema: str
    effects: Effects
    cardinality: Cardinality = "single"
    check: bool = False
    rules: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    examples: tuple[Mapping[str, object], ...] = ()
    example_results: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        """Validate the field values."""

        def bad(problem: str) -> ValueError:
            return ValueError(f"Command {self.name!r}: {problem}")

        if not isinstance(self.name, str) or not _COMMAND_NAME.fullmatch(self.name):
            raise bad("name must be '<group> <verb>' in lowercase")
        expected_id = f"{TOOL}_" + self.name.replace(" ", "_").replace("-", "_")
        if self.operation_id != expected_id:
            raise bad(f"operation_id must be {expected_id!r}")
        if len(self.operation_id) > OPERATION_ID_MAX_CHARS:
            raise bad(
                f"operation_id is longer than {OPERATION_ID_MAX_CHARS} characters"
            )
        if not self.summary.strip() or "\n" in self.summary:
            raise bad("summary must be a non-empty single line")
        if len(self.summary) > SUMMARY_MAX_CHARS:
            raise bad(f"summary is longer than {SUMMARY_MAX_CHARS} characters")
        if not self.description.strip():
            raise bad("description must be a non-empty string")
        budget = len(self.summary) + len(self.description) + len(" ".join(self.rules))
        if budget > DESCRIPTION_MAX_CHARS:
            raise bad(
                f"summary, description and rules take {budget} characters; "
                f"the limit is {DESCRIPTION_MAX_CHARS}"
            )
        if not _RESULT_SCHEMA.fullmatch(self.result_schema):
            raise bad("result_schema must look like 'retman-<kind>/<n>'")
        if not _FUNCTION_PATH.fullmatch(self.function):
            raise bad("function must be a dotted path 'package.module.function'")
        for field_name in ("options", "rules", "errors", "examples", "example_results"):
            if not isinstance(getattr(self, field_name), tuple):
                raise bad(f"{field_name} must be a tuple")
        if not all(isinstance(option, Option) for option in self.options):
            raise bad("options must hold Option instances")
        names = [option.name for option in self.options]
        if len(set(names)) != len(names):
            raise bad("option names must be unique")
        if self.check != ("check" in names):
            raise bad("a command has the option 'check' if and only if check is true")
        if not self.examples:
            raise bad("at least one example is required")
        if len(self.example_results) != len(self.examples):
            raise bad("example_results must hold one excerpt per example")
        unknown_errors = sorted(set(self.errors) - set(ERROR_CODE_NAMES))
        if unknown_errors or len(set(self.errors)) != len(self.errors):
            raise bad(f"errors must be unique registry codes, got {list(self.errors)}")
        for number, example in enumerate(self.examples):
            unknown = sorted(set(example) - set(names))
            if unknown:
                raise bad(f"example #{number} uses unknown options: {unknown}")

    @property
    def group(self) -> str:
        """str: first word of :attr:`name` (``"plan"``)."""
        return self.name.split(" ", 1)[0]

    @property
    def verb(self) -> str:
        """str: second word of :attr:`name` (``"run"``)."""
        return self.name.split(" ", 1)[1]

    @property
    def check_command(self) -> str | None:
        """Str or None: the command that plans this one: itself, with ``check``."""
        return self.name if self.check else None

    def option(self, name: str) -> Option:
        """Return the option called ``name``.

        Raises
        ------
        KeyError
            The command has no such option.
        """
        for option in self.options:
            if option.name == name:
                return option
        raise KeyError(name)

    def command_line(self, options: Mapping[str, object]) -> str:
        """Return the command line that gives this command the ``options``.

        The line is written the way the CLI parses it: ``retman <group> <verb>`` and
        the flags in catalog order, a list as the repeated flag, booleans as bare flags.

        Parameters
        ----------
        options : Mapping[str, object]
            Option values by name; every name is an option of the command.

        Returns
        -------
        str
            The line, quoted for a POSIX shell.
        """
        words = [TOOL, *self.name.split(" ")]
        for option in self.options:
            if option.name not in options:
                continue
            value = options[option.name]
            if option.type == "boolean":
                if value:
                    words.append(option.flag)
                continue
            if isinstance(value, list | tuple):
                for item in value:
                    words += [option.flag, shlex.quote(str(item))]
                continue
            words += [option.flag, shlex.quote(str(value))]
        return " ".join(words)

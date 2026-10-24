"""Exceptions of Retman and the error document of the Nogat registry (ERR-3, ERR-4).

Every error derives from :class:`RetmanError`, which carries what the shared registry
asks of an error (DEV-11.1): a registry ``code``, an English ``message``,
JSON-compatible ``details`` and a one-line ``hint``. Each class has a default code
(:attr:`RetmanError.default_code`) and, where the registry code is coarser than the
class, a default ``details["reason"]`` (:attr:`RetmanError.default_reason`, ERR-1); a
raise site may pass another code or reason. The CLI, the Python API and the
``retman-error/1`` document report the same error the same way
(:func:`error_document`); ``retman._errors`` is generated from the registry copy in
``schemas/nogat/error_registry.json``.

Notes
-----
Messages and hints are English: they are machine output (AGI-9.2). Text for the user
lives in the translation files and is chosen by the code that shows it; where an
exception carries such a text (:class:`OutOfScopeError`) it is a separate attribute.
"""

import copy
import errno
import os
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Any, ClassVar, Final, Literal

from retman._errors import CODES, ErrorCodeName, RegistryCode

ErrorCode = ErrorCodeName
"""Name of a registry code that a CLI call can end with (``_errors.ErrorCodeName``)."""

ERROR_SCHEMA: Final = "retman-error/1"
"""Value of the ``schema`` key of an error document."""

USED_CODES: Final[tuple[str, ...]] = (
    "internal_error",
    "validation_error",
    "not_found",
    "conflict",
    "source_unavailable",
    "missing_dependency",
    "data_error",
    "store_unavailable",
    "io_error",
    "forbidden",
    "calculation_error",
    "no_data",
    "unsupported",
    "cancelled",
    "terminated",
)
"""Registry codes a Retman call can end with; Retman adds none of its own (ERR-1)."""

ERROR_CODES: Final[Mapping[str, RegistryCode]] = MappingProxyType(
    {entry.code: entry for entry in CODES if entry.code in USED_CODES}
)
"""The registry codes Retman uses, keyed by code (from ``_errors``, ERR-3)."""

_INTERNAL_HINT: Final = (
    "This is a bug: report it with the command, the inputs and the Retman version."
)
_IO_HINT: Final = "Check that the path exists and that you have permission to use it."


class Terminated(BaseException):
    """SIGTERM arrived (container stop, timeout): the call ends with ``terminated``.

    A ``BaseException`` like ``KeyboardInterrupt``: no ``except Exception`` of the
    pipeline may turn it into a failed result.
    """


def _jsonable(value: object) -> Any:
    """Return ``value`` as a JSON value; unknown objects become their ``str``."""
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        return sorted((_jsonable(item) for item in value), key=str)
    if isinstance(value, Iterable):
        return [_jsonable(item) for item in value]
    return str(value)


class RetmanError(Exception):
    """Base class of all Retman errors.

    Parameters
    ----------
    message : str, optional
        English description; becomes ``str(exc)``.
    code : ErrorCode or None, optional
        Registry code from :data:`ERROR_CODES`; ``None`` selects the class default
        (:attr:`default_code`).
    details : Mapping[str, object] or None, optional
        JSON-compatible context (``reason``, ``option``, ``value``, ``allowed``,
        ``path``, ``paths``...); stored as an independent copy with ``reason`` first.
    hint : str or None, optional
        One-line remedy naming the option or the command.
    text : str or None, optional
        Translated text for the user, when the raise site has one; the CLI shows it
        instead of ``message``. Never part of the error document.

    Attributes
    ----------
    default_code : ErrorCode
        Code used when the raise site passes none.
    default_reason : str or None
        ``details["reason"]`` used when the raise site gives none.
    code : ErrorCode
        Registry code of this instance.
    details : dict
        Copy of the given context.
    hint : str or None
        Remedy, if any.
    text : str or None
        Translated text for the user, if any.

    Raises
    ------
    ValueError
        If ``code`` is not a key of :data:`ERROR_CODES`.

    Examples
    --------
    >>> error = RetmanError("boom", code="not_found", details={"path": "x"})
    >>> error.code, error.exit_code
    ('not_found', 3)
    """

    default_code: ClassVar[ErrorCode] = "internal_error"
    default_reason: ClassVar[str | None] = None

    code: ErrorCode
    details: dict[str, Any]
    hint: str | None
    text: str | None

    def __init__(
        self,
        message: str = "",
        *,
        code: ErrorCode | None = None,
        details: Mapping[str, object] | None = None,
        hint: str | None = None,
        text: str | None = None,
    ) -> None:
        resolved = self.default_code if code is None else code
        if resolved not in ERROR_CODES:
            raise ValueError(
                f"Unknown error code {resolved!r}; allowed: {', '.join(ERROR_CODES)}"
            )
        super().__init__(message)
        self.code = resolved
        given = copy.deepcopy(dict(details or {}))
        reason = given.pop("reason", self.default_reason)
        self.details = ({"reason": reason} if reason is not None else {}) | given
        self.hint = hint
        self.text = text

    @property
    def exit_code(self) -> int:
        """int: process exit code of this error's code (the registry's)."""
        exit_code = ERROR_CODES[self.code].exit_code
        assert exit_code is not None  # every code of USED_CODES has one
        return exit_code


class UsageError(RetmanError):
    """A command-line option or an environment variable has a wrong value.

    Default code: ``validation_error``, reason ``usage``.
    """

    default_code: ClassVar[ErrorCode] = "validation_error"
    default_reason: ClassVar[str | None] = "usage"


class InvalidValueError(RetmanError, ValueError):
    """A value given to the public API cannot be used (a plan value, an answer).

    Default code: ``validation_error``, reason ``invalid_value``; ``details.option``
    names the value. Also a :class:`ValueError`, so ``except ValueError`` of callers
    that handled the plain exception keeps working.
    """

    default_code: ClassVar[ErrorCode] = "validation_error"
    default_reason: ClassVar[str | None] = "invalid_value"


class ConfigError(RetmanError):
    """The settings cannot be used (DEV-18.1).

    Default code: ``validation_error``, reason ``invalid_config``; a settings file
    named by ``--config`` or ``NOGAT_CONFIG`` that does not exist is ``not_found``
    (reason ``missing_config``) and one that ``retman init`` would overwrite is
    ``conflict`` (reason ``output_exists``).

    Parameters
    ----------
    path : Path
        Settings file that was read (or expected).
    problems : list[str]
        Translation keys under ``config`` in ``src/retman/i18n/pl.toml``,
        e.g. ``"missing_key"``.
    problem_details : dict[str, str]
        Per problem: the setting keys concerned (or other values for the text).
    """

    default_code: ClassVar[ErrorCode] = "validation_error"
    default_reason: ClassVar[str | None] = "invalid_config"

    _SPECIAL: ClassVar[Mapping[str, tuple[ErrorCode, str, str]]] = {
        "missing_file": (
            "not_found",
            "missing_config",
            "Name an existing settings file with `--config` or NOGAT_CONFIG, or "
            "create one with `retman init`.",
        ),
        "already_exists": (
            "conflict",
            "output_exists",
            "Edit the existing [retman] table instead; `retman init` never "
            "overwrites it.",
        ),
    }
    _HINT: ClassVar[str] = (
        "Fix the settings named in details.keys (`retman config show` lists every "
        "setting with its value and source); `retman init` writes a complete "
        "[retman] table into a settings file that has none."
    )

    def __init__(
        self,
        path: Path,
        problems: list[str],
        problem_details: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.problems = problems
        self.problem_details = problem_details or {}
        special = self._SPECIAL.get(problems[0]) if len(problems) == 1 else None
        listed = "; ".join(
            f"{problem} ({self.problem_details[problem]})"
            if self.problem_details.get(problem)
            else problem
            for problem in problems
        )
        details: dict[str, object] = {"path": str(path), "problems": list(problems)}
        if self.problem_details:
            details["keys"] = dict(self.problem_details)
        if special is not None:
            code, reason, hint = special
            details = {"reason": reason} | details
        else:
            code, hint = "validation_error", self._HINT
        super().__init__(
            f"The settings in {path} cannot be used: {listed}",
            code=code,
            details=details,
            hint=hint,
        )


class EvalDatasetError(RetmanError):
    """One or more eval commands are malformed or contradict tool manifests.

    Default code: ``data_error``, reason ``invalid_eval_commands``.
    """

    default_code: ClassVar[ErrorCode] = "data_error"
    default_reason: ClassVar[str | None] = "invalid_eval_commands"

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__(
            "Invalid eval commands: " + "; ".join(problems),
            details={"problems": list(problems)},
            hint="Fix the listed entries of the commands file.",
        )


class ManifestError(RetmanError):
    """A tool manifest or its translations are invalid (programmer error).

    Default code: ``internal_error``, reason ``invalid_manifest``.
    """

    default_code: ClassVar[ErrorCode] = "internal_error"
    default_reason: ClassVar[str | None] = "invalid_manifest"


class TranslationError(RetmanError):
    """A translation key is missing (programmer error).

    Default code: ``internal_error``, reason ``missing_translation``.
    """

    default_code: ClassVar[ErrorCode] = "internal_error"
    default_reason: ClassVar[str | None] = "missing_translation"


class OutOfScopeError(RetmanError):
    """The command matches none of the available operations (W-03).

    Default code: ``unsupported``, reason ``out_of_scope``.

    Parameters
    ----------
    operations : list[str]
        Labels of the available operations shown to the user — of their
        categories when there are more operations than one question can offer.
    text : str
        Translated text for the user listing what Retman can do.
    decisions : list[dict[str, Any]], optional
        The model decisions that led here (audit records: ``name``, ``key``,
        ``confidence``, ``confidence_method``, ``probabilities``), in order.
    """

    default_code: ClassVar[ErrorCode] = "unsupported"
    default_reason: ClassVar[str | None] = "out_of_scope"

    def __init__(
        self,
        operations: list[str],
        text: str,
        decisions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.operations = operations
        self.decisions = decisions or []
        super().__init__(
            "The command matches none of the operations Retman offers",
            details={"operations": list(operations)},
            hint="Describe one of the operations listed in details.operations.",
            text=text,
        )


class KindValidationError(RetmanError):
    """A file does not match its declared data kind (ARCHITECTURE 3.2.6).

    Default code: ``data_error``; a missing file is ``not_found``, one that cannot
    be read ``io_error`` and an undeclared kind ``internal_error``. ``details.reason``
    is ``reason``.

    Parameters
    ----------
    kind : str
        Declared data kind.
    path : Path
        Checked file.
    reason : str
        Translation key under ``kinds.errors`` in ``src/retman/i18n/pl.toml``.
    """

    default_code: ClassVar[ErrorCode] = "data_error"
    _CODES: ClassVar[Mapping[str, ErrorCode]] = {
        "missing_file": "not_found",
        "unreadable_file": "io_error",
        "unknown_kind": "internal_error",
    }

    def __init__(self, kind: str, path: Path, reason: str) -> None:
        self.kind = kind
        self.path = path
        self.reason = reason
        super().__init__(
            f"{path} is not a valid {kind}: {reason}",
            code=self._CODES.get(reason, self.default_code),
            details={"reason": reason, "kind": kind, "path": str(path)},
            hint=f"Give a file that is a valid {kind}.",
        )


class BackendError(RetmanError):
    """The decision or text backend failed.

    Default code: ``source_unavailable``, reason ``backend_error``: the model server
    is a remote service.

    Parameters
    ----------
    url : str
        Server address of the backend (shown by ``retman doctor``).
    message : str, optional
        What went wrong, appended to the summary.
    """

    default_code: ClassVar[ErrorCode] = "source_unavailable"
    default_reason: ClassVar[str | None] = "backend_error"
    summary: ClassVar[str] = "The model server failed"
    remedy: ClassVar[str] = (
        "Run `retman doctor` to test the model server and its settings."
    )

    def __init__(self, url: str, message: str = "") -> None:
        self.url = url
        text = f"{self.summary}: {url}"
        super().__init__(
            f"{text} ({message})" if message else text,
            details={"url": url},
            hint=self.remedy,
        )


class BackendConnectionError(BackendError):
    """The model server did not respond (connection error or timeout).

    Reason ``backend_connection``.
    """

    default_reason: ClassVar[str | None] = "backend_connection"
    summary: ClassVar[str] = "The model server did not respond"
    remedy: ClassVar[str] = (
        "Start the model server or fix the `decision` url; `retman doctor` tests it."
    )


class InvalidModelAnswerError(BackendError):
    """The model answered with something that is not one of the allowed keys.

    Reason ``invalid_model_answer``.
    """

    default_reason: ClassVar[str | None] = "invalid_model_answer"
    summary: ClassVar[str] = "The model answered outside the allowed options"
    remedy: ClassVar[str] = (
        "Repeat the command, or tune the model with `retman eval`; "
        "`retman doctor` tests the model server."
    )


class PlanNotConfirmedError(RetmanError):
    """``execute()`` was called with a plan that was not confirmed.

    Default code: ``conflict``, reason ``plan_not_confirmed``.
    """

    default_code: ClassVar[ErrorCode] = "conflict"
    default_reason: ClassVar[str | None] = "plan_not_confirmed"


class InputRequiredError(RetmanError):
    """An answer or a confirmation is needed and cannot be asked (AGI-3.5).

    Default code: ``validation_error``, reason ``input_required``. ``details.questions``
    lists the open questions (``name``, ``text``, ``options``); ``details.option``
    names the option that gives a confirmation or a value without a prompt.
    """

    default_code: ClassVar[ErrorCode] = "validation_error"
    default_reason: ClassVar[str | None] = "input_required"


class PlanIncompleteError(InputRequiredError):
    """``confirm()`` or ``execute()`` was called while questions are still open.

    Default code: ``validation_error``, reason ``input_required``: an answer is
    missing.
    """


class CheckNotConfirmedError(RetmanError):
    """``Retman.check()`` was called without a fresh ``plan.confirm_check()``.

    A sibling of ``PlanNotConfirmedError``, not a subclass: the remedy differs
    (the availability check needs its own consent, ARCHITECTURE 6.5). Default code:
    ``conflict``, reason ``check_not_confirmed``.
    """

    default_code: ClassVar[ErrorCode] = "conflict"
    default_reason: ClassVar[str | None] = "check_not_confirmed"


def _os_error_parts(exc: OSError) -> tuple[str, dict[str, Any]]:
    """Message and details of a file-system error (``errno`` name and ``path``)."""
    filename = exc.filename
    path = (
        os.fsdecode(filename)
        if isinstance(filename, str | bytes | os.PathLike)
        else None
    )
    reason = exc.strerror or str(exc)
    details: dict[str, Any] = {}
    if exc.errno is not None:
        details["errno"] = errno.errorcode.get(exc.errno, str(exc.errno))
    if path is not None:
        details["path"] = path
    return (f"{reason}: {path}" if path else reason), details


def error_document(
    exc: BaseException,
    command: str | None = None,
    lang: Literal["pl", "en"] = "en",
) -> dict[str, Any]:
    """Describe an exception as a ``retman-error/1`` document (AGI-4.3).

    The document is the last line of stderr of every CLI call that ends with an
    error (AGI-3.3). A :class:`RetmanError` keeps its ``code``, ``hint`` and
    ``details``. An :class:`OSError` that no operation wrapped is ``io_error``
    (``details``: ``errno`` name and ``path``), :class:`Terminated` is
    ``terminated``, every other exception is a bug and becomes ``internal_error``
    with the exception class in ``details["exception"]``.

    Parameters
    ----------
    exc : BaseException
        The exception to describe.
    command : str or None, optional
        Catalog name of the failed command (``"plan run"``), if known.
    lang : {"pl", "en"}, optional
        Language of ``title`` (machine output is English, AGI-9.2); ``message`` and
        ``hint`` are always English.

    Returns
    -------
    dict
        ``{"schema": "retman-error/1", "code", "title", "message", "hint",
        "details", "exit_code", "command"}``; JSON-compatible. ``hint`` and
        ``command`` are left out when there is none.

    Raises
    ------
    ValueError
        If ``lang`` is not ``"pl"`` or ``"en"``.

    Examples
    --------
    >>> document = error_document(UsageError("bad option"), "plan run")
    >>> document["code"], document["exit_code"], document["details"]["reason"]
    ('validation_error', 2, 'usage')
    """
    if lang not in ("pl", "en"):
        raise ValueError(f"Unknown language {lang!r}; allowed: pl, en")
    details: Mapping[str, object]
    hint: str | None
    if isinstance(exc, RetmanError):
        code: ErrorCode = exc.code
        message = str(exc)
        hint = exc.hint
        details = exc.details
    elif isinstance(exc, Terminated):
        code = "terminated"
        message = "The process received SIGTERM"
        hint = None
        details = {}
    elif isinstance(exc, OSError):
        code = "io_error"
        message, details = _os_error_parts(exc)
        hint = _IO_HINT
    else:
        code = "internal_error"
        message = f"{type(exc).__name__}: {exc}"
        hint = _INTERNAL_HINT
        details = {"exception": type(exc).__name__}
    entry = ERROR_CODES[code]
    document: dict[str, Any] = {
        "schema": ERROR_SCHEMA,
        "code": code,
        "title": entry.title if lang == "en" else entry.title_pl,
        "message": message or entry.title,
    }
    if hint:
        document["hint"] = hint
    document["details"] = _jsonable(details)
    document["exit_code"] = entry.exit_code
    if command is not None:
        document["command"] = command
    return document

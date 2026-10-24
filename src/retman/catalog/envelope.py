"""Result envelope ``retman-result/1`` and the return protocol of operations (AGI-4.2).

:func:`~retman.catalog.run_command` wraps what an operation returns in a
:class:`CommandResult`, the one document that the CLI (``--json``) and Python callers
share (Nogat ``result-1``)::

    {
      "schema": "retman-result/1",
      "tool": "retman",
      "version": "0.1.0",
      "command": "doctor check",
      "check": false,
      "status": "partial",
      "result": {"schema": "retman-doctor/1", "...": "..."},
      "items": [{"id": "model.1", "status": "failed", "code": "source_unavailable"}],
      "notices": [{"level": "warning", "code": "...", "message": "..."}],
      "page": {"total": 40, "next_cursor": "...", "truncated": true}
    }

``status`` follows from ``items``: ``ok`` when no unit failed, ``partial`` when some
did and some did not, ``failed`` when none succeeded; a call that the user stopped is
``cancelled``. ``partial`` and ``failed`` are outcomes, not errors (ERR §1): the
document is printed and the exit code is 10 or 11. An error raises a
:class:`~retman.exceptions.RetmanError` instead and leaves no envelope.

Return protocol of an operation
-------------------------------
An operation (a function of :mod:`retman.operations`) returns an :class:`Output`: the
domain document (a mapping, the ``schema`` key is added), the per-unit ``items`` of a
batch, the non-fatal :class:`Notice` objects, the paths of the files it wrote (listed
in ``result["files"]`` with size and SHA-256), the page of a collection and, for the
terminal, a ``view`` that renders the result as text.
"""

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from retman import __version__
from retman._errors import OUTCOMES
from retman._json import to_jsonable
from retman.exceptions import ERROR_CODES, RetmanError
from retman.i18n.loader import Texts

RESULT_SCHEMA: Final = "retman-result/1"
"""Value of the ``schema`` key of a serialized :class:`CommandResult`."""
TOOL: Final = "retman"
"""Value of the ``tool`` key of a serialized :class:`CommandResult`."""

Status = Literal["ok", "partial", "failed", "cancelled"]
NoticeLevel = Literal["info", "warning"]
ItemStatus = Literal["ok", "failed"]
FileStatus = Literal["written", "replaced"]

_NOTICE_LEVELS: Final[tuple[str, ...]] = ("info", "warning")
_NOTICE_CODE = re.compile(r"[a-z][a-z0-9_]*")
_HASH_CHUNK = 1 << 20


@dataclass(frozen=True)
class Notice:
    """Non-fatal observation reported next to a result (AGI-4.2 ``notices``).

    Parameters
    ----------
    level : {"info", "warning"}
        Severity.
    code : str
        Stable machine-readable ``snake_case`` identifier.
    message : str
        Human-readable message.

    Raises
    ------
    ValueError
        If ``level`` is unknown, ``code`` is not ``snake_case`` or ``message`` is
        empty.
    """

    level: NoticeLevel
    code: str
    message: str

    def __post_init__(self) -> None:
        """Validate the field values."""
        if self.level not in _NOTICE_LEVELS:
            raise ValueError(
                f"Unknown notice level {self.level!r}; allowed: info, warning"
            )
        if not _NOTICE_CODE.fullmatch(self.code):
            raise ValueError(f"Notice code {self.code!r} must be snake_case")
        if not self.message.strip():
            raise ValueError("Notice message must not be empty")

    def to_dict(self) -> dict[str, str]:
        """Return ``{"level", "code", "message"}``."""
        return {"level": self.level, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class Item:
    """Outcome of one unit of a batch operation (AGI-4.2 ``items``).

    Parameters
    ----------
    id : str or int
        Identifier of the unit, stable within one command.
    status : {"ok", "failed"}
        Whether the unit succeeded.
    code : str, optional
        Registry code of the failure; required for a failed unit.
    reason : str, optional
        Project-specific sub-code of the failure (``details.reason``, ERR-1).
    message : str, optional
        What happened.

    Raises
    ------
    ValueError
        If the status is unknown, a failed unit has no registry code or an
        unsuccessful one carries a code.
    """

    id: str | int
    status: ItemStatus
    code: str | None = None
    reason: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        """Validate the field values."""
        if self.status not in ("ok", "failed"):
            raise ValueError(
                f"Unknown item status {self.status!r}; allowed: ok, failed"
            )
        if self.status == "failed" and self.code not in ERROR_CODES:
            raise ValueError(f"A failed unit needs a registry code, got {self.code!r}")
        if self.status == "ok" and self.code is not None:
            raise ValueError("A unit that succeeded has no error code")

    def to_dict(self) -> dict[str, Any]:
        """Return ``{"id", "status"}`` and ``code``, ``reason``, ``message`` if set."""
        document: dict[str, Any] = {"id": self.id, "status": self.status}
        for key in ("code", "reason", "message"):
            value = getattr(self, key)
            if value is not None:
                document[key] = value
        return document


@dataclass(frozen=True)
class FileRecord:
    """File written by a command, as listed in ``result["files"]`` (DEV-19.19).

    Parameters
    ----------
    path : str
        Absolute path of the file.
    size_bytes : int
        Size of the file in bytes.
    sha256 : str
        Hex SHA-256 digest of the file content.
    status : {"written", "replaced"}, optional
        ``"replaced"`` when the file existed before (``force``), else ``"written"``.
    """

    path: str
    size_bytes: int
    sha256: str
    status: FileStatus = "written"

    def to_dict(self) -> dict[str, Any]:
        """Return ``{"path", "size_bytes", "sha256", "status"}``."""
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status,
        }


@dataclass(frozen=True)
class Output:
    """What an operation returns: its document and everything that goes with it.

    Parameters
    ----------
    result : Mapping or None
        The domain document without its ``schema`` (the envelope adds it); ``None``
        when nothing was produced (a cancelled call).
    items : sequence of Item, optional
        Per-unit outcomes of a batch operation; they decide the ``status``.
    notices : sequence of Notice, optional
        Non-fatal observations.
    files, replaced : sequence of str or os.PathLike, optional
        Paths of the files the operation wrote (absolute; they must exist) and the
        ones among them that existed before.
    check : bool, optional
        The result is the plan of a ``check`` run: nothing was written.
    cancelled : bool, optional
        The user stopped the call (a declined plan); ``status`` is ``cancelled``.
    page : Mapping, optional
        ``{"total", "next_cursor", "truncated"}`` of a collection.
    schema : str, optional
        Id of the document when it is not the one the command declares (the plan of
        a ``check`` run).
    view : callable, optional
        Renders the result as text for the terminal; it gets the translated texts.
        Never part of the document.
    """

    result: Mapping[str, Any] | None
    items: Sequence[Item] = ()
    notices: Sequence[Notice] = ()
    files: Sequence[str | os.PathLike[str]] = ()
    replaced: Sequence[str | os.PathLike[str]] = ()
    check: bool = False
    cancelled: bool = False
    page: Mapping[str, Any] | None = None
    schema: str | None = None
    view: Callable[[Texts], str] | None = field(default=None, compare=False)


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Return the hex SHA-256 digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def file_records(
    paths: Iterable[str | os.PathLike[str]],
    replaced: Iterable[str | os.PathLike[str]] = (),
) -> tuple[FileRecord, ...]:
    """Describe the files an operation wrote: absolute path, size and SHA-256.

    Raises
    ------
    RetmanError
        A reported file does not exist (``internal_error``, reason
        ``missing_output_file``).
    """
    replaced_paths = {os.path.abspath(os.fspath(item)) for item in replaced}
    records: dict[str, FileRecord] = {}
    for item in paths:
        path = os.path.abspath(os.fspath(item))
        if path in records:
            continue
        if not os.path.isfile(path):
            raise RetmanError(
                f"The operation reported an output file that does not exist: {path}",
                details={"reason": "missing_output_file", "path": path},
            )
        records[path] = FileRecord(
            path=path,
            size_bytes=os.path.getsize(path),
            sha256=sha256_file(path),
            status="replaced" if path in replaced_paths else "written",
        )
    return tuple(records.values())


def status_of(items: Sequence[Item]) -> Literal["ok", "partial", "failed"]:
    """Return the outcome that the per-unit outcomes make (AGI-4.2).

    Parameters
    ----------
    items : sequence of Item
        The units of a batch.

    Returns
    -------
    {"ok", "partial", "failed"}
        ``ok`` when no unit failed, ``failed`` when no unit succeeded, else
        ``partial``.
    """
    failed = sum(1 for item in items if item.status == "failed")
    if not failed:
        return "ok"
    return "failed" if failed == len(items) else "partial"


@dataclass(frozen=True)
class CommandResult:
    """Envelope of a command run (``retman-result/1``).

    Parameters
    ----------
    command : str
        Catalog name of the command (``"doctor check"``).
    result_schema : str
        Id of the domain document, the ``schema`` key of the serialized ``result``.
    output : Output
        What the operation returned.

    Attributes
    ----------
    status : {"ok", "partial", "failed", "cancelled"}
        The overall outcome.
    exit_code : int
        The exit code of that outcome (ERR §1): 0, 10, 11 or 130.
    """

    command: str
    result_schema: str
    output: Output
    files: tuple[FileRecord, ...] = field(init=False)

    def __post_init__(self) -> None:
        """Describe the written files."""
        object.__setattr__(
            self, "files", file_records(self.output.files, self.output.replaced)
        )

    @property
    def check(self) -> bool:
        """bool: the run was a plan without effects."""
        return self.output.check

    @property
    def result(self) -> Mapping[str, Any] | None:
        """Mapping or None: the domain document without its ``schema``."""
        return self.output.result

    @property
    def items(self) -> Sequence[Item]:
        """Sequence of Item: the per-unit outcomes of a batch."""
        return self.output.items

    @property
    def notices(self) -> Sequence[Notice]:
        """Sequence of Notice: the non-fatal observations."""
        return self.output.notices

    @property
    def status(self) -> Status:
        """str: ``ok``, ``partial``, ``failed`` or ``cancelled``."""
        return "cancelled" if self.output.cancelled else status_of(self.output.items)

    @property
    def exit_code(self) -> int:
        """int: the exit code of :attr:`status` (the registry's outcomes)."""
        return OUTCOMES[self.status]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the envelope to a JSON-compatible ``retman-result/1`` dict.

        Returns
        -------
        dict
            ``schema``, ``tool``, ``version``, ``command``, ``check``, ``status``,
            ``result`` (a document with its ``schema`` first, and ``files`` when
            files were written; ``None`` when nothing was produced), ``items``,
            ``notices`` and, for a collection, ``page``.

        Raises
        ------
        TypeError
            If the result is not a document (a mapping).
        """
        result: dict[str, Any] | None = None
        if self.output.result is not None:
            document = to_jsonable(self.output.result)
            if not isinstance(document, dict):
                raise TypeError(
                    f"The result of {self.command!r} must be a document (a mapping), "
                    f"got {type(document).__name__}"
                )
            result = {"schema": self.output.schema or self.result_schema, **document}
            if self.files:
                result["files"] = [record.to_dict() for record in self.files]
        envelope: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "tool": TOOL,
            "version": __version__,
            "command": self.command,
            "check": self.check,
            "status": self.status,
            "result": result,
            "items": [item.to_dict() for item in self.items],
            "notices": [notice.to_dict() for notice in self.notices],
        }
        if self.output.page is not None:
            envelope["page"] = to_jsonable(dict(self.output.page))
        return envelope

    def to_json(self, indent: int | None = None) -> str:
        """Serialize the envelope to JSON text (UTF-8 characters are not escaped).

        Parameters
        ----------
        indent : int, optional
            Indentation of the output; ``None`` gives a single line.
        """
        return json.dumps(
            self.to_dict(), ensure_ascii=False, allow_nan=False, indent=indent
        )

    def view(self, texts: Texts) -> str:
        """Render the result for the terminal in the language of ``texts``.

        The operation's own rendering when it has one, else the document as indented
        JSON.
        """
        if self.output.view is not None:
            return self.output.view(texts)
        return self.to_json(indent=2) + "\n"

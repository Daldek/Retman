"""Outcomes and errors of a command-line call: exit codes, documents, SIGTERM.

An error (ERR §2) ends a call with the exit code of its registry code and, as the last
line of stderr, the ``retman-error/1`` document as compact JSON (AGI-3.3). An outcome
(ERR §1) that is not an error needs no error document: ``cancelled`` (the user stopped
the call) has its own exit code, and ``partial`` and ``failed`` print the result they
belong to: the ``retman-result/1`` envelope with ``--json`` (AGI-3.2), the text of the
result otherwise (:func:`report_outcome`). The CLI has one place for this, here.
"""

import json
import signal
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from types import FrameType
from typing import TYPE_CHECKING, Any, Final, TextIO

from retman._errors import OUTCOMES
from retman.exceptions import Terminated, error_document

if TYPE_CHECKING:
    from retman.catalog.envelope import CommandResult
    from retman.i18n.loader import Texts

EXIT_OK: Final = OUTCOMES["ok"]
EXIT_PARTIAL: Final = OUTCOMES["partial"]
EXIT_FAILED: Final = OUTCOMES["failed"]
EXIT_CANCELLED: Final = OUTCOMES["cancelled"]


def write_document(document: Mapping[str, Any], stream: TextIO | None = None) -> int:
    """Write an error document as the last line of stderr; return its exit code.

    Parameters
    ----------
    document : Mapping[str, Any]
        A ``retman-error/1`` document.
    stream : TextIO, optional
        Where the line goes; stderr when ``None``.

    Returns
    -------
    int
        The document's ``exit_code``.
    """
    target = stream if stream is not None else sys.stderr
    print(json.dumps(document, separators=(",", ":")), file=target, flush=True)
    exit_code: int = document["exit_code"]
    return exit_code


def report_outcome(
    result: "CommandResult",
    *,
    as_json: bool,
    texts: "Texts",
    stream: TextIO | None = None,
) -> int:
    """Print the result of a command and return the exit code of its status.

    With ``as_json`` the stream gets exactly the envelope on one line and nothing
    else (AGI-3.2); otherwise the text of the result in the language of ``texts``.
    ``ok``, ``partial``, ``failed`` and ``cancelled`` are all printed: they are
    outcomes, not errors (ERR §1).

    Parameters
    ----------
    result : CommandResult
        The envelope of the command.
    as_json : bool
        Print the envelope instead of the text.
    texts : Texts
        Translated texts for the terminal rendering.
    stream : TextIO, optional
        Where the output goes; stdout when ``None``.

    Returns
    -------
    int
        ``0``, ``10``, ``11`` or ``130``.
    """
    target = stream if stream is not None else sys.stdout
    if as_json:
        print(result.to_json(), file=target, flush=True)
    else:
        print(result.view(texts), end="", file=target, flush=True)
    return result.exit_code


def report_error(
    error: BaseException,
    *,
    text: str | None = None,
    command: str | None = None,
    stream: TextIO | None = None,
) -> int:
    """Write the text for the user, then the error document; return the exit code.

    Parameters
    ----------
    error : BaseException
        What ended the call.
    text : str, optional
        The text for the user in the language of the call; printed before the
        document. Nothing else follows the document.
    command : str, optional
        Catalog name of the command that failed, for the document.
    stream : TextIO, optional
        Where the lines go; stderr when ``None``.

    Returns
    -------
    int
        The exit code of the error's registry code.
    """
    target = stream if stream is not None else sys.stderr
    if text:
        print(text, file=target)
    return write_document(error_document(error, command), target)


@contextmanager
def sigterm_as_exception() -> Iterator[None]:
    """Raise :class:`~retman.exceptions.Terminated` in the main thread on SIGTERM.

    The previous handler is restored on exit. Outside the main thread the handler
    cannot be installed and the block runs without it.
    """

    def handler(signum: int, frame: FrameType | None) -> None:
        raise Terminated

    try:
        previous = signal.signal(signal.SIGTERM, handler)
    except ValueError:  # not the main thread of the main interpreter
        yield
        return
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)

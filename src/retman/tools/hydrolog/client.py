"""Hydrolog's command client: the one module of the adapter that imports the tool.

It implements the ``RunClient`` protocol of ``retman.adapters.catalog`` over Hydrolog's
command layer (``validate_command``, ``run_command``, ``check_command``,
``format_command``, ``command_schema``) and turns Hydrolog's exceptions and its
``hydrolog-result/1`` envelopes into ``ToolError`` and ``ToolRun``.

Hydrolog computes offline and keeps no store, so it has no ``[retman.tools.hydrolog]``
table: the client adds nothing to a call. A file a command reads is the path of an
input of the plan and a file it writes lies in the result folder, both named by the
call builder. What each method may do is split by capability (PRD N-12): ``lookup``
runs only the commands whose catalog entry is read-only, offline and without a plan,
so a preview may let Hydrolog check a plan by computing it; the commands that write
(``soil hsg``, ``route network``) or serve (``gui serve``) never run through it.
"""

import functools
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import hydrolog

from retman.adapters.catalog import (
    CatalogCall,
    RunStatus,
    ToolDocument,
    ToolError,
    ToolFile,
    ToolNotice,
    ToolRun,
)

TOOL = "hydrolog"


@functools.cache
def _entry(command: str) -> Mapping[str, Any]:
    """Return the entry of a command of Hydrolog's catalog.

    The catalog of an installed tool does not change while the process runs.
    """
    document: Any = hydrolog.command_schema(command).to_dict()
    return cast(Mapping[str, Any], document["commands"][0])


def effect_free(command: str) -> bool:
    """Whether a run of the command only computes: no file, network or plan.

    A command with a plan (``check``) has an effect even when its entry says it is
    read-only: ``gui serve`` serves until it is stopped.
    """
    entry = _entry(command)
    effects = entry["effects"]
    return bool(effects["read_only"]) and not effects["network"] and not entry["check"]


def to_tool_error(err: Exception, call: CatalogCall | None = None) -> ToolError:
    """Hydrolog's exception as a ``ToolError`` with its registry ``code`` and reason.

    ``details.option`` and ``details.allowed`` of a rejection survive, so that the
    pipeline can ask the user again about the parameter at fault; ``OSError`` is
    ``io_error`` and anything else a bug of this client, ``internal_error``.
    """
    if isinstance(err, hydrolog.HydrologError):
        details = dict(err.details)
        option = details.get("option")
        allowed = details.get("allowed")
        return ToolError(
            TOOL,
            str(err.code),
            str(err),
            hint=err.hint,
            option=option if isinstance(option, str) else None,
            allowed=[str(item) for item in allowed]
            if isinstance(allowed, list | tuple)
            else None,
            details=details,
            call=call,
        )
    if isinstance(err, OSError):
        return ToolError(TOOL, "io_error", str(err), call=call)
    return ToolError(TOOL, "internal_error", f"{type(err).__name__}: {err}", call=call)


@contextmanager
def translated(call: CatalogCall | None = None) -> Iterator[None]:
    """Raise whatever goes wrong inside the block as a ``ToolError``.

    ``KeyboardInterrupt`` and the like are not ``Exception`` and pass through.
    """
    try:
        yield
    except ToolError:
        raise
    except Exception as err:
        raise to_tool_error(err, call) from err


def run_from_document(
    call: CatalogCall, document: ToolDocument, command_line: str = ""
) -> ToolRun:
    """Build a ``ToolRun`` from a ``hydrolog-result/1`` envelope.

    A computation is ``ok`` or an error (Hydrolog raises, it reports no failed units),
    so the run has no failures; the files are the ``files[]`` of the envelope (what a
    writing command wrote, with the checksum Hydrolog computed), the notices those of
    the envelope, and the whole envelope is the tool's document.
    """
    files = tuple(
        ToolFile(Path(item["path"]), item.get("sha256"), None, item.get("status"))
        for item in document.get("files") or ()
    )
    notices = tuple(
        ToolNotice(item["level"], item["code"], item["message"])
        for item in document.get("notices") or ()
    )
    return ToolRun(
        call.command,
        cast(RunStatus, document["status"]),
        files,
        (),
        notices,
        document,
        command_line,
        str(document.get("schema", "")),
    )


class HydrologClient:
    """The ``RunClient`` of Hydrolog; Hydrolog has no settings in Retman."""

    def __init__(self, settings: Mapping[str, Any]) -> None:
        self.settings = settings

    # --- what exists before the user confirms: offline, effects-free ----------

    def validate(self, call: CatalogCall) -> None:
        """Hydrolog's own checks of the options of the call, without running it."""
        with translated(call):
            hydrolog.validate_command(call.command, **call.options)

    def command_line(self, call: CatalogCall) -> str:
        """Return the canonical ``hydrolog`` command line of the call."""
        with translated(call):
            return hydrolog.format_command(call.command, dict(call.options))

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Run a command without effects and return its envelope.

        Raises
        ------
        ToolError
            ``not_offline`` for every command that writes a file or uses the network
            (``soil hsg``, ``route network``, ``report generate``...).
        """
        with translated(call):
            if not effect_free(call.command):
                raise ToolError(
                    TOOL,
                    "not_offline",
                    f"{call.command!r} is not an offline lookup",
                    call=call,
                )
            return cast(
                ToolDocument,
                hydrolog.run_command(call.command, **call.options).to_dict(),
            )

    # --- what exists only after consent ------------------------------------------

    def run(self, call: CatalogCall) -> ToolRun:
        """Run a command of the catalog; an error is a ``ToolError``."""
        with translated(call):
            result = hydrolog.run_command(call.command, **call.options)
        return run_from_document(call, result.to_dict(), self.command_line(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """Return Hydrolog's plan of a writing command: the target files and actions."""
        with translated(call):
            checked = hydrolog.check_command(call.command, **call.options)
        return cast(ToolDocument, checked.to_dict())

    def query(self, call: CatalogCall) -> ToolDocument:
        """Refuse: Hydrolog has no command that asks a service over the network."""
        raise ToolError(
            TOOL, "not_supported", f"{call.command!r} is not a query", call=call
        )


def create(settings: Mapping[str, Any]) -> HydrologClient:
    """Create the manifest's ``client``: no network and no writes at construction."""
    return HydrologClient(settings)

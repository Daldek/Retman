"""Obserwator command client: the only module of the adapter that imports the tool.

The tool is driven through its public command layer (``validate_command``,
``format_command``, ``run_command``, ``check_command``); the client adds the
environment Retman owns (``root`` and ``raw_root`` from ``[retman.tools.obserwator]``
``store_dir`` and ``raw_store_dir``), turns
the tool's ``obserwator-result/1`` envelope into a ``ToolRun`` and its exceptions into
``ToolError``. What each method may do is split by capability (PRD N-12):
``validate``, ``command_line`` and ``lookup`` are offline and effects-free
(planning code gets only these), ``run``, ``check`` and ``query`` may use the
network or write the store.
"""

import hashlib
import importlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

from retman.adapters.catalog import (
    CatalogCall,
    ToolDocument,
    ToolError,
    ToolFailure,
    ToolFile,
    ToolNotice,
    ToolRun,
)
from retman.exceptions import RetmanError

TOOL = "obserwator"
SCHEMA = "obserwator-result/1"
# Raised by Obserwator as a ``conflict`` when the file system has no hard links;
# Retman words it separately (the remedy is a different disk, not a retry)
NOT_ATOMIC = "not_atomic"
STORE_WRITE_UNSUPPORTED = "store_write_unsupported"
# Item states that are failures of a unit (sync, download, plan)
_FAILED_STATES = ("failed", "stale_plan", "check_failed")
# Commands whose result lists the plain files they wrote as ``files[]`` (``path``,
# ``size_bytes``, ``sha256``, ``status``): the exports to the one file ``output`` and
# the download to ``output_dir``
_WRITING_COMMANDS = ("series export", "store export", "datasets download")
# The command that may write the freshness plan given as ``plan``
_PLAN_COMMANDS = ("store check",)
# Run flags of every command line: ``--json`` makes the CLI print the envelope
# Retman keeps, not the summary for a person
_RUN_FLAGS: Mapping[str, object] = {"json": True}
# The commands whose ``root`` is the raw root (downloaded archives, station sources,
# PMAXTP cells; Obserwator ADR-017 D4); ``store init`` creates the kind of its
# ``kind`` option, the raw root by default. Every other command with a root works on
# the data root (series, station catalogs, analyses), and ``store info`` and
# ``store scan`` read the data root unless the call names a root
RAW_ROOT_COMMANDS: frozenset[str] = frozenset(
    {
        "datasets download",
        "pmaxtp check",
        "pmaxtp sync",
        "pmaxtp read",
        "store check",
        "store sync",
        "store export",
    }
)


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _tool_file(path: Path, status: str | None = None) -> ToolFile:
    return ToolFile(path, _sha256(path) if path.is_file() else None, None, status)


class ObserwatorClient:
    """A ``RunClient`` over the command catalog of Obserwator 3.x.

    ``settings`` is the ``[retman.tools.obserwator]`` table: the data root
    ``store_dir`` or the raw root ``raw_store_dir``, by the kind of the command
    (``RAW_ROOT_COMMANDS``), is added as ``root`` to every command that has that
    option and the call omits it, except where the call names plain files
    (``output_dir``), which the tool does not combine with a store; the raw root is
    also the ``raw_root`` the builders read (``series build``, ``store catalog``).
    ``reference_data_dir`` is exported as ``OBSERWATOR_REFERENCE_DIR`` once,
    before the tool is imported, so that ``store catalog`` reads its static station
    locations from there and not from the tool's own default
    (``<cache_dir>/obserwator/reference``).
    """

    def __init__(self, settings: Mapping[str, Any]) -> None:
        reference = settings.get("reference_data_dir")
        if not reference:
            raise RetmanError(f"[retman.tools.{TOOL}] has no reference_data_dir")
        os.environ["OBSERWATOR_REFERENCE_DIR"] = str(reference)
        self._settings = settings
        self._obserwator: Any = importlib.import_module("obserwator")
        self._exceptions: Any = importlib.import_module("obserwator.exceptions")
        self._commands = {item.name: item for item in self._obserwator.data_commands()}

    # --- options and errors -------------------------------------------------

    def _setting(self, name: str) -> Path:
        try:
            return Path(self._settings[name])
        except KeyError:
            raise RetmanError(f"[retman.tools.{TOOL}] has no {name}") from None

    def _store_root(self, command: str, options: Mapping[str, object]) -> Path:
        """Return the root of ``command``: the raw or the data root, by its kind."""
        if command == "store init":
            raw = options.get("kind", "raw") == "raw"
        else:
            raw = command in RAW_ROOT_COMMANDS
        return self._setting("raw_store_dir" if raw else "store_dir")

    def _options(self, call: CatalogCall) -> dict[str, object]:
        """Return the call's options plus ``root`` and ``raw_root`` where they apply.

        ``stations find`` takes a root only for ``source="store"`` and refuses it
        for the live source; the catalog names such conditions in ``env_root_when``.
        A command that writes plain files (``output_dir``) refuses a root beside
        them: the catalog names the options that exclude each other in ``exclusive``.
        """
        options = dict(call.options)
        spec = self._commands.get(call.command)
        if spec is None:
            return options
        names = {option.name for option in spec.options}
        if (
            "root" not in options
            and "root" in names
            and all(
                options.get(name) == value for name, value in spec.env_root_when.items()
            )
            and not any(
                "root" in group and any(name in options for name in group)
                for group in spec.exclusive
            )
        ):
            options["root"] = str(self._store_root(call.command, options))
        if "raw_root" in names and "raw_root" not in options:
            options["raw_root"] = str(self._setting("raw_store_dir"))
        return options

    def _error(self, err: Exception, call: CatalogCall) -> ToolError:
        """Build a ``ToolError`` for an exception of the tool, with the tool's code."""
        if isinstance(err, OSError):
            detail, details = self._exceptions.describe_os_error(err)
            return ToolError(TOOL, "io_error", str(detail), details=details, call=call)
        if not isinstance(err, self._obserwator.ObserwatorError):
            return ToolError(TOOL, "internal_error", repr(err), call=call)
        details = dict(err.details)
        code = str(err.code)
        if code == "conflict" and details.get("reason") == NOT_ATOMIC:
            code = STORE_WRITE_UNSUPPORTED
        option = details.get("option")
        allowed = details.get("allowed")
        return ToolError(
            TOOL,
            code,
            err.detail,
            hint=err.hint,
            option=option if isinstance(option, str) else None,
            allowed=[str(item) for item in allowed]
            if isinstance(allowed, list | tuple)
            else None,
            details=details,
            call=call,
        )

    def _normalize(self, call: CatalogCall) -> dict[str, object]:
        """Validate the call with the tool; return its options in the tool's form."""
        try:
            return cast(
                dict[str, object],
                self._obserwator.validate_command(
                    call.command, options=self._options(call)
                ),
            )
        except Exception as err:
            raise self._error(err, call) from err

    def _document(self, result: Any, options: Mapping[str, object]) -> ToolDocument:
        root = options.get("root")
        return cast(
            ToolDocument,
            result.to_json(root=root if isinstance(root, Path) else None),
        )

    # --- offline half (PlanClient) ------------------------------------------

    def validate(self, call: CatalogCall) -> None:
        """Validate the call with the tool's own offline check; raise ``ToolError``."""
        self._normalize(call)

    def command_line(self, call: CatalogCall) -> str:
        """Return the call as the tool's command line, ``--root`` included."""
        try:
            return self._format(call.command, self._options(call))
        except Exception as err:
            raise self._error(err, call) from err

    def _format(self, command: str, options: Mapping[str, object]) -> str:
        """Return the tool's command line with ``--json``, which prints the envelope."""
        return cast(
            str,
            self._obserwator.format_command(command, options=options, run=_RUN_FLAGS),
        )

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Return the document of a command that neither uses the network nor writes.

        Besides the catalog commands marked so, ``stations find`` is offline when
        it reads the store (``source="store"``). Anything else raises
        ``ToolError("not_offline")``.
        """
        spec = self._commands.get(call.command)
        if spec is None:
            raise ToolError(TOOL, "validation_error", call.command, option="command")
        reads_store = (
            call.command == "stations find" and call.options.get("source") == "store"
        )
        if (
            spec.network or spec.writes != "none" or spec.result == "stream"
        ) and not reads_store:
            raise ToolError(
                TOOL, "not_offline", f"{call.command} is not an offline lookup"
            )
        return self._execute(call).document

    # --- full client (RunClient) --------------------------------------------

    def run(self, call: CatalogCall) -> ToolRun:
        """Run a data command (network, store writes); the envelope as a ``ToolRun``.

        A command whose result is a stream of lines needs the ``output`` option:
        Retman never reads a stream into memory.
        """
        return self._execute(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        """Return the tool's freshness plan of the call (``check_command``); network."""
        options = self._normalize(call)
        try:
            result = self._obserwator.check_command(call.command, options=options)
        except Exception as err:
            raise self._error(err, call) from err
        return self._document(result, options)

    def query(self, call: CatalogCall) -> ToolDocument:
        """Run a read-only command outside ``run``; commands that write are refused."""
        spec = self._commands.get(call.command)
        if spec is None or spec.writes != "none" or spec.result == "stream":
            raise ToolError(TOOL, "not_read_only", f"{call.command} may write")
        return self._execute(call).document

    # --- running ------------------------------------------------------------

    def _execute(self, call: CatalogCall) -> ToolRun:
        options = self._normalize(call)
        spec = self._commands[call.command]
        if spec.result == "stream" and "output" not in options:
            raise ToolError(
                TOOL,
                "validation_error",
                f"{call.command} needs a target file",
                option="output",
                call=call,
            )
        try:
            result = self._obserwator.run_command(call.command, options=options)
        except Exception as err:
            raise self._error(err, call) from err
        document = self._document(result, options)
        status = cast(Literal["ok", "partial", "failed", "cancelled"], result.status)
        return ToolRun(
            command=call.command,
            status=status,
            files=self._files(call.command, options, document),
            failed=self._failures(call.command, status, document),
            notices=tuple(
                ToolNotice(notice.level, notice.code, notice.message)
                for notice in result.notices
            ),
            document=document,
            command_line=self._format(call.command, options),
            schema=SCHEMA,
        )

    @staticmethod
    def _files(
        command: str, options: Mapping[str, object], document: ToolDocument
    ) -> tuple[ToolFile, ...]:
        """Return the files the tool itself wrote: an export, a plan, archives.

        A writing command reports each plain file it wrote with the checksum it
        computed while writing it, which is used as it is.
        """
        result = document.get("result")
        if command in _PLAN_COMMANDS:
            plan = options.get("plan")
            return (_tool_file(Path(str(plan))),) if plan else ()
        if command in _WRITING_COMMANDS and isinstance(result, dict):
            return tuple(
                ToolFile(Path(item["path"]), item["sha256"], None, item["status"])
                for item in result.get("files") or ()
                if isinstance(item, dict)
            )
        return ()

    @staticmethod
    def _failures(
        command: str, status: str, document: ToolDocument
    ) -> tuple[ToolFailure, ...]:
        """Units a command could not handle: failed items and plans, a failed build.

        The result of a list command is the list of its items; any other result is
        one object whose ``items`` and ``files`` are its units.
        """
        result = document.get("result")
        if isinstance(result, list):
            units: list[Any] = list(result)
            result = {}
        elif isinstance(result, dict):
            units = [*(result.get("items") or ()), *(result.get("files") or ())]
        else:
            return ()
        failures: list[ToolFailure] = []
        for item in units:
            state = item.get("status") if isinstance(item, dict) else None
            if state in _FAILED_STATES:
                unit = item.get("slot") or item.get("server_path") or ""
                failures.append(
                    ToolFailure(
                        str(unit),
                        str(item.get("error_code") or state),
                        str(item.get("error") or state),
                    )
                )
        if not failures and status == "failed":
            problems = "; ".join(map(str, result.get("problems") or ()))
            failures.append(ToolFailure(command, "failed", problems or "failed"))
        return tuple(failures)


def create_client(settings: Mapping[str, Any]) -> ObserwatorClient:
    """Create the manifest's ``client``: once per Retman, no network, no writes."""
    return ObserwatorClient(settings)

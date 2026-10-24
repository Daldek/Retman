"""IMGWTools command client: the only module of the adapter that imports the tool.

The tool is driven through its public command layer (``validate_command``,
``format_command``, ``run_command``, ``check_command``); the client adds the
environment Retman owns (``root`` from ``[retman.tools.imgwtools] store_dir``), turns
the tool's ``imgw-result/1`` envelope into a ``ToolRun`` and its exceptions into
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

TOOL = "imgwtools"
SCHEMA = "imgw-result/1"
# Raised by IMGWTools as a ``conflict`` when the file system has no hard links;
# Retman words it separately (the remedy is a different disk, not a retry)
NOT_ATOMIC = "not_atomic"
STORE_WRITE_UNSUPPORTED = "store_write_unsupported"
# ``project add`` keeps the options of another command in this option, and the tool
# names a rejection of any of them by it
TASK_OPTIONS = "options"
# Item states that are failures of a unit (sync, download, plan, project)
_FAILED_STATES = ("failed", "stale_plan", "check_failed")
# Commands whose result is the file given as ``path``
_FILE_COMMANDS = ("series export", "store export")
# Commands that may write the freshness plan given as ``plan``
_PLAN_COMMANDS = ("store check", "project check")


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _tool_file(path: Path, status: str | None = None) -> ToolFile:
    return ToolFile(path, _sha256(path) if path.is_file() else None, None, status)


class IMGWToolsClient:
    """A ``RunClient`` over the command catalog of IMGWTools 3.x.

    ``settings`` is the ``[retman.tools.imgwtools]`` table: ``store_dir`` is added as
    ``root`` to every command that has that option and the call omits it;
    ``reference_data_dir`` is exported as ``IMGW_DATA_DIR`` once, before the tool
    is imported, so that ``store catalog`` reads its static station locations
    from there and never from the working directory.
    """

    def __init__(self, settings: Mapping[str, Any]) -> None:
        reference = settings.get("reference_data_dir")
        if not reference:
            raise RetmanError(f"[retman.tools.{TOOL}] has no reference_data_dir")
        os.environ["IMGW_DATA_DIR"] = str(reference)
        self._settings = settings
        self._imgw: Any = importlib.import_module("imgwtools")
        self._exceptions: Any = importlib.import_module("imgwtools.exceptions")
        self._commands = {item.name: item for item in self._imgw.data_commands()}

    # --- options and errors -------------------------------------------------

    def _store_root(self) -> Path:
        try:
            return Path(self._settings["store_dir"])
        except KeyError:
            raise RetmanError(f"[retman.tools.{TOOL}] has no store_dir") from None

    def _options(self, call: CatalogCall) -> dict[str, object]:
        """Return the call's options plus ``root`` where the command reads a store.

        ``stations find`` takes a root only for ``source="store"`` and refuses it
        for the live source; the catalog names such conditions in ``env_root_when``.
        """
        options = dict(call.options)
        spec = self._commands.get(call.command)
        if (
            spec is not None
            and "root" not in options
            and any(option.name == "root" for option in spec.options)
            and all(
                options.get(name) == value for name, value in spec.env_root_when.items()
            )
        ):
            options["root"] = str(self._store_root())
        return options

    def _task_option(self, err: Exception) -> str | None:
        """Return the path ``options.<name>`` of the task option a rejection concerns.

        ``project add`` carries the options of another command in ``options``. The
        tool re-raises a rejection of that command with ``option`` replaced by
        ``options`` (the original ``option`` is lost) and keeps the original error
        as the cause. The path says what the user got wrong: ``CatalogCall.params``
        routes ``options.variables`` to the parameter ``variables``, where
        ``options`` alone names nothing to ask about. ``None`` when the tool gave no
        cause (a missing option of ``project add`` itself).
        """
        cause = err.__cause__
        if not isinstance(cause, self._imgw.IMGWError):
            return None
        inner = cause.details.get("option")
        if isinstance(inner, str) and inner != TASK_OPTIONS:
            return f"{TASK_OPTIONS}.{inner}"
        return None

    def _error(self, err: Exception, call: CatalogCall) -> ToolError:
        """Build a ``ToolError`` for an exception of the tool, with the tool's code."""
        if isinstance(err, OSError):
            detail, details = self._exceptions.describe_os_error(err)
            return ToolError(TOOL, "io_error", detail, details=details, call=call)
        if not isinstance(err, self._imgw.IMGWError):
            return ToolError(TOOL, "internal_error", repr(err), call=call)
        details = dict(err.details)
        code = str(err.code)
        if code == "conflict" and details.get("reason") == NOT_ATOMIC:
            code = STORE_WRITE_UNSUPPORTED
        option = details.get("option")
        if option == TASK_OPTIONS:
            option = self._task_option(err) or option
        allowed = details.get("allowed")
        return ToolError(
            TOOL,
            code,
            err.detail,
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
                self._imgw.validate_command(call.command, options=self._options(call)),
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
            return cast(
                str,
                self._imgw.format_command(call.command, options=self._options(call)),
            )
        except Exception as err:
            raise self._error(err, call) from err

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

        A command whose result is a stream of lines needs the ``path`` option:
        Retman never reads a stream into memory.
        """
        return self._execute(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        """Return the tool's freshness plan of the call (``check_command``); network."""
        options = self._normalize(call)
        try:
            result = self._imgw.check_command(call.command, options=options)
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
        if spec.result == "stream" and "path" not in options:
            raise ToolError(
                TOOL,
                "validation_error",
                f"{call.command} needs a target file",
                option="path",
                call=call,
            )
        try:
            result = self._imgw.run_command(call.command, options=options)
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
                ToolNotice(notice.level, notice.code, notice.text)
                for notice in result.notices
            ),
            document=document,
            command_line=cast(
                str, self._imgw.format_command(call.command, options=options)
            ),
            schema=SCHEMA,
        )

    @staticmethod
    def _files(
        command: str, options: Mapping[str, object], document: ToolDocument
    ) -> tuple[ToolFile, ...]:
        """Return the files the tool itself wrote: an export, a plan, archives."""
        result = document.get("result")
        if command in _FILE_COMMANDS:
            target = result if isinstance(result, str) else options.get("path")
            return (_tool_file(Path(str(target))),) if target else ()
        if command in _PLAN_COMMANDS:
            plan = options.get("plan")
            return (_tool_file(Path(str(plan))),) if plan else ()
        if command == "datasets download" and isinstance(result, dict):
            return tuple(
                _tool_file(Path(item["path"]), "downloaded")
                for item in result.get("items", ())
                if isinstance(item, dict)
                and item.get("status") == "downloaded"
                and item.get("path")
            )
        return ()

    @staticmethod
    def _failures(
        command: str, status: str, document: ToolDocument
    ) -> tuple[ToolFailure, ...]:
        """Units a command could not handle: failed items, plans, series, tasks."""
        result = document.get("result")
        if not isinstance(result, dict):
            return ()
        failures: list[ToolFailure] = []
        for key in ("items", "files"):
            for item in result.get(key) or ():
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
        for report in result.get("series") or ():
            if isinstance(report, dict) and report.get("status") == "failed":
                problems = "; ".join(map(str, report.get("problems") or ()))
                failures.append(ToolFailure("series", "failed", problems or "failed"))
        tasks = result.get("tasks")
        if isinstance(tasks, dict):
            failures.extend(
                ToolFailure(str(name), "failed", "failed")
                for name, state in tasks.items()
                if state == "failed"
            )
        if not failures and status == "failed":
            problems = "; ".join(map(str, result.get("problems") or ()))
            failures.append(ToolFailure(command, "failed", problems or "failed"))
        return tuple(failures)


def create_client(settings: Mapping[str, Any]) -> IMGWToolsClient:
    """Create the manifest's ``client``: once per Retman, no network, no writes."""
    return IMGWToolsClient(settings)

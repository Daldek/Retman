"""Kartograf's command client: the one module that talks to Kartograf for Retman.

It implements the ``RunClient`` protocol of ``retman.adapters.catalog`` over
Kartograf's command layer (``validate_command``, ``run_command``,
``check_command``, ``format_command``) and its offline lookups, and turns
Kartograf's exceptions and its ``kartograf-result/1`` envelopes into ``ToolError`` and
``ToolRun``.

The environment of every call comes from ``[retman.tools.kartograf]`` and nowhere else
(PRD N-11): the store (``root``, never plain files: the data are shared by all
projects), the number of workers, the update mode and an explicit metadata cache.
Kartograf's own defaults are never used: not its default store (``KARTOGRAF_ROOT``,
``nogat.toml``, ``<data_dir>/kartograf``) and not ``cache=True``, which would open the
default cache of the user instead of the one the settings name. A call gets the
workers and the update mode only if its command declares them (``store init`` does
not): the command layer refuses an option that does not belong to the command.
"""

import functools
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Literal, cast

import kartograf

from retman.adapters.catalog import (
    CatalogCall,
    RunStatus,
    ToolDocument,
    ToolError,
    ToolFailure,
    ToolFile,
    ToolNotice,
    ToolRun,
)
from retman.exceptions import RetmanError
from retman.tools.kartograf.areas import ENVELOPE

TOOL = "kartograf"

UpdateMode = Literal["upgrade", "force"]

# ``[retman.tools.kartograf] update`` to the update mode of ``run_command``:
# "local" keeps the stored versions and downloads only what is missing
_UPDATE_MODES: dict[str, UpdateMode | None] = {
    "local": None,
    "upgrade": "upgrade",
    "force": "force",
}

# Offline lookups are Kartograf's query commands without effects (``sheet parse``,
# ``sheet find``, ``<group> list-sources``, ``store sidecar``) and the envelope of a
# geometry file, which Kartograf offers as a function only
_LIST_SOURCES = " list-sources"
# The ``details.reason`` Kartograf's ``ValidationError`` has by default, for the
# rejections the client makes by the same rule
INVALID_INPUT = "invalid_input"


def _required(settings: Mapping[str, Any], key: str) -> Any:
    try:
        return settings[key]
    except KeyError:
        raise RetmanError(f"[retman.tools.{TOOL}] has no {key}") from None


def update_mode(settings: Mapping[str, Any]) -> UpdateMode | None:
    """Return the ``update`` argument of Kartograf's download functions."""
    return _UPDATE_MODES[_required(settings, "update")]


def metadata_cache(settings: Mapping[str, Any]) -> kartograf.MetadataCache:
    """Kartograf's metadata cache at ``[retman.tools.kartograf] cache_file``.

    Creates nothing by itself: the file appears with the first write.
    """
    return kartograf.MetadataCache(db_path=_required(settings, "cache_file"))


@functools.cache
def declared_options(command: str) -> frozenset[str]:
    """Return the names of the options a command of Kartograf's catalog declares.

    The catalog says which of the environment of a call a command takes: ``root``,
    ``workers`` and ``update`` belong to a download, ``root`` alone to ``store init``.
    The catalog of an installed tool does not change while the process runs.
    """
    document: Any = kartograf.command_schema(command).to_dict()
    return frozenset(option["name"] for option in document["commands"][0]["options"])


def to_tool_error(err: Exception, call: CatalogCall | None = None) -> ToolError:
    """Kartograf's exception as a ``ToolError`` with its registry ``code`` and reason.

    ``option``, ``options`` and ``allowed`` of a rejection survive, so that the
    pipeline can ask the user again about the parameter at fault, and ``details.reason``
    is the reason of the exception; ``OSError`` is ``io_error`` and anything else a bug
    of this client, ``internal_error``.
    """
    if isinstance(err, kartograf.KartografError):
        return ToolError(
            TOOL,
            err.code,
            str(err),
            hint=err.hint or err.DEFAULT_HINT,
            option=getattr(err, "option", None),
            options=getattr(err, "options", None) or (),
            allowed=getattr(err, "allowed", None),
            details=err.details(),
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


def _arguments(options: Mapping[str, object]) -> dict[str, Any]:
    """JSON-form options as keyword arguments of the library functions.

    A rectangle is four numbers with ``bbox_crs`` in the JSON form and a ``BBox``
    in the library.
    """
    arguments = {name: value for name, value in options.items() if name != "bbox_crs"}
    if "bbox" in options:
        bbox, crs = options["bbox"], options.get("bbox_crs")
        if not (
            isinstance(bbox, list | tuple) and len(bbox) == 4 and isinstance(crs, str)
        ):
            raise ToolError(
                TOOL,
                "validation_error",
                "a rectangle needs four numbers and bbox_crs",
                options=("bbox", "bbox_crs"),
                details={"reason": INVALID_INPUT},
            )
        min_x, min_y, max_x, max_y = bbox
        arguments["bbox"] = kartograf.BBox(min_x, min_y, max_x, max_y, crs)
    return arguments


def run_from_document(
    call: CatalogCall, document: ToolDocument, command_line: str = ""
) -> ToolRun:
    """Build a ``ToolRun`` from a ``kartograf-result/1`` envelope of a data command.

    ``status`` is Kartograf's verdict on the whole request: ``partial`` is a request
    with a failed unit and a delivered one (the user gets what exists), ``failed`` one
    with no delivered unit. A request is ``ok`` even when GUGiK has no data for some of
    its sheets; that is only a ``no_coverage_some`` notice. The files are the
    ``files[]`` of the domain document in ``result`` (``kartograf-download/1``), the
    failures the failed ``items[]`` of the envelope (a registry ``code`` with its
    ``reason``) and the notices those of the envelope; the whole envelope is kept as
    the tool's document.
    """
    result = document.get("result") or {}
    files = tuple(
        ToolFile(Path(item["path"]), item["sha256"], item.get("label"), item["status"])
        for item in result.get("files", ())
    )
    failed = tuple(
        ToolFailure(
            item["id"],
            item.get("code") or "failed",
            item.get("message") or item.get("code") or "failed",
            item.get("reason"),
        )
        for item in document.get("items", ())
        if item["status"] == "failed"
    )
    notices = tuple(
        ToolNotice(item["level"], item["code"], item["message"])
        for item in document.get("notices", ())
    )
    return ToolRun(
        call.command,
        cast(RunStatus, document["status"]),
        files,
        failed,
        notices,
        document,
        command_line,
        str(document.get("schema", "")),
    )


class KartografClient:
    """The ``RunClient`` of Kartograf, built from ``[retman.tools.kartograf]``."""

    def __init__(self, settings: Mapping[str, Any]) -> None:
        self.settings = settings

    # --- what exists before the user confirms: offline, effects-free ----------

    def validate(self, call: CatalogCall) -> None:
        """Kartograf's own checks of the call, without network and without writing."""
        with translated(call):
            kartograf.validate_command(
                call.command, call.options, root=self.settings.get("store_dir")
            )

    def command_line(self, call: CatalogCall) -> str:
        """Return the canonical ``kartograf`` command line of the call."""
        flags: dict[str, object] = {}
        if "store_dir" in self.settings:
            flags["root"] = str(self.settings["store_dir"])
        with translated(call):
            declared = declared_options(call.command)
            if "workers" in declared and "workers" in self.settings:
                flags["workers"] = self.settings["workers"]
            mode = self.settings.get("update", "local")
            if "update" in declared and mode != "local":
                flags[mode] = True
            return kartograf.format_command(call.command, call.options, run=flags)

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Answer an offline lookup: sheet codes, lists, sources, sidecars, envelopes.

        Raises
        ------
        ToolError
            ``not_offline`` for every command that may use the network or write
            (a data command, ``elevation availability``, ``store init``).
        """
        options = call.options
        with translated(call):
            try:
                if call.command == "sheet parse":
                    return kartograf.describe_sheet(
                        str(options["sheet"]),
                        hierarchy=bool(options.get("hierarchy")),
                        children=bool(options.get("children")),
                        descendants=_text(options, "descendants"),
                    ).to_dict()
                if call.command == "sheet find":
                    return kartograf.find_sheets(**_arguments(options)).to_dict()
                if call.command.endswith(_LIST_SOURCES):
                    return kartograf.list_sources(
                        group=call.command.removesuffix(_LIST_SOURCES),
                        product=_text(options, "product"),
                    ).to_dict()
                if call.command == "store sidecar":
                    return kartograf.read_store_sidecar(str(options["path"])).to_dict()
                if call.command == ENVELOPE:
                    box = kartograf.get_overall_bbox(
                        Path(str(options["geometry"])), _text(options, "layer")
                    )
                    return {
                        "schema": "retman-kartograf-envelope/1",
                        "bbox": [box.min_x, box.min_y, box.max_x, box.max_y],
                        "crs": box.crs,
                    }
            except KeyError as err:
                raise ToolError(
                    TOOL,
                    "validation_error",
                    f"missing option {err}",
                    details={"reason": INVALID_INPUT},
                    call=call,
                ) from err
        raise ToolError(
            TOOL, "not_offline", f"{call.command!r} is not an offline lookup", call=call
        )

    # --- what exists only after consent: network and store writes -------------

    def _run_arguments(self, command: str) -> dict[str, Any]:
        """Return the workers and the update mode of a run, if the command has them."""
        declared = declared_options(command)
        arguments: dict[str, Any] = {}
        if "update" in declared:
            arguments["update"] = update_mode(self.settings)
        if "workers" in declared:
            arguments["workers"] = _required(self.settings, "workers")
        return arguments

    def run(self, call: CatalogCall) -> ToolRun:
        """Run a command of the catalog into the store; an error is a ``ToolError``.

        ``store init`` is such a command: it writes the marker of the store.
        """
        store = _required(self.settings, "store_dir")
        with translated(call), closing(metadata_cache(self.settings)) as cache:
            result = kartograf.run_command(
                call.command,
                call.options,
                root=store,
                cache=cache,
                **self._run_arguments(call.command),
            )
        return run_from_document(call, result.to_dict(), self.command_line(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """Kartograf's freshness plan of a data command (``kartograf-plan/1``).

        The plan is the ``result`` of the envelope ``check_command`` answers with. A
        network step for most commands, so Retman asks for consent first.
        """
        store = _required(self.settings, "store_dir")
        with translated(call), closing(metadata_cache(self.settings)) as cache:
            checked = kartograf.check_command(
                call.command, call.options, root=store, cache=cache
            )
        if checked.result is None:
            raise ToolError(TOOL, "internal_error", "no plan in the result", call=call)
        return checked.result.to_dict()

    def query(self, call: CatalogCall) -> ToolDocument:
        """Run a read-only network query: ``elevation availability`` only."""
        if call.command != "elevation availability":
            raise ToolError(
                TOOL, "not_supported", f"{call.command!r} is not a query", call=call
            )
        with translated(call), closing(metadata_cache(self.settings)) as cache:
            report = kartograf.check_availability(
                **_arguments(call.options), cache=cache
            )
        return report.to_dict()


def _text(options: Mapping[str, object], name: str) -> str | None:
    value = options.get(name)
    return None if value is None else str(value)


def create(settings: Mapping[str, Any]) -> KartografClient:
    """Create the manifest's ``client``: no network and no writes at construction."""
    return KartografClient(settings)

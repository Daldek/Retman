"""Kartograf's command client: the one module that talks to Kartograf for Retman.

It implements the ``RunClient`` protocol of ``retman.adapters.catalog`` over
Kartograf's command layer (``validate_command``, ``run_command``,
``check_command``, ``format_command``) and its offline lookups, and turns
Kartograf's exceptions and JSON documents into ``ToolError`` and ``ToolRun``.

The environment of every call comes from ``[retman.tools.kartograf]`` and nowhere else
(PRD N-11): the store (``output_dir``), the number of workers, the update mode and
an explicit metadata cache. Kartograf's own defaults are never used: ``cache=True``
would create ``.kartograf_cache.db`` in the current directory, i.e. in the user's
project.
"""

from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Literal

import kartograf

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

# Offline lookups are Kartograf's query commands without effects (``parse``,
# ``find_sheets``, ``<group> list-sources``, ``store_sidecar``) and the envelope of a
# geometry file, which Kartograf offers as a function only
_LIST_SOURCES = " list-sources"


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


def to_tool_error(err: Exception, call: CatalogCall | None = None) -> ToolError:
    """Kartograf's exception as a ``ToolError`` with the tool's own error ``code``.

    ``option``, ``options`` and ``allowed`` of a rejection survive, so that the
    pipeline can ask the user again about the parameter at fault; ``OSError`` is
    ``io_error`` and anything else a bug of this client, ``internal_error``.
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
                "invalid_input",
                "a rectangle needs four numbers and bbox_crs",
                options=("bbox", "bbox_crs"),
            )
        min_x, min_y, max_x, max_y = bbox
        arguments["bbox"] = kartograf.BBox(min_x, min_y, max_x, max_y, crs)
    return arguments


def run_from_document(
    call: CatalogCall, document: ToolDocument, command_line: str = ""
) -> ToolRun:
    """Build a ``ToolRun`` from a ``kartograf-download/1`` document.

    ``ok`` is Kartograf's verdict on the whole request: ``false`` with files is a
    ``partial`` run (the user gets what exists), ``false`` without any file a
    ``failed`` one. A request is ``ok`` even when GUGiK has no data for some of its
    sheets; that is only a ``no_coverage_some`` notice.
    """
    files = tuple(
        ToolFile(
            Path(item["file"]["path"]),
            item["file"].get("sha256"),
            item["file"].get("label"),
            item["file"].get("status"),
        )
        for item in document.get("files", ())
    )
    failed = tuple(
        ToolFailure(item["unit"], item["kind"], item["error"])
        for item in document.get("failed", ())
    )
    notices = tuple(
        ToolNotice(item["level"], item["code"], item["text"])
        for item in document.get("notices", ())
    )
    if document.get("ok"):
        status: Literal["ok", "partial", "failed"] = "ok"
    else:
        status = "partial" if files else "failed"
    return ToolRun(
        call.command,
        status,
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
                call.command, call.options, output_dir=self.settings.get("store_dir")
            )

    def command_line(self, call: CatalogCall) -> str:
        """Return the canonical ``kartograf`` command line of the call."""
        flags: dict[str, object] = {}
        if "store_dir" in self.settings:
            flags["output_dir"] = str(self.settings["store_dir"])
        if "workers" in self.settings:
            flags["workers"] = self.settings["workers"]
        mode = self.settings.get("update", "local")
        if mode != "local":
            flags[mode] = True
        with translated(call):
            return kartograf.format_command(call.command, call.options, run=flags)

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Answer an offline lookup: sheet codes, lists, sources, sidecars, envelopes.

        Raises
        ------
        ToolError
            ``not_offline`` for every command that may use the network or write
            (a data command, ``elevation availability``).
        """
        options = call.options
        with translated(call):
            try:
                if call.command == "parse":
                    return kartograf.describe_sheet(
                        str(options["sheet"]),
                        hierarchy=bool(options.get("hierarchy")),
                        children=bool(options.get("children")),
                        descendants=_text(options, "descendants"),
                    ).to_dict()
                if call.command == "find_sheets":
                    return kartograf.find_sheets(**_arguments(options)).to_dict()
                if call.command.endswith(_LIST_SOURCES):
                    return kartograf.list_sources(
                        group=call.command.removesuffix(_LIST_SOURCES),
                        product=_text(options, "product"),
                    ).to_dict()
                if call.command == "store_sidecar":
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
                    TOOL, "invalid_input", f"missing option {err}", call=call
                ) from err
        raise ToolError(
            TOOL, "not_offline", f"{call.command!r} is not an offline lookup", call=call
        )

    # --- what exists only after consent: network and store writes -------------

    def run(self, call: CatalogCall) -> ToolRun:
        """Run a data command into the store; a Kartograf error is a ``ToolError``."""
        store = _required(self.settings, "store_dir")
        with translated(call), closing(metadata_cache(self.settings)) as cache:
            report = kartograf.run_command(
                call.command,
                call.options,
                output_dir=store,
                update=update_mode(self.settings),
                workers=_required(self.settings, "workers"),
                cache=cache,
            )
        return run_from_document(call, report.to_dict(), self.command_line(call))

    def check(self, call: CatalogCall) -> ToolDocument:
        """Kartograf's freshness plan of a data command (``kartograf-plan/1``).

        A network step for most commands, so Retman asks for consent first.
        """
        store = _required(self.settings, "store_dir")
        with translated(call), closing(metadata_cache(self.settings)) as cache:
            plan = kartograf.check_command(
                call.command, call.options, output_dir=store, cache=cache
            )
        return plan.to_dict()

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

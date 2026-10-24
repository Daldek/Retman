"""Call builders of the ``imgw_archives`` operations (nos. 12-19).

A builder is ``calls(params, ctx) -> list[CatalogCall]``: pure, with the options
taken from the parameters and the manifest's ``tool_values``. ``root`` is never
given here, the client adds it from ``[tools.imgwtools] store_dir``. Files the
tool writes (downloads, plans, exports) get a target in the result folder only
once it exists, i.e. when the operation runs; while planning the commands are
validated without them. The offline lookups feed the previews and, for the
export, the list of calls.
"""

from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any

from retman.adapters.catalog import CatalogCall, ToolContext

PLAN_FILE = "plan.json"

# Tool options named differently from the parameter they come from
_DOWNLOAD_ROUTES = {"params": "hydro_params"}
_STORE_ROUTES = {"datasets": "dataset"}


def selected_years(value: Mapping[str, Any]) -> list[int]:
    """Return the archive years a ``years`` or ``year_list`` value names, ascending."""
    if value["type"] == "years":
        return list(range(value["first"], value["last"] + 1))
    return [int(year) for year in value["years"]]


def years_text(value: Mapping[str, Any]) -> str:
    """Render ``years``/``year_list`` values for a plan row: ``2000–2020``."""
    if value["type"] == "years":
        first, last = value["first"], value["last"]
        return str(first) if first == last else f"{first}–{last}"
    return ", ".join(str(year) for year in value["years"])


def _selection(params: Mapping[str, Any], ctx: ToolContext) -> dict[str, object]:
    """Dataset, years and stations as the archive commands take them.

    ``years`` is absent for the whole-history ČHMÚ dataset, ``stations`` for the
    country-wide IMGW-PIB archives: the manifest applies them by dataset.
    """
    options: dict[str, object] = {
        "dataset": ctx.tool_value("dataset", params["dataset"])
    }
    if "years" in params:
        options["years"] = selected_years(params["years"])
    if "stations" in params:
        options["stations"] = [station["code"] for station in params["stations"]]
    return options


def _store_selection(params: Mapping[str, Any], ctx: ToolContext) -> dict[str, object]:
    """Return the selection of ``store check`` and ``store sync``."""
    options = _selection(params, ctx)
    dataset = options.pop("dataset")
    return {"datasets": [dataset], **options}


def _download_selection(
    params: Mapping[str, Any], ctx: ToolContext
) -> dict[str, object]:
    options = _selection(params, ctx)
    chosen = params.get("hydro_params")
    # ``all`` is the tool's default: nothing to pass
    if chosen is not None and chosen != "all":
        options["params"] = [ctx.tool_value("hydro_params", chosen)]
    return options


def archive_files_call(params: Mapping[str, Any], ctx: ToolContext) -> CatalogCall:
    """Build the offline listing of the archive files a selection names."""
    return CatalogCall(
        "datasets files", _download_selection(params, ctx), params=_DOWNLOAD_ROUTES
    )


# --- 12, 13: download to the result folder -----------------------------------------


def _download(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    options = _download_selection(params, ctx)
    if ctx.output_dir is not None:
        options["output"] = str(ctx.output_dir)
    return [
        CatalogCall(
            "datasets download",
            options,
            kind="imgw_archive",
            params=_DOWNLOAD_ROUTES,
        )
    ]


def download_hydro_archives(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``datasets download`` of a hydrological dataset into the result folder."""
    return _download(params, ctx)


def download_meteo_archives(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``datasets download`` of a meteorological dataset into the result folder."""
    return _download(params, ctx)


# --- 14-16: freshness plan and synchronisation of the store -------------------------


def check_imgw_archives(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``store check``; the tool writes the ``imgw-plan/1`` file into the result."""
    options = _store_selection(params, ctx)
    if ctx.output_dir is not None:
        options["plan"] = str(ctx.output_dir / PLAN_FILE)
    return [CatalogCall("store check", options, kind="imgw_plan", params=_STORE_ROUTES)]


def sync_imgw_store(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``store sync`` of the selection, building the series of the datasets after it."""
    return [
        CatalogCall(
            "store sync",
            {**_store_selection(params, ctx), "series": True},
            params=_STORE_ROUTES,
        )
    ]


def sync_imgw_store_by_plan(
    params: dict[str, Any], ctx: ToolContext
) -> list[CatalogCall]:
    """``store sync`` of exactly the plan the user chose (workspace input ``plan``)."""
    return [CatalogCall("store sync", {"plan": str(ctx.inputs["plan"])})]


# --- 17: export of stored archives ---------------------------------------------------


@dataclass(frozen=True)
class StoredArchive:
    """The current stored version of one archive file of an export selection.

    ``version`` is the path the tool reports, relative to the store; ``selector``
    the slot's path part (``2020/codz_2020_01.zip``), which names the file.
    """

    slot: str
    version: str
    selector: str

    @property
    def stem(self) -> str:
        """The file name without its extension."""
        return PurePosixPath(self.selector).stem


def _instant(text: str) -> datetime:
    moment = datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _signal_time(meta: Mapping[str, Any]) -> datetime:
    """When a version was published: its ``Last-Modified``, else the download time."""
    http = (meta.get("extra") or {}).get("http")
    modified = http.get("last_modified") if isinstance(http, Mapping) else None
    if modified:
        try:
            return parsedate_to_datetime(modified).astimezone(UTC)
        except (TypeError, ValueError, OverflowError):
            pass
    return _instant(meta["downloaded_at"])


def current_archive_versions(
    items: Iterable[Mapping[str, Any]], dataset: str, years: Collection[int] | None
) -> list[StoredArchive]:
    """Return the current version of every stored archive of ``dataset`` and ``years``.

    ``items`` are the entries of ``store scan``. The tool's own order decides which
    version of a slot is current (``current_version``): newest ``Last-Modified``,
    then download time, then path. ``years`` of ``None`` selects every year.
    """
    newest: dict[str, tuple[tuple[datetime, datetime, str], Mapping[str, Any]]] = {}
    for item in items:
        meta = item.get("meta")
        if (
            item.get("kind") != "archive"
            or not isinstance(meta, Mapping)
            or meta.get("dataset_key") != dataset
        ):
            continue
        if years is not None and (meta.get("request") or {}).get("year") not in years:
            continue
        order = (
            _signal_time(meta),
            _instant(meta["downloaded_at"]),
            str(item["version"]),
        )
        slot = str(item["slot"])
        if slot not in newest or order > newest[slot][0]:
            newest[slot] = (order, item)
    found = [
        StoredArchive(slot, str(item["version"]), slot.split(":", 2)[2])
        for slot, (_, item) in newest.items()
    ]
    return sorted(found, key=lambda archive: archive.selector)


def stored_archives(params: Mapping[str, Any], ctx: ToolContext) -> list[StoredArchive]:
    """Return the archives of the selection that the store holds (``store scan``)."""
    provider = ctx.option_meta("dataset", params["dataset"])["provider"]
    years = set(selected_years(params["years"])) if "years" in params else None
    document = ctx.client.lookup(
        CatalogCall("store scan", {"kind": "archive", "provider": provider})
    )
    result = document.get("result")
    items = result.get("items") if isinstance(result, Mapping) else None
    return current_archive_versions(
        items or (), ctx.tool_value("dataset", params["dataset"]), years
    )


def expected_archives(params: Mapping[str, Any], ctx: ToolContext) -> int | None:
    """How many archive files the selection names, when that is known offline.

    The country-wide IMGW-PIB archives are listed from the dataset and years alone;
    a ČHMÚ file belongs to a station, and an export names none: unknown, ``None``.
    """
    if ctx.option_meta("dataset", params["dataset"])["provider"] != "IMGW-PIB":
        return None
    document = ctx.client.lookup(archive_files_call(params, ctx))
    result = document.get("result")
    items = result.get("items") if isinstance(result, Mapping) else None
    return len(items) if items else 0


def export_names(archives: Iterable[StoredArchive], extension: str) -> list[str]:
    """One file name per archive, ``<stem>.<extension>``; stems are made unique."""
    seen: Counter[str] = Counter()
    names = []
    for archive in archives:
        seen[archive.stem] += 1
        number = seen[archive.stem]
        names.append(f"{archive.stem}{'' if number == 1 else f'_{number}'}.{extension}")
    return names


def export_imgw_archive(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """One ``store export`` per stored archive of the selection (current versions).

    The list comes from an offline ``store scan``; a selection the store does not
    hold gives no calls, and the preview says so.
    """
    extension = ctx.tool_value("format", params["format"])
    archives = stored_archives(params, ctx)
    calls = []
    for archive, name in zip(archives, export_names(archives, extension), strict=True):
        options: dict[str, object] = {
            "version": archive.version,
            "format": extension,
        }
        if ctx.output_dir is not None:
            options["path"] = str(ctx.output_dir / name)
        calls.append(
            CatalogCall(
                "store export",
                options,
                kind="archive_records",
                params={"version": "dataset"},
            )
        )
    return calls


# --- 18, 19: the store itself --------------------------------------------------------


def init_imgw_store(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``store init`` of the configured store folder (idempotent, refuses others)."""
    return [CatalogCall("store init", {})]


def inspect_imgw_store(params: dict[str, Any], ctx: ToolContext) -> list[CatalogCall]:
    """``store info`` and ``store scan``; both documents are kept as reports."""
    scan: dict[str, object] = {}
    for name in ("kind", "provider"):
        if name in params:
            scan[name] = ctx.tool_value(name, params[name])
    return [
        CatalogCall("store info", {}, kind="imgw_report"),
        CatalogCall("store scan", scan, kind="imgw_report"),
    ]

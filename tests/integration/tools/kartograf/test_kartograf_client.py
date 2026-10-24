"""Kartograf's command client: offline checks, lookups and the way a run is made.

Validation, command lines and lookups use the real Kartograf offline. What needs the
network (``run_command``, ``check_command``, ``check_availability``) is replaced by a
recorder, so that the arguments the client hands to Kartograf can be asserted.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import kartograf
import pytest
from kartograf_support import (
    SHEET,
    TERYT,
    context,
    document,
    geometry,
    settings,
)

from retman.adapters.catalog import CatalogCall, ToolError, ToolNotice, ToolRun
from retman.tools.kartograf import calls
from retman.tools.kartograf.areas import ENVELOPE
from retman.tools.kartograf.client import KartografClient, create, run_from_document

NMT_5M = {"area": SHEET, "resolution": "5m", "vertical_crs": "evrf2007"}
DOWNLOAD = CatalogCall(
    "elevation download",
    {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "5m",
        "vertical_crs": "EVRF2007",
    },
    "dem",
)
BBOX_OPTIONS = {
    "product": "nmt",
    "country": "pl",
    "bbox": [530000, 382000, 530100, 382100],
    "bbox_crs": "EPSG:2180",
}


def tree(root: Path) -> set[Path]:
    """Every file and folder below ``root``."""
    return set(root.rglob("*"))


class Report:
    """What a Kartograf command returns: an object with ``to_dict()``."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return self.data


class Recorder:
    """Stands in for a Kartograf function; records its use, returns or raises."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.uses: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.uses.append((args, kwargs))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


@pytest.fixture
def cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """An empty working directory next to the store, to catch stray files."""
    folder = tmp_path / "cwd"
    folder.mkdir()
    monkeypatch.chdir(folder)
    yield folder
    assert tree(folder) == set(), "the client wrote into the working directory"


def run_with(
    monkeypatch: pytest.MonkeyPatch, outcome: Any, client: KartografClient
) -> Recorder:
    """Replace ``kartograf.run_command`` and run ``DOWNLOAD`` through ``client``."""
    recorder = Recorder(outcome)
    monkeypatch.setattr(kartograf, "run_command", recorder)
    client.run(DOWNLOAD)
    return recorder


# --- validate ---------------------------------------------------------------


def test_validate_names_the_parameters_of_a_pair_kartograf_rejects(
    tmp_path: Path, cwd: Path
) -> None:
    (call,) = calls.download_dem_sheet(
        {"area": SHEET, "resolution": "5m", "vertical_crs": "kron86"},
        context("download_dem_sheet"),
    )

    with pytest.raises(ToolError) as caught:
        KartografClient(settings(tmp_path)).validate(call)

    assert caught.value.code == "invalid_input"
    assert {"resolution", "vertical_crs"} <= set(caught.value.options)
    assert caught.value.call is call


def test_validate_accepts_a_good_call_and_writes_nothing(
    tmp_path: Path, cwd: Path
) -> None:
    (call,) = calls.download_dem_sheet(NMT_5M, context("download_dem_sheet"))
    before = tree(tmp_path)

    KartografClient(settings(tmp_path)).validate(call)

    assert tree(tmp_path) == before
    assert not (tmp_path / "store").exists()
    assert not (tmp_path / "data").exists()


# --- command_line -----------------------------------------------------------


@pytest.mark.parametrize(
    ("update", "flag"),
    [("local", None), ("upgrade", "--upgrade"), ("force", "--force")],
)
def test_command_line_carries_store_workers_and_the_update_flag(
    tmp_path: Path, update: str, flag: str | None
) -> None:
    client = KartografClient({**settings(tmp_path), "update": update})

    words = client.command_line(DOWNLOAD).split()

    store = str(tmp_path / "store")
    assert words[words.index("-o") + 1] == store
    assert words[words.index("-w") + 1] == "2"
    for other in ("--upgrade", "--force"):
        assert (other in words) == (other == flag)


# --- lookup (the real Kartograf, offline) ------------------------------------


@pytest.mark.parametrize(
    ("sheet", "scale", "count"),
    [("N-34-130-D-d-2", "1:10000", 4), ("7.171.21", "1:2000", 25)],
)
def test_lookup_parse_counts_the_descendant_sheets(
    tmp_path: Path, sheet: str, scale: str, count: int
) -> None:
    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("parse", {"sheet": sheet, "descendants": scale})
    )

    assert found["descendants"]["count"] == count
    assert found["descendants"]["scale"] == scale


def test_lookup_find_sheets_reads_a_geometry_file_and_a_rectangle(
    tmp_path: Path,
) -> None:
    client = KartografClient(settings(tmp_path))
    area = geometry(tmp_path / "area")

    by_file = client.lookup(
        CatalogCall(
            "find_sheets",
            {"geometry": area["path"], "scale": "1:10000", "sheet_system": "1992"},
        )
    )
    by_box = client.lookup(
        CatalogCall(
            "find_sheets",
            {
                "bbox": [530000, 382000, 531000, 383000],
                "bbox_crs": "EPSG:2180",
                "scale": "1:10000",
                "sheet_system": "1992",
            },
        )
    )

    assert by_file["count"] == 4
    assert by_box["count"] == 4


def test_lookup_lists_the_sources_of_the_registry(tmp_path: Path) -> None:
    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("elevation list-sources", {"product": "nmt"})
    )

    assert "pl.gugik.nmt_1m" in {source["key"] for source in found["sources"]}


def test_lookup_envelope_of_a_geometry_file_is_its_bounding_box(
    tmp_path: Path,
) -> None:
    area = geometry(tmp_path / "area")

    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall(ENVELOPE, {"geometry": area["path"]})
    )

    assert found["bbox"] == [530000.0, 382000.0, 532000.0, 384000.0]
    assert found["crs"] == "EPSG:2180"


def test_lookup_store_sidecar_returns_what_the_meta_file_says(
    tmp_path: Path,
) -> None:
    data = tmp_path / "store" / "sheet.asc"
    data.parent.mkdir()
    data.write_text("x", encoding="utf-8")
    (tmp_path / "store" / "sheet.asc.meta.json").write_text(
        '{"schema": "kartograf-meta/1", "extra": {"mask": {"masked_pixels": 3}}}',
        encoding="utf-8",
    )

    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("store_sidecar", {"path": str(data)})
    )

    assert found["sidecar"]["extra"] == {"mask": {"masked_pixels": 3}}


@pytest.mark.parametrize(
    "call",
    [
        CatalogCall("elevation download", DOWNLOAD.options),
        CatalogCall("imagery download", {"sheet": "N-34-130-D-d-2-4"}),
        CatalogCall("landcover download", {"teryt": "2264"}),
        CatalogCall("elevation availability", BBOX_OPTIONS),
    ],
    ids=lambda call: call.command,
)
def test_lookup_refuses_a_command_that_needs_the_network(
    tmp_path: Path, call: CatalogCall
) -> None:
    client = KartografClient(settings(tmp_path))

    with pytest.raises(ToolError) as caught:
        client.lookup(call)

    assert caught.value.code == "not_offline"
    assert caught.value.call is call


def test_lookup_without_its_required_option_is_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as caught:
        KartografClient(settings(tmp_path)).lookup(CatalogCall("parse", {}))

    assert caught.value.code == "invalid_input"


# --- run ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("update", "mode"), [("local", None), ("upgrade", "upgrade"), ("force", "force")]
)
def test_run_hands_kartograf_the_store_workers_update_mode_and_cache(
    tmp_path: Path,
    cwd: Path,
    monkeypatch: pytest.MonkeyPatch,
    update: str,
    mode: str | None,
) -> None:
    config = {**settings(tmp_path), "update": update}
    report = Report(document("sheets_one_of_four", tmp_path / "store"))

    recorder = run_with(monkeypatch, report, KartografClient(config))

    ((args, kwargs),) = recorder.uses
    assert args == (DOWNLOAD.command, DOWNLOAD.options)
    assert kwargs["output_dir"] == config["store_dir"]
    assert kwargs["workers"] == 2
    assert kwargs["update"] == mode
    cache = kwargs["cache"]
    assert isinstance(cache, kartograf.MetadataCache)
    assert Path(cache.db_path) == Path(config["cache_file"])


def test_run_returns_the_documents_files_notices_and_command_line(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "store"
    monkeypatch.setattr(
        kartograf,
        "run_command",
        Recorder(Report(document("sheets_one_of_four", store))),
    )

    run = KartografClient(settings(tmp_path)).run(DOWNLOAD)

    assert isinstance(run, ToolRun)
    assert run.status == "ok"
    assert run.schema == "kartograf-download/1"
    assert run.command == "elevation download"
    (file,) = run.files
    assert file.path.name == "N-34-139-C-a-3-1.asc"
    assert file.path.is_relative_to(store)
    assert file.sha256 == (
        "9c1a23d3176aeeeb963758c6d593be67251c4dfe21b479d31a78833ce4c7b7eb"
    )
    assert file.version == "2025-10-21_84183"
    assert file.status == "new"
    assert run.notices
    assert all(isinstance(notice, ToolNotice) for notice in run.notices)
    assert {"incomplete_campaign", "no_coverage_some"} == {n.code for n in run.notices}
    assert run.command_line.startswith("kartograf elevation download")
    assert str(store) in run.command_line


@pytest.mark.parametrize(
    ("name", "status", "files", "failures"),
    [
        ("sheets_one_delivered", "ok", 1, []),
        ("sheets_one_of_four", "ok", 1, []),
        ("sheets_hard_failure", "partial", 1, [("download", "PL")]),
        ("sheets_none_delivered", "failed", 0, [("no_coverage", "PL")]),
        ("cutout_all_nodata", "ok", 1, []),
        ("bdot10k_gpkg_one_county_failed", "partial", 2, [("download", "0224")]),
    ],
)
def test_run_from_document_maps_every_recorded_outcome(
    tmp_path: Path,
    name: str,
    status: str,
    files: int,
    failures: list[tuple[str, str]],
) -> None:
    run = run_from_document(DOWNLOAD, document(name, tmp_path / "store"))

    assert run.status == status
    assert len(run.files) == files
    assert [(item.kind, item.unit) for item in run.failed] == failures
    assert run.schema == "kartograf-download/1"


# --- errors -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (kartograf.NoCoverageError("x", sheet="s", hints=("h",)), "no_coverage"),
        (kartograf.DownloadError("x"), "download_failed"),
        (OSError("disk full"), "io_error"),
        (RuntimeError("bug"), "internal_error"),
    ],
)
def test_run_turns_every_failure_into_a_tool_error_with_the_original_as_cause(
    tmp_path: Path,
    cwd: Path,
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    code: str,
) -> None:
    with pytest.raises(ToolError) as caught:
        run_with(monkeypatch, raised, KartografClient(settings(tmp_path)))

    assert caught.value.code == code
    assert caught.value.__cause__ is raised
    assert caught.value.call is DOWNLOAD


def test_run_keeps_the_hints_of_a_sheet_without_coverage(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raised = kartograf.NoCoverageError("x", sheet="s", hints=("h",))

    with pytest.raises(ToolError) as caught:
        run_with(monkeypatch, raised, KartografClient(settings(tmp_path)))

    assert list(caught.value.details["hints"]) == ["h"]


def test_run_lets_a_keyboard_interrupt_through(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(KeyboardInterrupt):
        run_with(monkeypatch, KeyboardInterrupt(), KartografClient(settings(tmp_path)))


# --- check and query ----------------------------------------------------------


def test_check_asks_kartograf_for_the_plan_of_the_store_with_the_cache_file(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = Report(document("plan_bdot10k_teryt", tmp_path / "store"))
    recorder = Recorder(plan)
    monkeypatch.setattr(kartograf, "check_command", recorder)

    answer = KartografClient(settings(tmp_path)).check(DOWNLOAD)

    assert answer == plan.data
    ((args, kwargs),) = recorder.uses
    assert args == (DOWNLOAD.command, DOWNLOAD.options)
    assert kwargs["output_dir"] == str(tmp_path / "store")
    assert isinstance(kwargs["cache"], kartograf.MetadataCache)
    assert Path(kwargs["cache"].db_path) == tmp_path / "data" / "kartograf_cache.db"


def test_query_turns_a_rectangle_into_a_bbox_and_uses_the_cache_file(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = Report(document("availability_nmt_sheet", tmp_path / "store"))
    recorder = Recorder(answer)
    monkeypatch.setattr(kartograf, "check_availability", recorder)

    found = KartografClient(settings(tmp_path)).query(
        CatalogCall("elevation availability", BBOX_OPTIONS)
    )

    assert found == answer.data
    ((args, kwargs),) = recorder.uses
    assert args == ()
    assert kwargs["bbox"] == kartograf.BBox(530000, 382000, 530100, 382100, "EPSG:2180")
    assert "bbox_crs" not in kwargs
    assert kwargs["product"] == "nmt"
    assert isinstance(kwargs["cache"], kartograf.MetadataCache)
    assert Path(kwargs["cache"].db_path) == tmp_path / "data" / "kartograf_cache.db"


def test_query_of_a_rectangle_without_its_crs_is_invalid_input(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder(Report({}))
    monkeypatch.setattr(kartograf, "check_availability", recorder)
    options = {k: v for k, v in BBOX_OPTIONS.items() if k != "bbox_crs"}

    with pytest.raises(ToolError) as caught:
        KartografClient(settings(tmp_path)).query(
            CatalogCall("elevation availability", options)
        )

    assert caught.value.code == "invalid_input"
    assert recorder.uses == []


def test_query_of_any_other_command_is_refused_before_kartograf_is_asked(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder(Report({}))
    monkeypatch.setattr(kartograf, "check_availability", recorder)

    with pytest.raises(ToolError):
        KartografClient(settings(tmp_path)).query(
            CatalogCall("landcover download", {"teryt": TERYT["code"]})
        )

    assert recorder.uses == []


# --- the factory --------------------------------------------------------------


def test_create_builds_a_client_and_leaves_the_disk_alone(
    tmp_path: Path, cwd: Path
) -> None:
    before = tree(tmp_path)

    client = create(settings(tmp_path))

    assert isinstance(client, KartografClient)
    assert client.settings == settings(tmp_path)
    assert tree(tmp_path) == before

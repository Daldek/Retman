"""Kartograf's command client: offline checks, lookups and the way a run is made.

Validation, command lines, lookups, runs and plans use the real Kartograf in process,
offline (``kartograf_offline``: its network is a stub, its store a real folder). Where a
test asserts what the client hands to Kartograf, ``run_command`` and the like are
replaced by a recorder.
"""

import contextlib
import hashlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import kartograf
import pytest
from kartograf_offline import GugikIndex, flight, gugik_index
from kartograf_support import (
    CHILDREN,
    FOUR,
    NMT_OPTIONS,
    SHEET,
    TERYT,
    built_store,
    context,
    document,
    geometry,
    settings,
    sheets,
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
# The call of the real runs: a sheet that expands into four, of which the index of
# the scenario "one of four" has one flight
DOWNLOAD_FOUR = CatalogCall("elevation download", {**NMT_OPTIONS, "sheet": FOUR}, "dem")
BBOX_OPTIONS = {
    "product": "nmt",
    "country": "pl",
    "bbox": [530000, 382000, 530100, 382100],
    "bbox_crs": "EPSG:2180",
}


def tree(root: Path) -> set[Path]:
    """Every file and folder below ``root``."""
    return set(root.rglob("*"))


def one_of_four() -> GugikIndex:
    """An index with a flight of the first of the four sheets of ``FOUR``."""
    return GugikIndex([flight(CHILDREN[0], "2025-10-21", "84183", full=False)])


class Report:
    """What a Kartograf command returns: an object with ``to_dict()``.

    ``result`` is the domain document of an envelope (the plan of ``check_command``).
    """

    def __init__(self, data: dict[str, Any], result: dict[str, Any] | None = None):
        self.data = data
        self.result = Report(result) if result is not None else None

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

    # The registry code of the tool, its reason as the precision
    assert caught.value.tool_code == "validation_error"
    assert caught.value.code == "validation_error"
    assert caught.value.details["reason"] == "invalid_input"
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

    line = client.command_line(DOWNLOAD)

    words = line.split()
    store = str(tmp_path / "store")
    # The store is the store root, never the plain directory of a write
    assert words[words.index("--root") + 1] == store
    assert "--output-dir" not in words and "-o" not in words
    assert words[words.index("-w") + 1] == "2"
    for other in ("--upgrade", "--force"):
        assert (other in words) == (other == flag)
    # Kartograf reads its own line back into the call
    parsed = kartograf.parse_command(line)
    assert parsed.options == {
        "product": "nmt",
        "sheet": "N-34-130-D-d-2-4",
        "resolution": "5m",
        "vertical_crs": "EVRF2007",
    }
    assert parsed.run["root"] == store


# --- lookup (the real Kartograf, offline) ------------------------------------


@pytest.mark.parametrize(
    ("sheet", "scale", "count"),
    [("N-34-130-D-d-2", "1:10000", 4), ("7.171.21", "1:2000", 25)],
)
def test_lookup_parse_counts_the_descendant_sheets(
    tmp_path: Path, sheet: str, scale: str, count: int
) -> None:
    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("sheet parse", {"sheet": sheet, "descendants": scale})
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
            "sheet find",
            {"geometry": area["path"], "scale": "1:10000", "sheet_system": "1992"},
        )
    )
    by_box = client.lookup(
        CatalogCall(
            "sheet find",
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


def test_lookup_store_sidecar_reads_the_sidecar_of_a_file_of_the_tools_store(
    tmp_path: Path,
) -> None:
    store = built_store(tmp_path / "store")
    newest = store.files[0].versions[-1]

    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("store sidecar", {"path": str(store.files[0].path)})
    )

    assert found["sidecar"]["dataset"] == "pl.gugik.nmt_1m"
    assert found["sidecar"]["sha256"] == newest.sha256
    assert found["sidecar"]["size_bytes"] == newest.size_bytes


def test_lookup_store_sidecar_returns_the_extra_facts_of_the_meta_file(
    tmp_path: Path,
) -> None:
    from kartograf.testing import make_sidecar

    data = tmp_path / "store" / "sheet.asc"
    data.parent.mkdir()
    data.write_text("x", encoding="utf-8")
    meta = make_sidecar(extra={"mask": {"masked_pixels": 3}})
    Path(f"{data}.meta.json").write_text(json.dumps(meta), encoding="utf-8")

    found = KartografClient(settings(tmp_path)).lookup(
        CatalogCall("store sidecar", {"path": str(data)})
    )

    assert found["sidecar"]["extra"]["mask"] == {"masked_pixels": 3}


@pytest.mark.parametrize(
    "call",
    [
        CatalogCall("elevation download", DOWNLOAD.options),
        CatalogCall("imagery download", {"sheet": "N-34-130-D-d-2-4"}),
        CatalogCall("landcover download", {"teryt": "2264"}),
        CatalogCall("elevation availability", BBOX_OPTIONS),
        CatalogCall("store init", {}),
        CatalogCall("cache clear", {}),
    ],
    ids=lambda call: call.command,
)
def test_lookup_refuses_a_command_that_needs_the_network_or_writes(
    tmp_path: Path, call: CatalogCall
) -> None:
    client = KartografClient(settings(tmp_path))

    with pytest.raises(ToolError) as caught:
        client.lookup(call)

    assert caught.value.tool_code == "not_offline"
    assert caught.value.call is call
    assert not (tmp_path / "store").exists()


def test_lookup_without_its_required_option_is_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(ToolError) as caught:
        KartografClient(settings(tmp_path)).lookup(CatalogCall("sheet parse", {}))

    assert caught.value.tool_code == "validation_error"
    assert caught.value.details["reason"] == "invalid_input"


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
    report = Report(sheets("one_of_four", tmp_path / "elsewhere"))

    recorder = run_with(monkeypatch, report, KartografClient(config))

    ((args, kwargs),) = recorder.uses
    assert args == (DOWNLOAD.command, DOWNLOAD.options)
    # The store is the versioned store of the settings, not a directory of plain files
    assert kwargs["root"] == config["store_dir"]
    assert "output_dir" not in kwargs
    assert kwargs["workers"] == 2
    assert kwargs["update"] == mode
    cache = kwargs["cache"]
    assert isinstance(cache, kartograf.MetadataCache)
    assert Path(cache.db_path) == Path(config["cache_file"])


def test_run_writes_the_store_the_settings_name_and_nothing_into_the_working_directory(
    tmp_path: Path, cwd: Path
) -> None:
    index = one_of_four()
    store = tmp_path / "store"

    with gugik_index(index):
        run = KartografClient(settings(tmp_path)).run(DOWNLOAD_FOUR)

    assert isinstance(run, ToolRun)
    assert run.status == "ok"
    assert run.schema == "kartograf-result/1"
    assert run.command == "elevation download"
    (file,) = run.files
    assert file.path.name == "N-34-139-C-a-3-1.asc"
    assert file.path.is_relative_to(store)
    assert file.sha256 == hashlib.sha256(file.path.read_bytes()).hexdigest()
    assert file.version == "2025-10-21_84183"
    assert file.status == "new"
    # The first write into a new root marks the store (DEV-19.12)
    assert json.loads((store / "kartograf-store.json").read_text("utf-8"))[
        "schema"
    ] == ("kartograf-store/1")
    assert run.command_line.startswith("kartograf elevation download")
    assert f"--root {store}" in run.command_line
    assert index.resolved == list(CHILDREN)


def test_run_returns_the_notices_of_the_envelope_as_they_are(
    tmp_path: Path, cwd: Path
) -> None:
    with gugik_index(one_of_four()):
        run = KartografClient(settings(tmp_path)).run(DOWNLOAD_FOUR)

    assert run.notices
    assert all(isinstance(notice, ToolNotice) for notice in run.notices)
    assert {"incomplete_campaign", "no_coverage_some"} == {n.code for n in run.notices}
    assert {notice.level for notice in run.notices} == {"warning"}
    # The whole envelope is the tool's document, notices and units included
    assert run.document["notices"][0]["code"] == run.notices[0].code
    assert run.document["result"]["schema"] == "kartograf-download/1"
    assert [item["id"] for item in run.document["items"]] == [CHILDREN[0]]


def test_a_repeated_run_finds_the_version_in_the_store_and_says_unchanged(
    tmp_path: Path, cwd: Path
) -> None:
    index = GugikIndex([flight(CHILDREN[0], "2025-10-21", "84183")])
    client = KartografClient(settings(tmp_path))
    call = CatalogCall(
        "elevation download", {**NMT_OPTIONS, "sheet": CHILDREN[0]}, "dem"
    )

    with gugik_index(index):
        client.run(call)
        again = client.run(call)

    # The document says unchanged for a version that was not transferred again
    (file,) = again.files
    assert file.status == "unchanged"
    assert len(index.downloaded) == 1


@pytest.mark.parametrize(
    ("scenario", "status", "files", "failures"),
    [
        ("one_delivered", "ok", 1, []),
        ("one_of_four", "ok", 1, []),
        ("hard_failure", "partial", 1, [("source_unavailable", "PL", None)]),
        ("none_delivered", "failed", 0, [("no_data", "PL", "no_coverage")]),
    ],
)
def test_run_from_document_maps_every_outcome_of_the_tool(
    tmp_path: Path,
    scenario: str,
    status: str,
    files: int,
    failures: list[tuple[str, str, str | None]],
) -> None:
    doc = sheets(scenario, tmp_path / "store")

    run = run_from_document(DOWNLOAD_FOUR, doc)

    assert run.status == status
    assert len(run.files) == files
    assert [(item.kind, item.unit, item.reason) for item in run.failed] == [
        (code, unit, reason) for code, unit, reason in failures
    ]
    assert run.schema == "kartograf-result/1"
    assert run.document is doc


def test_run_from_document_reads_a_failed_county_and_a_cutout_of_all_nodata(
    tmp_path: Path,
) -> None:
    counties = run_from_document(DOWNLOAD, bdot10k_document(tmp_path))
    cutout = run_from_document(
        DOWNLOAD, document("cutout_all_nodata", tmp_path / "store")
    )

    assert counties.status == "partial"
    assert [f.path.name for f in counties.files] == ["0208.gpkg", "0261.gpkg"]
    assert [(f.kind, f.unit) for f in counties.failed] == [
        ("source_unavailable", "0224")
    ]
    assert cutout.status == "ok"
    # Every notice is kept; the info notice stays in the audit and is not shown
    assert [notice.code for notice in cutout.notices] == ["cutout_size", "all_nodata"]


def bdot10k_document(tmp_path: Path) -> dict[str, Any]:
    """The envelope of BDOT10k of three counties, one of which fails."""
    from kartograf_support import bdot10k

    return bdot10k("GPKG", tmp_path / "store")


# --- errors -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raised", "code", "reason"),
    [
        (
            kartograf.NoCoverageError("x", sheet="s", hints=("h",)),
            "no_data",
            "no_coverage",
        ),
        (kartograf.DownloadError("x"), "source_unavailable", None),
        (kartograf.ConflictError("x", reason="not_empty"), "conflict", "not_empty"),
        (
            kartograf.StoreUnavailableError("x", reason="no_marker"),
            "store_unavailable",
            "no_marker",
        ),
        (kartograf.CacheError("x"), "store_unavailable", "cache"),
        (OSError("disk full"), "io_error", None),
        (RuntimeError("bug"), "internal_error", None),
    ],
    ids=lambda value: type(value).__name__ if isinstance(value, Exception) else None,
)
def test_run_turns_every_failure_into_a_tool_error_with_the_registry_code(
    tmp_path: Path,
    cwd: Path,
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    code: str,
    reason: str | None,
) -> None:
    with pytest.raises(ToolError) as caught:
        run_with(monkeypatch, raised, KartografClient(settings(tmp_path)))

    assert caught.value.tool_code == code
    assert caught.value.code == code
    assert caught.value.details.get("reason") == reason
    assert caught.value.__cause__ is raised
    assert caught.value.call is DOWNLOAD


def test_run_keeps_the_hints_of_a_sheet_without_coverage(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raised = kartograf.NoCoverageError("x", sheet="s", hints=("h",))

    with pytest.raises(ToolError) as caught:
        run_with(monkeypatch, raised, KartografClient(settings(tmp_path)))

    assert list(caught.value.details["tool_details"]["hints"]) == ["h"]


def test_run_lets_a_keyboard_interrupt_through(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(KeyboardInterrupt):
        run_with(monkeypatch, KeyboardInterrupt(), KartografClient(settings(tmp_path)))


# --- the marker of the store (DEV-19.12 to DEV-19.14) -------------------------------


def unmarked_layout(tmp_path: Path) -> Path:
    """A store whose marker is gone: its layout, no ``kartograf-store.json``."""
    store = built_store(tmp_path / "store")
    (store.root / "kartograf-store.json").unlink()
    return store.root


def other_files(tmp_path: Path) -> Path:
    """A folder with a file that is no part of a store."""
    store = tmp_path / "store"
    store.mkdir()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")
    return store


def inside_a_store(tmp_path: Path) -> Path:
    """A folder that does not exist yet, in the store of another tool or version."""
    return built_store(tmp_path / "outer").root / "inner"


@pytest.mark.parametrize("prepare", [unmarked_layout, other_files, inside_a_store])
def test_a_run_into_a_store_kartograf_refuses_writes_and_fetches_nothing(
    tmp_path: Path, cwd: Path, prepare: Callable[[Path], Path]
) -> None:
    store = prepare(tmp_path)
    before = tree(tmp_path)
    index = one_of_four()

    # Reported as the failure of the sheets or raised: either way, nothing happens
    with gugik_index(index), contextlib.suppress(ToolError):
        KartografClient({**settings(tmp_path), "store_dir": str(store)}).run(
            DOWNLOAD_FOUR
        )

    assert tree(tmp_path) == before
    assert index.downloaded == []


@pytest.mark.xfail(
    strict=True,
    reason="Kartograf reports a refused store as the failure of each sheet "
    "(source_unavailable, kind download) after the work has begun. Its fix: a refused "
    "store is a command error with its registry code and reason, raised before any "
    "work. Drop this marker when the Kartograf pin has that fix.",
)
@pytest.mark.parametrize(
    ("prepare", "code", "reason"),
    [
        (unmarked_layout, "store_unavailable", "no_marker"),
        (other_files, "conflict", "not_empty"),
        (inside_a_store, "conflict", "nested_store"),
    ],
    ids=["no_marker", "not_empty", "nested_store"],
)
def test_a_run_into_a_store_kartograf_refuses_is_an_error_with_its_registry_code(
    tmp_path: Path,
    cwd: Path,
    prepare: Callable[[Path], Path],
    code: str,
    reason: str,
) -> None:
    store = prepare(tmp_path)

    with gugik_index(one_of_four()), pytest.raises(ToolError) as caught:
        KartografClient({**settings(tmp_path), "store_dir": str(store)}).run(
            DOWNLOAD_FOUR
        )

    # The reason survives as details.reason, so that nothing parses the text of the tool
    assert (caught.value.code, caught.value.details["reason"]) == (code, reason)


# --- check and query ----------------------------------------------------------


def test_check_asks_kartograf_for_the_plan_of_the_store_with_the_cache_file(
    tmp_path: Path, cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = {"schema": "kartograf-plan/1", "mode": "store", "items": []}
    recorder = Recorder(Report({"result": plan}, plan))
    monkeypatch.setattr(kartograf, "check_command", recorder)

    answer = KartografClient(settings(tmp_path)).check(DOWNLOAD)

    # The plan is the result of the envelope, not the envelope
    assert answer == plan
    ((args, kwargs),) = recorder.uses
    assert args == (DOWNLOAD.command, DOWNLOAD.options)
    assert kwargs["root"] == str(tmp_path / "store")
    assert "output_dir" not in kwargs
    assert isinstance(kwargs["cache"], kartograf.MetadataCache)
    assert Path(kwargs["cache"].db_path) == tmp_path / "data" / "kartograf_cache.db"


def test_check_of_a_request_returns_the_plan_of_the_store_and_writes_nothing(
    tmp_path: Path, cwd: Path
) -> None:
    with gugik_index(one_of_four()):
        answer = KartografClient(settings(tmp_path)).check(DOWNLOAD_FOUR)

    assert answer["schema"] == "kartograf-plan/1"
    assert answer["mode"] == "store"
    assert answer["root"] == str(tmp_path / "store")
    assert [item["status"] for item in answer["items"]] == ["missing"]
    # A plan creates nothing, not even the store (DEV-19.10)
    assert not (tmp_path / "store").exists()


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

    assert caught.value.tool_code == "validation_error"
    assert caught.value.details["reason"] == "invalid_input"
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

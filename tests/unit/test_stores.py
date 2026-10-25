"""Folders of the tool stores: ``retman doctor check`` and IMGWTools set-up."""

import errno
import os
import sys
import tempfile
from pathlib import Path

import pytest
from imgw_store_files import write_layout, write_marker, write_server_state

from retman.stores import (
    IMGW_MARKER,
    ImgwStore,
    hardlink_error,
    imgw_store_state,
    init_imgw_store,
    probe_imgw_write,
    symlink_component,
)


def test_symlink_component_finds_a_link_in_any_part_of_the_path(tmp_path: Path):
    real = tmp_path / "real"
    (real / "deeper").mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")

    assert symlink_component(tmp_path / "real" / "deeper") is None
    assert symlink_component(link / "deeper") == link
    # A folder that does not exist yet below a link is still reached through it
    assert symlink_component(link / "new" / "store") == link


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ("missing", ImgwStore("missing")),
        ("file", ImgwStore("not_a_directory")),
        ("empty", ImgwStore("empty")),
        ("ready", ImgwStore("ready", "imgw-store/1")),
        ("foreign", ImgwStore("foreign")),
        ("unreadable", ImgwStore("unreadable")),
        ("no_schema", ImgwStore("unreadable")),
        ("newer", ImgwStore("unsupported", "imgw-store/2")),
        # A layout is a store that lost its marker (or never had one): `store init`
        ("layout", ImgwStore("no_marker")),
        ("layout_and_notes", ImgwStore("no_marker")),
        ("marked_layout", ImgwStore("ready", "imgw-store/1")),
        ("tree_is_a_file", ImgwStore("foreign")),
        # The key file of the REST server lives in the default store folder
        ("server_state", ImgwStore("empty")),
        ("server_state_and_notes", ImgwStore("foreign")),
    ],
)
def test_imgw_store_state_tells_what_the_folder_holds(
    tmp_path: Path, setup: str, expected: ImgwStore
):
    folder = tmp_path / "store"
    raw_markers = {
        "unreadable": "{",
        "no_schema": '{"created_by": "imgwtools 3.0.0"}',
        "newer": '{"schema": "imgw-store/2"}',
    }
    if setup == "file":
        folder.write_text("x", encoding="utf-8")
    elif setup != "missing":
        folder.mkdir()
    if setup in raw_markers:
        (folder / IMGW_MARKER).write_text(raw_markers[setup], encoding="utf-8")
    if setup in ("ready", "marked_layout"):
        write_marker(folder)
    if setup in ("layout", "layout_and_notes", "marked_layout"):
        write_layout(folder, "series")
    if setup in ("server_state", "server_state_and_notes"):
        write_server_state(folder)
    if setup in ("foreign", "layout_and_notes", "server_state_and_notes"):
        (folder / "notes.txt").write_text("x", encoding="utf-8")
    if setup == "tree_is_a_file":
        (folder / "archives").write_text("x", encoding="utf-8")

    assert imgw_store_state(folder) == expected


@pytest.mark.parametrize("tree", ["archives", "series", "stations", "pmaxtp"])
def test_imgw_store_state_sees_the_layout_in_every_tree_of_a_store(
    tmp_path: Path, tree: str
):
    write_layout(tmp_path, tree)

    assert imgw_store_state(tmp_path) == ImgwStore("no_marker")


def test_hardlink_test_works_in_the_folder_and_leaves_nothing_behind(tmp_path: Path):
    assert hardlink_error(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_hardlink_test_returns_the_error_of_a_file_system_without_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def refuse(source: object, target: object) -> None:
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr("retman.stores.os.link", refuse)

    failure = hardlink_error(tmp_path)

    assert failure is not None and failure.errno == errno.EOPNOTSUPP
    assert list(tmp_path.iterdir()) == []


def test_hardlink_test_raises_when_the_folder_takes_no_files(tmp_path: Path):
    with pytest.raises(OSError):
        hardlink_error(tmp_path / "absent")


def test_missing_imgwtools_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setitem(sys.modules, "imgwtools", None)

    assert init_imgw_store(tmp_path / "store").status == "tool_missing"
    assert probe_imgw_write().status == "tool_missing"
    assert not (tmp_path / "store").exists()


# The tests below run the real IMGWTools: offline, no network


@pytest.fixture
def imgwtools():
    pytest.importorskip("pyarrow")
    return pytest.importorskip("imgwtools")


def test_init_imgw_store_creates_the_marker_once(tmp_path: Path, imgwtools):
    store = tmp_path / "data" / "imgwtools"

    first = init_imgw_store(store)
    second = init_imgw_store(store)

    assert (first.status, second.status) == ("ok", "existing")
    assert first.version == str(imgwtools.__version__)
    assert imgw_store_state(store).state == "ready"


def test_init_imgw_store_returns_the_refusal_of_the_tool(tmp_path: Path, imgwtools):
    store = tmp_path / "store"
    store.mkdir()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")

    outcome = init_imgw_store(store)

    assert outcome.status == "refused"
    assert str(store) in outcome.detail
    assert not (store / IMGW_MARKER).exists()


def test_init_imgw_store_marks_a_layout_whose_marker_is_gone_and_keeps_its_files(
    tmp_path: Path, imgwtools
):
    from imgwtools.testing import build_fixture_store

    store = tmp_path / "store"
    build_fixture_store(store)
    (store / IMGW_MARKER).unlink()
    files = {path.relative_to(store) for path in store.rglob("*")}
    assert imgw_store_state(store).state == "no_marker"

    outcome = init_imgw_store(store)

    assert outcome.status == "ok"
    assert imgw_store_state(store) == ImgwStore("ready", "imgw-store/1")
    marked = {path.relative_to(store) for path in store.rglob("*")}
    assert marked == files | {Path(IMGW_MARKER)}


def test_init_imgw_store_refuses_a_layout_with_a_foreign_file_beside_its_trees(
    tmp_path: Path, imgwtools
):
    from imgwtools.testing import build_fixture_store

    store = tmp_path / "store"
    build_fixture_store(store)
    (store / IMGW_MARKER).unlink()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")
    assert imgw_store_state(store).state == "no_marker"

    outcome = init_imgw_store(store)

    assert (outcome.status, outcome.reason) == ("refused", "invalid_layout")
    assert not (store / IMGW_MARKER).exists()


def test_init_imgw_store_takes_a_folder_that_holds_only_the_key_file_of_the_server(
    tmp_path: Path, imgwtools
):
    write_server_state(tmp_path)
    assert imgw_store_state(tmp_path).state == "empty"

    outcome = init_imgw_store(tmp_path)

    assert outcome.status == "ok"
    assert imgw_store_state(tmp_path).state == "ready"
    assert (tmp_path / "api_keys.json").read_text(encoding="utf-8") == "{}"


def test_init_imgw_store_refuses_a_path_through_a_symlink(tmp_path: Path, imgwtools):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")

    outcome = init_imgw_store(link / "store")

    assert outcome.status == "refused"
    assert not (real / "store").exists()


def test_write_probe_builds_a_store_and_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, imgwtools
):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    outcome = probe_imgw_write()

    assert outcome.status == "ok"
    assert list(scratch.iterdir()) == []


def test_write_probe_returns_the_error_of_the_tool_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, imgwtools
):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    def unsupported(root: object, **options: object) -> None:
        raise imgwtools.IMGWStoreConflictError("System plików nie zapewnia zapisu")

    monkeypatch.setattr("imgwtools.testing.build_fixture_store", unsupported)

    outcome = probe_imgw_write()

    assert outcome.status == "refused"
    assert outcome.detail == "System plików nie zapewnia zapisu"
    assert list(scratch.iterdir()) == []


def test_init_imgw_store_names_the_reason_when_the_disk_has_no_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, imgwtools
):
    def refuse(source: object, target: object) -> None:
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr(os, "link", refuse)

    outcome = init_imgw_store(tmp_path / "store")

    assert (outcome.status, outcome.reason) == ("refused", "not_atomic")
    assert "Operation not supported" in outcome.detail

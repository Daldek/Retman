"""Folders of the tool stores: ``retman doctor check`` and IMGWTools set-up."""

import errno
import os
import sys
import tempfile
from pathlib import Path

import pytest

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
    ],
)
def test_imgw_store_state_tells_what_the_folder_holds(
    tmp_path: Path, setup: str, expected: ImgwStore
):
    folder = tmp_path / "store"
    markers = {
        "ready": '{"schema": "imgw-store/1", "created_by": "imgwtools 3.0.0"}',
        "unreadable": "{",
        "no_schema": '{"created_by": "imgwtools 3.0.0"}',
        "newer": '{"schema": "imgw-store/2"}',
    }
    if setup == "file":
        folder.write_text("x", encoding="utf-8")
    elif setup != "missing":
        folder.mkdir()
    if setup in markers:
        (folder / IMGW_MARKER).write_text(markers[setup], encoding="utf-8")
    if setup == "foreign":
        (folder / "notes.txt").write_text("x", encoding="utf-8")

    assert imgw_store_state(folder) == expected


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

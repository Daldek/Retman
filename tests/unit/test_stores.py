"""Folders of the tool stores: ``retman doctor check`` and Obserwator set-up."""

import errno
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from kartograf_store_files import (
    MARKER,
    write_marker,
    write_other_marker,
    write_product_files,
)
from obserwator_store_files import write_layout, write_server_state

from retman.stores import (
    KARTOGRAF_MARKER,
    KARTOGRAF_SCHEMA,
    KARTOGRAF_STAGING,
    KARTOGRAF_TREES,
    OBSERWATOR_MARKERS,
    OBSERWATOR_SCHEMAS,
    STORE_MARKERS,
    KartografStore,
    ObserwatorRoot,
    ObserwatorStore,
    ObserwatorStoreState,
    hardlink_error,
    init_obserwator_store,
    kartograf_store_state,
    obserwator_store_state,
    probe_obserwator_write,
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


# The names of the two roots of Obserwator, spelled out: not taken from
# ``retman.stores``. The trees of each kind, for layouts.
MARKERS = {"raw": "obserwator-store.json", "data": "obserwator-data.json"}
SCHEMAS = {"raw": "obserwator-store/1", "data": "obserwator-data/1"}
LAYOUT_TREES = {
    "raw": ["archives", "pmaxtp"],
    "data": ["series", "stations", "analyses"],
}
OTHER = {"raw": "data", "data": "raw"}
KINDS: list[ObserwatorRoot] = ["raw", "data"]

# (setup, state of the folder for a root of each kind); a ready root's detail is
# the schema of its kind, an unsupported one's the schema its marker names
OBSERWATOR_STATES = [
    ("missing", {"raw": "missing", "data": "missing"}),
    ("file", {"raw": "not_a_directory", "data": "not_a_directory"}),
    ("empty", {"raw": "empty", "data": "empty"}),
    ("ready", {"raw": "ready", "data": "ready"}),
    ("foreign", {"raw": "foreign", "data": "foreign"}),
    ("unreadable", {"raw": "unreadable", "data": "unreadable"}),
    ("no_schema", {"raw": "unreadable", "data": "unreadable"}),
    ("newer", {"raw": "unsupported", "data": "unsupported"}),
    # A layout is a root that lost its marker (or never had one): `store init`
    ("layout", {"raw": "no_marker", "data": "no_marker"}),
    ("layout_and_notes", {"raw": "no_marker", "data": "no_marker"}),
    # The trees of the other kind without a marker are foreign to this kind
    ("other_layout", {"raw": "foreign", "data": "foreign"}),
    ("tree_is_a_file", {"raw": "foreign", "data": "foreign"}),
    # The key file of the REST server lives in the default root folder
    ("server_state", {"raw": "empty", "data": "empty"}),
    ("server_state_and_notes", {"raw": "foreign", "data": "foreign"}),
    # A root of the other kind, as the tool builds it
    ("other_root", {"raw": "wrong_root", "data": "wrong_root"}),
    # A store from before the split: the raw marker beside the data trees
    ("unsplit", {"raw": "ready", "data": "wrong_root"}),
]
OBSERWATOR_CASES = [
    pytest.param(setup, kind, states[kind], id=f"{kind}-{setup}")
    for setup, states in OBSERWATOR_STATES
    for kind in KINDS
]

# What the check of a write into a data root says of a folder in each state, by the
# tool: the ``code/reason`` of the error it raises or of the one conflict it plans
# (DEV-19.10)
OBSERWATOR_WRITE_VERDICTS = {
    "missing": "ok",
    "empty": "ok",
    "ready": "ok",
    "no_marker": "store_unavailable/no_marker",
    "foreign": "conflict/not_empty",
    "not_a_directory": "conflict/not_empty",
    "unreadable": "data_error/invalid_marker",
    "unsupported": "store_unavailable/unsupported",
    "wrong_root": "store_unavailable/wrong_root",
}
# What ``store init --kind`` does with a folder in each state: it verifies a layout
# without its marker before marking it, so that state has two outcomes
OBSERWATOR_INIT_VERDICTS: dict[str, str | set[str]] = {
    **OBSERWATOR_WRITE_VERDICTS,
    "no_marker": {"ok", "data_error/invalid_layout"},
}


def make_obserwator_folder(
    setup: str, kind: str, root: Path, request: pytest.FixtureRequest
) -> Path:
    """Build the scenario ``setup`` for a root of ``kind`` as ``root/store``."""
    folder = root / "store"
    raw_markers = {
        "unreadable": "{",
        "no_schema": '{"created_by": "obserwator 3.0.0"}',
        "newer": json.dumps({"schema": SCHEMAS[kind].replace("/1", "/2")}),
    }
    if setup in ("ready", "other_root", "unsplit"):
        # The roots as the tool builds them, not a marker written by hand
        roots = request.getfixturevalue("obserwator_store_template")
        built = {"ready": kind, "other_root": OTHER[kind], "unsplit": "raw"}[setup]
        shutil.copytree(roots[built], folder)
        if setup == "unsplit":
            for tree in ("series", "stations"):
                shutil.copytree(roots["data"] / tree, folder / tree)
    elif setup == "file":
        folder.write_text("x", encoding="utf-8")
    elif setup != "missing":
        folder.mkdir()
    if setup in raw_markers:
        (folder / MARKERS[kind]).write_text(raw_markers[setup], encoding="utf-8")
    if setup in ("layout", "layout_and_notes"):
        write_layout(folder, LAYOUT_TREES[kind][0])
    if setup == "other_layout":
        write_layout(folder, LAYOUT_TREES[OTHER[kind]][0])
    if setup in ("server_state", "server_state_and_notes"):
        write_server_state(folder)
    if setup in ("foreign", "layout_and_notes", "server_state_and_notes"):
        (folder / "notes.txt").write_text("x", encoding="utf-8")
    if setup == "tree_is_a_file":
        (folder / LAYOUT_TREES[kind][0]).write_text("x", encoding="utf-8")
    return folder


@pytest.mark.parametrize(("setup", "kind", "state"), OBSERWATOR_CASES)
def test_obserwator_store_state_tells_what_the_folder_holds(
    tmp_path: Path,
    setup: str,
    kind: ObserwatorRoot,
    state: ObserwatorStoreState,
    request: pytest.FixtureRequest,
):
    folder = make_obserwator_folder(setup, kind, tmp_path, request)
    detail = {
        "ready": SCHEMAS[kind],
        "unsupported": SCHEMAS[kind].replace("/1", "/2"),
    }.get(state, "")

    assert obserwator_store_state(folder, kind=kind) == ObserwatorStore(state, detail)


@pytest.mark.parametrize("setup", [setup for setup, _ in OBSERWATOR_STATES])
def test_obserwator_store_state_agrees_with_the_check_of_a_write_into_a_data_root(
    tmp_path: Path, request: pytest.FixtureRequest, setup: str
):
    obserwator = pytest.importorskip("obserwator")
    folder = make_obserwator_folder(setup, "data", tmp_path, request)
    raw = tmp_path / "raw"
    shutil.copytree(request.getfixturevalue("obserwator_store_template")["raw"], raw)
    options = obserwator.validate_command(
        "series build",
        options={
            "root": str(folder),
            "raw_root": str(raw),
            "dataset": "pl.imgw.hydro_daily",
        },
    )

    # The plan of a series build reads the roots only: no request, whatever the folder
    try:
        plan = obserwator.check_command("series build", options=options)
        actions = plan.to_json(root=folder)["result"].get("actions", [])
        refusals = [item for item in actions if item.get("action") == "conflict"]
        verdict = f"conflict/{refusals[0]['reason']}" if refusals else "ok"
    except obserwator.ObserwatorError as error:
        verdict = f"{error.code}/{error.details.get('reason')}"

    state = obserwator_store_state(folder, kind="data").state
    assert verdict == OBSERWATOR_WRITE_VERDICTS[state]


@pytest.mark.parametrize(("setup", "kind", "state"), OBSERWATOR_CASES)
def test_obserwator_store_state_agrees_with_store_init_of_the_kind(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    setup: str,
    kind: ObserwatorRoot,
    state: str,
):
    obserwator = pytest.importorskip("obserwator")
    folder = make_obserwator_folder(setup, kind, tmp_path, request)
    found = obserwator_store_state(folder, kind=kind)

    try:
        obserwator.run_command(
            "store init", options={"root": str(folder), "kind": kind}
        )
        verdict = "ok"
    except obserwator.ObserwatorError as error:
        verdict = f"{error.code}/{error.details.get('reason')}"

    expected = OBSERWATOR_INIT_VERDICTS[found.state]
    assert verdict in expected if isinstance(expected, set) else verdict == expected


@pytest.mark.parametrize(
    ("kind", "tree"),
    [(kind, tree) for kind in KINDS for tree in LAYOUT_TREES[kind]],
)
def test_obserwator_store_state_sees_the_layout_in_every_tree_of_a_root(
    tmp_path: Path, kind: ObserwatorRoot, tree: str
):
    write_layout(tmp_path, tree)

    assert obserwator_store_state(tmp_path, kind=kind) == ObserwatorStore("no_marker")


@pytest.mark.parametrize(
    ("kind", "tree"),
    [(kind, tree) for kind in KINDS for tree in LAYOUT_TREES[kind]],
)
def test_obserwator_layout_trees_are_the_ones_the_tool_marks(
    tmp_path: Path, kind: ObserwatorRoot, tree: str
):
    obserwator = pytest.importorskip("obserwator")
    write_layout(tmp_path, tree)

    # A tree of the kind is a layout the tool marks; a foreign folder it refuses
    obserwator.run_command("store init", options={"root": str(tmp_path), "kind": kind})

    assert obserwator_store_state(tmp_path, kind=kind).state == "ready"


def test_obserwator_root_names_are_the_ones_of_the_tool(
    obserwator_store_template: dict[str, Path],
):
    output = pytest.importorskip("obserwator.output")

    markers = (OBSERWATOR_MARKERS["raw"], OBSERWATOR_MARKERS["data"])
    assert markers == (output.STORE_MARKER, output.DATA_MARKER)
    for kind in KINDS:
        folder = obserwator_store_template[kind]
        marker = json.loads(
            (folder / OBSERWATOR_MARKERS[kind]).read_text(encoding="utf-8")
        )
        assert marker["schema"] == OBSERWATOR_SCHEMAS[kind]


# The product trees of Kartograf, spelled out: not taken from ``retman.stores``
KARTOGRAF_PRODUCT_TREES = [
    "boundaries",
    "cadastre",
    "contours",
    "geodesy",
    "hsg",
    "hydro",
    "intensity",
    "landcover",
    "laz",
    "maps",
    "models3d",
    "names",
    "nmpt",
    "nmt",
    "oblique-orto",
    "orto",
    "soil",
    "true-orto",
]

# (folder, state, detail) of ``kartograf_store_state``. The detail of a store inside
# or holding another is the folder of the other store, relative to the test folder.
KARTOGRAF_STATES = [
    ("missing", "missing", ""),
    ("file", "not_a_directory", ""),
    ("empty", "empty", ""),
    # Neither folders of products without a file, nor a staging folder, nor the file of
    # a writer that is about to mark the folder are content: the first write marks it
    ("empty_trees", "empty", ""),
    ("staging_in_a_tree", "empty", ""),
    ("marker_being_written", "empty", ""),
    ("ready", "ready", "kartograf-store/1"),
    ("foreign", "foreign", ""),
    ("foreign_folder", "foreign", ""),
    ("tree_is_a_file", "foreign", ""),
    ("unreadable", "unreadable", ""),
    ("no_schema", "unreadable", ""),
    ("newer", "unsupported", "kartograf-store/2"),
    # A layout is a store that lost its marker (or never had one): `store init`
    ("layout", "no_marker", ""),
    ("layout_and_notes", "no_marker", ""),
    # A store never lies in, is or holds the store of another tool or place
    ("in_a_kartograf_store", "nested", "outer"),
    ("in_an_obserwator_store", "nested", "outer"),
    ("is_an_obserwator_store", "nested", "store"),
    ("holds_an_obserwator_store", "nested", "store/imports"),
    # The product trees of a store are its own data: they are not searched
    ("marker_in_a_tree", "ready", "kartograf-store/1"),
]

# What Kartograf's check before a plan or a write says of a folder in each state
KARTOGRAF_VERDICTS = {
    "missing": "ok",
    "empty": "ok",
    "ready": "ok",
    "no_marker": "store_unavailable/no_marker",
    "foreign": "conflict/not_empty",
    "not_a_directory": "conflict/not_empty",
    "unreadable": "data_error/invalid_layout",
    "unsupported": "data_error/invalid_layout",
    "nested": "conflict/nested_store",
}


# The scenarios made from a store that the tool itself built (DEV-10.6)
BUILT_BY_THE_TOOL = (
    "ready",
    "layout",
    "layout_and_notes",
    "holds_an_obserwator_store",
    "marker_in_a_tree",
)


def make_kartograf_folder(
    setup: str, root: Path, request: pytest.FixtureRequest
) -> Path:
    """Build the scenario ``setup`` below ``root``; return the folder to judge."""
    folder = root / "store"
    if setup in BUILT_BY_THE_TOOL:
        shutil.copytree(request.getfixturevalue("kartograf_store_template"), folder)
    match setup:
        case "missing" | "ready":
            pass
        case "file":
            folder.write_text("x", encoding="utf-8")
        case "empty":
            folder.mkdir()
        case "empty_trees":
            (folder / "nmt" / "a_variant" / "versions").mkdir(parents=True)
        case "staging_in_a_tree":
            staging = folder / "nmt" / "a_variant" / ".incoming"
            staging.mkdir(parents=True)
            (staging / "part.bin").write_text("x", encoding="utf-8")
        case "marker_being_written":
            folder.mkdir()
            (folder / f".{MARKER}.0123abcd.tmp").write_text("{", encoding="utf-8")
        case "foreign":
            folder.mkdir()
            (folder / "notes.txt").write_text("x", encoding="utf-8")
        case "foreign_folder":
            (folder / "docs").mkdir(parents=True)
            (folder / "docs" / "notes.txt").write_text("x", encoding="utf-8")
        case "tree_is_a_file":
            folder.mkdir()
            (folder / "nmt").write_text("x", encoding="utf-8")
        case "unreadable":
            folder.mkdir()
            (folder / MARKER).write_text("{", encoding="utf-8")
        case "no_schema":
            folder.mkdir()
            (folder / MARKER).write_text('{"tool": "kartograf"}', encoding="utf-8")
        case "newer":
            write_marker(folder, "kartograf-store/2")
        case "layout" | "layout_and_notes":
            (folder / MARKER).unlink()
            if setup == "layout_and_notes":
                (folder / "notes.txt").write_text("x", encoding="utf-8")
        case "in_a_kartograf_store":
            write_marker(root / "outer")
            folder = root / "outer" / "inner"
        case "in_an_obserwator_store":
            write_other_marker(root / "outer")
            folder = root / "outer" / "inner"
        case "is_an_obserwator_store":
            write_other_marker(folder)
        case "holds_an_obserwator_store":
            write_other_marker(folder / "imports")
        case "marker_in_a_tree":
            write_other_marker(folder / "nmt" / "a_copy")
        case _:
            raise ValueError(setup)
    return folder


@pytest.mark.parametrize(
    ("setup", "state", "detail"),
    KARTOGRAF_STATES,
    ids=[setup for setup, _, _ in KARTOGRAF_STATES],
)
def test_kartograf_store_state_tells_what_the_folder_holds(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    setup: str,
    state: str,
    detail: str,
):
    folder = make_kartograf_folder(setup, tmp_path, request)

    found = kartograf_store_state(folder)

    other = str(tmp_path / detail) if state == "nested" else detail
    assert (found.state, found.detail) == (state, other)


@pytest.mark.parametrize("tree", KARTOGRAF_PRODUCT_TREES)
def test_kartograf_store_state_sees_the_layout_in_every_product_tree(
    tmp_path: Path, tree: str
):
    write_product_files(tmp_path, tree)

    assert kartograf_store_state(tmp_path) == KartografStore("no_marker")


@pytest.mark.parametrize("setup", [setup for setup, _, _ in KARTOGRAF_STATES])
def test_kartograf_store_state_agrees_with_the_check_the_tool_makes(
    tmp_path: Path, request: pytest.FixtureRequest, setup: str
):
    kartograf = pytest.importorskip("kartograf")
    marker = pytest.importorskip("kartograf.marker")
    folder = make_kartograf_folder(setup, tmp_path, request)

    try:
        marker.lenient_store(folder)
        verdict = "ok"
    except kartograf.KartografError as error:
        verdict = f"{error.code}/{error.details().get('reason')}"

    assert verdict == KARTOGRAF_VERDICTS[kartograf_store_state(folder).state]


def test_kartograf_store_names_are_the_ones_of_the_tool():
    marker = pytest.importorskip("kartograf.marker")

    assert marker.MARKER == KARTOGRAF_MARKER
    assert marker.MARKER_SCHEMA == KARTOGRAF_SCHEMA
    assert marker.STORE_MARKERS == STORE_MARKERS
    assert marker.INCOMING == KARTOGRAF_STAGING
    # A product the tool adds must show up here: files in its tree are a layout
    assert marker.managed_trees() == KARTOGRAF_TREES


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


def test_missing_obserwator_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setitem(sys.modules, "obserwator", None)

    assert init_obserwator_store(tmp_path / "store", kind="raw").status == (
        "tool_missing"
    )
    assert probe_obserwator_write().status == "tool_missing"
    assert not (tmp_path / "store").exists()


# The tests below run the real Obserwator: offline, no network


@pytest.fixture
def obserwator():
    pytest.importorskip("pyarrow")
    return pytest.importorskip("obserwator")


@pytest.mark.parametrize("kind", KINDS)
def test_init_obserwator_store_creates_the_marker_of_the_kind_once(
    tmp_path: Path, obserwator, kind: ObserwatorRoot
):
    store = tmp_path / "data" / "obserwator"

    first = init_obserwator_store(store, kind=kind)
    second = init_obserwator_store(store, kind=kind)

    assert (first.status, second.status) == ("ok", "existing")
    assert first.version == str(obserwator.__version__)
    assert obserwator_store_state(store, kind=kind) == ObserwatorStore(
        "ready", SCHEMAS[kind]
    )
    assert not (store / MARKERS[OTHER[kind]]).exists()


def test_init_obserwator_store_returns_the_refusal_of_the_tool(
    tmp_path: Path, obserwator
):
    store = tmp_path / "store"
    store.mkdir()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")

    outcome = init_obserwator_store(store, kind="data")

    assert outcome.status == "refused"
    assert str(store) in outcome.detail
    assert list(store.iterdir()) == [store / "notes.txt"]


@pytest.mark.parametrize("kind", KINDS)
def test_init_obserwator_store_refuses_a_root_of_the_other_kind(
    tmp_path: Path, obserwator_store_template: dict[str, Path], kind: ObserwatorRoot
):
    store = tmp_path / "store"
    shutil.copytree(obserwator_store_template[OTHER[kind]], store)

    outcome = init_obserwator_store(store, kind=kind)

    assert (outcome.status, outcome.reason) == ("refused", "wrong_root")
    assert not (store / MARKERS[kind]).exists()


@pytest.mark.parametrize("kind", KINDS)
def test_init_obserwator_store_marks_a_layout_whose_marker_is_gone_and_keeps_its_files(
    tmp_path: Path, obserwator_store_template: dict[str, Path], kind: ObserwatorRoot
):
    store = tmp_path / "store"
    shutil.copytree(obserwator_store_template[kind], store)
    (store / MARKERS[kind]).unlink()
    files = {path.relative_to(store) for path in store.rglob("*")}
    assert obserwator_store_state(store, kind=kind).state == "no_marker"

    outcome = init_obserwator_store(store, kind=kind)

    assert outcome.status == "ok"
    assert obserwator_store_state(store, kind=kind) == ObserwatorStore(
        "ready", SCHEMAS[kind]
    )
    marked = {path.relative_to(store) for path in store.rglob("*")}
    assert marked == files | {Path(MARKERS[kind])}


def test_init_obserwator_store_refuses_a_layout_with_a_foreign_file_beside_its_trees(
    tmp_path: Path, obserwator_store_template: dict[str, Path]
):
    store = tmp_path / "store"
    shutil.copytree(obserwator_store_template["data"], store)
    (store / MARKERS["data"]).unlink()
    (store / "notes.txt").write_text("not a store", encoding="utf-8")
    assert obserwator_store_state(store, kind="data").state == "no_marker"

    outcome = init_obserwator_store(store, kind="data")

    assert (outcome.status, outcome.reason) == ("refused", "invalid_layout")
    assert not (store / MARKERS["data"]).exists()


def test_init_obserwator_store_takes_a_folder_holding_only_the_key_file_of_the_server(
    tmp_path: Path, obserwator
):
    write_server_state(tmp_path)
    assert obserwator_store_state(tmp_path, kind="raw").state == "empty"

    outcome = init_obserwator_store(tmp_path, kind="raw")

    assert outcome.status == "ok"
    assert obserwator_store_state(tmp_path, kind="raw").state == "ready"
    assert (tmp_path / "api_keys.json").read_text(encoding="utf-8") == "{}"


def test_init_obserwator_store_refuses_a_path_through_a_symlink(
    tmp_path: Path, obserwator
):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")

    outcome = init_obserwator_store(link / "store", kind="data")

    assert outcome.status == "refused"
    assert not (real / "store").exists()


def test_write_probe_builds_a_store_and_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, obserwator
):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    outcome = probe_obserwator_write()

    assert outcome.status == "ok"
    assert list(scratch.iterdir()) == []


def test_write_probe_returns_the_error_of_the_tool_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, obserwator
):
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))

    def unsupported(root: object, **options: object) -> None:
        raise obserwator.ObserwatorStoreConflictError(
            "System plików nie zapewnia zapisu"
        )

    monkeypatch.setattr("obserwator.testing.build_fixture_store", unsupported)

    outcome = probe_obserwator_write()

    assert outcome.status == "refused"
    assert outcome.detail == "System plików nie zapewnia zapisu"
    assert list(scratch.iterdir()) == []


def test_init_obserwator_store_names_the_reason_when_the_disk_has_no_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, obserwator
):
    def refuse(source: object, target: object) -> None:
        raise OSError(errno.EOPNOTSUPP, "Operation not supported")

    monkeypatch.setattr(os, "link", refuse)

    outcome = init_obserwator_store(tmp_path / "store", kind="data")

    assert (outcome.status, outcome.reason) == ("refused", "not_atomic")
    assert "Operation not supported" in outcome.detail

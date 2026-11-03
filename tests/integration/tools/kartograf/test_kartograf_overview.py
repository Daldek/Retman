"""The overview of the Kartograf store (``store overview``): a read, offline.

The stores are built by ``kartograf.testing`` (DEV-10.6) and read by the real
Kartograf through its command layer.
"""

from pathlib import Path

from kartograf.testing import build_fixture_store
from kartograf_support import OfflineClient, context, operations, settings

from retman.adapters.catalog import run_calls
from retman.registry.manifest import HandlerOutput
from retman.tools.kartograf import preview

NAME = "inspect_kartograf_store"


def run(tmp_path: Path) -> HandlerOutput:
    """Run the overview of the store ``tmp_path/store`` as ``execute`` does."""
    client = OfflineClient(settings(tmp_path))
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    ctx = context(NAME, client, root=tmp_path, output_dir=output_dir)
    return run_calls(operations()[NAME], {}, {}, output_dir, ctx)


def test_the_overview_lists_the_segments_of_the_store_without_files(
    tmp_path: Path,
) -> None:
    build_fixture_store(tmp_path / "store")

    output = run(tmp_path)

    values = output["values"]
    assert values["segment_count"] == 2
    assert values["product_counts"] == {"nmt": 2}
    assert {segment["dataset_key"] for segment in values["segments"]} == {
        "pl.gugik.nmt_1m",
        "cz.cuzk.dmr4g",
    }
    assert output["files"] == {}
    assert output["warnings"] == []
    # A read: the command line names the store and nothing else
    (call,) = output["tool"]["calls"]
    assert call["command"] == "store overview"


def test_a_segment_the_installed_kartograf_does_not_know_is_a_warning(
    tmp_path: Path,
) -> None:
    build_fixture_store(tmp_path / "store", variant="unknown_segment")

    output = run(tmp_path)

    (warning,) = output["warnings"]
    assert warning["key"] == "unknown_segments"
    assert warning["args"]["segments"] == "newproduct/pl_experimental"


def test_an_overview_of_a_store_folder_that_does_not_exist_ends_the_plan(
    tmp_path: Path,
) -> None:
    ctx = context(NAME, OfflineClient(settings(tmp_path)), root=tmp_path)

    output = preview.inspect_kartograf_store({}, ctx)

    (problem,) = output["problems"]
    assert problem["params"] == []
    assert (problem.get("code"), problem.get("reason")) == (
        "store_unavailable",
        "not_initialised",
    )


def test_a_store_without_its_marker_can_still_be_inspected(tmp_path: Path) -> None:
    store = build_fixture_store(tmp_path / "store").root
    (store / "kartograf-store.json").unlink()
    ctx = context(NAME, OfflineClient(settings(tmp_path)), root=tmp_path)

    assert preview.inspect_kartograf_store({}, ctx)["problems"] == []
    assert run(tmp_path)["values"]["segment_count"] == 2

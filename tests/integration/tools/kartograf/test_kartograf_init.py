"""``init_kartograf_store``: ``store init`` is a catalog call like the others.

The generic runner calls Kartograf's command layer, which writes the marker of the store
(offline, idempotent), saves the document of the tool and names the call in the audit.
The real Kartograf runs in process on a store folder of the test.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from kartograf_store_files import write_marker
from kartograf_support import built_store, execute, operations, settings

from retman.core.result import Result
from retman.testing import tool_context
from retman.tools.kartograf.client import KartografClient


def init(tmp_path: Path, **overrides: Any) -> Result:
    """Run the operation on the store folder of ``settings(tmp_path)``."""
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    config = {**settings(tmp_path), **overrides}
    ctx = tool_context(
        operations()["init_kartograf_store"],
        client=KartografClient(config),
        settings=config,
        output_dir=output_dir,
    )
    return execute("init_kartograf_store", ctx)


def test_init_marks_a_new_folder_and_a_second_run_leaves_it_as_it_is(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"

    first = init(tmp_path)
    marker = json.loads((store / "kartograf-store.json").read_text("utf-8"))
    second = init(tmp_path)

    assert first.ok and second.ok, (first.error, second.error)
    assert marker["schema"] == "kartograf-store/1" and marker["tool"] == "kartograf"
    assert first.values == {
        "store": str(store),
        "marker": str(store / "kartograf-store.json"),
        "created": True,
    }
    assert second.values["created"] is False
    assert json.loads((store / "kartograf-store.json").read_text("utf-8")) == marker
    # It writes the marker and no file of data, and says nothing that needs a warning
    assert first.files == {} and first.warnings == []


@pytest.mark.parametrize("update", ["local", "upgrade", "force"])
def test_init_is_given_the_store_only_and_the_audit_names_the_call(
    tmp_path: Path, update: str
) -> None:
    store = tmp_path / "store"

    # A download gets the workers and the update mode of the settings; the command that
    # marks the store declares neither, and the command layer refuses an option that
    # is not its own
    result = init(tmp_path, update=update, workers=3)

    assert result.ok, result.error
    assert result.tool is not None
    (call,) = result.tool["calls"]
    saved = tmp_path / "result" / call["document_file"]
    assert (call["command"], call["options"], call["status"], call["files"]) == (
        "store init",
        {},
        "ok",
        [],
    )
    assert call["command_line"] == f"kartograf store init --root {store}"
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == call["sha256"]
    document = json.loads(saved.read_text("utf-8"))
    assert (document["schema"], document["command"]) == (
        "kartograf-result/1",
        "store init",
    )
    assert document["result"]["marker"] == str(store / "kartograf-store.json")


def test_init_marks_a_layout_whose_marker_is_gone_and_keeps_its_files(
    tmp_path: Path,
) -> None:
    store = built_store(tmp_path / "store").root
    (store / "kartograf-store.json").unlink()
    held = set(store.rglob("*"))

    result = init(tmp_path)

    assert result.ok, result.error
    assert set(store.rglob("*")) == held | {store / "kartograf-store.json"}


@pytest.mark.parametrize(
    ("setup", "code", "reason"),
    [
        ("foreign_files", "conflict", "not_empty"),
        ("layout_with_a_foreign_file", "data_error", "invalid_layout"),
        ("inside_a_store", "conflict", "nested_store"),
    ],
)
def test_init_is_refused_by_the_tool_for_a_folder_that_is_not_its_store(
    tmp_path: Path, setup: str, code: str, reason: str
) -> None:
    store = tmp_path / "store"
    if setup == "foreign_files":
        store.mkdir()
        (store / "notes.txt").write_text("not a store", encoding="utf-8")
    elif setup == "layout_with_a_foreign_file":
        built_store(store)
        (store / "kartograf-store.json").unlink()
        (store / "notes.txt").write_text("not a store", encoding="utf-8")
    else:
        write_marker(tmp_path)

    result = init(tmp_path)

    # The registry code and the reason of the tool, in the result and its failure
    assert not result.ok and result.failure is not None
    assert result.error_code == code
    assert (result.failure["code"], result.failure["details"]["reason"]) == (
        code,
        reason,
    )
    assert not (store / "kartograf-store.json").exists()

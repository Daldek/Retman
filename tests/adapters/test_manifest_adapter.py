"""Real file validation and failure isolation against a dummy tool."""

from pathlib import Path

import pytest

from retman.adapters.manifest_adapter import execute_operation
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations


@pytest.fixture
def operations(monkeypatch: pytest.MonkeyPatch):
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_dir))
    from dummy_tool.manifest import MANIFEST

    return load_operations(
        "pl",
        manifests=[(MANIFEST, fixture_dir / "dummy_tool")],
        version_lookup=lambda _: "1.2",
    )


def test_execute_operation_writes_valid_declared_file(operations, tmp_path):
    output_dir = tmp_path / "001_make_dem"
    output_dir.mkdir()

    result = execute_operation(
        operations["make_dem"],
        {"area": {"type": "sheet", "code": "N-34"}, "style": "raw"},
        {},
        output_dir,
        1,
        {},
        {},
        load_core_texts("pl"),
    )

    assert result.ok
    assert result.outputs == ["dem"]
    assert result.files["dem"][0].read_bytes().startswith(b"ncols 1")
    assert "Wynik #1" in result.summary


def test_execute_operation_tool_exception_does_not_escape(operations, tmp_path):
    output_dir = tmp_path / "001_broken_dem"
    output_dir.mkdir()

    result = execute_operation(
        operations["broken_dem"], {}, {}, output_dir, 1, {}, {}, load_core_texts("pl")
    )

    assert not result.ok
    assert result.error is not None
    assert "dummy failure" in result.error
    assert not result.files


def test_execute_operation_rejects_file_outside_numbered_dir(operations, tmp_path):
    output_dir = tmp_path / "001_escape_dem"
    output_dir.mkdir()

    result = execute_operation(
        operations["escape_dem"], {}, {}, output_dir, 1, {}, {}, load_core_texts("pl")
    )

    assert not result.ok
    assert result.error is not None
    assert "outside result directory" in result.error
    assert result.outputs == []

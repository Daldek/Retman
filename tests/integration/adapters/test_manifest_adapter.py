"""Real file validation, failure isolation and the command layer, on a dummy tool."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from retman.adapters.catalog import (
    CatalogCall,
    ToolError,
    ToolFailure,
    ToolFile,
    ToolNotice,
    ToolRun,
)
from retman.adapters.manifest_adapter import execute_operation
from retman.i18n.loader import load_core_texts
from retman.testing import FakeToolClient, tool_context

DEM = b"ncols 1\nnrows 1\nxllcorner 0\nyllcorner 0\ncellsize 1\nNODATA_value -9999\n3\n"
FETCH_PARAMS = {
    "area": {"type": "sheet", "code": "N-34-130-D-d-2-4"},
    "resolution": "0_5m",
    "vertical_crs": "evrf2007",
}


def run_operation(operation, tmp_path: Path, params, *, client=None, settings=None):
    """Execute ``operation`` in a fresh numbered folder; returns result and folder."""
    output_dir = tmp_path / "retman-output" / "001_op"
    output_dir.mkdir(parents=True)
    context = tool_context(
        operation, client=client, settings=settings, output_dir=output_dir
    )
    result = execute_operation(
        operation, params, {}, output_dir, 1, {}, {}, load_core_texts("pl"), context
    )
    return result, output_dir


def test_execute_operation_writes_valid_declared_file(operations, tmp_path):
    result, _ = run_operation(
        operations["make_dem"],
        tmp_path,
        {"area": {"type": "sheet", "code": "N-34"}, "style": "raw"},
    )

    assert result.ok
    assert result.outputs == ["dem"]
    assert result.files["dem"][0].read_bytes().startswith(b"ncols 1")
    assert "Wynik #1" in result.summary


def test_execute_operation_tool_exception_does_not_escape(operations, tmp_path):
    result, _ = run_operation(operations["broken_dem"], tmp_path, {})

    assert not result.ok
    assert result.error is not None
    assert "dummy failure" in result.error
    assert not result.files


def test_execute_operation_rejects_file_outside_numbered_dir(operations, tmp_path):
    result, _ = run_operation(operations["escape_dem"], tmp_path, {})

    assert not result.ok
    assert result.error is not None
    assert "outside result directory" in result.error
    assert result.outputs == []


def test_files_of_the_tools_own_store_are_accepted_and_referenced(operations, tmp_path):
    store = tmp_path / "stores" / "dummy"

    result, output_dir = run_operation(
        operations["store_dem"], tmp_path, {}, settings={"store_dir": str(store)}
    )

    assert result.ok
    assert result.files["dem"] == [(store / "stored.asc").resolve()]
    assert not (output_dir / "stored.asc").exists()
    # The result says where the files are, instead of pointing at an empty folder
    assert str(store) in result.summary


def test_a_store_does_not_open_the_rest_of_the_disk(operations, tmp_path):
    store = tmp_path / "stores" / "dummy"
    store.mkdir(parents=True)

    result, _ = run_operation(
        operations["escape_dem"], tmp_path, {}, settings={"store_dir": str(store)}
    )

    assert not result.ok and "outside result directory" in result.error


def _ok_run(store: Path, **changes) -> ToolRun:
    store.mkdir(parents=True, exist_ok=True)
    stored = store / "N-34-130-D-d-2-4.asc"
    stored.write_bytes(DEM)
    base = ToolRun(
        "elevation download",
        "ok",
        files=(ToolFile(stored, hashlib.sha256(DEM).hexdigest(), "v1", "new"),),
        document={"schema": "dummy-download/1", "ok": True},
        command_line="dummy elevation download --sheet N-34-130-D-d-2-4",
        schema="dummy-download/1",
    )
    return replace(base, **changes)


def test_catalog_operation_runs_the_builders_calls_and_audits_them(
    operations, tmp_path
):
    store = tmp_path / "stores" / "dummy"
    client = FakeToolClient(runs={"elevation download": lambda call: _ok_run(store)})

    result, output_dir = run_operation(
        operations["fetch_dem"],
        tmp_path,
        FETCH_PARAMS,
        client=client,
        settings={"store_dir": str(store)},
    )

    # The tool receives the tool's own values, not Retman's option keys
    assert client.calls == [
        (
            "run",
            CatalogCall(
                "elevation download",
                {
                    "product": "nmt",
                    "resolution": "0.5m",
                    "vertical_crs": "EVRF2007",
                    "sheet": "N-34-130-D-d-2-4",
                },
                kind="dem",
                params={"sheet": "area", "geometry": "area", "layer": "area"},
            ),
        )
    ]
    assert result.ok and result.files["dem"] == [(store / "N-34-130-D-d-2-4.asc")]
    # The operation's describe function adds values; its summary template uses them
    assert result.values == {"calls": 1, "file_count": 1, "resolution": "0.5m"}
    assert result.summary == "Pobrano 1 plik(i), rozdzielczość 0.5m."
    saved = output_dir / "tool_1_elevation_download.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == {
        "schema": "dummy-download/1",
        "ok": True,
    }
    assert result.tool == {
        "tool": "dummy_tool",
        "version": "1.2.0",
        "calls": [
            {
                "command": "elevation download",
                "options": client.calls[0][1].options,
                "command_line": "dummy elevation download --sheet N-34-130-D-d-2-4",
                "schema": "dummy-download/1",
                "status": "ok",
                "files": [
                    {
                        "path": str(store / "N-34-130-D-d-2-4.asc"),
                        "sha256": hashlib.sha256(DEM).hexdigest(),
                        "version": "v1",
                        "status": "new",
                    }
                ],
                "document_file": "tool_1_elevation_download.json",
                "sha256": hashlib.sha256(saved.read_bytes()).hexdigest(),
            }
        ],
    }


def test_notices_and_partial_failures_are_never_dropped(operations, tmp_path):
    store = tmp_path / "stores" / "dummy"
    run = _ok_run(
        store,
        status="partial",
        notices=(
            ToolNotice("warning", "all_nodata", "Wszystkie piksele sa NODATA"),
            ToolNotice("warning", "license_terms", "Dane IMGW-PIB: obowiazuja warunki"),
            ToolNotice("info", "cache_hit", "z pamieci podrecznej"),
        ),
        failed=(ToolFailure("PL", "download", "2 z 5 arkuszy nie pobrano"),),
    )
    client = FakeToolClient(runs={"elevation download": run})

    result, _ = run_operation(
        operations["fetch_dem"],
        tmp_path,
        FETCH_PARAMS,
        client=client,
        settings={"store_dir": str(store)},
    )

    assert result.ok
    assert result.warnings == [
        # A code the tool's translation knows is shown with Retman's own text ...
        "Wszystkie piksele wyniku są bez danych.",
        # ... any other notice verbatim behind a generic prefix; info stays in audit
        "Narzędzie dummy_tool: Dane IMGW-PIB: obowiazuja warunki",
        "Nie wszystko się udało (PL): 2 z 5 arkuszy nie pobrano",
    ]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (
            "validation_error",
            "Narzędzie odrzuca wybór „Układ wysokościowy”: KRON86 tylko do 1 m",
        ),
        (
            "weird_new_code",
            "Narzędzie dummy_tool zgłosiło błąd (weird_new_code): KRON86 tylko do 1 m",
        ),
    ],
)
def test_tool_error_is_shown_with_retman_text_chosen_by_its_code(
    operations, tmp_path, code, expected
):
    error = ToolError("dummy_tool", code, "KRON86 tylko do 1 m", option="vertical_crs")

    def refuse(call: CatalogCall) -> ToolRun:
        raise error

    result, _ = run_operation(
        operations["fetch_dem"],
        tmp_path,
        FETCH_PARAMS,
        client=FakeToolClient(runs={"elevation download": refuse}),
    )

    assert not result.ok
    assert result.error == expected
    assert result.error_code == code
    assert result.summary == f"Wynik #1 nie powiódł się: {expected}"


def test_runner_stops_at_the_first_failed_command_and_keeps_its_document(
    operations, tmp_path
):
    two_calls = replace(
        operations["fetch_dem"],
        spec={**operations["fetch_dem"].spec, "calls": "dummy_tool.calls:fetch_twice"},
    )
    failing = ToolRun(
        "elevation download",
        "failed",
        failed=(ToolFailure("PL", "no_data", "brak pokrycia", "no_coverage"),),
        document={"schema": "dummy-download/1", "ok": False},
    )
    client = FakeToolClient(runs={"elevation download": failing})

    result, output_dir = run_operation(two_calls, tmp_path, FETCH_PARAMS, client=client)

    assert not result.ok and result.error_code == "no_data"
    # The reason of the failed unit is the precision of the registry code
    assert result.failure is not None
    assert result.failure["details"]["reason"] == "no_coverage"
    assert result.error == "Brak danych dla tego obszaru (brak pokrycia)."
    assert [method for method, _ in client.calls] == ["run"]  # the second never ran
    assert (output_dir / "tool_1_elevation_download.json").is_file()


def test_runner_continues_after_a_partial_run(operations, tmp_path):
    store = tmp_path / "stores" / "dummy"
    two_calls = replace(
        operations["fetch_dem"],
        spec={**operations["fetch_dem"].spec, "calls": "dummy_tool.calls:fetch_twice"},
    )
    partial = _ok_run(
        store, status="partial", failed=(ToolFailure("PL", "download", "1 z 2"),)
    )
    client = FakeToolClient(runs={"elevation download": partial})

    result, output_dir = run_operation(
        two_calls,
        tmp_path,
        FETCH_PARAMS,
        client=client,
        settings={"store_dir": str(store)},
    )

    assert result.ok and len(client.calls) == 2
    assert [item["document_file"] for item in result.tool["calls"]] == [
        "tool_1_elevation_download.json",
        "tool_2_elevation_download.json",
    ]
    assert (output_dir / "tool_2_elevation_download.json").is_file()

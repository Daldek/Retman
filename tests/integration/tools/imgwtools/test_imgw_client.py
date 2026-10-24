"""The IMGWTools client against the real tool, offline.

The store is the tool's own fixture store, the network is a replayed answer or
nothing: what these tests pin is the contract the rest of Retman relies on —
what ``lookup`` may do, how the tool's errors become ``ToolError``, what a
``ToolRun`` holds, and that ``root`` and ``IMGW_DATA_DIR`` come from the
``[tools.imgwtools]`` settings.
"""

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import imgwtools
import pytest
from imgw_support import (
    PMAXTP_URL,
    fixture_store,
    isolate_environment,
    pmaxtp_payload,
    real_client,
    replay_http,
    settings_for,
)

from retman.adapters.catalog import CatalogCall, ToolError
from retman.exceptions import RetmanError
from retman.tools.imgwtools.client import IMGWToolsClient, create_client

PRECIP = "pl.imgw.meteo_precip_daily"
EXPORT = CatalogCall(
    "series export",
    {
        "dataset": PRECIP,
        "station": "123750000",
        "start": "2001-01-01",
        "end": "2001-01-31",
        "year_type": "calendar",
    },
)


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    isolate_environment(monkeypatch)


@pytest.fixture
def client(tmp_path: Path) -> IMGWToolsClient:
    return real_client(tmp_path)


def test_the_store_root_comes_from_the_settings_and_is_never_in_a_call(client):
    line = client.command_line(EXPORT)

    assert f"--root {fixture_store()}" in line
    # The stream form is valid without a target: this is what planning validates
    client.validate(EXPORT)


def test_the_live_station_search_gets_no_root_but_the_store_search_does(client):
    live = client.command_line(CatalogCall("stations find", {"source": "live"}))
    store = client.command_line(CatalogCall("stations find", {"source": "store"}))

    # The tool refuses a root with the live source
    assert "--root" not in live
    assert f"--root {fixture_store()}" in store


def test_validation_is_the_tools_and_names_the_option_at_fault(client):
    call = CatalogCall(
        "pmaxtp fetch", {"latitude": 10.0, "longitude": 21.0, "method": "POT"}
    )

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    assert caught.value.tool == "imgwtools"
    assert caught.value.tool_code == "validation_error"
    assert caught.value.option == "latitude"
    assert "poza zakresem" in caught.value.detail


def test_a_rejected_option_value_lists_what_the_tool_allows(client):
    call = CatalogCall(
        "pmaxtp fetch", {"latitude": 52.0, "longitude": 21.0, "method": "XYZ"}
    )

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    assert caught.value.option == "method"
    assert caught.value.allowed == ("POT", "AMP")


def add_task(project: Path, options: dict[str, Any], **given: Any) -> CatalogCall:
    """``project add`` of a ``series select`` task, as the builders make it."""
    return CatalogCall(
        "project add",
        {
            "project_dir": str(project),
            "name": "task",
            "command": "series select",
            "options": options,
            **given,
        },
    )


TASK = {
    "dataset": "pl.imgw.hydro_monthly",
    "years": [2000, 2001],
    "year_type": "hydrological",
    "stations": ["150000111"],
}


def test_a_rejected_task_option_is_named_by_its_path_inside_options(client, tmp_path):
    # The tool says only "options" and keeps the option at fault as the cause
    with pytest.raises(ToolError) as caught:
        client.validate(add_task(tmp_path, {**TASK, "variables": ["Q"]}))

    assert caught.value.tool_code == "validation_error"
    assert caught.value.option == "options.variables"
    assert caught.value.allowed is not None and "Q_mean" in caught.value.allowed


def test_a_rejection_that_names_no_task_option_keeps_the_tools_option(client, tmp_path):
    without_years = {key: TASK[key] for key in TASK if key != "years"}

    with pytest.raises(ToolError) as bad_name:
        client.validate(add_task(tmp_path, TASK, name="Bad Name!"))
    with pytest.raises(ToolError) as no_years:
        client.validate(add_task(tmp_path, without_years))

    # An option of ``project add`` itself; and "options" where the tool says no more
    assert bad_name.value.option == "name"
    assert no_years.value.option == "options"


def test_lookup_refuses_every_command_that_uses_the_network_or_writes(client):
    refused = [
        command
        for command in imgwtools.data_commands()
        if command.network or command.writes != "none" or command.result == "stream"
    ]

    assert {command.name for command in refused} >= {
        "stations find",
        "store init",
        "store sync",
        "store catalog",
        "series export",
        "datasets download",
        "current hydro",
        "pmaxtp fetch",
    }
    for command in refused:
        with pytest.raises(ToolError) as caught:
            client.lookup(CatalogCall(command.name, {}))
        assert caught.value.tool_code == "not_offline", command.name


def test_lookup_serves_the_store_and_the_registry_as_the_tools_envelope(client):
    stations = client.lookup(CatalogCall("stations find", {"source": "store"}))
    info = client.lookup(CatalogCall("store info", {}))
    datasets = client.lookup(CatalogCall("datasets list", {"provider": "CHMI"}))

    assert stations["schema"] == "imgw-result/1" and stations["status"] == "ok"
    assert stations["result"]["total"] == len(stations["result"]["items"]) == 11
    assert info["result"]["exists"] and info["result"]["supported"]
    assert {item["key"] for item in datasets["result"]["items"]} >= {
        "cz.chmi.hydro_daily",
        "cz.chmi.meteo_daily",
    }


def test_lookup_of_the_store_search_refuses_the_live_source(client):
    with pytest.raises(ToolError) as caught:
        client.lookup(CatalogCall("stations find", {"source": "live"}))

    assert caught.value.tool_code == "not_offline"


def test_errors_of_a_lookup_keep_the_tools_code(client):
    with pytest.raises(ToolError) as no_series:
        client.lookup(
            CatalogCall("series summary", {"dataset": "pl.imgw.hydro_semiannual"})
        )
    with pytest.raises(ToolError) as no_station:
        client.lookup(
            CatalogCall("series select", {"dataset": PRECIP, "stations": ["999999999"]})
        )

    assert no_series.value.tool_code == "not_found"
    assert no_station.value.tool_code == "validation_error"
    assert no_station.value.option == "stations"


def test_a_missing_store_is_an_answer_of_store_info_but_an_error_elsewhere(tmp_path):
    client = real_client(tmp_path, tmp_path / "no-such-store")

    info = client.lookup(CatalogCall("store info", {}))
    with pytest.raises(ToolError) as caught:
        client.lookup(CatalogCall("stations find", {"source": "store"}))

    assert info["result"]["exists"] is False
    assert caught.value.tool_code == "store_unavailable"


def test_run_of_an_export_returns_the_file_the_licence_and_the_command(
    client, tmp_path
):
    target = tmp_path / "series.csv"
    call = replace(EXPORT, options={**EXPORT.options, "path": str(target)})

    run = client.run(call)

    assert run.status == "ok" and run.schema == "imgw-result/1"
    (file,) = run.files
    assert file.path == target
    assert file.sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    assert run.failed == ()
    assert [(n.level, n.code) for n in run.notices] == [("info", "license_terms")]
    assert run.document["result"] == str(target)
    assert run.command_line.startswith(f"imgw series export --root {fixture_store()}")
    assert f"--path {target}" in run.command_line


def test_a_stream_command_without_a_target_file_is_refused_before_it_runs(client):
    with pytest.raises(ToolError) as caught:
        client.run(EXPORT)

    assert caught.value.tool_code == "validation_error"
    assert caught.value.option == "path"


def test_run_of_a_live_command_reads_the_answer_without_a_socket(client):
    payload = pmaxtp_payload()
    answer = {
        "url": PMAXTP_URL.format(method="P", lat="52.2300", lon="21.0100"),
        "json": payload,
    }
    call = CatalogCall(
        "pmaxtp fetch", {"latitude": 52.23, "longitude": 21.01, "method": "POT"}
    )

    with replay_http(answer) as requested:
        run = client.run(call)

    assert requested == [answer["url"]]
    assert run.status == "ok"
    assert (
        run.document["result"]["data"]["ks"]["15"]["1"]
        == payload["data"]["ks"]["15"]["1"]
    )


def test_a_source_that_cannot_be_reached_is_a_tool_error(client):
    call = CatalogCall(
        "pmaxtp fetch", {"latitude": 52.23, "longitude": 21.01, "method": "POT"}
    )

    with replay_http() as requested, pytest.raises(ToolError) as caught:
        client.run(call)

    assert requested  # it tried the endpoint and found no answer
    assert caught.value.tool_code == "source_unavailable"
    assert caught.value.call == call


def test_check_returns_the_plan_of_an_offline_check_twin(client, tmp_path):
    call = replace(EXPORT, options={**EXPORT.options, "path": str(tmp_path / "x.csv")})

    document = client.check(call)

    assert document["check"] is True
    assert document["result"]["schema"] == "imgw-plan/1"


def test_query_runs_read_only_commands_and_refuses_the_rest(client):
    document = client.query(CatalogCall("store info", {}))

    assert document["result"]["supported"] is True
    for command in ("store init", "store sync", "series export"):
        with pytest.raises(ToolError) as caught:
            client.query(CatalogCall(command, {}))
        assert caught.value.tool_code == "not_read_only"


class _Failing:
    """A stand-in tool entry point that raises what the tool or the system would."""

    def __init__(self, real: Any, error: Exception) -> None:
        self.real = real
        self.error = error

    def __getattr__(self, name: str) -> Any:
        return getattr(self.real, name)

    def run_command(self, *args: Any, **kwargs: Any) -> Any:
        raise self.error


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            imgwtools.IMGWStoreConflictError(
                "brak dowiązań twardych", details={"reason": "not_atomic"}
            ),
            "store_write_unsupported",
        ),
        (imgwtools.IMGWStoreConflictError("kolizja wersji"), "conflict"),
        (imgwtools.IMGWDataError("zły plik"), "data_error"),
        (PermissionError(13, "Permission denied", "/magazyn"), "io_error"),
        (RuntimeError("błąd w narzędziu"), "internal_error"),
    ],
)
def test_the_tools_exceptions_become_tool_errors_with_a_code(client, error, code):
    client._imgw = _Failing(client._imgw, error)
    call = CatalogCall("store init", {})

    with pytest.raises(ToolError) as caught:
        client.run(call)

    assert caught.value.tool_code == code
    assert caught.value.__cause__ is error


def test_units_a_command_could_not_handle_are_listed_as_failures():
    sync = {
        "result": {
            "items": [
                {"slot": "archive:a", "status": "created", "error": None},
                {
                    "slot": "archive:b",
                    "status": "failed",
                    "error": "HTTP 500",
                    "error_code": "source_unavailable",
                },
                {"slot": "archive:c", "status": "stale_plan", "error": "zmienione"},
            ],
            "series": [{"status": "failed", "problems": ["brak archiwów"]}],
        }
    }
    download = {
        "result": {
            "items": [
                {"slot": "archive:x", "status": "not_published", "error": "nie ma"},
                {"slot": "archive:y", "status": "downloaded", "path": "/o/y.zip"},
            ]
        }
    }
    project = {"result": {"tasks": {"a": "current", "b": "failed"}, "files": []}}
    catalog = {"result": {"status": "failed", "problems": ["lista niedostępna"]}}

    failures = IMGWToolsClient._failures
    assert [
        (f.unit, f.kind, f.detail) for f in failures("store sync", "partial", sync)
    ] == [
        ("archive:b", "source_unavailable", "HTTP 500"),
        ("archive:c", "stale_plan", "zmienione"),
        ("series", "failed", "brak archiwów"),
    ]
    # An archive the source does not publish is not a failure
    assert failures("datasets download", "ok", download) == ()
    assert [f.unit for f in failures("project download", "partial", project)] == ["b"]
    assert [
        (f.unit, f.detail) for f in failures("store catalog", "failed", catalog)
    ] == [("store catalog", "lista niedostępna")]


def test_the_files_a_download_wrote_are_reported_with_their_checksums(tmp_path):
    archive = tmp_path / "codz_2020_01.zip"
    archive.write_bytes(b"PK\x03\x04 zip")
    document = {
        "result": {
            "items": [
                {"status": "downloaded", "path": str(archive)},
                {"status": "not_published", "path": None},
            ]
        }
    }

    files = IMGWToolsClient._files("datasets download", {}, document)

    assert [(f.path, f.status) for f in files] == [(archive, "downloaded")]
    assert files[0].sha256 == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_the_reference_directory_is_exported_before_the_tool_is_imported(tmp_path):
    settings = settings_for(tmp_path)

    create_client(settings)

    assert os.environ["IMGW_DATA_DIR"] == settings["reference_data_dir"]


def test_a_client_needs_the_reference_directory_and_a_store_to_work(tmp_path):
    with pytest.raises(RetmanError, match="reference_data_dir"):
        IMGWToolsClient({"store_dir": str(tmp_path)})

    client = IMGWToolsClient({"reference_data_dir": str(tmp_path)})
    with pytest.raises(RetmanError, match="store_dir"):
        client.validate(CatalogCall("store info", {}))

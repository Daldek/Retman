"""The IMGWTools client against the real tool, offline.

The store is the tool's own fixture store, the network is a replayed answer or
nothing: what these tests pin is the contract the rest of Retman relies on —
what ``lookup`` may do, how the tool's errors become ``ToolError``, what a
``ToolRun`` holds, and that ``root`` and ``IMGW_REFERENCE_DIR`` come from the
``[retman.tools.imgwtools]`` settings.
"""

import hashlib
import io
import os
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import imgwtools
import pytest
from imgw_support import (
    PMAXTP_URL,
    copy_store,
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
PHENOMENA_URL = (
    "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/"
    "dane_hydrologiczne/dobowe/2020/zjaw_2020.zip"
)
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
    assert "outside Poland" in caught.value.detail


def test_a_rejected_option_value_lists_what_the_tool_allows(client):
    call = CatalogCall(
        "pmaxtp fetch", {"latitude": 52.0, "longitude": 21.0, "method": "XYZ"}
    )

    with pytest.raises(ToolError) as caught:
        client.validate(call)

    assert caught.value.option == "method"
    assert caught.value.allowed == ("POT", "AMP")


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
    call = replace(EXPORT, options={**EXPORT.options, "output": str(target)})

    run = client.run(call)

    assert run.status == "ok" and run.schema == "imgw-result/1"
    (file,) = run.files
    assert file.path == target
    assert file.sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    assert file.status == "written"
    assert run.failed == ()
    assert [(n.level, n.code) for n in run.notices] == [("info", "license_terms")]
    assert run.document["result"]["output"] == str(target)
    assert run.command_line.startswith(f"imgw series export --root {fixture_store()}")
    assert f"--output {target}" in run.command_line


def test_a_stream_command_without_a_target_file_is_refused_before_it_runs(client):
    with pytest.raises(ToolError) as caught:
        client.run(EXPORT)

    assert caught.value.tool_code == "validation_error"
    assert caught.value.option == "output"


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


def test_check_plans_the_target_of_an_export_as_write_or_conflict(client, tmp_path):
    target = tmp_path / "x.csv"
    call = replace(EXPORT, options={**EXPORT.options, "output": str(target)})

    new = client.check(call)
    target.write_text("taken")
    taken = client.check(call)

    assert new["check"] is True and new["result"]["schema"] == "imgw-plan/1"
    assert [(a["action"], a["path"]) for a in new["result"]["actions"]] == [
        ("write", str(target))
    ]
    # A plan that lists a conflict is still an answer; only the run refuses
    assert taken["status"] == "ok"
    assert [(a["action"], a["reason"]) for a in taken["result"]["actions"]] == [
        ("conflict", "output_exists")
    ]


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
                {"slot": "archive:a", "status": "new", "error": None},
                {
                    "slot": "archive:b",
                    "status": "failed",
                    "error": "HTTP error 500",
                    "error_code": "source_unavailable",
                },
                {"slot": "archive:c", "status": "stale_plan", "error": "changed"},
            ],
            "series": [{"status": "failed", "problems": ["no archives"]}],
        }
    }
    download = {
        "result": {
            "items": [
                {"slot": "archive:x", "status": "not_published", "error": "gone"},
                {"slot": "archive:y", "status": "downloaded", "path": "/o/y.zip"},
            ]
        }
    }
    catalog = {"result": {"status": "failed", "problems": ["list unavailable"]}}

    failures = IMGWToolsClient._failures
    assert [
        (f.unit, f.kind, f.detail) for f in failures("store sync", "partial", sync)
    ] == [
        ("archive:b", "source_unavailable", "HTTP error 500"),
        ("archive:c", "stale_plan", "changed"),
        ("series", "failed", "no archives"),
    ]
    # An archive the source does not publish is not a failure
    assert failures("datasets download", "ok", download) == ()
    assert [
        (f.unit, f.detail) for f in failures("store catalog", "failed", catalog)
    ] == [("store catalog", "list unavailable")]


def test_a_download_to_plain_files_gets_no_store_root_and_a_sync_gets_one(client):
    dataset = "pl.imgw.hydro_daily"
    download = CatalogCall(
        "datasets download", {"dataset": dataset, "years": [2020], "output_dir": "/out"}
    )
    sync = CatalogCall("store sync", {"datasets": [dataset], "years": [2020]})

    plain = client.command_line(download)
    stored = client.command_line(sync)

    # The tool refuses both targets in one call; a call that names no directory
    # writes the store
    assert "--output-dir /out" in plain and "--root" not in plain
    assert f"--root {fixture_store()}" in stored


def test_a_download_writes_plain_files_and_reports_them_with_the_tools_checksums(
    client, tmp_path
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("zjaw_2020.csv", "1;2;3\n")
    payload = buffer.getvalue()
    answer = {"url": PHENOMENA_URL, "content": payload}
    out = tmp_path / "out"
    call = CatalogCall(
        "datasets download",
        {"dataset": "pl.imgw.hydro_phenomena", "years": [2020], "output_dir": str(out)},
    )

    # The store takes no phenomena archives: a plain download is the only way
    with replay_http(answer) as requested:
        run = client.run(call)

    written = out / "dane_hydrologiczne" / "dobowe" / "2020" / "zjaw_2020.zip"
    assert requested == [PHENOMENA_URL]
    assert run.status == "ok" and run.failed == ()
    assert [(file.path, file.status) for file in run.files] == [(written, "written")]
    # The checksum comes from the tool, which computed it while it wrote the file
    assert run.files[0].sha256 == hashlib.sha256(written.read_bytes()).hexdigest()
    assert run.files[0].sha256 == hashlib.sha256(payload).hexdigest()
    result = run.document["result"]
    assert (result["mode"], result["output_dir"], result["root"]) == (
        "plain",
        str(out),
        None,
    )
    assert f"--output-dir {out}" in run.command_line
    assert "--root" not in run.command_line
    # The tool's staging folder is removed after the run
    assert [path.name for path in out.iterdir()] == ["dane_hydrologiczne"]


def test_a_download_into_a_store_is_refused_by_its_directory_before_any_request(
    client, tmp_path
):
    folder = copy_store(tmp_path) / "results" / "1_download"
    call = CatalogCall(
        "datasets download",
        {
            "dataset": "pl.imgw.hydro_phenomena",
            "years": [2020],
            "output_dir": str(folder),
        },
    )

    with replay_http() as requested, pytest.raises(ToolError) as caught:
        client.run(call)

    assert (caught.value.code, caught.value.details["reason"]) == (
        "conflict",
        "output_in_store",
    )
    # The directory is named once, not each file that the download would have written
    assert caught.value.details["tool_details"]["paths"] == [str(folder)]
    assert requested == [] and not folder.exists()


def test_the_reference_directory_is_exported_before_the_tool_is_imported(tmp_path):
    settings = settings_for(tmp_path)

    create_client(settings)

    assert os.environ["IMGW_REFERENCE_DIR"] == settings["reference_data_dir"]


def test_a_client_needs_the_reference_directory_and_a_store_to_work(tmp_path):
    with pytest.raises(RetmanError, match="reference_data_dir"):
        IMGWToolsClient({"store_dir": str(tmp_path)})

    client = IMGWToolsClient({"reference_data_dir": str(tmp_path)})
    with pytest.raises(RetmanError, match="store_dir"):
        client.validate(CatalogCall("store info", {}))

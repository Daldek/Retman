"""Call builders of the archive operations: golden calls, the tool's own validation."""

from pathlib import Path
from typing import Any

import pytest
from imgw_ops_support import PROJECT, STORE, YEARS, context, operations, station
from imgw_support import fixture_store, real_client

from retman.adapters.catalog import CatalogCall, ToolError, route_error
from retman.testing import FakeToolClient
from retman.tools.imgwtools import calls_archives as calls

LIST = {"type": "year_list", "years": [2010, 2012, 2015]}
CZ_HYDRO = station("0-203-1-001000", "CHMI")
CZ_METEO = station("0-203-0-11514", "CHMI", "meteo")


def build(builder: Any, operation: str, params: dict[str, Any], **kw: Any) -> Any:
    return builder(params, context(operation, FakeToolClient(), **kw))


@pytest.mark.parametrize(
    ("dataset", "extra", "options"),
    [
        ("pl_hydro_daily", {"years": YEARS}, {"years": [2000, 2001, 2002]}),
        ("pl_hydro_daily", {"years": LIST}, {"years": [2010, 2012, 2015]}),
        (
            "pl_hydro_semiannual",
            {"years": LIST, "hydro_params": "h"},
            {"years": [2010, 2012, 2015], "params": ["H"]},
        ),
        # "all" is the tool's default: nothing is passed
        (
            "pl_hydro_semiannual",
            {"years": YEARS, "hydro_params": "all"},
            {"years": [2000, 2001, 2002]},
        ),
        (
            "cz_hydro_daily",
            {"years": YEARS, "stations": [CZ_HYDRO]},
            {"years": [2000, 2001, 2002], "stations": ["0-203-1-001000"]},
        ),
        ("pl_hydro_phenomena", {"years": YEARS}, {"years": [2000, 2001, 2002]}),
    ],
)
def test_hydro_download_names_the_dataset_years_and_parameters_as_the_tool_does(
    tmp_path: Path, dataset: str, extra: dict[str, Any], options: dict[str, Any]
) -> None:
    params = {"dataset": dataset, **extra}
    tool_key = operations()["download_hydro_archives"].parameter("dataset")[
        "tool_values"
    ][dataset]  # type: ignore[index]

    (planned,) = build(calls.download_hydro_archives, "download_hydro_archives", params)
    (running,) = build(
        calls.download_hydro_archives,
        "download_hydro_archives",
        params,
        output_dir=tmp_path,
    )

    assert planned == CatalogCall(
        "datasets download",
        {"dataset": tool_key, **options, "output_dir": str(PROJECT)},
        kind="imgw_archive",
        params={"params": "hydro_params"},
    )
    # The result folder exists only while the operation runs; until then the project
    # folder stands in, so that the tool validates a download of plain files (given
    # no directory it writes the store, which takes only some of the datasets)
    assert running.options == {**planned.options, "output_dir": str(tmp_path)}


def test_the_whole_history_dataset_of_czechia_takes_stations_and_no_years() -> None:
    params = {"dataset": "cz_meteo_daily", "stations": [CZ_METEO]}

    (call,) = build(calls.download_meteo_archives, "download_meteo_archives", params)

    assert call.options == {
        "dataset": "cz.chmi.meteo_daily",
        "stations": ["0-203-0-11514"],
        "output_dir": str(PROJECT),
    }


def test_store_check_writes_its_plan_into_the_result_and_sync_builds_series(
    tmp_path: Path,
) -> None:
    params = {"dataset": "pl_meteo_precip_daily", "years": YEARS}

    (planned,) = build(calls.check_imgw_archives, "check_imgw_archives", params)
    (check,) = build(
        calls.check_imgw_archives, "check_imgw_archives", params, output_dir=tmp_path
    )
    (sync,) = build(calls.sync_imgw_store, "sync_imgw_store", params)

    selection = {
        "datasets": ["pl.imgw.meteo_precip_daily"],
        "years": [2000, 2001, 2002],
    }
    assert planned.options == selection and planned.kind == "imgw_plan"
    assert check.options == {**selection, "plan": str(tmp_path / "plan.json")}
    assert sync.options == {**selection, "series": True} and sync.kind is None
    # A rejected dataset goes back to the "dataset" parameter, not to "datasets"
    assert planned.params == sync.params == {"datasets": "dataset"}


def test_sync_by_plan_hands_the_workspace_plan_to_the_tool(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"

    (call,) = build(
        calls.sync_imgw_store_by_plan,
        "sync_imgw_store_by_plan",
        {},
        inputs={"plan": plan},
    )

    assert call == CatalogCall("store sync", {"plan": str(plan)})


def test_the_tool_accepts_every_dataset_it_is_offered(tmp_path: Path) -> None:
    client = real_client(tmp_path, tmp_path / "unused-store")
    hydro = operations()["download_hydro_archives"].parameter("dataset")["options"]  # type: ignore[index]
    meteo = operations()["download_meteo_archives"].parameter("dataset")["options"]  # type: ignore[index]

    for kind, builder, keys in (
        ("hydro", calls.download_hydro_archives, hydro),
        ("meteo", calls.download_meteo_archives, meteo),
    ):
        for key in keys:
            params: dict[str, Any] = {"dataset": key}
            if not key.startswith("cz_meteo"):
                params["years"] = {"type": "years", "first": 2020, "last": 2020}
            if key.startswith("cz_"):
                params["stations"] = [CZ_HYDRO if kind == "hydro" else CZ_METEO]
            if key == "pl_hydro_semiannual":
                params["hydro_params"] = "q"
            ctx = context(f"download_{kind}_archives", client)
            for call in builder(params, ctx):
                client.validate(call)
    # The store commands take the series datasets; the plan target may be any file
    for key in operations()["sync_imgw_store"].parameter("dataset")["options"]:  # type: ignore[index]
        params = {
            "dataset": key,
            "years": {"type": "years", "first": 2020, "last": 2020},
        }
        if key == "cz_meteo_daily":
            del params["years"]
        if key.startswith("cz_"):
            params["stations"] = [CZ_HYDRO if "hydro" in key else CZ_METEO]
        for builder, name in (
            (calls.check_imgw_archives, "check_imgw_archives"),
            (calls.sync_imgw_store, "sync_imgw_store"),
        ):
            for call in builder(params, context(name, client)):
                client.validate(call)


def test_years_before_the_dataset_begins_are_routed_back_to_the_years(
    tmp_path: Path,
) -> None:
    client = real_client(tmp_path, tmp_path / "unused-store")
    params = {
        "dataset": "pl_hydro_daily",
        "years": {"type": "years", "first": 1900, "last": 1901},
    }
    ctx = context("sync_imgw_store", client)

    (call,) = calls.sync_imgw_store(params, ctx)
    with pytest.raises(ToolError) as caught:
        client.validate(call)

    names = [param["name"] for param in operations()["sync_imgw_store"].spec["params"]]
    assert route_error(call, caught.value, names) == ["years"]


def test_the_current_version_is_the_one_the_tool_calls_current() -> None:
    """The newest ``Last-Modified`` wins: mirrored from the tool, checked against it."""
    from imgwtools.store import current_version

    store = fixture_store()
    client = real_client(store.parent, store)
    document = client.lookup(CatalogCall("store scan", {"kind": "archive"}))
    items = document["result"]["items"]

    for dataset, years, slot in (
        (
            "pl.imgw.hydro_daily",
            {2024},
            "archive:pl.imgw.hydro_daily:2024/codz_2024.zip",
        ),
        (
            "cz.chmi.hydro_daily",
            {2024},
            "archive:cz.chmi.hydro_daily:H_0-203-1-900001_DQ_2024.json",
        ),
    ):
        (mine,) = [
            archive
            for archive in calls.current_archive_versions(items, dataset, years)
            if archive.slot == slot
        ]
        expected = current_version(store, slot=slot)
        assert expected is not None and expected.version is not None
        assert (store / mine.version).resolve() == expected.version.resolve()


def _entry(slot: str, version: str, **meta: Any) -> dict[str, Any]:
    http = meta.pop("http", None)
    return {
        "kind": "archive",
        "slot": slot,
        "version": version,
        "meta": {
            "dataset_key": "pl.imgw.hydro_daily",
            "downloaded_at": meta.pop("downloaded_at", "2026-10-19T10:00:00Z"),
            "request": {"year": meta.pop("year", 2020)},
            "extra": {"http": http} if http else {},
        },
    }


def test_versions_are_ordered_by_last_modified_then_download_time_then_path() -> None:
    slot = "archive:pl.imgw.hydro_daily:2020/codz_2020_01.zip"
    modified = {"last_modified": "Sat, 17 Oct 2026 12:00:00 GMT"}
    newer = {"last_modified": "Sun, 18 Oct 2026 12:00:00 GMT"}
    items = [
        _entry(
            slot,
            "a/2026-10-17_x/f.zip",
            http=modified,
            downloaded_at="2026-10-20T00:00:00Z",
        ),
        _entry(
            slot,
            "a/2026-10-18_x/f.zip",
            http=newer,
            downloaded_at="2026-10-19T00:00:00Z",
        ),
        # no Last-Modified: the download time stands in for it
        _entry(slot, "a/2026-10-20_x/f.zip", downloaded_at="2026-10-17T06:00:00Z"),
    ]

    (current,) = calls.current_archive_versions(items, "pl.imgw.hydro_daily", {2020})
    assert current.version == "a/2026-10-18_x/f.zip"

    tie = [
        _entry(slot, f"a/{name}/f.zip", downloaded_at="2026-10-19T00:00:00Z")
        for name in ("b", "a")
    ]
    (current,) = calls.current_archive_versions(tie, "pl.imgw.hydro_daily", None)
    assert current.version == "a/b/f.zip"


def test_only_the_selected_dataset_and_years_are_taken_and_names_stay_unique() -> None:
    items = [
        _entry("archive:pl.imgw.hydro_daily:2020/codz_2020_01.zip", "v/1", year=2020),
        _entry("archive:pl.imgw.hydro_daily:2021/codz_2021_01.zip", "v/2", year=2021),
        _entry("archive:pl.imgw.hydro_daily:2019/codz_2020_01.zip", "v/3", year=2020),
    ]
    items.append(
        {
            **_entry("archive:x:1/a.zip", "v/4"),
            "meta": {**items[0]["meta"], "dataset_key": "other"},
        }
    )

    found = calls.current_archive_versions(items, "pl.imgw.hydro_daily", {2020})

    assert [archive.version for archive in found] == ["v/3", "v/1"]
    assert calls.export_names(found, "csv") == [
        "codz_2020_01.csv",
        "codz_2020_01_2.csv",
    ]


def test_export_makes_one_call_per_stored_archive(tmp_path: Path) -> None:
    slot = "archive:pl.imgw.hydro_daily:2020/codz_2020_{n}.zip"
    items = [
        _entry(slot.format(n="01"), "v/1", year=2020),
        _entry(slot.format(n="02"), "v/2", year=2020),
    ]
    client = FakeToolClient(documents={"store scan": {"result": {"items": items}}})
    params = {
        "dataset": "pl_hydro_daily",
        "years": {"type": "years", "first": 2020, "last": 2020},
        "format": "jsonl",
    }

    planned = calls.export_imgw_archive(params, context("export_imgw_archive", client))
    running = calls.export_imgw_archive(
        params, context("export_imgw_archive", client, output_dir=tmp_path)
    )

    assert client.calls[0] == (
        "lookup",
        CatalogCall("store scan", {"kind": "archive", "provider": "IMGW-PIB"}),
    )
    assert [call.options for call in planned] == [
        {"version": "v/1", "format": "jsonl"},
        {"version": "v/2", "format": "jsonl"},
    ]
    assert [call.options["output"] for call in running] == [
        str(tmp_path / "codz_2020_01.jsonl"),
        str(tmp_path / "codz_2020_02.jsonl"),
    ]
    assert {call.kind for call in running} == {"archive_records"}


def test_init_and_inspect_pass_only_what_the_user_chose() -> None:
    client = FakeToolClient()

    (init,) = calls.init_imgw_store({}, context("init_imgw_store", client))
    everything = calls.inspect_imgw_store({}, context("inspect_imgw_store", client))
    chosen = calls.inspect_imgw_store(
        {"kind": "archive", "provider": "chmi"}, context("inspect_imgw_store", client)
    )

    assert init == CatalogCall("store init", {})
    assert [call.options for call in everything] == [{}, {}]
    assert [call.command for call in chosen] == ["store info", "store scan"]
    assert chosen[1].options == {"kind": "archive", "provider": "CHMI"}
    assert STORE.is_absolute()

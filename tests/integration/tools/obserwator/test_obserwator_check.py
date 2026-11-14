"""The availability checks of the Obserwator operations (network step, own consent).

The documents are the tool's own: ``obserwator-plan/1`` plans built from its public
result objects and put into the ``obserwator-result/1`` envelope exactly as the
client does. The checks themselves are run through ``run_check``, the adapter
function the pipeline uses, so the report texts are the user's.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import obserwator
import pytest
from obserwator_support import (
    PlanStatus,
    data_root,
    raw_root,
    real_client,
    replay_http,
    settings_for,
)

from retman.adapters.catalog import PlanClient, PlanView, RunStatus
from retman.adapters.manifest_adapter import run_check
from retman.core.check import CheckReport
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations
from retman.registry.operation import Operation
from retman.testing import FakeToolClient, tool_context
from retman.tools.obserwator import manifest as obserwator_manifest
from retman.tools.obserwator import plans
from retman.tools.obserwator.calls import export_station_series
from retman.tools.obserwator.check import summarize_plan

TEXTS = load_core_texts("pl")
PRECIP = "pl_meteo_precip_daily"
NOON = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def operations() -> dict[str, Operation]:
    return load_operations(
        "pl",
        manifests=[
            (obserwator_manifest.MANIFEST, Path(obserwator_manifest.__file__).parent)
        ],
        version_lookup=lambda _: "3.0.0",
    )


def plan_item(
    month: int, status: PlanStatus, size: int | None = None, error: str | None = None
):
    (archive,) = obserwator.archive_files(
        "pl.imgw.meteo_precip_daily", years=(2001,), months=(month,)
    )
    return obserwator.PlanItem(archive, status, None, None, None, None, size, error)


def plan_document(
    items: list[Any],
    actions: tuple[Any, ...] = (),
    *,
    command: str = "store sync",
    status: RunStatus = "ok",
) -> dict[str, Any]:
    plan = obserwator.StorePlan(
        "obserwator-plan/1", Path("/store"), NOON, tuple(items), {}, actions
    )
    envelope = obserwator.CommandResult(command, True, status, plan, ())
    return envelope.to_json(root=Path("/store"))


def series(**changes: Any) -> dict[str, Any]:
    return {
        "dataset": PRECIP,
        "station": {
            "type": "station",
            "provider": "IMGW-PIB",
            "kind": "meteo",
            "code": "123750000",
            "name": "S",
            "river": None,
            "in_catalog": True,
        },
        "period": {"type": "years", "first": 2001, "last": 2001},
        "year_type": "calendar",
        "data_source": "server",
        **changes,
    }


def check(
    operations: dict[str, Operation],
    operation: str,
    params: dict[str, Any],
    tmp_path: Path,
    client: PlanClient,
    store: Path | None = None,
) -> CheckReport:
    context = tool_context(
        operations[operation],
        client=client,
        settings=settings_for(tmp_path, store),
        project_dir=tmp_path,
    )
    return run_check(operations[operation], params, context, TEXTS)


def test_the_archives_to_fetch_are_counted_with_their_size(operations, tmp_path):
    items = [
        plan_item(1, "current"),
        plan_item(2, "current"),
        plan_item(3, "newer", 2_000_000),
        plan_item(4, "missing", 3_500_000),
    ]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(operations, "export_station_series", series(), tmp_path, client)

    assert report.status == "available"
    assert report.lines == [
        "Do pobrania 2 z 4 plików (5.5 MB); 2 już aktualnych w magazynie."
    ]
    # Exactly the synchronisation the operation would run, asked as a check
    (sync, *_) = export_station_series(
        series(),
        tool_context(operations["export_station_series"], client=client),
    )
    assert client.calls == [("check", sync)]


def test_a_server_that_gave_no_sizes_is_reported_as_such(operations, tmp_path):
    items = [plan_item(1, "missing"), plan_item(2, "current")]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(operations, "export_station_series", series(), tmp_path, client)

    assert report.lines == [
        "Do pobrania 1 z 2 plików (serwer nie podał rozmiaru); 1 już aktualnych "
        "w magazynie."
    ]


def test_files_the_server_does_not_publish_make_the_answer_partial(
    operations, tmp_path
):
    items = [
        plan_item(1, "current"),
        plan_item(2, "unverifiable", error="not published"),
        plan_item(3, "unverifiable", error="no signal from the server"),
    ]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(operations, "export_station_series", series(), tmp_path, client)

    assert report.status == "partial"
    assert report.lines[-1] == "Nieopublikowane u źródła: 1 plików."


@pytest.mark.parametrize(
    ("states", "status"),
    [
        (["current", "check_failed"], "partial"),
        (["check_failed", "check_failed"], "unavailable"),
    ],
)
def test_archives_the_check_could_not_reach_lower_the_status(
    operations, tmp_path, states, status
):
    items = [plan_item(month, state) for month, state in enumerate(states, 1)]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(operations, "export_station_series", series(), tmp_path, client)

    assert report.status == status
    failed = states.count("check_failed")
    assert report.lines[-1] == f"Nie udało się sprawdzić: {failed} plików."


def test_a_cancelled_check_is_unknown(operations, tmp_path):
    document = plan_document([plan_item(1, "current")], status="cancelled")
    client = FakeToolClient(documents={"check:store sync": document})

    report = check(operations, "export_station_series", series(), tmp_path, client)

    assert report.status == "unknown"


def test_the_store_as_the_source_needs_no_network_to_check(operations, tmp_path):
    client = FakeToolClient()

    report = check(
        operations,
        "export_station_series",
        series(data_source="store"),
        tmp_path,
        client,
    )

    assert report.status == "available"
    assert report.lines == ["Dane pochodzą z magazynu; sieć nie jest potrzebna."]
    assert client.calls == []


def test_a_check_of_the_station_catalog_counts_the_reachable_and_new_station_sources(
    operations, tmp_path
):
    hydro, meteo = obserwator.station_source_files(provider="IMGW-PIB")
    items = [
        obserwator.PlanItem(hydro, "newer", None, None, None, None, None, None),
        obserwator.PlanItem(
            meteo, "check_failed", None, None, None, None, None, "HTTP 503"
        ),
    ]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(
        operations,
        "build_obserwator_station_catalog",
        {"provider": "imgw_pib"},
        tmp_path,
        client,
    )

    # The catalog is built offline: only the sync of the station sources is checked
    assert report.status == "partial"
    assert [(item["key"], item["args"]) for item in report.items] == [
        ("sources", {"reachable": "1", "total": "2"}),
        ("sources_to_download", {"to_download": "1", "total": "2"}),
    ]
    assert len(report.lines) == 2
    ((method, call),) = client.calls
    assert (method, call.command) == ("check", "store sync")
    assert dict(call.options) == {
        "datasets": [
            "pl.imgw.hydro_stations",
            "pl.imgw.meteo_stations",
            "pl.imgw.hydro_now",
            "pl.imgw.meteo_now",
        ]
    }


def test_a_check_of_the_station_catalog_with_no_reachable_source_is_unavailable(
    operations, tmp_path
):
    hydro, meteo = obserwator.station_source_files(provider="CHMI")
    items = [
        obserwator.PlanItem(source, "check_failed", None, None, None, None, None, "x")
        for source in (hydro, meteo)
    ]
    client = FakeToolClient(documents={"check:store sync": plan_document(items)})

    report = check(
        operations,
        "build_obserwator_station_catalog",
        {"provider": "chmi"},
        tmp_path,
        client,
    )

    assert report.status == "unavailable"
    assert report.items[0]["args"] == {"reachable": "0", "total": "2"}


def test_a_check_given_only_the_planning_client_cannot_use_the_network(
    operations, tmp_path
):
    client = FakeToolClient(documents={"check:store sync": plan_document([])})
    context = tool_context(
        operations["export_station_series"],
        client=PlanView(client),
        settings=settings_for(tmp_path),
        project_dir=tmp_path,
    )

    report = run_check(operations["export_station_series"], series(), context, TEXTS)

    assert report.status == "unknown"
    assert client.calls == []


@pytest.mark.parametrize(
    ("operation", "params"),
    [
        ("export_station_series", series()),
        ("build_obserwator_station_catalog", {"provider": "imgw_pib"}),
        (
            "sync_obserwator_store",
            {
                "dataset": PRECIP,
                "years": {"type": "years", "first": 2001, "last": 2001},
            },
        ),
    ],
)
def test_a_store_the_tool_refuses_is_the_whole_answer_of_the_check(
    operations, tmp_path, operation, params
):
    store = tmp_path / "other-files"
    for root in (raw_root(store), data_root(store)):
        root.mkdir(parents=True)
        (root / "notes.txt").write_text("not a store", encoding="utf-8")

    # The real tool plans the refusal of the root as its one action (conflict,
    # not_empty), asks the servers for nothing and calls the plan ok
    with replay_http() as requested:
        report = check(
            operations, operation, params, tmp_path, real_client(tmp_path, store), store
        )

    assert requested == []
    assert report.status == "unavailable"
    (item,) = report.items
    assert item["key"] == "store_refused"
    assert "odmówi zapisu" in report.lines[0]
    assert str(raw_root(store)) in report.lines[0]


def test_the_summary_of_a_plan_counts_what_the_checks_need():
    items = [
        plan_item(1, "newer", 10),
        plan_item(2, "missing", 20),
        plan_item(3, "missing"),
        plan_item(4, "current", 99),
        plan_item(5, "unverifiable", error="not published"),
    ]
    # An action of the plan is no archive: it is counted nowhere
    action = obserwator.PlanAction("store catalog", "missing", "no catalog")

    summary = summarize_plan(plan_document(items, (action,)))

    assert (summary.total, summary.to_download, summary.current) == (5, 3, 1)
    assert (summary.unpublished, summary.failed) == (1, 0)
    # Only the archives to fetch count, and only the sizes the server gave
    assert summary.size_bytes == 30
    assert summarize_plan({}).total == 0


def test_the_text_of_an_unpublished_file_is_the_one_of_the_installed_tool():
    # The adapter compares the text of a plan item's error: a tool that words it
    # differently makes every unpublished file a failure
    from obserwator.fetch import UNPUBLISHED

    assert plans.UNPUBLISHED == UNPUBLISHED

"""The command layer's contract: routing, context lookups and the capability split."""

from pathlib import Path

import pytest

from retman.adapters.catalog import (
    CatalogCall,
    NoClient,
    PlanView,
    ToolError,
    ToolNotice,
    create_client,
    notice_warnings,
    route_error,
    run_calls,
)
from retman.exceptions import RetmanError
from retman.testing import FakeToolClient, tool_context

CALL = CatalogCall(
    "elevation download",
    {"sheet": "N-34", "resolution": "1m"},
    params={"sheet": "area", "geometry": "area"},
)
PARAMS = ("area", "resolution", "vertical_crs")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        # A tool option is routed through the call's own map ...
        (ToolError("t", "invalid_input", "x", option="sheet"), ["area"]),
        # ... or, where the names agree, by name; several options keep their order
        (
            ToolError(
                "t", "invalid_input", "x", options=("vertical_crs", "resolution")
            ),
            ["vertical_crs", "resolution"],
        ),
        # An option the operation fixes itself names no parameter: that is drift
        (ToolError("t", "invalid_input", "x", option="product"), []),
        (ToolError("t", "invalid_input", "x"), []),
        # Two options of one parameter route once
        (ToolError("t", "invalid_input", "x", options=("sheet", "geometry")), ["area"]),
    ],
)
def test_route_error_names_the_retman_parameters_a_rejection_concerns(error, expected):
    assert route_error(CALL, error, PARAMS) == expected


def test_context_lookups_read_the_manifest_not_the_tool(operations):
    context = tool_context(operations["fetch_dem"], settings={"store_dir": "/data/d"})

    assert context.tool_value("resolution", "0_5m") == "0.5m"
    # An option without an entry keeps its key; no meta means an empty mapping
    assert context.tool_value("resolution", "1m") == "1m"
    assert context.option_meta("resolution", "1m") == {"cell_m": 1}
    assert context.option_meta("resolution", "5m") == {}
    assert context.store_dir == Path("/data/d")


def test_store_dir_is_required_only_when_asked_for(operations):
    context = tool_context(operations["fetch_dem"], settings={})

    with pytest.raises(RetmanError, match="no store_dir"):
        _ = context.store_dir


def test_planning_code_gets_only_the_offline_half_of_a_client(operations):
    fake = FakeToolClient()
    view = PlanView(fake)
    planning = tool_context(operations["fetch_dem"], client=view)

    # No network verb exists on the object planning code receives (N-12) ...
    assert not any(hasattr(view, verb) for verb in ("run", "check", "query"))
    with pytest.raises(RetmanError, match="only after consent"):
        _ = planning.runner
    # ... while the offline half still reaches the tool
    view.validate(CALL)
    assert fake.calls == [("validate", CALL)]
    assert fake.network_calls == []
    assert tool_context(operations["fetch_dem"], client=fake).runner is fake


def test_a_tool_without_a_client_fails_loudly_on_any_use():
    client = NoClient("hydrolog")

    with pytest.raises(RetmanError, match="hydrolog declares no command client"):
        client.validate(CALL)
    with pytest.raises(RetmanError, match="no command client"):
        client.run(CALL)


def test_client_factory_receives_the_tool_settings_table(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "fixtures"))
    from dummy_tool.client import BUILT

    BUILT.clear()
    settings = {"store_dir": "/data/dummy", "workers": 4}

    client = create_client("dummy_tool.client:create_client", settings)

    assert [settings] == BUILT
    assert isinstance(client, FakeToolClient)


def test_a_context_carries_its_operation_so_a_handler_can_delegate_to_run_calls(
    operations, tmp_path
):
    operation = operations["fetch_dem"]
    client = FakeToolClient()
    context = tool_context(operation, client=client, output_dir=tmp_path)
    params = {
        "area": {"type": "sheet", "code": "N-34-130-D-d-2-4"},
        "resolution": "0_5m",
        "vertical_crs": "evrf2007",
    }

    assert context.operation == operation
    delegate = context.operation
    assert delegate is not None
    output = run_calls(delegate, params, {}, tmp_path, context)

    assert [call.options["resolution"] for _, call in client.network_calls] == ["0.5m"]
    assert output["values"]["resolution"] == "0.5m"
    assert output["tool"]["version"] == operation.version


def test_a_repeated_notice_code_shows_a_few_and_counts_the_rest(operations):
    notices = [ToolNotice("warning", "point_rejected", f"stacja {n}") for n in range(8)]
    notices += [
        ToolNotice("warning", "list_problem", "powtórzony kod"),
        ToolNotice("info", "slow_source", "wolne źródło"),
    ]

    warnings = notice_warnings(operations["fetch_dem"], "dummy_tool", notices)

    texts = [warning["args"].get("text") for warning in warnings]
    assert texts == ["stacja 0", "stacja 1", "stacja 2", None, "powtórzony kod"]
    assert warnings[3] == {
        "key": "tool_notices_more",
        "args": {"tool": "dummy_tool", "code": "point_rejected", "count": "5"},
    }


def test_a_code_at_the_grouping_limit_is_shown_in_full(operations):
    notices = [ToolNotice("warning", "point_rejected", f"stacja {n}") for n in range(5)]

    warnings = notice_warnings(operations["fetch_dem"], "dummy_tool", notices)

    assert [warning["key"] for warning in warnings] == ["tool_notice"] * 5

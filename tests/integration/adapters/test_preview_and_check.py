"""Offline plan review and the availability check, at the adapter boundary."""

import pytest

from retman.adapters.catalog import (
    CatalogCall,
    PlanView,
    ToolDriftError,
    ToolError,
)
from retman.adapters.manifest_adapter import preview_operation, run_check
from retman.i18n.loader import load_core_texts
from retman.testing import FakeToolClient, tool_context

TEXTS = load_core_texts("pl")
SHEET = {"type": "sheet", "code": "N-34-130-D-d-2-4"}
PARAMS = {"area": SHEET, "resolution": "5m", "vertical_crs": "kron86"}


def reject_pair(call: CatalogCall) -> ToolError | None:
    """The tool refuses 5 m with KRON86 and names both options."""
    if call.options["resolution"] == "5m" and call.options["vertical_crs"] == "KRON86":
        return ToolError(
            "dummy_tool",
            "invalid_input",
            "5 m nie ma KRON86",
            options=("resolution", "vertical_crs"),
        )
    return None


def preview(operations, params, validation=None):
    client = FakeToolClient(validation=validation)
    context = tool_context(operations["fetch_dem"], client=PlanView(client))
    return preview_operation(operations["fetch_dem"], params, context, TEXTS), client


def test_rejected_combination_names_every_parameter_the_tool_blames(operations):
    result, client = preview(operations, PARAMS, {"elevation download": reject_pair})

    (problem,) = result.problems
    assert problem.params == ("resolution", "vertical_crs")
    # Retman's text chosen by the error code, with the tool's wording as detail
    assert problem.text == (
        "Narzędzie odrzuca wybór „Rozdzielczość, Układ wysokościowy”: 5 m nie ma KRON86"
    )
    # A plan the tool refuses is not previewed further, and nothing but validation ran
    assert result.rows == [] and result.values == {}
    assert [method for method, _ in client.calls] == ["validate"]


def test_a_rejection_of_the_geometry_layer_goes_back_to_the_area(operations):
    geometry = {"type": "geometry", "path": "/p/z.gpkg", "layer": "dzialki"}

    def refuse_layer(call: CatalogCall) -> ToolError:
        return ToolError("dummy_tool", "invalid_input", "brak warstwy", option="layer")

    result, _ = preview(
        operations,
        {**PARAMS, "area": geometry},
        {"elevation download": refuse_layer},
    )

    assert [problem.params for problem in result.problems] == [("area",)]


def test_a_rejection_naming_no_parameter_is_drift_not_a_question(operations):
    def refuse_product(call: CatalogCall) -> ToolError:
        return ToolError(
            "dummy_tool", "invalid_input", "nieznany produkt", option="product"
        )

    with pytest.raises(ToolDriftError) as caught:
        preview(operations, PARAMS, {"elevation download": refuse_product})

    assert caught.value.code == "internal_error"
    assert caught.value.details["reason"] == "tool_drift"
    assert caught.value.text is not None and "retman doctor" in caught.value.text


def test_accepted_plan_gets_the_operations_rows_values_and_own_problems(operations):
    accepted, client = preview(operations, {**PARAMS, "resolution": "1m"})
    unavailable, _ = preview(
        operations,
        {**PARAMS, "resolution": "1m", "area": {"type": "sheet", "code": "N-34-2-1"}},
    )

    assert accepted.rows == [("Rodzaj obszaru", "sheet")]
    assert accepted.values == {"area_type": "sheet"}
    assert accepted.problems == []
    assert client.network_calls == []
    # The operation's own preview can reject what the tool's validation accepts
    (problem,) = unavailable.problems
    assert problem.params == ("area",)
    assert problem.text == "Arkusz N-34-2-1 nie jest dostępny w usłudze."


def check(operations, client, *, planning=False):
    context = tool_context(
        operations["fetch_dem"], client=PlanView(client) if planning else client
    )
    return run_check(operations["fetch_dem"], PARAMS, context, TEXTS)


def test_check_reports_what_the_tool_says_and_never_changes_the_plan(operations):
    client = FakeToolClient(
        documents={"query:elevation availability": {"complete": True}}
    )

    report = check(operations, client)

    assert report.status == "available"
    assert report.lines == ["Twój wybór: 5m — dostępny"]
    assert report.header.startswith("Sprawdzenie dostępności (dummy_tool 1.2.0, ")
    assert report.header.endswith("): dane dostępne")
    assert client.calls == [
        ("query", CatalogCall("elevation availability", {"resolution": "5m"}))
    ]


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (
            ToolError("dummy_tool", "no_coverage", "brak"),
            "Brak danych dla tego obszaru (brak).",
        ),
        (RuntimeError("serwer nie odpowiada"), "serwer nie odpowiada"),
    ],
)
def test_a_failed_check_is_a_report_not_a_crash(operations, failure, error):
    def fail(call: CatalogCall):
        raise failure

    report = check(
        operations, FakeToolClient(documents={"query:elevation availability": fail})
    )

    assert report.status == "unknown" and report.error == error
    assert report.lines == [f"Sprawdzenie nie powiodło się: {error}"]


def test_interrupting_a_check_is_not_swallowed(operations):
    def interrupt(call: CatalogCall):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        check(
            operations,
            FakeToolClient(documents={"query:elevation availability": interrupt}),
        )


def test_a_check_given_only_the_planning_client_cannot_reach_the_network(operations):
    client = FakeToolClient(
        documents={"query:elevation availability": {"complete": True}}
    )

    report = check(operations, client, planning=True)

    assert report.status == "unknown"
    assert client.calls == []


def blocked_preview(params, ctx):
    """A preview whose only problem needs no answer of the user (a missing store)."""
    return {
        "values": {},
        "rows": [],
        "problems": [{"params": [], "key": "sheet_unavailable", "args": {"code": "X"}}],
    }


def test_a_problem_without_parameters_blocks_the_plan_and_asks_nothing(
    operations, monkeypatch
):
    monkeypatch.setattr("dummy_tool.hooks.preview_fetch_dem", blocked_preview)

    result, _ = preview(operations, PARAMS)

    (problem,) = result.problems
    assert problem.params == ()
    assert problem.text == "Arkusz X nie jest dostępny w usłudze."

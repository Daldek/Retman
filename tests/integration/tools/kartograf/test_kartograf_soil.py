"""The SoilGrids operations: a soil layer and the hydrologic soil groups (HSG).

The real Kartograf validates, plans, downloads and computes in process; only the
SoilGrids WCS is a stub (``kartograf_offline.SoilGrids``), so the documents, the
sidecars and the HSG summary are those of the pinned version.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from kartograf_offline import LOAM, SoilGrids, soilgrids
from kartograf_support import (
    SHEET,
    OfflineClient,
    built_store,
    context,
    geometry,
    operations,
    settings,
)

from retman.adapters.catalog import ToolError, route_error, run_calls
from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.kinds import validate_file
from retman.registry.manifest import HandlerOutput
from retman.testing import FakeDecisionBackend
from retman.tools.kartograf import calls, checks, preview

CLAY = {"property": "clay", "depth": "0_5cm", "stat": "mean", "area": SHEET}
CARBON_STOCK = {
    "property": "organic_carbon",
    "carbon": "ocs",
    "depth": "0_30cm",
    "stat": "q0_5",
    "area": SHEET,
}
HSG = {"depth": "0_5cm", "area": SHEET}


def run(tmp_path: Path, name: str, params: dict[str, Any]) -> HandlerOutput:
    """Run the operation's calls with the real Kartograf into a store of the test."""
    client = OfflineClient(settings(tmp_path))
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(name, client, root=tmp_path, output_dir=output_dir)
    return run_calls(operations()[name], params, {}, output_dir, ctx)


def keys(output: HandlerOutput) -> list[str]:
    return [warning["key"] for warning in output["warnings"]]


def test_a_carbon_stock_asks_kartograf_for_the_measure_the_user_chose() -> None:
    (call,) = calls.download_soil_layer(CARBON_STOCK, context("download_soil_layer"))

    assert call.command == "soil download"
    assert call.options == {
        "property": "ocs",
        "depth": "0-30cm",
        "stat": "Q0.5",
        "sheet": "N-34-130-D-d-2-4",
    }
    assert call.kind == "soil_raster"


def test_a_carbon_stock_at_a_standard_depth_is_asked_again_as_the_depth() -> None:
    params = {**CARBON_STOCK, "depth": "0_5cm"}
    (call,) = calls.download_soil_layer(params, context("download_soil_layer"))

    with pytest.raises(ToolError) as caught:
        OfflineClient({}).validate(call)

    names = [p["name"] for p in operations()["download_soil_layer"].spec["params"]]
    assert route_error(call, caught.value, names) == ["depth"]
    assert caught.value.allowed == ("0-30cm",)


def test_a_soil_layer_lands_in_the_store_with_the_unit_of_its_values(
    tmp_path: Path,
) -> None:
    with soilgrids(SoilGrids(LOAM)) as service:
        output = run(tmp_path, "download_soil_layer", CLAY)

    assert service.layers == [("clay", "0-5cm", "mean")]
    (path,) = output["files"]["soil_raster"]
    assert path.is_relative_to(tmp_path / "store")
    validate_file("soil_raster", path)
    values = output["values"]
    # SoilGrids keeps clay in g/kg: the result says so, and how to get percent
    assert (values["unit"], values["conventional_unit"], values["divisor"]) == (
        "g/kg",
        "%",
        10,
    )
    assert values["edition"] == "2.0"
    assert keys(output) == []


def test_a_masked_soil_layer_is_reported_in_soil_words_not_as_a_cutout(
    tmp_path: Path,
) -> None:
    with soilgrids(SoilGrids({})):
        output = run(tmp_path, "download_soil_layer", CLAY)

    assert keys(output) == ["soil_all_nodata"]


def test_the_hsg_reports_the_share_of_each_group_from_the_summary_of_the_run(
    tmp_path: Path,
) -> None:
    with soilgrids(SoilGrids(LOAM)) as service:
        output = run(tmp_path, "classify_soil_hsg", HSG)

    assert sorted(service.layers) == [
        ("clay", "0-5cm", "mean"),
        ("sand", "0-5cm", "mean"),
        ("silt", "0-5cm", "mean"),
    ]
    (path,) = output["files"]["hsg_raster"]
    validate_file("hsg_raster", path)
    groups = output["values"]["groups"]
    # A loam is group B over the whole area; the client always asks for the summary
    assert groups["B"]["percent"] == 100.0
    assert groups["A"]["percent"] == groups["nodata"]["percent"] == 0.0
    assert groups["B"]["area_ha"] > 0
    assert output["values"]["input_count"] == 3
    (audit,) = output["tool"]["calls"]
    assert "--summary" in audit["command_line"]


def test_an_hsg_without_texture_data_is_a_warning_in_its_own_words(
    tmp_path: Path,
) -> None:
    with soilgrids(SoilGrids({})):
        output = run(tmp_path, "classify_soil_hsg", HSG)

    assert "hsg_all_nodata" in keys(output)
    assert "all_nodata" not in keys(output)
    assert output["values"]["groups"]["nodata"]["percent"] == 100.0


@pytest.mark.parametrize(
    ("name", "params"), [("download_soil_layer", CLAY), ("classify_soil_hsg", HSG)]
)
def test_a_soil_plan_shows_the_envelope_of_a_geometry_file(
    tmp_path: Path, name: str, params: dict[str, Any]
) -> None:
    area = geometry(tmp_path / "project", "zlewnia.gpkg")
    ctx = context(name, OfflineClient(settings(tmp_path)), root=tmp_path)

    output = getattr(preview, name)({**params, "area": area}, ctx)

    assert output["problems"] == []
    assert [row["key"] for row in output["rows"]] == ["envelope"]


@pytest.mark.parametrize(
    ("name", "params"), [("download_soil_layer", CLAY), ("classify_soil_hsg", HSG)]
)
def test_a_soil_plan_into_a_store_without_its_marker_is_blocked(
    tmp_path: Path, name: str, params: dict[str, Any]
) -> None:
    store = built_store(tmp_path / "store").root
    (store / "kartograf-store.json").unlink()
    ctx = context(name, OfflineClient(settings(tmp_path)), root=tmp_path)

    output = getattr(preview, name)(params, ctx)

    assert [(p["key"], p["params"]) for p in output["problems"]] == [
        ("store_no_marker", [])
    ]


def test_the_soil_check_names_the_edition_and_then_what_the_store_holds(
    tmp_path: Path,
) -> None:
    client = OfflineClient(settings(tmp_path))
    ctx = context("download_soil_layer", client, root=tmp_path)

    with soilgrids(SoilGrids(LOAM)) as service:
        before = checks.download_soil_layer(CLAY, ctx)
        run(tmp_path, "download_soil_layer", CLAY)
        after = checks.download_soil_layer(CLAY, ctx)

    assert before["status"] == "available"
    assert before["items"] == [
        {"key": "soil_edition", "args": {"edition": "2.0", "count": "1"}}
    ]
    assert {"key": "in_store", "args": {"count": "1"}} in after["items"]
    # The check fetched nothing: only the run transferred the layer
    assert service.layers == [("clay", "0-5cm", "mean")]


def test_the_hsg_check_says_when_the_stored_groups_are_current(tmp_path: Path) -> None:
    client = OfflineClient(settings(tmp_path))
    ctx = context("classify_soil_hsg", client, root=tmp_path)

    with soilgrids(SoilGrids(LOAM)):
        before = checks.classify_soil_hsg(HSG, ctx)
        run(tmp_path, "classify_soil_hsg", HSG)
        after = checks.classify_soil_hsg(HSG, ctx)

    assert before["items"][0]["args"]["count"] == "3"
    assert "hsg_current" not in [item["key"] for item in before["items"]]
    assert "hsg_current" in [item["key"] for item in after["items"]]


# --- the whole pipeline ------------------------------------------------------


def make_app(tmp_path: Path, rules: dict[str, Any]) -> tuple[Retman, OfflineClient]:
    """A pipeline over the Kartograf operations and an offline client."""
    config = load_config(
        init_config(tmp_path / "config.toml", stores_dir=tmp_path / "stores")
    )
    config = replace(config, collect_commands=False)
    project = tmp_path / "project"
    project.mkdir()
    client = OfflineClient(config.tools["kartograf"])
    app = Retman(
        config,
        # More operations than one question offers: the category comes first
        FakeDecisionBackend({"soil_data": "soil_data", **rules}),
        project,
        operations=operations(),
        clients={"kartograf": client},
    )
    return app, client


def asked(plan: Plan) -> set[str]:
    return {question.name for question in plan.questions}


def number(plan: Plan, name: str, key: str) -> str:
    """The answer that picks option ``key`` of an open question."""
    (question,) = [q for q in plan.questions if q.name == name]
    return str([option.key for option in question.options].index(key) + 1)


def test_organic_carbon_is_a_question_and_a_stock_asks_for_its_depth_again(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_soil_layer": "download_soil_layer",
            "organic_carbon": "organic_carbon",
            "0_5cm": "0_5cm",
            "mean": "mean",
        },
    )

    plan = app.plan(
        "Pobierz węgiel organiczny w glebie 0-5 cm, średnia, dla arkusza "
        "N-34-130-D-d-2-4"
    )

    # Three measures of organic carbon: the command names none of them
    assert asked(plan) == {"carbon"}
    plan = plan.answer("carbon", number(plan, "carbon", "ocs"))
    # The carbon stock exists for 0-30 cm only: Kartograf refuses 0-5 cm
    assert asked(plan) == {"depth"}
    plan = plan.answer("depth", number(plan, "depth", "0_30cm"))
    assert plan.questions == []
    assert client.network == []


def test_the_hsg_is_planned_offline_and_computed_into_the_store(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path, {"classify_soil_hsg": "classify_soil_hsg", "15_30cm": "15_30cm"}
    )

    plan = app.plan(
        "Wyznacz grupy hydrologiczne gleb z głębokości 15-30 cm dla arkusza "
        "N-34-130-D-d-2-4"
    )
    assert plan.questions == []
    assert client.network == []  # the plan and its preview are offline (N-12)

    with soilgrids(SoilGrids(LOAM)):
        result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert [kind for kind, _ in client.network] == ["run"]
    assert result.values["groups"]["B"]["percent"] == 100.0
    (record_path,) = (app.workspace.project_dir / app.config.results_dir).glob(
        "*/result.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    (entry,) = record["files"]["hsg_raster"]
    assert entry["store"] == "kartograf"
    assert Path(entry["path"]).is_relative_to(tmp_path / "stores" / "kartograf")

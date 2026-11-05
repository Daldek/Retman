"""Polish commands planned and run on the real Hydrolog through the whole pipeline.

The decision model is a fake that picks the operation and the choices it is told to;
every number comes from the extractors, the plan is validated and previewed by the real
tool offline, and nothing runs before the user confirms (N-12).
"""

import json
from pathlib import Path

from hydrolog_support import (
    asked,
    earlier_result,
    inflow_network,
    make_app,
    option_number,
    series_file,
    texture_rasters,
    watershed_file,
)


def test_effective_rainfall_is_planned_from_numbers_and_run_after_consent(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path, {"compute_effective_rainfall": "compute_effective_rainfall"}
    )

    plan = app.plan("Oblicz opad efektywny metodą SCS-CN dla CN 72 i opadu 50 mm.")

    assert plan.questions == []
    assert {name: entry.value for name, entry in plan.values.items()} == {
        "cn": 72,
        "rainfall": 50,
        "amc": "normal",
    }
    assert plan.values["amc"].source == "default"
    assert client.network == []
    # The preview let Hydrolog compute the plan offline
    assert [call.command for call in client.lookups] == ["scs effective"]

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert [kind for kind, _ in client.network] == ["run"]
    assert "7.09 mm" in result.summary
    (record_path,) = (app.workspace.project_dir / app.config.results_dir).glob(
        "*/result.json"
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    (entry,) = record["files"]["hydrolog_report"]
    assert Path(entry["path"]).name == "effective_rainfall.json"


def test_a_hydrograph_reads_each_duration_by_its_role(tmp_path: Path) -> None:
    app, client = make_app(
        tmp_path,
        {
            "generate_design_hydrograph": "generate_design_hydrograph",
            "euler_ii": "euler_ii",
        },
    )

    plan = app.plan(
        "Policz hydrogram projektowy dla zlewni 45,3 km², CN 72, czas koncentracji "
        "1,5 h, opad 62 mm w 120 min z krokiem 10 min, hietogram Euler II."
    )

    assert plan.questions == []
    values = {name: entry.value for name, entry in plan.values.items()}
    assert values == {
        "catchment_area": 45.3,
        "cn": 72,
        "concentration_time": 90,
        "hyetograph": "euler_ii",
        "rainfall": 62,
        "duration": 120,
        "time_step": 10,
        "amc": "normal",
    }
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert result.values["peak_discharge_m3s"] > 0


def test_a_hyetograph_without_its_shape_asks_for_it(tmp_path: Path) -> None:
    app, client = make_app(
        tmp_path, {"build_design_hyetograph": "build_design_hyetograph"}
    )

    plan = app.plan("Oblicz hietogram opadu 50 mm trwającego 60 min.")

    assert asked(plan) == {"hyetograph"}
    plan = plan.answer("hyetograph", option_number(plan, "hyetograph", "block"))
    assert plan.questions == []
    assert plan.values["time_step"].value == 5
    assert client.network == []


def test_a_step_longer_than_the_rain_reopens_both(tmp_path: Path) -> None:
    app, client = make_app(
        tmp_path,
        {"build_design_hyetograph": "build_design_hyetograph", "block": "block"},
    )

    plan = app.plan("Hietogram blokowy 30 mm w 20 min z krokiem 30 min.")

    assert asked(plan) == {"duration", "time_step"}
    plan = plan.answer("time_step", "5 min")
    plan = plan.answer("duration", "20 min")
    assert plan.questions == []
    assert client.network == []


def test_a_method_the_watershed_cannot_serve_is_asked_again(tmp_path: Path) -> None:
    app, client = make_app(
        tmp_path,
        {"compute_concentration_time": "compute_concentration_time", "nrcs": "nrcs"},
    )
    watershed_file(
        app.workspace.project_dir, "zlewnia.json", mean_slope_m_per_m=0.05, cn=None
    )

    plan = app.plan(
        "Oblicz czas koncentracji metodą NRCS dla zlewni z pliku zlewnia.json"
    )

    # The watershed has no curve number, which NRCS needs: the method is asked again
    assert asked(plan) == {"method"}
    (question,) = plan.questions
    assert question.error is not None and "cn" in question.error
    plan = plan.answer("method", option_number(plan, "method", "kirpich"))
    assert plan.questions == []
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert result.values["method"] == "kirpich"


def test_flood_quantiles_of_a_series_file_show_its_years_in_the_plan(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path, {"estimate_flood_quantiles": "estimate_flood_quantiles"}
    )
    series_file(app.workspace.project_dir, "przeplywy.csv", years=15)

    plan = app.plan("Oblicz przepływy maksymalne Q1% i Q10% z pliku przeplywy.csv.")

    assert plan.questions == []
    assert plan.values["probability"].value == [0.01, 0.1]
    assert plan.values["distribution"].value == "all"
    assert plan.inputs["series"].value["kind"] == "hydro_series"
    assert ("Maksima roczne", "15 pełnych lat hydrologicznych (2011–2025)") in (
        plan.preview_rows
    )
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert "Q1% " in result.summary and "Q10% " in result.summary


def test_a_morphometry_takes_the_watershed_of_a_file_named_in_the_command(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path, {"compute_watershed_morphometry": "compute_watershed_morphometry"}
    )
    watershed_file(app.workspace.project_dir, "zlewnia.json", area_km2=45.3)

    plan = app.plan("Oblicz parametry morfometryczne zlewni z pliku zlewnia.json.")

    assert plan.questions == []
    assert ("Zlewnia z pliku", "Potok Testowy") in plan.preview_rows
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert result.values["area_km2"] == 45.3
    assert "45.3 km²" in result.summary


def test_soil_groups_take_each_texture_from_the_result_of_its_property(
    tmp_path: Path,
) -> None:
    app, client = make_app(tmp_path, {"classify_soil_groups": "classify_soil_groups"})
    rasters = texture_rasters(app.workspace.project_dir / "soil")
    for number, name in enumerate(("silt", "clay", "sand"), 1):
        earlier_result(app, number, "soil_raster", rasters[name], {"property": name})

    plan = app.plan(
        "Wyznacz grupy HSG z rastrów iłu, piasku i pyłu z wyników #1, #2 i #3."
    )

    # The results are told apart by their property, not by the order of the numbers
    assert plan.questions == []
    assert {name: entry.value["number"] for name, entry in plan.inputs.items()} == {
        "clay": 2,
        "sand": 3,
        "silt": 1,
    }
    assert plan.labels["clay"] == "Raster zawartości iłu"
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert result.values["counts"]["B"] == 2
    assert "A 20%, B 40%, C 20%, D 20%" in result.summary


def test_a_texture_with_two_results_of_its_property_is_asked_by_its_name(
    tmp_path: Path,
) -> None:
    app, client = make_app(tmp_path, {"classify_soil_groups": "classify_soil_groups"})
    rasters = texture_rasters(app.workspace.project_dir / "soil")
    second = texture_rasters(app.workspace.project_dir / "soil_2")
    for number, (name, path) in enumerate(
        [*rasters.items(), ("clay", second["clay"])], 1
    ):
        earlier_result(app, number, "soil_raster", path, {"property": name})

    plan = app.plan("Policz grupy hydrologiczne gleb z rastrów uziarnienia.")

    # Sand and silt have one result each; clay has two, offered by name
    assert asked(plan) == {"clay"}
    (question,) = plan.questions
    assert question.text == (
        "Raster zawartości iłu: którego pliku rodzaju soil_raster użyć?"
    )
    assert [option.value["number"] for option in question.options] == [1, 4]
    plan = plan.answer("clay", "2")
    assert plan.questions == []
    assert plan.inputs["clay"].value["number"] == 4
    assert client.network == []


def test_a_network_and_its_inflows_named_in_the_command_fill_both_inputs(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path, {"route_river_network_inflows": "route_river_network_inflows"}
    )
    inflow_network(app.workspace.project_dir)

    plan = app.plan(
        "Przeprowadź hydrogramy przez sieć z pliku network.json "
        "z dopływami z pliku inflows.csv."
    )

    assert plan.questions == []
    assert plan.inputs["network"].value["kind"] == "hydrolog_network"
    assert plan.inputs["inflows"].value["kind"] == "hydrograph_table"
    assert ("Sieć rzeczna", "Culvert inflow: 5 węzłów, wylot OUT") in (
        plan.preview_rows
    )
    assert [call.command for call in client.lookups] == ["route network"]
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert len(result.files["hydrograph_table"]) == 5
    assert "na wylocie OUT szczyt 0.175 m³/s po 25.0 min" in result.summary

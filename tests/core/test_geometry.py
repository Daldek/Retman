"""A geometry file as an area: layers are listed offline and never guessed."""

import hashlib
import json
from pathlib import Path

import pytest

from retman.core.geometry import GeometryFileError, describe_geometry, geometry_layers
from retman.exceptions import RetmanError

RULES = {"make_dem": "make_dem", "raw": "raw"}
SHAPEFILE_HEADER = (9994).to_bytes(4, "big") + bytes(96)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_layers_are_the_feature_tables_in_file_order(tmp_path, make_gpkg):
    many = make_gpkg(tmp_path / "many.gpkg", "zlewnie", "dzialki")
    none = make_gpkg(tmp_path / "none.gpkg")

    assert geometry_layers(many) == ("zlewnie", "dzialki")
    assert geometry_layers(none) == ()
    # A Shapefile has no layers; it is not even opened
    assert geometry_layers(tmp_path / "absent.shp") == ()


def test_a_file_that_is_not_a_geopackage_is_reported_not_guessed(tmp_path):
    fake = tmp_path / "fake.gpkg"
    fake.write_bytes(b"not a database at all")

    with pytest.raises(GeometryFileError, match="not a database"):
        geometry_layers(fake)


def test_audit_fingerprints_every_file_that_makes_up_the_area(tmp_path, make_gpkg):
    stem = tmp_path / "obszar"
    for extension in (".shp", ".shx", ".dbf", ".prj", ".qix"):
        stem.with_suffix(extension).write_bytes(SHAPEFILE_HEADER + extension.encode())
    gpkg = make_gpkg(tmp_path / "obszar.gpkg", "a")

    shapefile = describe_geometry(stem.with_suffix(".shp"))

    # The members Kartograf reads; an unrelated sibling is not part of the area
    assert shapefile == {
        f"obszar{ext}": sha(stem.with_suffix(ext))
        for ext in (".shp", ".shx", ".dbf", ".prj")
    }
    assert describe_geometry(gpkg) == {"obszar.gpkg": sha(gpkg)}


@pytest.fixture
def project(create_app):
    app = create_app(RULES)
    return app, app.workspace.project_dir


def test_several_layers_are_a_numbered_question_never_the_first_table(
    project, make_gpkg
):
    app, folder = project
    make_gpkg(folder / "many.gpkg", "zlewnie", "dzialki")

    plan = app.plan("NMT z pliku many.gpkg")
    (question,) = plan.questions
    chosen = plan.answer("area", "2")

    assert question.name == "area" and question.type == "choice"
    assert question.text == "Która warstwa pliku many.gpkg wyznacza obszar?"
    assert [option.label for option in question.options] == ["zlewnie", "dzialki"]
    assert "area" not in plan.values
    assert chosen.questions == [] and chosen.values["area"].source == "user"
    assert chosen.values["area"].value == {
        "type": "geometry",
        "path": str(folder / "many.gpkg"),
        "layer": "dzialki",
    }
    assert (
        f"obszar z pliku {folder / 'many.gpkg'}, warstwa „dzialki”" in chosen.summary()
    )


def test_a_shapefile_has_no_layer(project):
    app, folder = project
    (folder / "obszar.shp").write_bytes(SHAPEFILE_HEADER)

    plan = app.plan("NMT z pliku obszar.shp")

    assert plan.values["area"].value["layer"] is None
    assert plan.display["area"] == f"obszar z pliku {folder / 'obszar.shp'}"


def test_a_typed_path_to_a_multi_layer_file_asks_for_the_layer(project, make_gpkg):
    app, folder = project
    make_gpkg(folder / "many.gpkg", "zlewnie", "dzialki")
    plan = app.plan("NMT")

    asked = plan.answer("area", "many.gpkg")

    assert [q.name for q in asked.questions] == ["area"]
    assert asked.questions[0].type == "choice" and "area" not in asked.values
    assert asked.answer("area", "1").values["area"].value["layer"] == "zlewnie"


def test_an_unreadable_geopackage_is_asked_about_with_the_reason(project):
    app, folder = project
    (folder / "broken.gpkg").write_bytes(b"SQLite format 3\x00 but nothing else")

    plan = app.plan("NMT z pliku broken.gpkg")

    (question,) = plan.questions
    assert question.name == "area"
    assert (
        question.error is not None
        and "Nie można odczytać pliku geometrii" in question.error
    )


def test_changing_the_area_forgets_the_layer(project, make_gpkg):
    app, folder = project
    make_gpkg(folder / "many.gpkg", "zlewnie", "dzialki")
    plan = app.plan("NMT z pliku many.gpkg").answer("area", "2")

    reopened = plan.change("area")
    asked_again = reopened.answer("area", "many.gpkg")

    assert [q.name for q in reopened.questions] == ["area"]
    assert "area" not in reopened.values
    assert [q.name for q in asked_again.questions] == ["area"]  # the layer, again


def test_known_area_must_name_its_layer_and_it_must_exist(project, make_gpkg):
    app, folder = project
    many = make_gpkg(folder / "many.gpkg", "zlewnie", "dzialki")
    area = {"type": "geometry", "path": str(many)}

    # A fixed value is never asked about: a missing layer is an error ...
    with pytest.raises(RetmanError, match="ma kilka warstw"):
        app.plan("NMT", known={"area": area})
    with pytest.raises(RetmanError, match="nie ma warstwy „mokradla”"):
        app.plan("NMT", known={"area": {**area, "layer": "mokradla"}})
    # ... and an explicit one is used as given
    plan = app.plan("NMT", known={"area": {**area, "layer": "dzialki"}})
    assert plan.values["area"].value["layer"] == "dzialki"


def test_audit_and_collection_keep_files_and_layer_without_local_paths(
    project, make_gpkg
):
    app, folder = project
    many = make_gpkg(folder / "many.gpkg", "zlewnie", "dzialki")
    plan = app.plan("NMT z pliku many.gpkg").answer("area", "1")

    result = app.execute(plan.confirm())
    saved = json.loads(
        (
            app.workspace.root / f"{result.number:03d}_make_dem" / "result.json"
        ).read_text()
    )
    plan_event = next(e for e in app.journal.entries() if e["event"] == "plan")

    # The checksum of the file the tool read is part of the record
    assert saved["params"]["area"]["files"] == {"many.gpkg": sha(many)}
    assert saved["params"]["area"]["value"]["layer"] == "zlewnie"
    # The journal keeps the file name and the layer, not the folder
    assert plan_event["values"]["area"]["value"] == {
        "type": "geometry",
        "path": "many.gpkg",
        "layer": "zlewnie",
    }

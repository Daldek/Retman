"""Commands that name a geometry file are evaluated against a placeholder file."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from retman.config import init_config, load_config
from retman.core.geometry import geometry_layers
from retman.eval.dataset import EvalCommand
from retman.eval.placeholders import (
    create_geometry_files,
    write_geopackage,
    write_shapefile,
)
from retman.eval.runner import run_evaluation
from retman.kinds import validate_file
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend


@pytest.fixture
def context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    monkeypatch.syspath_prepend(str(fixtures))
    from dummy_tool.manifest import MANIFEST

    operations = load_operations(
        "pl",
        manifests=[(MANIFEST, fixtures / "dummy_tool")],
        version_lookup=lambda _: "1.2.0",
    )
    config = load_config(init_config(tmp_path / "config.toml"))
    return replace(config, collect_commands=False), operations


def test_placeholders_pass_retmans_own_checks_of_an_area_file(tmp_path: Path) -> None:
    write_shapefile(tmp_path / "granica.shp")
    write_geopackage(tmp_path / "zlewnia.gpkg")

    validate_file("area_geometry", tmp_path / "granica.shp")
    validate_file("area_geometry", tmp_path / "zlewnia.gpkg")
    assert geometry_layers(tmp_path / "zlewnia.gpkg") == ("obszar",)
    with closing(sqlite3.connect(tmp_path / "zlewnia.gpkg")) as database:
        assert database.execute("PRAGMA application_id").fetchone() == (0x47504B47,)
    assert {path.suffix for path in tmp_path.glob("granica.*")} == {
        ".shp",
        ".shx",
        ".dbf",
        ".prj",
    }


@pytest.mark.parametrize("name", ["granica.shp", "zlewnia.gpkg"])
def test_placeholders_are_real_geometry_to_kartograf(tmp_path: Path, name: str) -> None:
    """Kartograf's offline checks read the file as the run would; none must fail."""
    kartograf = pytest.importorskip("kartograf")
    path = tmp_path / name
    (write_shapefile if name.endswith(".shp") else write_geopackage)(path)
    layer = {} if name.endswith(".shp") else {"layer": "obszar"}

    box = kartograf.get_overall_bbox(path, layer.get("layer"))
    kartograf.validate_command(
        "elevation download",
        {
            "product": "nmt",
            "geometry": str(path),
            "country": "pl",
            "cutout": True,
            "horizontal_crs": "EPSG:2180",
            "vertical_crs": "EVRF2007",
            **layer,
        },
    )
    kartograf.validate_command(
        "landcover download",
        {"product": "bdot10k", "geometry": str(path), "format": "GPKG", **layer},
    )

    assert (box.min_x, box.min_y, box.max_x, box.max_y) == (
        530000.0,
        382000.0,
        532000.0,
        384000.0,
    )


def test_a_command_gets_a_file_only_where_it_names_one_inside_the_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    kept = project / "obszar.shp"
    kept.write_bytes(b"the user's own file")

    created = create_geometry_files(
        "NMT dla granica.shp, zlewnia.gpkg, ../poza.shp, obszar.shp i dane.geojson",
        project,
    )

    assert sorted(path.name for path in created) == ["granica.shp", "zlewnia.gpkg"]
    assert kept.read_bytes() == b"the user's own file"
    assert not (tmp_path / "poza.shp").exists()
    assert not (project / "dane.geojson").exists()


def test_a_command_naming_a_file_is_planned_with_that_area(
    context: tuple[Any, Any], tmp_path: Path
) -> None:
    config, operations = context
    entry = EvalCommand(
        "geometry-001",
        "Zrób surowy NMT dla obszaru z pliku granica.shp",
        "make_dem",
        {"area": {"type": "geometry", "path": "granica.shp"}, "style": "raw"},
        [],
        ["formal", "complete"],
        None,
    )

    records, _ = run_evaluation(
        [entry],
        config,
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        operations=operations,
        temporary_dir=tmp_path,
    )

    record = records[0]
    # Retman did not ask for the area, and the record holds what the command said
    assert "area" not in record["questions"]
    assert record["values"]["area"] == {
        "value": {"type": "geometry", "path": "granica.shp"},
        "source": "command",
    }
    assert record["outcome"] == "plan"

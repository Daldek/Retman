"""Kartograf through the whole pipeline: plan, offline preview, check, execute.

The real Kartograf validates and looks things up offline; the network and the store
are an ``OfflineClient`` with recorded documents. ``client.network`` must stay empty
until the user has confirmed (N-12): the plan, its questions and its preview are
all offline.
"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import kartograf
import pytest
from kartograf_support import OfflineClient, document, geometry, materialise, operations

from retman.config import init_config, load_config
from retman.core.pipeline import Retman
from retman.core.plan import Plan
from retman.testing import FakeDecisionBackend

AVAILABILITY = Path(__file__).resolve().parents[3] / "fixtures" / "kartograf"


def make_app(
    tmp_path: Path, rules: dict[str, Any], **programmed: Any
) -> tuple[Any, Any]:
    """A pipeline over the Kartograf operations and an offline client."""
    config = load_config(
        init_config(tmp_path / "config.toml", stores_dir=tmp_path / "stores")
    )
    config = replace(config, collect_commands=False)
    project = tmp_path / "project"
    project.mkdir()
    client = OfflineClient(config.tools["kartograf"], **programmed)
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"kartograf": client},
    )
    return app, client


def asked(plan: Plan) -> dict[str, Any]:
    return {question.name: question for question in plan.questions}


def number(plan: Plan, name: str, key: str) -> str:
    """The answer that picks option ``key`` of an open question."""
    return str([option.key for option in asked(plan)[name].options].index(key) + 1)


def test_a_geometry_request_is_validated_and_previewed_before_any_network(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
    )
    geometry(app.workspace.project_dir, "granica.shp")

    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla obszaru z pliku granica.shp")

    assert plan.questions == []
    assert plan.values["area"].value["type"] == "geometry"
    assert dict(plan.preview_rows)["Liczba arkuszy"] == "4 × 1:10000 (PL-1992)"
    assert "Obwiednia obszaru" in dict(plan.preview_rows)
    assert plan.preview_values["sheet_count"] == 4
    assert client.network == []


def test_a_grid_pair_kartograf_refuses_is_asked_again_with_the_reason(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {"download_dem_sheet": "download_dem_sheet", "5m": "5m", "kron86": "kron86"},
    )

    plan = app.plan("Pobierz NMT 5 m KRON86 dla arkusza N-34-130-D-d-2-4")

    # The pair is asked about again: the model's choices are not asked a second time
    assert set(asked(plan)) == {"resolution"}
    assert "EVRF2007" in asked(plan)["resolution"].error
    plan = plan.answer("resolution", number(plan, "resolution", "1m"))
    # 1 m with the KRON86 the command asked for is a pair Kartograf accepts
    assert plan.questions == []
    assert plan.values["vertical_crs"].value == "kron86"
    assert dict(plan.preview_rows)["Liczba arkuszy"] == "1 × 1:10000 (PL-1992)"
    assert client.network == []


def test_an_orthophoto_of_a_geometry_file_asks_for_the_product_and_the_area_again(
    tmp_path: Path,
) -> None:
    app, client = make_app(
        tmp_path,
        {
            "download_sheet_hierarchy": "download_sheet_hierarchy",
            "orthophoto": "orthophoto",
            "scale_10000": "scale_10000",
            "cir": "cir",
        },
    )
    geometry(app.workspace.project_dir, "granica.shp")

    plan = app.plan(
        "Pobierz ortofotomapę CIR w skali 1:10000 dla obszaru z pliku granica.shp"
    )

    assert set(asked(plan)) == {"product", "area"}
    assert "godła arkusza" in asked(plan)["area"].error
    plan = plan.answer("area", "N-34-130-D-d-2")
    assert asked(plan).keys() == {"product"}
    assert client.network == []


def test_the_availability_check_is_a_separate_step_after_its_own_consent(
    tmp_path: Path,
) -> None:
    availability = json.loads(
        (AVAILABILITY / "availability_nmt_sheet.json").read_text("utf-8")
    )
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
        queries={"elevation availability": availability},
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4")

    assert plan.can_check
    assert "GUGiK" in plan.check_notice()
    assert client.network == []  # planning and the notice used no network
    report = app.check(plan.confirm_check())

    assert [method for method, _ in client.network] == ["query"]
    assert report.status == "available"
    assert any("2025" in line for line in report.lines)
    # The report informs; the plan itself still has to be confirmed
    assert not plan.confirmed and plan.checks == [report]


def _only_result(app: Any) -> tuple[Path, dict[str, Any]]:
    (path,) = (app.workspace.project_dir / app.config.results_dir).glob("*/result.json")
    return path.parent, json.loads(path.read_text(encoding="utf-8"))


def test_executed_sheets_stay_in_the_store_and_the_record_names_the_tool_run(
    tmp_path: Path,
) -> None:
    doc = document("sheets_one_of_four", tmp_path / "stores" / "kartograf")
    materialise(doc)
    app, client = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
        runs={"elevation download": doc},
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-139-C-a-3")
    assert client.network == []

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert [method for method, _ in client.network] == ["run"]
    folder, record = _only_result(app)
    (entry,) = record["files"]["dem"]
    assert entry["store"] == "kartograf" and len(entry["sha256"]) == 64
    assert Path(entry["path"]).is_relative_to(tmp_path / "stores" / "kartograf")
    assert record["tool"]["calls"][0]["command"] == "elevation download"
    assert (folder / record["tool"]["calls"][0]["document_file"]).is_file()
    assert record["preview"]["sheet_count"] == 4
    # 1 of 4 sheets: the user is told in words, not only in the record
    assert any("1 z 4" in warning for warning in result.warnings)


def test_a_failed_run_is_a_result_with_retmans_text_of_the_tools_error_code(
    tmp_path: Path,
) -> None:
    doc = document("sheets_none_delivered", tmp_path / "stores" / "kartograf")
    app, _ = make_app(
        tmp_path,
        {
            "download_dem_sheet": "download_dem_sheet",
            "1m": "1m",
            "evrf2007": "evrf2007",
        },
        runs={"elevation download": doc},
    )
    plan = app.plan("Pobierz NMT 1 m EVRF2007 dla arkusza N-34-139-C-a-4")

    result = app.execute(plan.confirm())

    assert not result.ok
    assert result.error_code == "no_coverage"
    assert "GUGiK nie ma danych" in (result.error or "")


def test_an_orthophoto_runs_through_the_provider_and_lands_in_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "stores" / "kartograf"
    sheet = store / "orto" / "pl_1992_cir" / "N-34-139-C-a-3-1.tif"
    sheet.parent.mkdir(parents=True)
    sheet.write_bytes(b"II*\x00" + bytes(12))
    versioned = kartograf.VersionedFile(
        path=sheet,
        status="new",
        label="2025-04-26_1",
        sha256="0" * 64,
        version_path=sheet,
    )
    outcome = kartograf.DownloadResult(
        succeeded=[sheet], files={"N-34-139-C-a-3-1": (versioned,)}
    )

    class Provider:
        def __init__(self, session: Any = None, cache: Any = None, *, color: str):
            self.color = color

    class Manager:
        def __init__(self, output_dir: Path, provider: Any, **_: Any) -> None:
            self.provider = provider

        def download_sheet(self, code: str, **_: Any) -> Any:
            return outcome

    monkeypatch.setattr(kartograf, "GugikOrtoProvider", Provider)
    monkeypatch.setattr(kartograf, "DownloadManager", Manager)
    app, client = make_app(
        tmp_path,
        {
            "download_sheet_hierarchy": "download_sheet_hierarchy",
            "orthophoto": "orthophoto",
            "scale_10000": "scale_10000",
            "cir": "cir",
        },
    )
    plan = app.plan(
        "Pobierz ortofotomapę CIR z arkuszy pod N-34-139-C-a-3 w skali 1:10000"
    )
    assert plan.questions == [], [q.name for q in plan.questions]

    result = app.execute(plan.confirm())

    assert result.ok, result.error
    assert client.network == []  # the provider route does not use the command client
    _, record = _only_result(app)
    (entry,) = record["files"]["orthophoto"]
    assert entry["store"] == "kartograf"
    assert record["tool"]["calls"][0]["options"]["color"] == "CIR"
    assert record["params"]["color"]["value"] == "cir"

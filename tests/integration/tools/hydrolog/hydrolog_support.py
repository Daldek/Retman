"""Helpers of the Hydrolog tool tests (plain functions: a ``conftest.py`` in a
subfolder would clash with ``tests/conftest.py`` under ``mypy tests/``).

The tests run the real Hydrolog in process: it computes offline, so nothing is a stub.
A watershed file is the object ``hydrolog.testing.watershed`` builds (read back by the
real reader of watersheds), a flow series is a daily series in the columns of an
Obserwator series export (``date,year,Q [m3/s],Q_flag,...``), which the data kind
``hydro_series`` holds Retman to, a river network is a document of
``hydrolog.testing`` and the texture rasters are small GeoTIFFs in SoilGrids units.
"""

import csv
import json
import math
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("hydrolog")

from hydrolog.testing import (  # noqa: E402
    build_network_fixture,
    example_network_document,
    watershed,
    write_network_document,
)

from retman.adapters.catalog import CatalogCall, ToolContext, ToolDocument, ToolRun  # noqa: E402
from retman.config import init_config, load_config  # noqa: E402
from retman.core.pipeline import Retman  # noqa: E402
from retman.core.plan import Plan  # noqa: E402
from retman.registry.loader import load_operations  # noqa: E402
from retman.registry.operation import Operation  # noqa: E402
from retman.testing import FakeDecisionBackend, tool_context  # noqa: E402
from retman.tools.hydrolog import client as hydrolog_client  # noqa: E402
from retman.tools.hydrolog.client import HydrologClient  # noqa: E402
from retman.tools.hydrolog.manifest import MANIFEST  # noqa: E402

TOOL_DIR = Path(hydrolog_client.__file__).parent
SERIES_HEADER = [
    "date",
    "year",
    "H [cm]",
    "H_flag",
    "Q [m3/s]",
    "Q_flag",
    "attribution_source",
    "attribution_processed",
]
ATTRIBUTION = [
    "Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej",
    "Dane Instytutu Meteorologii i Gospodarki Wodnej zostały przetworzone",
]


@cache
def operations() -> dict[str, Operation]:
    """The Hydrolog operations as the registry loads them (version 1.0.0.dev0)."""
    return load_operations(
        "pl", manifests=[(MANIFEST, TOOL_DIR)], version_lookup=lambda _: "1.0.0.dev0"
    )


def context(
    name: str,
    client: Any = None,
    *,
    inputs: Mapping[str, Path] | None = None,
    output_dir: Path | None = None,
) -> ToolContext:
    """A ``ToolContext`` of one operation with the real client by default."""
    return tool_context(
        operations()[name],
        client=client if client is not None else HydrologClient({}),
        inputs=inputs,
        output_dir=output_dir,
    )


def watershed_file(folder: Path, name: str = "zlewnia.json", **fields: Any) -> Path:
    """Write a watershed of ``hydrolog.testing`` (a 12 km² catchment, CN 75).

    ``fields`` override its values; ``cn=None`` leaves the curve number out.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    document = watershed(**{"name": "Potok Testowy", **fields})
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def series_file(
    folder: Path,
    name: str = "przeplywy.csv",
    *,
    first_year: int = 2010,
    years: int = 12,
    missing: date | None = None,
    column: str = "Q [m3/s]",
) -> Path:
    """Write the daily flows of complete hydrological years as Obserwator exports them.

    The series runs from 1 November of ``first_year`` for ``years`` hydrological years;
    the day ``missing`` has no value (an empty cell flagged ``missing``), which leaves
    its hydrological year incomplete.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    header = [column if item == "Q [m3/s]" else item for item in SERIES_HEADER]
    day = date(first_year, 11, 1)
    end = date(first_year + years, 10, 31)
    rows: list[list[str]] = []
    index = 0
    while day <= end:
        flow = 12 + 9 * math.sin(index / 47.0) + (index % 113) / 7.0 + day.year % 7
        value = "" if day == missing else f"{flow:.2f}"
        hydrological = day.year + (1 if day.month >= 11 else 0)
        flag = "missing" if not value else "value"
        rows.append(
            [day.isoformat(), str(hydrological), "150.0", "value", value, flag]
            + ATTRIBUTION
        )
        day += timedelta(days=1)
        index += 1
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def rain_network(folder: Path, name: str = "siec.json") -> Path:
    """Write a network whose three subcatchments compute their flows from rain."""
    return write_network_document(folder / name, example_network_document())


def inflow_network(folder: Path) -> tuple[Path, Path]:
    """Write a network whose subcatchments read an inflow table, and the table.

    Two subcatchments (``A`` and ``B``, read from the column ``tributary_B``), the
    Muskingum reach ``R1``, the junction ``J1`` and the outlet ``OUT``.
    """
    fixture = build_network_fixture(folder)
    return fixture.network_file, fixture.inflows_file


# Six cells of clay, sand and silt in g/kg, as SoilGrids keeps them; the last cell has
# no data. Hydrolog counts one cell of group A, two of B, one of C and one of D
TEXTURE = {
    "clay": [[100, 250, 450], [50, 300, -32768]],
    "sand": [[800, 400, 200], [900, 300, -32768]],
    "silt": [[100, 350, 350], [50, 400, -32768]],
}
TEXTURE_COUNTS = {"A": 1, "B": 2, "C": 1, "D": 1, "nodata": 1}


def texture_rasters(folder: Path, nodata_only: bool = False) -> dict[str, Path]:
    """Write the clay, sand and silt rasters of ``TEXTURE`` on one grid (EPSG:4326)."""
    np = pytest.importorskip("numpy")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    folder.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, cells in TEXTURE.items():
        values = np.array(cells, dtype="int16")
        if nodata_only:
            values[:] = -32768
        path = folder / f"{name}_0-5cm_mean.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=values.shape[0],
            width=values.shape[1],
            count=1,
            dtype="int16",
            crs="EPSG:4326",
            transform=from_origin(19.0, 52.0, 0.01, 0.01),
            nodata=-32768,
        ) as target:
            target.write(values, 1)
        paths[name] = path
    return paths


def earlier_result(
    app: Retman, number: int, kind: str, path: Path, values: dict[str, Any]
) -> None:
    """Record a successful earlier result of the project holding ``path`` as ``kind``.

    Only what the workspace reads of a result: its number, state, summary, end time,
    values and files (relative to the project folder).
    """
    folder = app.workspace.root / f"{number:03d}_download_soil_layer"
    folder.mkdir(parents=True)
    record = {
        "ok": True,
        "number": number,
        "operation": "download_soil_layer",
        "summary": f"Warstwa SoilGrids {values.get('property', '')}",
        "values": values,
        "files": {kind: [{"path": str(path.relative_to(app.workspace.project_dir))}]},
        "timing": {"end": "2026-11-04T10:00:00+00:00"},
    }
    (folder / "result.json").write_text(json.dumps(record), encoding="utf-8")


class RecordingClient(HydrologClient):
    """Hydrolog's real client, which remembers every run, check and query.

    ``network`` must stay empty until the user has confirmed (N-12): the plan, its
    questions and its preview use only validation and the offline lookups.
    """

    def __init__(self) -> None:
        super().__init__({})
        self.network: list[tuple[str, CatalogCall]] = []
        self.lookups: list[CatalogCall] = []

    def lookup(self, call: CatalogCall) -> ToolDocument:
        """Compute the command offline and record it."""
        self.lookups.append(call)
        return super().lookup(call)

    def run(self, call: CatalogCall) -> ToolRun:
        """Run the command and record it."""
        self.network.append(("run", call))
        return super().run(call)

    def check(self, call: CatalogCall) -> ToolDocument:
        """Plan the command and record it."""
        self.network.append(("check", call))
        return super().check(call)

    def query(self, call: CatalogCall) -> ToolDocument:
        """Refuse the query and record it."""
        self.network.append(("query", call))
        return super().query(call)


def make_app(tmp_path: Path, rules: dict[str, Any]) -> tuple[Retman, RecordingClient]:
    """A pipeline over the Hydrolog operations and the recording client."""
    config = load_config(
        init_config(tmp_path / "config.toml", stores_dir=tmp_path / "stores")
    )
    config = replace(config, collect_commands=False)
    project = tmp_path / "project"
    project.mkdir()
    client = RecordingClient()
    app = Retman(
        config,
        FakeDecisionBackend(rules),
        project,
        operations=operations(),
        clients={"hydrolog": client},
    )
    return app, client


def asked(plan: Plan) -> set[str]:
    """The names of the open questions of a plan."""
    return {question.name for question in plan.questions}


def option_number(plan: Plan, name: str, key: str) -> str:
    """The answer that picks option ``key`` of an open question."""
    (question,) = [q for q in plan.questions if q.name == name]
    return str([option.key for option in question.options].index(key) + 1)

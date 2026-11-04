"""Helpers of the Hydrolog tool tests (plain functions: a ``conftest.py`` in a
subfolder would clash with ``tests/conftest.py`` under ``mypy tests/``).

The tests run the real Hydrolog in process: it computes offline, so nothing is a stub.
A watershed file is the object ``hydrolog.testing.watershed`` builds (read back by the
real reader of watersheds) and a flow series is a daily series in the columns of an
Obserwator series export (``date,year,Q [m3/s],Q_flag,...``), which the data kind
``hydro_series`` holds Retman to.
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

from hydrolog.testing import watershed  # noqa: E402

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

"""Deliberately opt-in end-to-end evaluation on a real model server."""

from dataclasses import replace
from pathlib import Path

import pytest

from retman.config import Thresholds, init_config, load_config
from retman.eval.dataset import EvalCommand
from retman.eval.report import render_report
from retman.eval.runner import run_evaluation
from retman.i18n.loader import load_core_texts
from retman.registry.loader import load_operations


@pytest.mark.live
def test_live_evaluation_plans_multiple_commands_without_executing(
    pytestconfig: pytest.Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    url = pytestconfig.getoption("--live-openai-url")
    model = pytestconfig.getoption("--live-openai-model")
    if not url or not model:
        pytest.skip("provide --live-openai-url and --live-openai-model")
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    monkeypatch.syspath_prepend(str(fixtures))
    from dummy_tool.manifest import MANIFEST

    operations = load_operations(
        "pl",
        manifests=[(MANIFEST, fixtures / "dummy_tool")],
        version_lookup=lambda _: "1.2.0",
    )
    settings = load_config(init_config(tmp_path / "config.toml"))
    config = replace(
        settings,
        decision=replace(
            settings.decision,
            backend="openai_compatible",
            url=url,
            model=model,
            timeout_s=90,
            confidence="none",
            thresholds=Thresholds(0.8, 0.8),
            consistency_runs=None,
        ),
    )
    entries = [
        EvalCommand(
            "live-1",
            "Zrób NMT dla arkusza N-34-130-D-d-2-4 w stylu surowym",
            "make_dem",
            {"area": {"type": "sheet", "code": "N-34-130-D-d-2-4"}, "style": "raw"},
            [],
            ["complete"],
            None,
        ),
        EvalCommand(
            "live-2",
            "Zrób NMT dla arkusza N-34-130-D-d-2-4",
            "make_dem",
            {"area": {"type": "sheet", "code": "N-34-130-D-d-2-4"}},
            ["style"],
            ["incomplete"],
            None,
        ),
        EvalCommand(
            "live-3",
            "Jaka będzie jutro pogoda?",
            "out_of_scope",
            {},
            [],
            ["out_of_scope"],
            None,
        ),
    ]
    records, summary = run_evaluation(
        entries, config, operations=operations, temporary_dir=tmp_path
    )
    report = render_report(summary, records, load_core_texts("pl"))
    assert [record["id"] for record in records] == [entry.id for entry in entries]
    assert all(record["model_queries"] >= 1 for record in records)
    assert url not in report
    assert summary.runs == len(entries)

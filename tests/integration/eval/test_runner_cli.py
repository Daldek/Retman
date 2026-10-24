"""Command-line exit codes, filtering and successful file outputs."""

import json
from pathlib import Path

import pytest

from retman.backends.base import Decision
from retman.config import config_template
from retman.eval.dataset import DEFAULT_COMMANDS, load_commands
from retman.eval.runner import main
from retman.testing import FakeDecisionBackend


def test_cli_validates_packaged_dataset_filters_and_writes_private_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    secret_url = "https://private.example.invalid/v1"
    config = tmp_path / "config.toml"
    config.write_text(
        config_template().replace("http://127.0.0.1:8000", secret_url), encoding="utf-8"
    )
    raw = tmp_path / "raw.jsonl"
    report = tmp_path / "report.md"
    repeat = 2
    args = [
        "--config",
        str(config),
        "--operations",
        "out_of_scope",
        "--tags",
        "near_miss",
        "--repeat",
        str(repeat),
        "--target-error",
        "0.01",
        "--output",
        str(raw),
        "--report",
        str(report),
    ]
    assert main(args, backend=FakeDecisionBackend()) == 0
    records = [
        json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()
    ]
    # The filters pick the near-miss commands the packaged dataset marks out of scope
    selected = [
        command
        for command in load_commands(DEFAULT_COMMANDS)
        if command.operation == "out_of_scope" and "near_miss" in command.tags
    ]
    assert selected
    assert len(records) == repeat * len(selected)
    assert all(record["outcome"] == "out_of_scope" for record in records)
    assert [record["repeat"] for record in records[:2]] == [0, 1]
    text = report.read_text(encoding="utf-8")
    assert "Stabilność decyzji" in text
    assert "near_miss" in text
    assert not capsys.readouterr().out
    assert secret_url not in raw.read_text(encoding="utf-8") + text
    assert str(tmp_path) not in raw.read_text(encoding="utf-8") + text

    # Above nine operations the model chooses a category first, then the operation
    rules: dict[str, str | Decision] = {
        "spatial_data": "spatial_data",
        "download_dem_sheet": "download_dem_sheet",
    }
    assert main(args, backend=FakeDecisionBackend(rules)) == 4
    assert "Naruszenia W-03" in report.read_text(encoding="utf-8")
    assert any(
        record["outcome"] == "plan"
        for record in (
            json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()
        )
    )


def test_cli_backend_error_does_not_create_partial_report(tmp_path: Path):
    from retman.exceptions import BackendConnectionError

    class FailingBackend(FakeDecisionBackend):
        def choose(self, state: str, question: str, options: dict[str, str]):
            if self.calls:
                raise BackendConnectionError("https://private.example.invalid/v1")
            return super().choose(state, question, options)

    config = tmp_path / "config.toml"
    config.write_text(config_template(), encoding="utf-8")
    commands = tmp_path / "commands.jsonl"
    commands.write_text(
        "".join(
            json.dumps(
                {
                    "id": f"oos-{index}",
                    "command": text,
                    "operation": "out_of_scope",
                    "tags": ["out_of_scope"],
                },
                ensure_ascii=False,
            )
            + "\n"
            for index, text in enumerate(
                ("Jaka będzie pogoda?", "Jaki jest kurs euro?"), 1
            )
        ),
        encoding="utf-8",
    )
    raw = tmp_path / "raw.jsonl"
    report = tmp_path / "report.md"
    assert (
        main(
            [
                "--config",
                str(config),
                "--commands",
                str(commands),
                "--output",
                str(raw),
                "--report",
                str(report),
            ],
            backend=FailingBackend(),
        )
        == 1
    )
    assert not raw.exists()
    assert not report.exists()

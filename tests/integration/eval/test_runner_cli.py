"""``retman eval run``: exit codes, filtering, file outputs and the plan of a write."""

import json
from pathlib import Path

import pytest
from document_schemas import violations
from error_documents import last_line_document

from retman import cli
from retman.backends.base import Decision
from retman.config import config_template
from retman.eval.dataset import DEFAULT_COMMANDS, load_commands
from retman.exceptions import BackendConnectionError
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
        "eval",
        "run",
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
    assert cli.main(args, backend=FakeDecisionBackend()) == 0
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
    # The terminal gets the line that names the report, not the report
    assert capsys.readouterr().out == f"Raport zapisano: {report}\n"
    assert secret_url not in raw.read_text(encoding="utf-8") + text
    assert str(tmp_path) not in raw.read_text(encoding="utf-8") + text

    # Above nine operations the model chooses a category first, then the operation
    rules: dict[str, str | Decision] = {
        "spatial_data": "spatial_data",
        "download_dem_sheet": "download_dem_sheet",
    }
    assert cli.main([*args, "--force"], backend=FakeDecisionBackend(rules)) == 11
    assert "Naruszenia W-03" in report.read_text(encoding="utf-8")
    assert any(
        record["outcome"] == "plan"
        for record in (
            json.loads(line) for line in raw.read_text(encoding="utf-8").splitlines()
        )
    )


def _one_command_set(tmp_path: Path) -> tuple[Path, Path]:
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
    return config, commands


def test_cli_backend_error_does_not_create_partial_report(tmp_path: Path):
    class FailingBackend(FakeDecisionBackend):
        def choose(self, state: str, question: str, options: dict[str, str]):
            if self.calls:
                raise BackendConnectionError("https://private.example.invalid/v1")
            return super().choose(state, question, options)

    config, commands = _one_command_set(tmp_path)
    raw = tmp_path / "raw.jsonl"
    report = tmp_path / "report.md"
    assert (
        cli.main(
            [
                "eval",
                "run",
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
        == 5
    )
    assert not raw.exists()
    assert not report.exists()


def test_cli_existing_files_are_a_conflict_that_lists_every_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config, commands = _one_command_set(tmp_path)
    raw = tmp_path / "raw.jsonl"
    report = tmp_path / "report.md"
    raw.write_text("keep", encoding="utf-8")
    report.write_text("keep", encoding="utf-8")

    status = cli.main(
        [
            "eval",
            "run",
            "--config",
            str(config),
            "--commands",
            str(commands),
            "--output",
            str(raw),
            "--report",
            str(report),
        ],
        backend=FakeDecisionBackend(),
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 4
    assert document["code"] == "conflict"
    assert document["details"]["reason"] == "output_exists"
    assert sorted(document["details"]["paths"]) == sorted([str(raw), str(report)])
    assert (
        raw.read_text(encoding="utf-8") == report.read_text(encoding="utf-8") == "keep"
    )


def test_cli_check_plans_the_two_files_and_runs_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config, commands = _one_command_set(tmp_path)
    raw = tmp_path / "raw.jsonl"
    report = tmp_path / "report.md"
    report.write_text("keep", encoding="utf-8")
    backend = FakeDecisionBackend()

    status = cli.main(
        [
            "eval",
            "run",
            "--config",
            str(config),
            "--commands",
            str(commands),
            "--output",
            str(raw),
            "--report",
            str(report),
            "--check",
            "--json",
        ],
        backend=backend,
    )

    envelope = json.loads(capsys.readouterr().out)
    assert status == 0 and envelope["check"] is True
    assert envelope["result"]["schema"] == "retman-targets/1"
    assert [(t["option"], t["action"]) for t in envelope["result"]["targets"]] == [
        ("output", "write"),
        ("report", "conflict"),
    ]
    assert backend.calls == [] and not raw.exists()
    assert report.read_text(encoding="utf-8") == "keep"


class _PlansTheWeather(FakeDecisionBackend):
    """Plans a download for the command about the weather and refuses the others."""

    def __init__(self) -> None:
        super().__init__()
        self._plans = FakeDecisionBackend(
            {"spatial_data": "spatial_data", "download_dem_sheet": "download_dem_sheet"}
        )

    def choose(self, state: str, question: str, options: dict[str, str]) -> Decision:
        self.calls.append((state, question, dict(options)))
        if "pogoda" in state:
            return self._plans.choose(state, question, options)
        return super().choose(state, question, options)


def test_cli_the_units_of_the_envelope_are_the_commands_to_refuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config, commands = _one_command_set(tmp_path)

    status = cli.main(
        ["eval", "run", "--config", str(config), "--commands", str(commands), "--json"],
        backend=_PlansTheWeather(),
    )

    envelope = json.loads(capsys.readouterr().out)
    assert status == 10 and envelope["status"] == "partial"
    assert [(item["id"], item["status"]) for item in envelope["items"]] == [
        ("oos-1", "failed"),
        ("oos-2", "ok"),
    ]
    failed = envelope["items"][0]
    assert (failed["code"], failed["reason"]) == ("unsupported", "planned_out_of_scope")
    assert envelope["result"]["schema"] == "retman-eval/1"
    assert violations("retman-eval/1", envelope["result"]) == []


def test_cli_when_every_refusal_failed_the_outcome_is_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config, commands = _one_command_set(tmp_path)
    rules: dict[str, str | Decision] = {
        "download_dem_sheet": "download_dem_sheet",
        "spatial_data": "spatial_data",
    }

    status = cli.main(
        ["eval", "run", "--config", str(config), "--commands", str(commands), "--json"],
        backend=FakeDecisionBackend(rules),
    )

    envelope = json.loads(capsys.readouterr().out)
    assert (status, envelope["status"]) == (11, "failed")
    assert {item["status"] for item in envelope["items"]} == {"failed"}

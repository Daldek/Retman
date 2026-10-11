"""CLI conversation, non-interactive safety and project history."""

import io
import json
from pathlib import Path

import pytest

from retman import cli
from retman.backends.base import Decision
from retman.config import init_config
from retman.exceptions import BackendConnectionError
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend

SHEET = "N-34-130-D-d-2-4"


class TerminalInput(io.StringIO):
    """Scripted terminal responses for a deterministic interactive session."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def command_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_dir))
    from dummy_tool.manifest import MANIFEST

    operations = load_operations(
        "pl",
        manifests=[(MANIFEST, fixture_dir / "dummy_tool")],
        version_lookup=lambda _: "1.2.0",
    )
    monkeypatch.setattr("retman.core.pipeline.load_operations", lambda *_: operations)
    config_path = init_config(tmp_path / "settings.toml")
    return ["--config", str(config_path)], tmp_path


def test_main_interactive_question_plan_confirm_result_and_audit(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))

    status = cli.main(
        [*config_args, f"Zrób NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    transcript = capsys.readouterr().out
    result = json.loads(
        (project / "retman-output" / "001_make_dem" / "result.json").read_text()
    )
    events = [
        json.loads(line)
        for line in (project / "retman-output" / "journal.jsonl")
        .read_text()
        .splitlines()
    ]

    assert status == 0
    assert "Jaki styl zapisu" in transcript
    assert "Plan:" in transcript
    assert "Wykonać?" in transcript
    assert "Wynik #1" in transcript
    assert result["ok"] and result["params"]["style"]["source"] == "user"
    assert [record["event"] for record in events] == [
        "command",
        "question",
        "answer",
        "plan",
        "execution",
    ]
    print("TRANSCRIPT:\n" + transcript)
    print("RESULT_JSON:\n" + json.dumps(result, ensure_ascii=False, indent=2))
    print(
        "JOURNAL_JSONL:\n"
        + "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
    )


def test_main_noninteractive_prints_missing_and_never_executes(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO("1\nt\n"))

    status = cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    assert status == 2
    assert "Brakuje:" in capsys.readouterr().out
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_plan_only_shows_complete_plan_without_execution(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        [*config_args, "--plan-only", f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )

    assert status == 0
    assert "Plan:" in capsys.readouterr().out
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_reject_and_cancel_preserve_project_journal(
    command_args, monkeypatch: pytest.MonkeyPatch
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("n\n"))
    backend = FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"})
    rejected = cli.main(
        [*config_args, f"NMT dla {SHEET}"], backend=backend, project_dir=project
    )
    monkeypatch.setattr("sys.stdin", TerminalInput("anuluj\n"))
    cancelled = cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    log = (project / "retman-output" / "journal.jsonl").read_text()

    assert rejected == cancelled == 3
    assert '"status": "rejected"' in log
    assert '"status": "cancelled"' in log
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_results_and_log_read_project_without_model(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))
    cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    capsys.readouterr()

    results_code = cli.main([*config_args, "results"], project_dir=project)
    listed = capsys.readouterr().out
    log_code = cli.main([*config_args, "log"], project_dir=project)
    events = capsys.readouterr().out

    assert results_code == log_code == 0
    assert "#1:" in listed
    assert "wykonanie" in events


def test_main_init_and_missing_config_report_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config = tmp_path / "new.toml"

    failure = cli.main(["--config", str(config), "results"], project_dir=tmp_path)
    missing = capsys.readouterr().err
    created = cli.main(["--config", str(config), "init"], project_dir=tmp_path)

    assert failure == 1 and "retman init" in missing
    assert created == 0 and config.exists()


def test_main_change_option_from_numbered_plan_list(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("?\nz\n2\n2\nt\n"))

    status = cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )
    audit = json.loads(
        (project / "retman-output" / "001_make_dem" / "result.json").read_text()
    )

    assert status == 0
    assert audit["params"]["style"]["value"] == "smooth"
    assert audit["params"]["detail"]["value"] == "high"
    assert (
        '"status": "changed"'
        in (project / "retman-output" / "journal.jsonl").read_text()
    )
    assert "Którą wartość zmienić?" in capsys.readouterr().out


def test_main_session_exits_after_command_and_keeps_result(
    command_args, monkeypatch: pytest.MonkeyPatch
):
    config_args, project = command_args
    monkeypatch.setattr(
        "sys.stdin", TerminalInput(f"Zrób NMT dla {SHEET}\n1\nt\nkoniec\n")
    )

    status = cli.main(
        config_args,
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    assert status == 0
    assert (project / "retman-output" / "001_make_dem" / "dem.asc").exists()


def test_main_explain_shows_actual_decisions_without_execution(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        [*config_args, "--plan-only", "--explain", f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )

    assert status == 0
    assert "Decyzja style: raw, pewność 1.0" in capsys.readouterr().out


def test_main_connection_error_suggests_doctor(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    class DisconnectedBackend(FakeDecisionBackend):
        def choose(
            self, state: str, question: str, options: dict[str, str]
        ) -> Decision:
            raise BackendConnectionError(self.url)

    status = cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=DisconnectedBackend(),
        project_dir=project,
    )

    assert status == 1
    assert "retman doctor" in capsys.readouterr().err

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


@pytest.fixture
def dummy_client(command_args, monkeypatch: pytest.MonkeyPatch):
    """The dummy tool's client module with fresh recorders for this test."""
    import dummy_tool.client as module

    monkeypatch.setattr(module, "BUILT", [])
    monkeypatch.setattr(module, "CLIENTS", [])
    monkeypatch.setattr(module, "PROGRAM", {})
    return module


FETCH_RULES: dict[str, str | Decision] = {
    "fetch_dem": "fetch_dem",
    "1m": "1m",
    "evrf2007": "evrf2007",
}
AVAILABILITY = "query:elevation availability"


def run_fetch(command_args, monkeypatch, keys: str, *flags: str) -> int:
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput(keys))
    return cli.main(
        [*config_args, *flags, f"Pobierz NMT dla {SHEET} 1 m"],
        backend=FakeDecisionBackend(FETCH_RULES),
        project_dir=project,
    )


def journal_events(project: Path) -> list[dict]:
    lines = (project / "retman-output" / "journal.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


def test_main_offers_the_check_only_for_operations_that_have_one(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    run_fetch(command_args, monkeypatch, "n\n")
    with_check = capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", TerminalInput("n\n"))
    cli.main(
        [*config_args, f"NMT dla {SHEET}"],
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )
    without_check = capsys.readouterr().out

    assert "[s]prawdź dostępność (sieć)" in with_check
    assert "Wykonać?" in without_check and "[s]prawdź" not in without_check


def test_main_check_has_its_own_notice_and_consent_then_the_plan_prompt_returns(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    _, project = command_args
    dummy_client.PROGRAM["documents"] = {AVAILABILITY: {"complete": True}}

    status = run_fetch(command_args, monkeypatch, "s\nt\nt\n")
    transcript = capsys.readouterr().out
    (client,) = dummy_client.CLIENTS
    events = journal_events(project)

    assert status == 0
    assert "osobny krok i jedyny, który łączy się z internetem" in transcript
    assert "Połączyć się z internetem i sprawdzić? [t]ak / [n]ie" in transcript
    assert "dane dostępne" in transcript and "Pobrano 0 plik(i)" in transcript
    # The prompt came back after the report, and only then was the plan run
    assert transcript.count("[s]prawdź dostępność (sieć)") == 2
    assert [method for method, _ in client.network_calls] == ["query", "run"]
    assert [e["event"] for e in events] == ["command", "check", "plan", "execution"]
    assert (events[1]["status"], events[1]["result"]) == ("approved", "available")


def test_main_anything_but_yes_declines_the_check_without_network(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    _, project = command_args

    status = run_fetch(command_args, monkeypatch, "s\nn\nn\n")
    transcript = capsys.readouterr().out
    (client,) = dummy_client.CLIENTS

    assert status == 3
    assert "Sprawdzenie pominięte." in transcript and "Plan odrzucony." in transcript
    assert client.network_calls == []
    check = next(e for e in journal_events(project) if e["event"] == "check")
    assert (check["status"], check["result"]) == ("rejected", None)


def test_main_interrupting_the_check_cancels_and_keeps_the_record(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    _, project = command_args

    def interrupt(call):
        raise KeyboardInterrupt

    dummy_client.PROGRAM["documents"] = {AVAILABILITY: interrupt}

    status = run_fetch(command_args, monkeypatch, "s\nt\n")

    assert status == 3 and "Anulowano." in capsys.readouterr().out
    (check,) = [e for e in journal_events(project) if e["event"] == "check"]
    assert check["status"] == "approved" and check["result"] is None


def test_main_plan_only_never_takes_a_network_step(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    status = run_fetch(command_args, monkeypatch, "", "--plan-only")
    (client,) = dummy_client.CLIENTS

    assert status == 0 and "Plan:" in capsys.readouterr().out
    # The tool validated the plan offline; nothing else touched it
    assert [method for method, _ in client.calls] == ["validate"]


def test_main_prints_the_warnings_of_a_result_after_its_summary(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("t\n"))

    status = cli.main(
        [*config_args, "Zrób NMT z ostrzeżeniami"],
        backend=FakeDecisionBackend({"noisy_dem": "noisy_dem"}),
        project_dir=project,
    )
    lines = capsys.readouterr().out.splitlines()

    assert status == 0
    summary = next(i for i, line in enumerate(lines) if "Gotowe." in line)
    assert lines[summary + 1 :] == [
        "Uwaga: Wszystkie piksele wyniku są bez danych.",
        "Uwaga: Narzędzie dummy_tool: Dane wymagają wskazania źródła.",
    ]


def test_main_log_names_the_checks_and_what_became_of_them(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    run_fetch(command_args, monkeypatch, "s\nn\nn\n")
    capsys.readouterr()

    cli.main([*config_args, "log"], project_dir=project)

    assert "sprawdzenie dostępności: pominięte" in capsys.readouterr().out

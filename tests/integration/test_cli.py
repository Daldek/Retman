"""``retman plan run``, ``results list`` and ``journal show``: the conversation in a
terminal, non-interactive safety, the envelope of ``--json`` and the project history."""

import io
import json
from pathlib import Path

import pytest
from document_schemas import violations
from error_documents import last_line_document

from retman import cli
from retman.backends.base import Decision
from retman.config import init_config
from retman.exceptions import BackendConnectionError, Terminated
from retman.registry.loader import load_operations
from retman.testing import FakeDecisionBackend

SHEET = "N-34-130-D-d-2-4"


class TerminalInput(io.StringIO):
    """Scripted terminal responses for a deterministic interactive session."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def command_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
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


def plan_run(config_args: list[str], text: str, *flags: str) -> list[str]:
    """Return the words of ``retman plan run --text <text>`` with more flags."""
    return ["plan", "run", *config_args, *flags, "--text", text]


def test_main_interactive_question_plan_confirm_result_and_audit(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))

    status = cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}"),
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


def test_main_noninteractive_never_asks_and_never_executes(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO("1\nt\n"))

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    captured = capsys.readouterr()

    assert status == 2
    assert captured.out == ""
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_check_shows_the_incomplete_plan_and_exits_zero(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--check", "--json"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)

    assert status == 0 and captured.err == ""
    assert (envelope["command"], envelope["check"], envelope["status"]) == (
        "plan run",
        True,
        "ok",
    )
    assert envelope["result"]["schema"] == "retman-plan/1"
    assert violations("retman-plan/1", envelope["result"]) == []
    assert envelope["result"]["complete"] is False
    assert [q["name"] for q in envelope["result"]["questions"]] == ["style"]
    assert [n["code"] for n in envelope["notices"]] == ["questions_open"]
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_yes_runs_a_complete_plan_and_prints_the_envelope(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        plan_run(
            config_args, f"Zrób NMT dla {SHEET} w stylu gładkim", "--yes", "--json"
        ),
        backend=FakeDecisionBackend({"make_dem": "make_dem", "smooth": "smooth"}),
        project_dir=project,
    )
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)

    assert status == 0 and captured.err == ""
    assert (envelope["check"], envelope["status"]) == (False, "ok")
    assert envelope["result"]["confirmed"] is True
    assert envelope["result"]["run"]["ok"] is True
    assert (project / "retman-output" / "001_make_dem" / "dem.asc").exists()


def test_main_a_complete_plan_without_yes_names_the_option(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET} w stylu gładkim"),
        backend=FakeDecisionBackend({"make_dem": "make_dem", "smooth": "smooth"}),
        project_dir=project,
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 2
    assert (document["code"], document["details"]["reason"]) == (
        "validation_error",
        "input_required",
    )
    assert document["details"]["option"] == "yes"
    assert not (project / "retman-output" / "001_make_dem").exists()


def test_main_check_and_yes_exclude_each_other(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--check", "--yes"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 2
    assert document["details"]["reason"] == "one_of"
    assert document["details"]["allowed"] == ["check", "yes"]


def test_main_a_call_without_text_and_terminal_names_the_option(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(["plan", "run", *config_args, "--json"], project_dir=project)

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 2
    assert document["details"]["reason"] == "input_required"
    assert document["details"]["option"] == "text"


def test_main_json_never_prompts_even_in_a_terminal(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--json"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    captured = capsys.readouterr()
    assert status == 2 and captured.out == ""
    assert last_line_document(captured.err)["details"]["reason"] == "input_required"


def test_main_check_shows_the_complete_plan_in_a_terminal_without_execution(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput())

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--check"),
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
        plan_run(config_args, f"NMT dla {SHEET}"), backend=backend, project_dir=project
    )
    monkeypatch.setattr("sys.stdin", TerminalInput("anuluj\n"))
    cancelled = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    log = (project / "retman-output" / "journal.jsonl").read_text()

    assert rejected == cancelled == 130
    assert '"status": "rejected"' in log
    assert '"status": "cancelled"' in log
    assert not (project / "retman-output" / "001_make_dem").exists()


@pytest.mark.parametrize(
    ("answers", "status", "recorded"),
    [("y", 0, None), ("n", 130, "rejected"), ("cancel", 130, "cancelled")],
)
def test_main_the_dialog_speaks_english_and_takes_the_answer_words_of_the_language(
    command_args,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answers: str,
    status: int,
    recorded: str | None,
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput(f"1\n{answers}\n"))

    code = cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}", "--lang", "en"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    transcript = capsys.readouterr().out
    log = (project / "retman-output" / "journal.jsonl").read_text()

    assert code == status
    assert "Run it? [y]es / [n]o / [c]hange" in transcript
    assert ("Result #1" in transcript) == (status == 0)
    assert ("Wykonać?" in transcript) is False
    assert (f'"status": "{recorded}"' in log) == (recorded is not None)


def test_main_cancelled_with_json_prints_the_cancelled_envelope(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    class Interrupted(FakeDecisionBackend):
        def choose(
            self, state: str, question: str, options: dict[str, str]
        ) -> Decision:
            raise KeyboardInterrupt

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--json"),
        backend=Interrupted(),
        project_dir=project,
    )

    envelope = json.loads(capsys.readouterr().out)
    assert status == 130
    assert (envelope["command"], envelope["status"], envelope["result"]) == (
        "plan run",
        "cancelled",
        None,
    )


def test_main_results_and_journal_read_project_without_model(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))
    cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    capsys.readouterr()

    results_code = cli.main(["results", "list", *config_args], project_dir=project)
    listed = capsys.readouterr().out
    log_code = cli.main(["journal", "show", *config_args], project_dir=project)
    events = capsys.readouterr().out

    assert results_code == log_code == 0
    assert "#1:" in listed
    assert "wykonanie" in events


def test_main_results_and_journal_are_documents_with_a_page(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))
    cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    capsys.readouterr()

    cli.main(["results", "list", *config_args, "--json"], project_dir=project)
    results = json.loads(capsys.readouterr().out)
    cli.main(
        ["journal", "show", *config_args, "--json", "--limit", "2"],
        project_dir=project,
    )
    journal = json.loads(capsys.readouterr().out)

    assert results["result"]["schema"] == "retman-results/1"
    assert [r["number"] for r in results["result"]["results"]] == [1]
    assert journal["result"]["schema"] == "retman-journal/1"
    assert len(journal["result"]["events"]) == 2
    assert journal["page"]["truncated"] is True and journal["page"]["next_cursor"]


def test_main_init_and_missing_config_report_clear_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    config = tmp_path / "new.toml"

    failure = cli.main(
        ["results", "list", "--config", str(config)], project_dir=tmp_path
    )
    missing = capsys.readouterr().err
    created = cli.main(
        ["config", "init", "--config", str(config)], project_dir=tmp_path
    )

    assert failure == 3 and "retman config init" in missing
    document = last_line_document(missing)
    assert (document["code"], document["details"]["reason"]) == (
        "not_found",
        "missing_config",
    )
    assert created == 0 and config.exists()


def test_main_change_option_from_numbered_plan_list(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("?\nz\n2\n2\nt\n"))

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
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
        ["plan", "run", *config_args],
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
        plan_run(config_args, f"NMT dla {SHEET}", "--check", "--explain"),
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )

    assert status == 0
    assert "Decyzja style: raw, pewność 1.0" in capsys.readouterr().out


def test_main_explain_adds_the_decisions_to_the_document(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    cli.main(
        plan_run(config_args, f"NMT dla {SHEET}", "--check", "--explain", "--json"),
        backend=FakeDecisionBackend({"make_dem": "make_dem", "raw": "raw"}),
        project_dir=project,
    )

    decisions = json.loads(capsys.readouterr().out)["result"]["decisions"]
    assert {"name": "style", "key": "raw"}.items() <= decisions[-1].items()


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
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=DisconnectedBackend(),
        project_dir=project,
    )

    assert status == 5
    stderr = capsys.readouterr().err
    assert "retman doctor check" in stderr
    document = last_line_document(stderr)
    assert (document["code"], document["exit_code"]) == ("source_unavailable", 5)
    assert document["details"]["reason"] == "backend_connection"


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
        plan_run(config_args, f"Pobierz NMT dla {SHEET} 1 m", *flags),
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
        plan_run(config_args, f"NMT dla {SHEET}"),
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

    assert status == 130
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

    assert status == 130 and "Anulowano." in capsys.readouterr().out
    (check,) = [e for e in journal_events(project) if e["event"] == "check"]
    assert check["status"] == "approved" and check["result"] is None


def test_main_check_never_takes_a_network_step(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    status = run_fetch(command_args, monkeypatch, "", "--check")
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
        plan_run(config_args, "Zrób NMT z ostrzeżeniami"),
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


def test_main_warnings_of_a_result_are_notices_of_the_envelope(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    status = cli.main(
        plan_run(config_args, "Zrób NMT z ostrzeżeniami", "--yes", "--json"),
        backend=FakeDecisionBackend({"noisy_dem": "noisy_dem"}),
        project_dir=project,
    )

    envelope = json.loads(capsys.readouterr().out)
    assert status == 0
    assert {notice["code"] for notice in envelope["notices"]} == {"operation_warning"}
    assert len(envelope["notices"]) == 2


def test_main_journal_names_the_checks_and_what_became_of_them(
    command_args, dummy_client, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    run_fetch(command_args, monkeypatch, "s\nn\nn\n")
    capsys.readouterr()

    cli.main(["journal", "show", *config_args], project_dir=project)

    assert "sprawdzenie dostępności: pominięte" in capsys.readouterr().out


def test_main_verbose_writes_the_technical_log_to_stderr_without_the_command(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))

    status = cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}", "--verbose"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    captured = capsys.readouterr()

    assert status == 0
    assert "DEBUG retman.core.pipeline" in captured.err
    assert "finished as result #1" in captured.err
    assert "DEBUG" not in captured.out
    # ARCHITECTURE 5.4: the technical log never holds the command or an answer
    assert SHEET not in captured.err
    assert "Zrób" not in captured.err


def test_main_logs_warnings_only_by_default(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))

    cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    assert capsys.readouterr().err == ""


def test_main_reads_the_log_level_from_the_environment(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))
    monkeypatch.setenv("RETMAN_LOG_LEVEL", "info")

    cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )
    err = capsys.readouterr().err

    assert "INFO retman.core.pipeline" in err
    assert "DEBUG" not in err


def test_main_the_option_beats_the_environment_for_the_log_level(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("1\nt\n"))
    monkeypatch.setenv("RETMAN_LOG_LEVEL", "debug")

    cli.main(
        plan_run(config_args, f"Zrób NMT dla {SHEET}", "--quiet"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    assert capsys.readouterr().err == ""


def test_main_rejects_an_unknown_log_level_naming_the_variable(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setenv("RETMAN_LOG_LEVEL", "loud")

    status = cli.main(["results", "list", *config_args], project_dir=project)

    assert status == 2
    document = last_line_document(capsys.readouterr().err)
    assert document["code"] == "validation_error"
    assert document["details"]["reason"] == "invalid_config"
    assert document["details"]["keys"]["invalid_value"] == (
        "log_level (RETMAN_LOG_LEVEL)"
    )


def test_main_out_of_scope_is_unsupported_and_ends_with_the_error_document(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    status = cli.main(
        plan_run(config_args, "Jaka będzie jutro pogoda w Poznaniu?"),
        backend=FakeDecisionBackend({"out_of_scope": "out_of_scope"}),
        project_dir=project,
    )

    stderr = capsys.readouterr().err
    document = last_line_document(stderr)
    assert status == document["exit_code"] == 15
    assert (document["code"], document["details"]["reason"]) == (
        "unsupported",
        "out_of_scope",
    )
    assert "Utworzenie NMT" in document["details"]["operations"]
    assert "Utworzenie NMT" in stderr  # the text for the user comes first


def test_main_without_a_terminal_names_the_open_questions_in_the_error_document(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=FakeDecisionBackend({"make_dem": "make_dem"}),
        project_dir=project,
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == 2
    assert (document["code"], document["details"]["reason"]) == (
        "validation_error",
        "input_required",
    )
    questions = document["details"]["questions"]
    assert questions and all(question["name"] for question in questions)


def test_main_a_failed_operation_ends_with_the_document_of_its_error(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", TerminalInput("t\n"))

    status = cli.main(
        plan_run(config_args, "Uruchom błędne narzędzie"),
        backend=FakeDecisionBackend({"broken_dem": "broken_dem"}),
        project_dir=project,
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 1
    assert (document["code"], document["details"]["exception"]) == (
        "internal_error",
        "RuntimeError",
    )


def test_main_a_failed_run_without_a_terminal_is_an_error_and_no_envelope(
    command_args, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args
    monkeypatch.setattr("sys.stdin", io.StringIO())

    status = cli.main(
        plan_run(config_args, "Uruchom błędne narzędzie", "--yes", "--json"),
        backend=FakeDecisionBackend({"broken_dem": "broken_dem"}),
        project_dir=project,
    )

    captured = capsys.readouterr()
    assert status == last_line_document(captured.err)["exit_code"] == 1
    assert captured.out == ""


def test_main_sigterm_ends_with_terminated(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    class Terminating(FakeDecisionBackend):
        def choose(
            self, state: str, question: str, options: dict[str, str]
        ) -> Decision:
            raise Terminated

    status = cli.main(
        plan_run(config_args, f"NMT dla {SHEET}"),
        backend=Terminating(),
        project_dir=project,
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 143
    assert document["code"] == "terminated"


@pytest.mark.parametrize(
    ("argv", "reason"),
    [
        (["--bad-option"], "usage"),
        (["results", "list", "--verbose", "--quiet"], "exclusive_options"),
        (["config"], "usage"),
        ([], "usage"),
        (["results", "list", "--limit", "many"], "usage"),
    ],
)
def test_main_a_mistake_in_the_call_is_a_validation_error(
    argv: list[str], reason: str, capsys: pytest.CaptureFixture[str]
):
    status = cli.main(argv)

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 2
    assert (document["code"], document["details"]["reason"]) == (
        "validation_error",
        reason,
    )


def test_main_a_value_outside_the_bounds_is_a_validation_error_naming_the_option(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    status = cli.main(
        ["results", "list", *config_args, "--limit", "0"], project_dir=project
    )

    document = last_line_document(capsys.readouterr().err)
    assert status == 2
    assert (document["details"]["option"], document["details"]["reason"]) == (
        "limit",
        "minimum",
    )


def test_config_show_json_prints_the_envelope_alone(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    status = cli.main(["config", "show", *config_args, "--json"], project_dir=project)

    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    document = envelope["result"]
    assert status == 0
    assert captured.err == ""
    assert (envelope["schema"], envelope["command"]) == (
        "retman-result/1",
        "config show",
    )
    assert document["schema"] == "retman-config/1"
    assert document["config_file"]["source"] == "option"
    assert document["keys"]["decision.backend"]["source"] == "file"


def test_config_show_still_works_when_the_file_cannot_be_used(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    broken = tmp_path / "nogat.toml"
    broken.write_text("[retman\n", encoding="utf-8")

    status = cli.main(["config", "show", "--config", str(broken), "--json"])

    document = json.loads(capsys.readouterr().out)["result"]
    assert status == 0
    assert document["config_file"]["error"]


def test_config_show_reports_an_option_as_the_source_of_the_language(
    command_args, capsys: pytest.CaptureFixture[str]
):
    config_args, project = command_args

    cli.main(
        ["config", "show", *config_args, "--json", "--lang", "en"], project_dir=project
    )

    keys = json.loads(capsys.readouterr().out)["result"]["keys"]
    assert (keys["lang"]["value"], keys["lang"]["source"]) == ("en", "option")


def test_a_command_without_the_model_server_names_the_missing_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    status = cli.main(plan_run([], f"NMT dla {SHEET}"), project_dir=tmp_path)

    document = last_line_document(capsys.readouterr().err)
    assert status == document["exit_code"] == 2
    assert document["details"]["reason"] == "invalid_config"
    assert "decision.url" in document["details"]["keys"]["missing_key"]


def test_results_need_no_settings_file_and_no_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    status = cli.main(["results", "list"], project_dir=tmp_path)

    assert status == 0
    assert "Brak wyników" in capsys.readouterr().out

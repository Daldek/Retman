"""``retman doctor``: blocking problems, hints and the report contract (ARCH 7.2)."""

import importlib.metadata
import json
from pathlib import Path

import httpx
import pytest

from retman import cli
from retman.backends.base import Decision
from retman.config import init_config
from retman.doctor import run_doctor
from retman.i18n.loader import load_core_texts
from retman.testing import FakeDecisionBackend

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MODEL_URL = "http://model.test/v1"


@pytest.fixture
def dummy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(FIXTURES))
    from dummy_tool.manifest import MANIFEST

    return [(MANIFEST, FIXTURES / "dummy_tool")]


def _openai_config(tmp_path: Path, *, confidence: str = "logprobs") -> Path:
    path = init_config(tmp_path / "retman.toml")
    text = (
        path.read_text(encoding="utf-8")
        .replace('backend = "basal"', 'backend = "openai_compatible"', 1)
        .replace('url = "http://127.0.0.1:8000"', f'url = "{MODEL_URL}"')
        .replace('model = "basal-1.5-mini"', 'model = "bielik-11b"')
        .replace('# confidence = "auto"', f'confidence = "{confidence}"')
        .replace("# consistency_runs = 3", "consistency_runs = 3")
        .replace('operation = "auto"', "operation = 0.9")
        .replace('parameter = "auto"', "parameter = 0.85")
    )
    path.write_text(text, encoding="utf-8")
    return path


def _server(models: list[str]) -> httpx.Client:
    def reply(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": name} for name in models]})

    return httpx.Client(transport=httpx.MockTransport(reply))


def _fake(key: str) -> FakeDecisionBackend:
    return FakeDecisionBackend(
        {key: Decision(key, {key: 0.97}, 0.97, "logprobs", "bielik-11b")}
    )


def _installed(version: str):
    return lambda _: version


def _not_installed(name: str) -> str:
    raise importlib.metadata.PackageNotFoundError(name)


def _lines(report, section: str) -> list[str]:
    return [
        check.text
        for found in report.sections
        if found.key == section
        for check in found.checks
    ]


def test_healthy_setup_shows_model_address_and_exits_zero(tmp_path: Path, dummy):
    config = _openai_config(tmp_path)

    with _server(["bielik-11b"]) as client:
        report, texts = run_doctor(
            config,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )
    text = report.to_text(texts)

    assert report.exit_code == 0
    # The address is always shown, never judged (N-04)
    assert MODEL_URL in text
    assert "pytanie testowe: poprawna odpowiedź (pewność 0,97" in text
    assert "progi pewności: operacja 0.9, parametr 0.85" in text
    assert "dummy_tool 1.2.0, obsługiwane >=1.2,<2, 4 operacje" in text
    assert "✗" not in text


def test_unreachable_model_blocks_work_and_says_how_to_fix(tmp_path: Path, dummy):
    config = _openai_config(tmp_path)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with httpx.Client(transport=httpx.MockTransport(refuse)) as client:
        report, texts = run_doctor(
            config,
            tmp_path,
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )
    text = report.to_text(texts)

    assert report.exit_code == 1
    assert (
        f"✗ serwer modelu nie odpowiada ({MODEL_URL}) → uruchom serwer modelu" in text
    )


def test_wrong_test_answer_and_unlisted_model_warn_without_blocking(
    tmp_path: Path, dummy
):
    config = _openai_config(tmp_path)

    with _server(["other-model"]) as client:
        report, texts = run_doctor(
            config,
            tmp_path,
            backend=_fake("weather"),
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )
    decision = _lines(report, "decision")

    assert report.exit_code == 0
    assert any("nie występuje na liście serwera: other-model" in t for t in decision)
    assert any(t.startswith("pytanie testowe: błędna odpowiedź") for t in decision)


def test_missing_config_points_to_init_and_still_checks_tools(tmp_path: Path, dummy):
    report, texts = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=dummy,
        version_lookup=_installed("1.2.0"),
    )
    text = report.to_text(texts)

    assert report.exit_code == 1
    assert "retman init" in text
    assert "dummy_tool 1.2.0" in text


@pytest.mark.parametrize(
    ("lookup", "expected"),
    [
        (
            _not_installed,
            '✗ dummy_tool: nie zainstalowany → uv tool install … --with "dummy-tool"',
        ),
        (
            _installed("2.0.0"),
            "! dummy_tool 2.0.0, obsługiwane >=1.2,<2 — wersja spoza zakresu",
        ),
    ],
)
def test_unusable_tool_shows_install_hint_and_blocks_without_operations(
    tmp_path: Path, dummy, lookup, expected: str
):
    config = _openai_config(tmp_path)

    with _server(["bielik-11b"]) as client:
        report, texts = run_doctor(
            config,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=dummy,
            version_lookup=lookup,
        )
    text = report.to_text(texts)

    assert expected in text
    assert "✗ brak dostępnych operacji" in text
    assert report.exit_code == 1


def test_unreadable_result_is_reported_but_does_not_block(tmp_path: Path, dummy):
    config = _openai_config(tmp_path)
    for name, content in (("001_make_dem", '{"number": 1}'), ("002_make_dem", "{")):
        folder = tmp_path / "retman-output" / name
        folder.mkdir(parents=True)
        (folder / "result.json").write_text(content, encoding="utf-8")

    with _server(["bielik-11b"]) as client:
        report, _ = run_doctor(
            config,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )
    configuration = _lines(report, "configuration")

    assert report.exit_code == 0
    assert any("(2 wyniki, zapis możliwy)" in t for t in configuration)
    assert any(t.endswith("result.json w: 002_make_dem") for t in configuration)


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, "1 operacja"),
        (3, "3 operacje"),
        (5, "5 operacji"),
        (12, "12 operacji"),
        (22, "22 operacje"),
    ],
)
def test_polish_plural_of_operation_counts(count: int, expected: str):
    from retman.doctor import _plural

    assert _plural(load_core_texts("pl"), "operations", count) == expected


def test_cli_doctor_json_reports_the_same_checks_and_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = cli.main(
        ["--config", str(tmp_path / "absent.toml"), "--json", "doctor"],
        project_dir=tmp_path,
    )
    report = json.loads(capsys.readouterr().out)

    assert code == report["exit_code"] == 1
    configuration = report["sections"][0]
    assert configuration["key"] == "configuration"
    assert configuration["checks"][0]["blocking"] is True

"""``retman doctor check``: blocking problems, hints and the report (ARCH 7.2)."""

import errno
import importlib.metadata
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from document_schemas import violations

from retman import cli
from retman.backends.base import Decision
from retman.config import init_config
from retman.doctor import _plural, run_doctor
from retman.i18n.loader import load_core_texts, localize
from retman.stores import ToolOutcome
from retman.testing import FakeDecisionBackend

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODEL_URL = "http://model.test/v1"


@pytest.fixture
def dummy(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(FIXTURES))
    from dummy_tool.manifest import MANIFEST

    return [(MANIFEST, FIXTURES / "dummy_tool")]


@pytest.fixture(autouse=True)
def local_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cache and reference folders below tmp_path: nothing real is read."""
    monkeypatch.setenv("NOGAT_CACHE_DIR", str(tmp_path / "cache"))


def _openai_config(tmp_path: Path, *, confidence: str = "logprobs") -> Path:
    path = init_config(tmp_path / "nogat.toml", stores_dir=tmp_path / "stores")
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
    """The texts of a section as the Polish terminal shows them."""
    polish = load_core_texts("pl")
    return [
        localize(check.text, polish)
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
    count = _plural(load_core_texts("pl"), "operations", len(dummy[0][0]["operations"]))
    assert f"dummy_tool 1.2.0, obsługiwane >=1.2,<2, {count}" in text
    assert "✗" not in text


def test_the_document_is_english_and_the_terminal_text_follows_the_language(
    tmp_path: Path, dummy
):
    config = _openai_config(tmp_path)

    with _server(["bielik-11b"]) as client:
        report, polish = run_doctor(
            config,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )
    document = json.dumps(report.document(), ensure_ascii=False)
    english = report.to_text(load_core_texts("en"))

    # AGI-9.2: the document is English whatever the language of the terminal
    assert not any(letter in document for letter in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
    assert "test question: correct answer (confidence 0.97 " in document
    assert "pytanie testowe: poprawna odpowiedź (pewność 0,97 " in report.to_text(
        polish
    )
    # the same message in the other language, not a Polish sentence in an English line
    assert "test question: correct answer (confidence 0.97 " in english
    assert "pytanie" not in english and "Konfiguracja" not in english


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

    assert report.exit_code == 10
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

    assert report.exit_code == 10
    assert "retman config init" in text
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
    assert report.exit_code == 10


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
    assert _plural(load_core_texts("pl"), "operations", count) == expected


def test_cli_doctor_json_prints_the_envelope_with_a_unit_per_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = cli.main(
        ["doctor", "check", "--config", str(tmp_path / "absent.toml"), "--json"],
        project_dir=tmp_path,
    )
    envelope = json.loads(capsys.readouterr().out)

    assert code == 10
    assert (envelope["command"], envelope["status"]) == ("doctor check", "partial")
    report = envelope["result"]
    assert report["schema"] == "retman-doctor/1"
    assert violations("retman-doctor/1", report) == []
    configuration = report["sections"][0]
    assert configuration["key"] == "configuration"
    assert configuration["checks"][0]["blocking"] is True
    failed = [item for item in envelope["items"] if item["status"] == "failed"]
    assert [(item["id"], item["code"], item["reason"]) for item in failed] == [
        ("configuration.1", "not_found", "missing_config")
    ]
    ok_ids = {item["id"] for item in envelope["items"] if item["status"] == "ok"}
    assert "configuration.1" not in ok_ids and ok_ids


# --- stores of the tools (ARCH 7.2, 9.1) ---------------------------------------------


@pytest.fixture
def store_tools(dummy):
    """Two tools named like the real ones, so their stores are checked."""
    manifest, folder = dummy[0]
    sources = {
        "kartograf": "git+https://github.com/Daldek/Kartograf",
        "imgwtools": "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools",
    }
    tools = []
    for tool, source in sources.items():
        copy = deepcopy(manifest)
        copy["tool"], copy["distribution"], copy["source"] = tool, tool, source
        tools.append((copy, folder))
    return tools


@pytest.fixture
def pyarrow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyarrow", SimpleNamespace(__version__="26.0.0"))


def _make_stores(tmp_path: Path, **skip: bool) -> dict[str, Path]:
    """Create the folders a healthy installation has; ``skip`` leaves one out."""
    paths = {
        "kartograf": tmp_path / "stores" / "kartograf",
        "cache": tmp_path / "cache" / "kartograf" / "metadata.db",
        "imgwtools": tmp_path / "stores" / "imgw",
        "reference": tmp_path / "cache" / "imgw" / "reference",
    }
    for name, path in paths.items():
        if skip.get(name):
            continue
        folder = path.parent if name == "cache" else path
        folder.mkdir(parents=True)
    if not skip.get("imgwtools"):
        marker = paths["imgwtools"] / "imgw-store.json"
        marker.write_text('{"schema": "imgw-store/1"}', encoding="utf-8")
    return paths


def _stores(report) -> list[tuple[str, str]]:
    polish = load_core_texts("pl")
    return [
        (check.status, localize(check.text, polish))
        for found in report.sections
        if found.key == "stores"
        for check in found.checks
    ]


def _probe(calls: list[str], outcome: ToolOutcome | None = None):
    def probe() -> ToolOutcome:
        calls.append("probe")
        return outcome or ToolOutcome("ok", version="3.0.0")

    return probe


def _run_stores(
    tmp_path: Path,
    tools,
    *,
    lookup=None,
    rewrite: tuple[str, str] | None = None,
    **options,
):
    config = _openai_config(tmp_path)
    if rewrite is not None:
        text = config.read_text(encoding="utf-8")
        config.write_text(text.replace(*rewrite), encoding="utf-8")
    with _server(["bielik-11b"]) as client:
        return run_doctor(
            config,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=tools,
            version_lookup=lookup or _installed("1.2.0"),
            **options,
        )


def test_healthy_stores_are_listed_and_the_slow_probe_is_not_run(
    tmp_path: Path, store_tools, pyarrow
):
    paths = _make_stores(tmp_path)
    calls: list[str] = []

    report, _ = _run_stores(tmp_path, store_tools, probe=_probe(calls))
    stores = _stores(report)

    assert report.exit_code == 0
    assert all(status == "ok" for status, _ in stores)
    text = "\n".join(text for _, text in stores)
    for expected in (
        f"magazyn {paths['kartograf']} (zapis możliwy, dowiązania twarde działają)",
        f"cache metadanych {paths['cache']}",
        f"magazyn {paths['imgwtools']} (znacznik imgw-store.json",
        "schemat imgw-store/1, dowiązania twarde działają)",
        "pyarrow 26.0.0",
        f"dane referencyjne {paths['reference']} (hydro_stations_locations.csv: brak)",
    ):
        assert expected in text
    assert calls == []
    # The write and link tests leave nothing behind in a user's store
    assert list(paths["kartograf"].iterdir()) == []


def test_stores_not_created_yet_warn_with_a_hint_and_do_not_block(
    tmp_path: Path, store_tools, pyarrow
):
    report, texts = _run_stores(tmp_path, store_tools)
    text = report.to_text(texts)

    assert report.exit_code == 0
    stores = _stores(report)
    assert [s for s, line in stores if "pyarrow" not in line] == ["warning"] * 4
    assert "Kartograf utworzy go przy pierwszym pobraniu" in text
    assert (
        "nie został jeszcze utworzony (brak imgw-store.json) → utwórz go: "
        "retman config init" in text
    )
    # Nothing was created while looking
    assert not (tmp_path / "stores").exists()
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        (None, "nie jest pusty i nie jest magazynem IMGWTools"),
        ('{"schema": "imgw-store/2"}', "nieobsługiwany schemat (imgw-store/2)"),
        ("{", "jest nieczytelny"),
    ],
    ids=["foreign_files", "unsupported_schema", "unreadable_marker"],
)
def test_imgw_folder_that_is_not_a_usable_store_blocks_work(
    tmp_path: Path, store_tools, pyarrow, marker: str | None, expected: str
):
    paths = _make_stores(tmp_path)
    store = paths["imgwtools"]
    if marker is None:
        (store / "imgw-store.json").unlink()
        (store / "notes.txt").write_text("not a store", encoding="utf-8")
    else:
        (store / "imgw-store.json").write_text(marker, encoding="utf-8")

    report, _ = _run_stores(tmp_path, store_tools)
    problems = [text for status, text in _stores(report) if status == "error"]

    assert report.exit_code == 10
    assert len(problems) == 1 and expected in problems[0]


def test_store_path_that_is_a_file_blocks_work(tmp_path: Path, store_tools, pyarrow):
    paths = _make_stores(tmp_path, kartograf=True)
    paths["kartograf"].write_text("a file", encoding="utf-8")

    report, _ = _run_stores(tmp_path, store_tools)

    assert report.exit_code == 10
    assert any(
        status == "error" and "nie jest folderem" in text
        for status, text in _stores(report)
    )


def test_symlink_in_a_store_path_is_refused_by_imgwtools_but_tolerated_by_kartograf(
    tmp_path: Path, store_tools, pyarrow
):
    real = tmp_path / "real"
    real.mkdir()
    try:
        (tmp_path / "stores").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")
    _make_stores(tmp_path)

    # init writes resolved paths, so the symlink comes from a hand-edited config
    rewrite = (str(real), str(tmp_path / "stores"))
    report, texts = _run_stores(tmp_path, store_tools, rewrite=rewrite)
    stores = _stores(report)
    kartograf = [item for item in stores if item[1].startswith("kartograf: w ścieżce")]
    imgwtools = [item for item in stores if item[1].startswith("imgwtools: w ścieżce")]

    assert [status for status, _ in kartograf] == ["warning"]
    assert [status for status, _ in imgwtools] == ["error"]
    assert report.exit_code == 10
    # The hint names the real path to write into the config
    assert f"wpisz ścieżkę rzeczywistą {real}/imgw" in report.to_text(texts)


def test_a_file_system_without_hard_links_blocks_both_stores(
    tmp_path: Path, store_tools, pyarrow, monkeypatch: pytest.MonkeyPatch
):
    _make_stores(tmp_path)
    refusal = OSError(errno.EPERM, "Operation not permitted")
    monkeypatch.setattr("retman.doctor.hardlink_error", lambda folder: refusal)

    report, texts = _run_stores(tmp_path, store_tools)
    stores = _stores(report)
    refused = [line for status, line in stores if status == "error"]

    assert report.exit_code == 10
    assert len(refused) == 2
    assert all(
        "nie obsługuje dowiązań twardych (Operation not permitted)" in r
        for r in refused
    )
    assert {line.split(":")[0] for line in refused} == {"kartograf", "imgwtools"}
    text = report.to_text(texts)
    assert (
        "[retman.tools.kartograf] store_dir" in text
        and "[retman.tools.imgwtools] store_dir" in text
    )
    # No "all is well" line next to the problem
    assert not any("zapis możliwy" in line for _, line in stores)
    assert not any("dowiązania twarde działają" in line for _, line in stores)


def test_hard_links_are_tried_where_a_missing_imgw_store_will_be_created(
    tmp_path: Path, store_tools, pyarrow, monkeypatch: pytest.MonkeyPatch
):
    paths = _make_stores(tmp_path, imgwtools=True)
    tried: list[Path] = []

    def record(folder: Path) -> None:
        tried.append(folder)

    monkeypatch.setattr("retman.doctor.hardlink_error", record)

    report, _ = _run_stores(tmp_path, store_tools)

    # The Kartograf store itself, and for the missing IMGWTools store the closest
    # existing folder: the same disk
    assert tried == [paths["kartograf"], paths["kartograf"].parent]
    assert report.exit_code == 0


def test_missing_pyarrow_disables_series_and_skips_the_probe(
    tmp_path: Path, store_tools, monkeypatch: pytest.MonkeyPatch
):
    _make_stores(tmp_path)
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    calls: list[str] = []

    report, texts = _run_stores(tmp_path, store_tools, deep=True, probe=_probe(calls))

    assert report.exit_code == 0
    assert any(
        status == "warning" and "brak pakietu pyarrow" in text
        for status, text in _stores(report)
    )
    assert (
        "imgwtools[store] @ git+https://github.com/Daldek/IMGWTools"
        in report.to_text(texts)
    )
    assert calls == []


@pytest.mark.parametrize("deep", [False, True])
def test_imgwtools_write_probe_runs_only_with_deep(
    tmp_path: Path, store_tools, pyarrow, deep: bool
):
    _make_stores(tmp_path)
    calls: list[str] = []

    report, _ = _run_stores(tmp_path, store_tools, probe=_probe(calls), deep=deep)

    assert calls == (["probe"] if deep else [])
    assert report.exit_code == 0
    assert (
        any("zapis do magazynu działa" in text for _, text in _stores(report)) == deep
    )


def test_failed_write_probe_blocks_work_and_quotes_the_tool(
    tmp_path: Path, store_tools, pyarrow
):
    _make_stores(tmp_path)
    refusal = ToolOutcome("refused", "System plików nie zapewnia atomowego zapisu")

    report, texts = _run_stores(
        tmp_path, store_tools, deep=True, probe=_probe([], refusal)
    )
    text = report.to_text(texts)

    assert report.exit_code == 10
    assert (
        "✗ imgwtools 1.2.0: zapis do magazynu nie działa na tym systemie: System plików"
        in text
    )
    assert "wyłącz narzędzie w [retman.adapters] enabled" in text


def test_stores_of_tools_that_are_not_in_use_are_not_checked(
    tmp_path: Path, store_tools, pyarrow
):
    def lookup(name: str) -> str:
        if name == "imgwtools":
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.2.0"

    calls: list[str] = []

    report, _ = _run_stores(
        tmp_path, store_tools, lookup=lookup, deep=True, probe=_probe(calls)
    )

    assert calls == []
    assert all("imgwtools" not in text for _, text in _stores(report))
    assert any("kartograf" in text for _, text in _stores(report))


def test_without_a_readable_config_there_are_no_store_checks(
    tmp_path: Path, store_tools
):
    report, _ = run_doctor(
        tmp_path / "absent.toml",
        tmp_path,
        manifests=store_tools,
        version_lookup=_installed("1.2.0"),
    )

    assert "stores" not in [section.key for section in report.sections]


def test_without_a_settings_file_the_defaults_apply_and_only_the_model_is_missing(
    tmp_path: Path, store_tools
):
    report, texts = run_doctor(
        None,
        tmp_path,
        manifests=store_tools,
        version_lookup=_installed("1.2.0"),
    )
    configuration = [
        check
        for found in report.sections
        for check in found.checks
        if found.key == ("configuration")
    ]

    blocking = [check.text for check in configuration if check.blocking]
    assert report.exit_code == 10
    assert len(blocking) == 1 and "decision.url" in blocking[0]
    # The stores follow the defaults and are still checked
    assert "stores" in [section.key for section in report.sections]
    assert "decision" not in [section.key for section in report.sections]


def test_the_model_server_can_come_from_variables_alone(
    tmp_path: Path, dummy, monkeypatch: pytest.MonkeyPatch
):
    for key, value in {
        "BACKEND": "openai_compatible",
        "URL": MODEL_URL,
        "MODEL": "bielik-11b",
        "TIMEOUT_S": "30",
        "CONFIDENCE": "logprobs",
        "CONSISTENCY_RUNS": "3",
        "THRESHOLDS_OPERATION": "0.9",
        "THRESHOLDS_PARAMETER": "0.85",
    }.items():
        monkeypatch.setenv(f"RETMAN_DECISION_{key}", value)

    with _server(["bielik-11b"]) as client:
        report, _ = run_doctor(
            None,
            tmp_path,
            backend=_fake("terrain"),
            client=client,
            manifests=dummy,
            version_lookup=_installed("1.2.0"),
        )

    assert report.exit_code == 0

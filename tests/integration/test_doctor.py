"""``retman doctor check``: blocking problems, hints and the report (ARCH 7.2)."""

import errno
import importlib.metadata
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from document_schemas import violations
from kartograf_store_files import write_marker
from obserwator_store_files import write_server_state

from retman import cli
from retman.backends.base import Decision
from retman.config import init_config
from retman.doctor import _plural, run_doctor
from retman.i18n.loader import load_core_texts, localize
from retman.stores import ToolOutcome
from retman.testing import FakeDecisionBackend

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MODEL_URL = "http://model.test/v1"
# The marker of each Obserwator root, spelled out (not taken from ``retman.stores``)
MARKERS = {"raw": "obserwator-store.json", "data": "obserwator-data.json"}


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
        .replace('url = "http://127.0.0.1:1234/v1"', f'url = "{MODEL_URL}"')
        .replace('model = "<model-name>"', 'model = "bielik-11b"')
        .replace('confidence = "auto"', f'confidence = "{confidence}"')
        .replace("operation = 0.90", "operation = 0.9")
        .replace("parameter = 0.90", "parameter = 0.85")
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
        "obserwator": "obserwator[store] @ git+https://github.com/Daldek/Obserwator",
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


def _make_stores(
    tmp_path: Path, obserwator_store_template: dict[str, Path], **skip: bool
) -> dict[str, Path]:
    """Create the folders a healthy installation has; ``skip`` leaves one out.

    The two Obserwator roots are copies of the fixture roots the tool builds itself.
    """
    paths = {
        "kartograf": tmp_path / "stores" / "kartograf",
        "cache": tmp_path / "cache" / "kartograf" / "metadata.db",
        "obserwator": tmp_path / "stores" / "obserwator",
        "obserwator_raw": tmp_path / "stores" / "obserwator-raw",
        "reference": tmp_path / "cache" / "obserwator" / "reference",
    }
    for name, path in paths.items():
        if skip.get(name):
            continue
        folder = path.parent if name == "cache" else path
        folder.mkdir(parents=True)
    for name, kind in (("obserwator", "data"), ("obserwator_raw", "raw")):
        if not skip.get(name):
            shutil.copytree(
                obserwator_store_template[kind], paths[name], dirs_exist_ok=True
            )
    return paths


def _stores(report) -> list[tuple[str, str]]:
    polish = load_core_texts("pl")
    return [
        (check.status, localize(check.text, polish))
        for found in report.sections
        if found.key == "stores"
        for check in found.checks
    ]


def _store_checks(report, status: str) -> list:
    """The checks of the stores section with ``status``."""
    return [
        check
        for found in report.sections
        if found.key == "stores"
        for check in found.checks
        if check.status == status
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
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    calls: list[str] = []

    report, _ = _run_stores(tmp_path, store_tools, probe=_probe(calls))
    stores = _stores(report)

    assert report.exit_code == 0
    assert all(status == "ok" for status, _ in stores)
    # Each Obserwator root is a line of its own that names its marker and schema
    for name, marker, schema in (
        ("obserwator", "obserwator-data.json", "obserwator-data/1"),
        ("obserwator_raw", "obserwator-store.json", "obserwator-store/1"),
    ):
        (line,) = [text for _, text in stores if f"{paths[name]} " in text]
        assert marker in line and schema in line
    for name in ("kartograf", "cache", "reference"):
        assert any(str(paths[name]) in text for _, text in stores)
    assert any("pyarrow 26.0.0" in text for _, text in stores)
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
    # Kartograf store, its cache, both Obserwator roots and the reference folder
    assert [s for s, line in stores if "pyarrow" not in line] == ["warning"] * 5
    # Each root's hint gives the command that initialises that root alone
    stores_dir = tmp_path / "stores"
    assert f"--kind data --root {stores_dir / 'obserwator'}" in text
    assert f"--kind raw --root {stores_dir / 'obserwator-raw'}" in text
    # Nothing was created while looking
    assert not stores_dir.exists()
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize(
    ("root", "kind"), [("obserwator", "data"), ("obserwator_raw", "raw")]
)
@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("foreign_files", "foreign_folder"),
        ("unsupported_schema", "marker_unsupported"),
        ("unreadable_marker", "marker_unreadable"),
    ],
)
def test_obserwator_folder_that_is_not_a_usable_root_blocks_work(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    root: str,
    kind: str,
    setup: str,
    reason: str,
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    store = paths[root]
    marker = store / MARKERS[kind]
    if setup == "foreign_files":
        shutil.rmtree(store)
        store.mkdir()
        (store / "notes.txt").write_text("not a store", encoding="utf-8")
    elif setup == "unsupported_schema":
        schema = json.loads(marker.read_text(encoding="utf-8"))["schema"]
        marker.write_text(
            json.dumps({"schema": schema.replace("/1", "/2")}), encoding="utf-8"
        )
    else:
        marker.write_text("{", encoding="utf-8")

    report, _ = _run_stores(tmp_path, store_tools)
    (problem,) = _store_checks(report, "error")

    assert report.exit_code == 10
    assert (problem.blocking, problem.code, problem.reason) == (
        True,
        "store_unavailable",
        reason,
    )
    assert str(store) in localize(problem.text, load_core_texts("pl"))


@pytest.mark.parametrize(
    ("root", "kind", "setting"),
    [
        ("obserwator", "data", "[retman.tools.obserwator] store_dir"),
        ("obserwator_raw", "raw", "[retman.tools.obserwator] raw_store_dir"),
    ],
)
def test_obserwator_root_of_the_other_kind_blocks_work_and_names_its_setting(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    root: str,
    kind: str,
    setting: str,
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    other = "raw" if kind == "data" else "data"
    shutil.rmtree(paths[root])
    shutil.copytree(obserwator_store_template[other], paths[root])

    report, texts = _run_stores(tmp_path, store_tools)
    (problem,) = _store_checks(report, "error")

    assert report.exit_code == 10
    assert (problem.code, problem.reason) == ("store_unavailable", "wrong_root")
    assert setting in localize(problem.hint, texts)


def test_obserwator_store_not_yet_split_is_refused_as_the_data_root(
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    # The combined store of Obserwator before ADR-017: the raw marker and all trees
    store = paths["obserwator"]
    shutil.rmtree(store)
    shutil.copytree(obserwator_store_template["raw"], store)
    for tree in ("series", "stations"):
        shutil.copytree(obserwator_store_template["data"] / tree, store / tree)
    held = set(store.rglob("*"))

    report, texts = _run_stores(tmp_path, store_tools)
    (problem,) = _store_checks(report, "error")

    assert report.exit_code == 10
    assert (problem.code, problem.reason) == ("store_unavailable", "wrong_root")
    # The hint gives the commands that split it, as Obserwator's USAGE describes
    hint = localize(problem.hint, texts)
    assert "cp -al" in hint and "store init --kind data" in hint
    # Looking changes nothing in the old store
    assert set(store.rglob("*")) == held


@pytest.mark.parametrize(
    ("root", "kind"), [("obserwator", "data"), ("obserwator_raw", "raw")]
)
def test_obserwator_layout_without_a_marker_blocks_work_and_says_how_to_mark_it(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    root: str,
    kind: str,
):
    store = _make_stores(tmp_path, obserwator_store_template)[root]
    (store / MARKERS[kind]).unlink()
    held = set(store.rglob("*"))

    report, texts = _run_stores(tmp_path, store_tools)
    (problem,) = _store_checks(report, "error")

    assert report.exit_code == 10
    assert (problem.blocking, problem.code, problem.reason) == (
        True,
        "store_unavailable",
        "no_marker",
    )
    assert f"store init --kind {kind} --root {store}" in localize(problem.hint, texts)
    # Looking changes nothing in a folder that may hold data: no probe, no marker
    assert set(store.rglob("*")) == held


def test_obserwator_folder_with_only_the_key_file_of_the_server_is_not_created_yet(
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    store = _make_stores(tmp_path, obserwator_store_template)["obserwator"]
    shutil.rmtree(store)
    store.mkdir()
    write_server_state(store)

    report, _ = _run_stores(tmp_path, store_tools)
    stores = _stores(report)

    assert report.exit_code == 0
    assert all(status != "error" for status, _ in stores)
    assert [status for status, text in stores if f"{store} " in text] == ["warning"]
    assert [path.name for path in store.iterdir()] == ["api_keys.json"]


def test_kartograf_store_with_its_marker_is_listed_with_it(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    kartograf_store_template: Path,
    store_tools,
    pyarrow,
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    shutil.copytree(kartograf_store_template, paths["kartograf"], dirs_exist_ok=True)

    report, _ = _run_stores(tmp_path, store_tools)
    stores = _stores(report)

    assert report.exit_code == 0
    assert all(status == "ok" for status, _ in stores)
    assert (
        f"kartograf: magazyn {paths['kartograf']} (znacznik kartograf-store.json, "
        "schemat kartograf-store/1, dowiązania twarde działają)"
    ) in [text for _, text in stores]


@pytest.mark.parametrize(
    ("setup", "reason", "expected"),
    [
        (
            "foreign_files",
            "foreign_folder",
            "nie jest pusty i nie jest magazynem Kartografa",
        ),
        (
            "unsupported_schema",
            "marker_unsupported",
            "nieobsługiwany schemat (kartograf-store/2)",
        ),
        ("unreadable_marker", "marker_unreadable", "jest nieczytelny"),
        ("inside_a_store", "nested_store", "leży w innym magazynie"),
    ],
)
def test_kartograf_folder_that_is_not_a_usable_store_blocks_work(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    setup: str,
    reason: str,
    expected: str,
):
    store = _make_stores(tmp_path, obserwator_store_template)["kartograf"]
    if setup == "foreign_files":
        (store / "notes.txt").write_text("not a store", encoding="utf-8")
    elif setup == "unsupported_schema":
        write_marker(store, "kartograf-store/2")
    elif setup == "unreadable_marker":
        (store / "kartograf-store.json").write_text("{", encoding="utf-8")
    else:
        # Both stores of the setting lie in a folder that is a store itself
        write_marker(tmp_path / "stores")

    report, _ = _run_stores(tmp_path, store_tools)
    (problem,) = [
        check
        for found in report.sections
        if found.key == "stores"
        for check in found.checks
        if check.status == "error"
    ]

    assert report.exit_code == 10
    assert (problem.blocking, problem.code, problem.reason) == (
        True,
        "store_unavailable",
        reason,
    )
    assert expected in localize(problem.text, load_core_texts("pl"))


def test_kartograf_layout_without_a_marker_blocks_work_and_says_how_to_mark_it(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    kartograf_store_template: Path,
    store_tools,
    pyarrow,
):
    store = _make_stores(tmp_path, obserwator_store_template)["kartograf"]
    shutil.copytree(kartograf_store_template, store, dirs_exist_ok=True)
    (store / "kartograf-store.json").unlink()
    held = set(store.rglob("*"))

    report, texts = _run_stores(tmp_path, store_tools)
    (problem,) = [
        check
        for found in report.sections
        if found.key == "stores"
        for check in found.checks
        if check.status == "error"
    ]

    assert report.exit_code == 10
    assert (problem.blocking, problem.code, problem.reason) == (
        True,
        "store_unavailable",
        "no_marker",
    )
    text = report.to_text(texts)
    assert (
        "ma układ magazynu Kartografa, ale nie ma znacznika kartograf-store.json"
        in text
    )
    assert f"kartograf store init --root {store}" in text
    # Looking changes nothing in a folder that may hold data: no marker, no probe file
    assert set(store.rglob("*")) == held


def test_store_path_that_is_a_file_blocks_work(
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    paths = _make_stores(tmp_path, obserwator_store_template, kartograf=True)
    paths["kartograf"].write_text("a file", encoding="utf-8")

    report, _ = _run_stores(tmp_path, store_tools)

    assert report.exit_code == 10
    assert any(
        status == "error" and "nie jest folderem" in text
        for status, text in _stores(report)
    )


def test_symlink_in_a_store_path_is_refused_by_obserwator_but_tolerated_by_kartograf(
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    real = tmp_path / "real"
    real.mkdir()
    try:
        (tmp_path / "stores").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")
    _make_stores(tmp_path, obserwator_store_template)

    # init writes resolved paths, so the symlink comes from a hand-edited config
    rewrite = (str(real), str(tmp_path / "stores"))
    report, texts = _run_stores(tmp_path, store_tools, rewrite=rewrite)
    (tolerated,) = _store_checks(report, "warning")
    refused = _store_checks(report, "error")

    assert "[retman.tools.kartograf] store_dir" in localize(tolerated.hint, texts)
    assert [check.reason for check in refused] == ["symlink_refused"] * 2
    assert report.exit_code == 10
    # Each hint names the real path to write into the setting of its root
    hints = [localize(check.hint, texts) for check in refused]
    assert str(real / "obserwator") in hints[0]
    assert "[retman.tools.obserwator] store_dir" in hints[0]
    assert str(real / "obserwator-raw") in hints[1]
    assert "[retman.tools.obserwator] raw_store_dir" in hints[1]


def test_a_file_system_without_hard_links_blocks_every_store_folder(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    monkeypatch: pytest.MonkeyPatch,
):
    paths = _make_stores(tmp_path, obserwator_store_template)
    refusal = OSError(errno.EPERM, "Operation not permitted")
    monkeypatch.setattr("retman.doctor.hardlink_error", lambda folder: refusal)

    report, texts = _run_stores(tmp_path, store_tools)
    refused = _store_checks(report, "error")

    assert report.exit_code == 10
    assert [check.reason for check in refused] == ["no_hardlinks"] * 3
    # Each line names its folder and the reason, each hint the setting to change
    for check, name, setting in zip(
        refused,
        ("kartograf", "obserwator", "obserwator_raw"),
        (
            "[retman.tools.kartograf] store_dir",
            "[retman.tools.obserwator] store_dir",
            "[retman.tools.obserwator] raw_store_dir",
        ),
        strict=True,
    ):
        text = localize(check.text, texts)
        assert f"{paths[name]}" in text and "Operation not permitted" in text
        assert setting in localize(check.hint, texts)
    # No "all is well" line next to the problem
    assert not any(
        str(tmp_path / "stores") in localize(check.text, texts)
        for check in _store_checks(report, "ok")
    )


def test_hard_links_are_tried_where_a_missing_obserwator_root_will_be_created(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    monkeypatch: pytest.MonkeyPatch,
):
    paths = _make_stores(tmp_path, obserwator_store_template, obserwator=True)
    tried: list[Path] = []

    def record(folder: Path) -> None:
        tried.append(folder)

    monkeypatch.setattr("retman.doctor.hardlink_error", record)

    report, _ = _run_stores(tmp_path, store_tools)

    # The Kartograf store and the raw root themselves, and for the missing data root
    # the closest existing folder: the same disk
    assert tried == [
        paths["kartograf"],
        paths["obserwator"].parent,
        paths["obserwator_raw"],
    ]
    assert report.exit_code == 0


def test_missing_pyarrow_disables_series_and_skips_the_probe(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    monkeypatch: pytest.MonkeyPatch,
):
    _make_stores(tmp_path, obserwator_store_template)
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    calls: list[str] = []

    report, texts = _run_stores(tmp_path, store_tools, deep=True, probe=_probe(calls))

    assert report.exit_code == 0
    assert any(
        status == "warning" and "brak pakietu pyarrow" in text
        for status, text in _stores(report)
    )
    assert (
        "obserwator[store] @ git+https://github.com/Daldek/Obserwator"
        in report.to_text(texts)
    )
    assert calls == []


@pytest.mark.parametrize("deep", [False, True])
def test_obserwator_write_probe_runs_only_with_deep(
    tmp_path: Path,
    obserwator_store_template: dict[str, Path],
    store_tools,
    pyarrow,
    deep: bool,
):
    _make_stores(tmp_path, obserwator_store_template)
    calls: list[str] = []

    report, _ = _run_stores(tmp_path, store_tools, probe=_probe(calls), deep=deep)

    assert calls == (["probe"] if deep else [])
    assert report.exit_code == 0
    assert (
        any("zapis do magazynu działa" in text for _, text in _stores(report)) == deep
    )


def test_failed_write_probe_blocks_work_and_quotes_the_tool(
    tmp_path: Path, obserwator_store_template: dict[str, Path], store_tools, pyarrow
):
    _make_stores(tmp_path, obserwator_store_template)
    refusal = ToolOutcome("refused", "System plików nie zapewnia atomowego zapisu")

    report, texts = _run_stores(
        tmp_path, store_tools, deep=True, probe=_probe([], refusal)
    )
    text = report.to_text(texts)

    assert report.exit_code == 10
    assert (
        "✗ obserwator 1.2.0: zapis do magazynu nie działa na tym systemie: "
        "System plików" in text
    )
    assert "wyłącz narzędzie w [retman.adapters] enabled" in text


def test_stores_of_tools_that_are_not_in_use_are_not_checked(
    tmp_path: Path, store_tools, pyarrow
):
    def lookup(name: str) -> str:
        if name == "obserwator":
            raise importlib.metadata.PackageNotFoundError(name)
        return "1.2.0"

    calls: list[str] = []

    report, _ = _run_stores(
        tmp_path, store_tools, lookup=lookup, deep=True, probe=_probe(calls)
    )

    assert calls == []
    assert all("obserwator" not in text for _, text in _stores(report))
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

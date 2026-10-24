"""``retman init``: the config, the tool store folders and the IMGWTools consent."""

import errno
import io
from pathlib import Path

import pytest

from retman import cli
from retman.config import load_config
from retman.stores import IMGW_MARKER, ToolOutcome


class Terminal(io.StringIO):
    """Scripted answers of a user at a terminal."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-user data folder below tmp_path: init never touches the real one."""
    folder = tmp_path / "data"
    monkeypatch.setattr("retman.config.default_data_dir", lambda: folder)
    return folder


@pytest.fixture
def imgw_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """IMGWTools is installed and its store set-up is recorded, not run."""
    calls: list[Path] = []

    def init(folder: Path) -> ToolOutcome:
        calls.append(folder)
        return ToolOutcome("ok", version="3.0.0")

    monkeypatch.setattr("retman.initialize.tool_installed", lambda package: True)
    monkeypatch.setattr("retman.initialize.init_imgw_store", init)
    return calls


def _init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answers: str | None
) -> tuple[int, Path]:
    config = tmp_path / "retman.toml"
    if answers is not None:
        monkeypatch.setattr("sys.stdin", Terminal(answers))
    return cli.main(["--config", str(config), "init"], project_dir=tmp_path), config


def test_init_without_a_terminal_writes_the_config_and_creates_nothing_else(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    status, config = _init(tmp_path, monkeypatch, None)
    output = capsys.readouterr().out
    tools = load_config(config).tools

    assert status == 0
    assert tools["kartograf"]["store_dir"] == str(data / "stores" / "kartograf")
    assert tools["imgwtools"]["store_dir"] == str(data / "stores" / "imgwtools")
    # The default paths are shown and written; no question was possible
    assert str(data / "stores" / "kartograf") in output
    assert "nie zostały utworzone" in output
    assert not data.exists()


def test_init_in_a_terminal_creates_the_folders_and_the_store_after_consent(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    stores = tmp_path / "disk" / "retman"

    status, config = _init(tmp_path, monkeypatch, f"n\n{stores}\nt\n")
    output = capsys.readouterr().out
    tools = load_config(config).tools

    assert status == 0
    assert tools["kartograf"]["store_dir"] == str(stores / "kartograf")
    assert tools["imgwtools"]["store_dir"] == str(stores / "imgwtools")
    # Both stores sit side by side on the chosen disk; cache and reference files
    # stay on the local per-user disk
    assert (stores / "kartograf").is_dir()
    assert Path(tools["kartograf"]["cache_file"]).parent == data
    assert Path(tools["imgwtools"]["reference_data_dir"]).is_dir()
    # The IMGWTools folder is left to the tool, which wants an empty one
    assert not (stores / "imgwtools").exists()
    assert imgw_calls == [stores / "imgwtools"]
    assert f"Magazyn IMGWTools gotowy: {stores / 'imgwtools'}" in output


def test_enter_keeps_the_default_folder_and_no_consent_means_no_store(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    status, config = _init(tmp_path, monkeypatch, "n\n\nn\n")
    output = capsys.readouterr().out

    assert status == 0
    kartograf = load_config(config).tools["kartograf"]["store_dir"]
    assert kartograf == str(data / "stores" / "kartograf")
    assert imgw_calls == []
    assert "Utwórz magazyn IMGW" in output


def test_a_relative_answer_is_asked_again(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    stores = tmp_path / "disk"

    status, config = _init(tmp_path, monkeypatch, f"n\nrelative/dir\n{stores}\nn\n")
    output = capsys.readouterr().out

    assert status == 0
    assert "Podaj ścieżkę bezwzględną" in output
    assert load_config(config).tools["kartograf"]["store_dir"] == str(
        stores / "kartograf"
    )


def test_a_refusal_of_the_tool_fails_the_command_but_keeps_the_config(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    refusal = ToolOutcome("refused", "Katalog nie jest pustym magazynem IMGW: /x")
    monkeypatch.setattr("retman.initialize.init_imgw_store", lambda folder: refusal)

    status, config = _init(tmp_path, monkeypatch, f"n\n{tmp_path / 'disk'}\nt\n")
    error = capsys.readouterr().err

    assert status == 1
    assert config.exists()
    assert "Katalog nie jest pustym magazynem IMGW: /x" in error


def test_a_folder_that_cannot_be_created_leaves_no_config_behind(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder", encoding="utf-8")

    status, config = _init(tmp_path, monkeypatch, f"n\n{blocker / 'stores'}\nt\n")
    error = capsys.readouterr().err

    assert status == 1
    assert not config.exists()
    assert str(blocker) in error and "wskaż inny folder" in error
    assert imgw_calls == []


def test_an_existing_config_is_reported_before_any_question(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    config = tmp_path / "retman.toml"
    config.write_text("# mine", encoding="utf-8")
    terminal = Terminal("n\n")
    monkeypatch.setattr("sys.stdin", terminal)

    status = cli.main(["--config", str(config), "init"], project_dir=tmp_path)
    captured = capsys.readouterr()

    assert status == 1
    assert captured.out == ""
    assert "już istnieje" in captured.err
    assert terminal.tell() == 0
    assert config.read_text(encoding="utf-8") == "# mine"


def test_without_imgwtools_the_consent_question_is_not_asked(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr("retman.initialize.tool_installed", lambda package: False)

    # Only two answers are scripted: a third question would end in EOFError
    status, _ = _init(tmp_path, monkeypatch, f"n\n{tmp_path / 'disk'}\n")
    output = capsys.readouterr().out

    assert status == 0
    assert "IMGWTools nie jest zainstalowany" in output


def test_init_creates_a_real_imgwtools_store(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    pytest.importorskip("pyarrow")
    pytest.importorskip("imgwtools")
    stores = tmp_path / "disk"

    status, config = _init(tmp_path, monkeypatch, f"n\n{stores}\nt\n")

    assert status == 0
    assert (stores / "imgwtools" / IMGW_MARKER).is_file()
    assert load_config(config).tools["imgwtools"]["store_dir"] == str(
        stores / "imgwtools"
    )


def test_a_disk_without_hard_links_is_refused_before_the_config_is_written(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    refusal = OSError(errno.EOPNOTSUPP, "Operation not supported")
    monkeypatch.setattr("retman.initialize.hardlink_error", lambda folder: refusal)

    status, config = _init(tmp_path, monkeypatch, f"n\n{tmp_path / 'fat'}\nt\n")
    error = capsys.readouterr().err

    assert status == 1
    assert not config.exists()
    assert "nie obsługuje dowiązań twardych (Operation not supported)" in error
    assert "wskaż folder na innym dysku" in error
    assert imgw_calls == []


def test_the_tools_no_hard_link_refusal_gets_its_own_advice(
    tmp_path: Path,
    data: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    imgw_calls: list[Path],
):
    refusal = ToolOutcome(
        "refused", "System plików nie obsługuje dowiązań", reason="not_atomic"
    )
    monkeypatch.setattr("retman.initialize.init_imgw_store", lambda folder: refusal)

    status, config = _init(tmp_path, monkeypatch, f"n\n{tmp_path / 'disk'}\nt\n")
    error = capsys.readouterr().err

    assert status == 1
    assert config.exists()
    assert "System plików nie obsługuje dowiązań" in error
    assert "[tools.kartograf] store_dir" in error

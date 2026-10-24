"""Central settings consumed by the core and safely rejected at startup."""

from pathlib import Path

import pytest

from retman import Retman
from retman.config import config_template, init_config, load_config
from retman.exceptions import ConfigError
from retman.i18n.loader import load_core_texts
from retman.testing import FakeDecisionBackend


def test_from_config_injected_backend_uses_explicit_project_folder(tmp_path: Path):
    config_path = init_config(tmp_path / "settings.toml")
    project = tmp_path / "project"
    project.mkdir()

    app = Retman.from_config(
        config_path, backend=FakeDecisionBackend(), project_dir=project
    )

    assert app.workspace.root == project / load_config(config_path).results_dir
    assert not app.workspace.root.exists()


def test_from_config_rejects_non_basal_auto_threshold(tmp_path: Path):
    config_path = init_config(tmp_path / "settings.toml")
    content = (
        config_path.read_text()
        .replace(
            'backend = "basal"                   #',
            'backend = "openai_compatible"       #',
            1,
        )
        .replace('# confidence = "auto"', 'confidence = "consistency"')
        .replace("# consistency_runs = 3", "consistency_runs = 3")
    )
    config_path.write_text(content)

    with pytest.raises(ConfigError) as error:
        Retman.from_config(
            config_path, backend=FakeDecisionBackend(), project_dir=tmp_path
        )

    assert "auto_threshold_without_basal" in error.value.problems


@pytest.mark.parametrize("directory", ["/elsewhere", "../outside", "nested/../outside"])
def test_from_config_rejects_results_folder_outside_project(
    tmp_path: Path, directory: str
):
    config_path = init_config(tmp_path / "settings.toml")
    config_path.write_text(
        config_path.read_text().replace(
            'results_dir = "retman-output"', f'results_dir = "{directory}"'
        )
    )

    with pytest.raises(ConfigError) as error:
        Retman.from_config(
            config_path, backend=FakeDecisionBackend(), project_dir=tmp_path
        )

    assert error.value.problem_details["invalid_value"] == "output.results_dir"


def test_init_writes_the_users_collection_answer_and_full_path(tmp_path: Path):
    agreed = load_config(init_config(tmp_path / "yes.toml", collect_commands=True))
    refused = load_config(init_config(tmp_path / "no.toml"))

    assert agreed.collect_commands is True
    assert refused.collect_commands is False
    # The path is written out in the file: no hidden default (N-11)
    assert agreed.collect_path.is_absolute()
    assert str(agreed.collect_path) in (tmp_path / "yes.toml").read_text("utf-8")


def test_collection_path_must_be_absolute(tmp_path: Path):
    config_path = init_config(tmp_path / "settings.toml")
    text = config_path.read_text("utf-8")
    start = text.index("collect_path = ")
    end = text.index("\n", start)
    config_path.write_text(text[:start] + "collect_path = 'here.jsonl'" + text[end:])

    with pytest.raises(ConfigError) as error:
        load_config(config_path)

    assert error.value.problem_details["invalid_value"] == "privacy.collect_path"


def _set(text: str, table: str, key: str, value: str | None) -> str:
    """Replace (or with ``None`` drop) ``key`` of ``[table]`` in a rendered config."""
    lines = text.splitlines()
    current = ""
    for index, line in enumerate(lines):
        if line.startswith("["):
            current = line.strip("[]")
        elif current == table and line.startswith(f"{key} = "):
            lines[index] = f"{key} = {value}" if value is not None else ""
            return "\n".join(lines) + "\n"
    raise AssertionError(f"{table}.{key} is not in the template")


def _load(tmp_path: Path, text: str):
    path = tmp_path / "retman.toml"
    path.write_text(text, encoding="utf-8")
    return load_config(path)


def _quoted(path: Path) -> str:
    return f"'{path}'"


def test_init_writes_both_tool_stores_in_full_next_to_each_other(tmp_path: Path):
    stores = tmp_path / "data"

    config = load_config(init_config(tmp_path / "retman.toml", stores_dir=stores))
    kartograf = config.tools["kartograf"]
    imgwtools = config.tools["imgwtools"]

    assert kartograf["store_dir"] == str(stores / "kartograf")
    assert imgwtools["store_dir"] == str(stores / "imgwtools")
    assert kartograf["workers"] == 4
    assert kartograf["update"] == "local"
    # Cache and reference files stay on the local disk, outside the shared stores
    for path in (kartograf["cache_file"], imgwtools["reference_data_dir"]):
        assert Path(path).is_absolute()
        assert not Path(path).is_relative_to(stores)
    # No hidden defaults (N-11): the paths are in the file
    assert str(stores / "kartograf") in (tmp_path / "retman.toml").read_text("utf-8")


def test_init_writes_a_folder_that_needs_quoting_as_valid_toml(tmp_path: Path):
    stores = tmp_path / "O'Brien" / "data"

    config = load_config(init_config(tmp_path / "retman.toml", stores_dir=stores))

    assert config.tools["kartograf"]["store_dir"] == str(stores / "kartograf")


def test_config_without_tool_stores_is_rejected_asking_to_regenerate_it(tmp_path: Path):
    old = config_template(stores_dir=tmp_path / "data")
    old = old.replace("[tools.kartograf]", "[x]").replace("[tools.imgwtools]", "[y]")

    with pytest.raises(ConfigError) as error:
        _load(tmp_path, old)

    assert error.value.problems == ["missing_tools"]
    assert error.value.problem_details["missing_tools"] == (
        "tools.kartograf, tools.imgwtools"
    )
    texts = load_core_texts("pl")
    message = texts.get(
        "config.missing_tools",
        path=error.value.path,
        keys=error.value.problem_details["missing_tools"],
    )
    assert "retman init" in message


def test_missing_tool_setting_is_reported_with_its_key(tmp_path: Path):
    text = _set(
        config_template(stores_dir=tmp_path), "tools.kartograf", "workers", None
    )

    with pytest.raises(ConfigError) as error:
        _load(tmp_path, text)

    assert error.value.problems == ["missing_key"]
    assert error.value.problem_details["missing_key"] == "tools.kartograf.workers"


@pytest.mark.parametrize(
    ("table", "key", "value"),
    [
        ("tools.kartograf", "store_dir", "'relative/store'"),
        ("tools.kartograf", "store_dir", "'/data/../elsewhere'"),
        ("tools.kartograf", "store_dir", "''"),
        ("tools.kartograf", "cache_file", "'cache.db'"),
        ("tools.kartograf", "workers", "0"),
        ("tools.kartograf", "workers", "true"),
        ("tools.kartograf", "workers", "'4'"),
        # "check" only reports what is stale and never downloads
        ("tools.kartograf", "update", "'check'"),
        ("tools.kartograf", "update", "'sometimes'"),
        ("tools.imgwtools", "store_dir", "'imgw'"),
        ("tools.imgwtools", "reference_data_dir", "'../reference'"),
    ],
)
def test_invalid_tool_setting_is_reported_with_its_key(
    tmp_path: Path, table: str, key: str, value: str
):
    text = _set(config_template(stores_dir=tmp_path), table, key, value)

    with pytest.raises(ConfigError) as error:
        _load(tmp_path, text)

    assert error.value.problems == ["invalid_value"]
    assert error.value.problem_details["invalid_value"] == f"{table}.{key}"


@pytest.mark.parametrize("update", ["local", "upgrade", "force"])
def test_every_update_mode_of_a_download_is_accepted(tmp_path: Path, update: str):
    text = _set(
        config_template(stores_dir=tmp_path), "tools.kartograf", "update", f"'{update}'"
    )

    assert _load(tmp_path, text).tools["kartograf"]["update"] == update


@pytest.mark.parametrize(
    ("table", "key", "folder"),
    [
        # the same folder, inside the other store and around it
        ("tools.imgwtools", "store_dir", "data/kartograf"),
        ("tools.imgwtools", "store_dir", "data/kartograf/imgwtools"),
        ("tools.imgwtools", "store_dir", "data"),
        # the cache and the reference files are not store content
        ("tools.kartograf", "cache_file", "data/kartograf/cache.db"),
        ("tools.imgwtools", "reference_data_dir", "data/imgwtools/reference"),
    ],
)
def test_stores_must_be_siblings_and_hold_nothing_but_their_data(
    tmp_path: Path, table: str, key: str, folder: str
):
    text = _set(
        config_template(stores_dir=tmp_path / "data"),
        table,
        key,
        _quoted(tmp_path / folder),
    )

    with pytest.raises(ConfigError) as error:
        _load(tmp_path, text)

    assert error.value.problems == ["paths_overlap"]
    assert f"{table}.{key}" in error.value.problem_details["paths_overlap"]
    message = load_core_texts("pl").get(
        "config.paths_overlap",
        path=error.value.path,
        keys=error.value.problem_details["paths_overlap"],
    )
    assert str(error.value.path) in message


def test_folders_with_a_common_name_prefix_are_not_nested(tmp_path: Path):
    text = _set(
        config_template(stores_dir=tmp_path / "data"),
        "tools.imgwtools",
        "store_dir",
        _quoted(tmp_path / "data" / "kartograf-2"),
    )

    config = _load(tmp_path, text)

    assert config.tools["imgwtools"]["store_dir"] == str(
        tmp_path / "data" / "kartograf-2"
    )

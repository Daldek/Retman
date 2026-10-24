"""The settings of Retman: defaults, the model server, ``config init``, checks."""

import tomllib
from pathlib import Path

import pytest

from retman import Retman
from retman.config import (
    config_template,
    init_config,
    load_config,
    load_settings,
)
from retman.environment import BY_NAME, KEYS, environment
from retman.exceptions import ConfigError
from retman.i18n.loader import load_core_texts
from retman.testing import FakeDecisionBackend

MODEL = {
    "RETMAN_DECISION_BACKEND": "openai_compatible",
    "RETMAN_DECISION_URL": "http://127.0.0.1:1234/v1",
    "RETMAN_DECISION_MODEL": "bielik",
    "RETMAN_DECISION_TIMEOUT_S": "30",
    "RETMAN_DECISION_CONFIDENCE": "consistency",
    "RETMAN_DECISION_CONSISTENCY_RUNS": "3",
    "RETMAN_DECISION_THRESHOLDS_OPERATION": "0.9",
    "RETMAN_DECISION_THRESHOLDS_PARAMETER": "0.8",
}


def write(folder: Path, text: str, name: str = "nogat.toml") -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def flatten(table: dict[str, object], prefix: str = "") -> set[str]:
    names: set[str] = set()
    for key, value in table.items():
        if isinstance(value, dict):
            names |= flatten(value, f"{prefix}{key}.")
        else:
            names.add(f"{prefix}{key}")
    return names


def test_without_any_file_the_settings_follow_the_user_folders(
    user_environment: Path,
) -> None:
    settings = load_settings()

    kartograf = settings.tools["kartograf"]
    imgwtools = settings.tools["imgwtools"]
    assert kartograf["store_dir"] == str(user_environment / "data" / "kartograf")
    assert kartograf["cache_file"] == str(
        user_environment / "cache" / "kartograf" / "metadata.db"
    )
    assert imgwtools["store_dir"] == str(user_environment / "data" / "imgw")
    assert imgwtools["reference_data_dir"] == str(
        user_environment / "cache" / "imgw" / "reference"
    )
    assert settings.collect_path == user_environment / "data" / "retman" / (
        "collected.jsonl"
    )
    assert (kartograf["workers"], kartograf["update"]) == (4, "local")
    assert settings.path == user_environment / "config" / "nogat.toml"
    assert settings.results_dir == "retman-output"
    assert (settings.language, settings.log_level) == ("pl", "warning")
    assert settings.journal_commands is True
    assert settings.collect_commands is False
    assert settings.enabled_tools is None


def test_a_shared_data_directory_moves_both_stores_and_the_collection(
    tmp_path: Path,
) -> None:
    file = write(tmp_path, f'[nogat]\ndata_dir = "{tmp_path / "shared"}"\n')

    settings = load_settings(file)

    assert settings.tools["kartograf"]["store_dir"] == str(
        tmp_path / "shared/kartograf"
    )
    assert settings.tools["imgwtools"]["store_dir"] == str(tmp_path / "shared/imgw")
    assert settings.collect_path == tmp_path / "shared" / "retman" / "collected.jsonl"


def test_a_language_without_texts_is_shown_in_polish() -> None:
    settings = load_settings(environ={"NOGAT_LANG": "en"})

    assert settings.language == "pl"


def test_the_model_server_has_no_default_and_the_error_lists_what_is_missing() -> None:
    with pytest.raises(ConfigError) as error:
        load_config()

    assert error.value.problems == ["missing_key"]
    missing = error.value.problem_details["missing_key"].split(", ")
    assert "decision.url" in missing
    assert "decision.thresholds.operation" in missing
    # A command that needs no model works without the section
    assert load_settings().language == "pl"


def test_the_model_server_can_be_set_by_variables_alone() -> None:
    config = load_config(environ=MODEL)

    decision = config.decision
    assert (decision.backend, decision.url, decision.model) == (
        "openai_compatible",
        "http://127.0.0.1:1234/v1",
        "bielik",
    )
    assert (decision.timeout_s, decision.consistency_runs) == (30.0, 3)
    assert decision.thresholds.operation == 0.9
    assert decision.api_key_env is None


def test_a_variable_wins_over_the_file(tmp_path: Path) -> None:
    file = init_config(tmp_path / "nogat.toml")

    config = load_config(file, environ={"RETMAN_DECISION_URL": "http://other:1/v1"})

    assert config.decision.url == "http://other:1/v1"
    assert config.decision.model == "basal-1.5-mini"


def test_openai_compatible_needs_the_confidence_method_and_the_runs() -> None:
    environ = {
        key: value
        for key, value in MODEL.items()
        if key not in ("RETMAN_DECISION_CONFIDENCE", "RETMAN_DECISION_CONSISTENCY_RUNS")
    }

    with pytest.raises(ConfigError) as error:
        load_config(environ=environ)

    assert error.value.problem_details["missing_key"] == (
        "decision.confidence, decision.consistency_runs"
    )


def test_auto_thresholds_are_for_basal_only() -> None:
    environ = MODEL | {"RETMAN_DECISION_THRESHOLDS_OPERATION": "auto"}

    with pytest.raises(ConfigError) as error:
        load_config(environ=environ)
    ignored = load_config(environ=environ | {"RETMAN_DECISION_CONFIDENCE": "none"})

    assert error.value.problems == ["auto_threshold_without_basal"]
    assert ignored.decision.thresholds.operation == "auto"


def test_from_config_injected_backend_uses_explicit_project_folder(
    tmp_path: Path,
) -> None:
    config_path = init_config(tmp_path / "settings.toml")
    project = tmp_path / "project"
    project.mkdir()

    app = Retman.from_config(
        config_path, backend=FakeDecisionBackend(), project_dir=project
    )

    assert app.workspace.root == project / load_config(config_path).results_dir
    assert not app.workspace.root.exists()


@pytest.mark.parametrize("directory", ["/elsewhere", "../outside", "nested/../outside"])
def test_results_folder_must_stay_inside_the_project(
    tmp_path: Path, directory: str
) -> None:
    file = write(tmp_path, f'[retman.output]\nresults_dir = "{directory}"\n')

    with pytest.raises(ConfigError) as error:
        load_settings(file)

    assert error.value.problem_details["invalid_value"] == "output.results_dir"


def test_every_problem_of_the_values_is_reported_at_once(tmp_path: Path) -> None:
    file = write(
        tmp_path,
        '[retman]\nlog_level = "loud"\n[retman.tools.kartograf]\nworkers = 0\n',
    )

    with pytest.raises(ConfigError) as error:
        load_settings(file, environ={"RETMAN_PRIVACY_COLLECT_PATH": "here.jsonl"})

    assert error.value.problems == ["invalid_value"]
    assert error.value.problem_details["invalid_value"].split(", ") == [
        "log_level",
        "tools.kartograf.workers",
        "privacy.collect_path (RETMAN_PRIVACY_COLLECT_PATH)",
    ]


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        (b"[retman\n", "invalid_toml"),
        (b"\xff\xfe\x00", "unreadable_file"),
        (b'retman = "text"\n', "invalid_section"),
    ],
)
def test_a_file_that_cannot_be_used_stops_every_command(
    tmp_path: Path, content: bytes, problem: str
) -> None:
    path = tmp_path / "nogat.toml"
    path.write_bytes(content)

    with pytest.raises(ConfigError) as settings:
        load_settings(path)
    with pytest.raises(ConfigError) as config:
        load_config(path, environ=MODEL)

    assert settings.value.problems == [problem]
    assert settings.value.problem_details["error"]
    assert config.value.problems == [problem]


def test_a_named_file_that_does_not_exist_is_not_found(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as error:
        load_settings(tmp_path / "missing.toml")

    assert error.value.problems == ["missing_file"]
    assert error.value.code == "not_found"


def test_init_writes_the_users_collection_answer_and_full_path(tmp_path: Path) -> None:
    agreed = load_config(
        init_config(tmp_path / "yes.toml", collect_commands=True), environ=MODEL
    )
    refused = load_config(init_config(tmp_path / "no.toml"), environ=MODEL)

    assert agreed.collect_commands is True
    assert refused.collect_commands is False
    # The path is written out in the file: no hidden default (N-11)
    assert agreed.collect_path.is_absolute()
    assert str(agreed.collect_path) in (tmp_path / "yes.toml").read_text("utf-8")


def test_init_writes_both_tool_stores_in_full_next_to_each_other(
    tmp_path: Path,
) -> None:
    stores = tmp_path / "data"

    config = load_config(init_config(tmp_path / "nogat.toml", stores_dir=stores))
    kartograf = config.tools["kartograf"]
    imgwtools = config.tools["imgwtools"]

    assert kartograf["store_dir"] == str(stores / "kartograf")
    assert imgwtools["store_dir"] == str(stores / "imgw")
    assert kartograf["workers"] == 4
    assert kartograf["update"] == "local"
    # Cache and reference files stay on the local disk, outside the shared stores
    for path in (kartograf["cache_file"], imgwtools["reference_data_dir"]):
        assert Path(path).is_absolute()
        assert not Path(path).is_relative_to(stores)
    # No hidden defaults (N-11): the paths are in the file
    assert str(stores / "kartograf") in (tmp_path / "nogat.toml").read_text("utf-8")


def test_init_writes_a_folder_that_needs_quoting_as_valid_toml(tmp_path: Path) -> None:
    stores = tmp_path / "O'Brien" / "data"

    config = load_config(init_config(tmp_path / "nogat.toml", stores_dir=stores))

    assert config.tools["kartograf"]["store_dir"] == str(stores / "kartograf")


def test_init_appends_to_a_file_of_other_tools_and_leaves_it_as_it_was(
    tmp_path: Path,
) -> None:
    before = '[nogat]\nlang = "en"\n\n[kartograf]\nroot = "/k"'
    file = write(tmp_path, before)

    init_config(file)

    text = file.read_text("utf-8")
    assert text.startswith(before + "\n\n")
    parsed = tomllib.loads(text)
    assert parsed["nogat"] == {"lang": "en"}
    assert parsed["kartograf"] == {"root": "/k"}
    assert parsed["retman"]["decision"]["backend"] == "basal"
    assert load_config(file).decision.model == "basal-1.5-mini"


@pytest.mark.parametrize("existing", ["[retman]\n", '[retman.decision]\nurl = "x"\n'])
def test_init_never_overwrites_a_retman_table(tmp_path: Path, existing: str) -> None:
    file = write(tmp_path, '[nogat]\nlang = "pl"\n' + existing)
    before = file.read_text("utf-8")

    with pytest.raises(ConfigError) as error:
        init_config(file)

    assert error.value.problems == ["already_exists"]
    assert error.value.code == "conflict"
    assert file.read_text("utf-8") == before


def test_init_does_not_append_to_a_file_it_cannot_read_as_toml(tmp_path: Path) -> None:
    file = write(tmp_path, "[nogat\n")

    with pytest.raises(ConfigError) as error:
        init_config(file)

    assert error.value.problems == ["invalid_toml"]
    assert file.read_text("utf-8") == "[nogat\n"


def test_init_creates_the_folder_of_the_file(tmp_path: Path) -> None:
    target = tmp_path / "new" / "folder" / "nogat.toml"

    assert init_config(target) == target
    assert target.is_file()


def test_the_template_names_only_known_keys_and_every_key_with_a_default() -> None:
    parsed = tomllib.loads(config_template(env=environment(environ={})))

    written = flatten(parsed["retman"])

    assert written <= set(BY_NAME)
    # What has a default, and the model server, is written out (no hidden default);
    # the shared keys are left to [nogat], and the rest is a commented example
    server = {
        "decision.backend",
        "decision.url",
        "decision.model",
        "decision.timeout_s",
        "decision.thresholds.operation",
        "decision.thresholds.parameter",
    }
    defaulted = {key.name for key in KEYS if key.default and not key.shared}
    assert defaulted | server <= written


@pytest.mark.parametrize(
    ("key", "folder"),
    [
        # the same folder, inside the other store and around it
        ("tools.imgwtools.store_dir", "data/kartograf"),
        ("tools.imgwtools.store_dir", "data/kartograf/imgw"),
        ("tools.imgwtools.store_dir", "data"),
        # the cache and the reference files are not store content
        ("tools.kartograf.cache_file", "data/kartograf/cache.db"),
        ("tools.imgwtools.reference_data_dir", "data/imgw/reference"),
    ],
)
def test_stores_must_be_siblings_and_hold_nothing_but_their_data(
    user_environment: Path, key: str, folder: str
) -> None:
    environ = {BY_NAME[key].variable: str(user_environment / folder)}

    with pytest.raises(ConfigError) as error:
        load_settings(environ=environ)

    assert error.value.problems == ["paths_overlap"]
    assert key in error.value.problem_details["paths_overlap"]
    message = load_core_texts("pl").get(
        "config.paths_overlap",
        path=error.value.path,
        keys=error.value.problem_details["paths_overlap"],
    )
    assert str(error.value.path) in message


def test_folders_with_a_common_name_prefix_are_not_nested(tmp_path: Path) -> None:
    file = write(
        tmp_path,
        f"[retman.tools.kartograf]\nstore_dir = '{tmp_path / 'data/kartograf'}'\n"
        f"[retman.tools.imgwtools]\nstore_dir = '{tmp_path / 'data/kartograf-2'}'\n",
    )

    settings = load_settings(file)

    assert settings.tools["imgwtools"]["store_dir"] == str(
        tmp_path / "data" / "kartograf-2"
    )


@pytest.mark.parametrize("update", ["local", "upgrade", "force"])
def test_every_update_mode_of_a_download_is_accepted(update: str) -> None:
    settings = load_settings(environ={"RETMAN_TOOLS_KARTOGRAF_UPDATE": update})

    assert settings.tools["kartograf"]["update"] == update


def test_check_is_not_an_update_mode() -> None:
    # "check" only reports what is stale and never downloads
    with pytest.raises(ConfigError):
        load_settings(environ={"RETMAN_TOOLS_KARTOGRAF_UPDATE": "check"})

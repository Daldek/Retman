"""Where a setting comes from: option, variables, ``nogat.toml``, default (DEV-18.1)."""

from pathlib import Path

import pytest

from retman.environment import (
    BY_NAME,
    KEYS,
    ConfigFile,
    environment,
    read_config_file,
)


def write(folder: Path, text: str, name: str = "nogat.toml") -> Path:
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def test_every_variable_name_is_distinct_and_in_the_namespace_of_retman() -> None:
    names = [key.variable for key in KEYS]

    assert len(set(names)) == len(names)
    assert all(name.startswith("RETMAN_") for name in names)
    # The dotted key in capitals with underscores
    assert BY_NAME["decision.url"].variable == "RETMAN_DECISION_URL"
    assert BY_NAME["log_level"].variable == "RETMAN_LOG_LEVEL"


def test_a_setting_without_any_source_has_its_default_and_says_so(
    user_environment: Path,
) -> None:
    setting = environment(environ={}).setting("tools.kartograf.store_dir")

    assert setting.value == user_environment / "data" / "kartograf"
    assert (setting.source, setting.name, setting.error) == ("default", None, None)


def test_the_model_server_has_no_default(user_environment: Path) -> None:
    env = environment(environ={})

    assert [
        env.setting(name).value
        for name in ("decision.backend", "decision.url", "decision.model")
    ] == [None, None, None]


def test_layers_in_the_order_of_the_standard(tmp_path: Path) -> None:
    file = write(
        tmp_path,
        '[nogat]\nlang = "en"\n\n[retman]\nlang = "pl"\nlog_level = "info"\n',
    )

    def lang(environ: dict[str, str], *, with_file: bool = True) -> tuple[str, str]:
        env = environment(file if with_file else None, environ)
        setting = env.setting("lang")
        return setting.value, str(setting.name)

    assert lang({"RETMAN_LANG": "en", "NOGAT_LANG": "pl"}) == ("en", "RETMAN_LANG")
    assert lang({"NOGAT_LANG": "en"}) == ("en", "NOGAT_LANG")
    assert lang({}) == ("pl", "[retman]")
    only_shared = write(tmp_path, '[nogat]\nlang = "en"\n', "shared.toml")
    assert environment(only_shared, {}).setting("lang").name == "[nogat]"
    assert lang({}, with_file=False) == ("pl", "None")


def test_only_the_shared_keys_are_read_from_nogat_variables_and_table(
    tmp_path: Path,
) -> None:
    file = write(
        tmp_path,
        '[nogat]\ndata_dir = "/shared/data"\nlog_level = "error"\n'
        '[nogat.decision]\nurl = "http://wrong"\n',
    )
    env = environment(file, {"NOGAT_DECISION_URL": "http://wrong"})

    assert env.setting("data_dir").value == Path("/shared/data")
    assert env.setting("log_level").value == "error"
    assert env.setting("decision.url").value is None


def test_an_empty_variable_counts_as_unset(tmp_path: Path) -> None:
    file = write(tmp_path, '[retman]\nlog_level = "debug"\n')

    setting = environment(file, {"RETMAN_LOG_LEVEL": "  "}).setting("log_level")

    assert (setting.value, setting.source) == ("debug", "file")


def test_nested_keys_are_read_from_their_tables(tmp_path: Path) -> None:
    file = write(
        tmp_path,
        "[retman.decision.thresholds]\noperation = 0.9\n"
        '[retman.tools.kartograf]\nupdate = "upgrade"\n',
    )
    env = environment(file, {})

    assert env.setting("decision.thresholds.operation").name == (
        "[retman.decision.thresholds]"
    )
    assert env.setting("decision.thresholds.operation").value == 0.9
    assert env.setting("tools.kartograf.update").value == "upgrade"


def test_a_value_that_cannot_be_used_is_dropped_and_explained(tmp_path: Path) -> None:
    file = write(tmp_path, '[retman.output]\nresults_dir = "/elsewhere"\n')

    setting = environment(file, {}).setting("output.results_dir")

    assert setting.value == "retman-output"
    assert setting.source == "default"
    assert setting.error is not None
    assert "[retman.output] results_dir" in setting.error
    assert setting.given is not None and setting.given.value == "/elsewhere"


@pytest.mark.parametrize(
    ("key", "raw"),
    [
        ("log_level", "loud"),
        ("lang", "de"),
        ("decision.timeout_s", "0"),
        ("decision.timeout_s", "nan"),
        ("decision.timeout_s", "soon"),
        ("decision.consistency_runs", "2.5"),
        ("decision.thresholds.operation", "1.5"),
        ("decision.thresholds.operation", "high"),
        ("tools.kartograf.workers", "-1"),
        ("tools.kartograf.store_dir", "relative/store"),
        ("tools.kartograf.store_dir", "/data/../elsewhere"),
        ("log.journal_commands", "maybe"),
        ("adapters.enabled", "kartograf,,imgwtools"),
    ],
)
def test_a_bad_variable_is_reported_with_the_variable_name(key: str, raw: str) -> None:
    variable = BY_NAME[key].variable

    setting = environment(environ={variable: raw}).setting(key)

    assert setting.error is not None
    assert variable in setting.error
    assert setting.source == "default"


@pytest.mark.parametrize(
    ("key", "raw", "expected"),
    [
        ("log_level", " DeBug ", "debug"),
        ("decision.timeout_s", "7.5", 7.5),
        ("decision.consistency_runs", "3", 3),
        ("decision.thresholds.operation", "0.85", 0.85),
        ("decision.thresholds.parameter", "AUTO", "auto"),
        ("log.journal_commands", "No", False),
        ("privacy.collect_commands", "1", True),
        ("adapters.enabled", "kartograf, imgwtools", ("kartograf", "imgwtools")),
        ("tools.kartograf.store_dir", "/data/k", Path("/data/k")),
    ],
)
def test_a_variable_is_parsed_to_the_kind_of_its_key(
    key: str, raw: str, expected: object
) -> None:
    setting = environment(environ={BY_NAME[key].variable: raw}).setting(key)

    assert (setting.value, setting.source) == (expected, "env")


@pytest.mark.parametrize(
    ("key", "toml_value"),
    [
        ("decision.timeout_s", '"30"'),
        ("tools.kartograf.workers", "2.0"),
        ("log.journal_commands", '"true"'),
        ("adapters.enabled", '"kartograf"'),
        ("decision.thresholds.operation", "true"),
    ],
)
def test_a_value_of_the_file_must_already_have_the_type_of_its_key(
    tmp_path: Path, key: str, toml_value: str
) -> None:
    table, _, name = key.rpartition(".")
    file = write(tmp_path, f"[retman.{table}]\n{name} = {toml_value}\n")

    assert environment(file, {}).setting(key).error is not None


def test_the_file_of_the_option_wins_over_nogat_config(tmp_path: Path) -> None:
    named = write(tmp_path, '[retman]\nlang = "en"\n', "named.toml")
    other = write(tmp_path, '[retman]\nlang = "pl"\n', "other.toml")
    environ = {"NOGAT_CONFIG": str(other)}

    by_option = read_config_file(named, environ)
    by_variable = read_config_file(None, environ)

    assert (by_option.path, by_option.source) == (named, "option")
    assert (by_variable.path, by_variable.source) == (other, "NOGAT_CONFIG")


def test_a_missing_default_file_is_no_problem_but_a_named_one_is(
    user_environment: Path, tmp_path: Path
) -> None:
    default = read_config_file(None, {})
    named = read_config_file(tmp_path / "missing.toml", {})

    assert default.path == user_environment / "config" / "nogat.toml"
    assert (default.exists, default.problem) == (False, None)
    assert (named.exists, named.problem) == (False, "missing_file")


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        (b"[retman\n", "invalid_toml"),
        (b"\xff\xfe\x00", "unreadable_file"),
        (b'retman = "text"\n', "invalid_section"),
    ],
)
def test_a_file_that_cannot_be_used_says_why_and_gives_no_values(
    tmp_path: Path, content: bytes, problem: str
) -> None:
    path = tmp_path / "nogat.toml"
    path.write_bytes(content)

    file = read_config_file(path, {})

    assert isinstance(file, ConfigFile)
    assert (file.problem, file.sections) == (problem, {})
    assert file.error


def test_a_directory_as_the_file_is_unreadable(tmp_path: Path) -> None:
    assert read_config_file(tmp_path, {}).problem == "unreadable_file"


def test_the_tables_of_other_tools_are_not_read(tmp_path: Path) -> None:
    file = write(tmp_path, '[kartograf]\nroot = "/k"\n[retman]\nlang = "en"\n')

    assert set(read_config_file(file, {}).sections) == {"retman"}

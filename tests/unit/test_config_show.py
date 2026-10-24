"""``retman config show``: every setting with its value and source (DEV-18.6)."""

import json
import os
from pathlib import Path

from retman import __version__
from retman.config_show import get_config, render_config
from retman.environment import KEYS
from retman.i18n.loader import load_core_texts


def write(folder: Path, text: str) -> Path:
    path = folder / "nogat.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_report_lists_every_setting_in_the_order_of_the_key_table(
    user_environment: Path,
) -> None:
    document = get_config(environ={}).to_dict()

    assert document["schema"] == "retman-config/1"
    assert (document["tool"], document["version"]) == ("retman", __version__)
    assert list(document["keys"]) == [key.name for key in KEYS]
    assert document["keys"]["lang"] == {
        "value": "pl",
        "source": "default",
        "name": None,
        "error": None,
    }
    assert document["keys"]["decision.url"]["value"] is None
    assert document["config_file"] == {
        "path": str(user_environment / "config" / "nogat.toml"),
        "source": "default",
        "exists": False,
        "error": None,
        "ignored": [],
    }
    json.dumps(document)  # plain JSON values only


def test_each_value_names_the_layer_that_gave_it(tmp_path: Path) -> None:
    file = write(tmp_path, '[retman.decision]\nurl = "http://file/v1"\n')
    environ = {"RETMAN_LOG_LEVEL": "debug", "NOGAT_DATA_DIR": str(tmp_path / "data")}

    keys = get_config(file, environ=environ).to_dict()["keys"]

    assert keys["decision.url"]["source"] == "file"
    assert keys["decision.url"]["name"] == "[retman.decision]"
    assert keys["log_level"]["name"] == "RETMAN_LOG_LEVEL"
    assert keys["data_dir"]["value"] == str(tmp_path / "data")
    assert keys["data_dir"]["name"] == "NOGAT_DATA_DIR"
    # A path that follows data_dir is a default, but it follows the value in force
    assert keys["tools.kartograf.store_dir"] == {
        "value": str(tmp_path / "data" / "kartograf"),
        "source": "default",
        "name": None,
        "error": None,
    }


def test_a_value_that_cannot_be_used_is_reported_not_raised(tmp_path: Path) -> None:
    file = write(tmp_path, '[retman]\nlog_level = "loud"\n')

    entry = get_config(file, environ={}).to_dict()["keys"]["log_level"]

    assert (entry["value"], entry["source"]) == ("warning", "default")
    assert "[retman] log_level" in entry["error"]


def test_a_file_that_cannot_be_used_is_reported_so_that_it_can_be_repaired(
    tmp_path: Path,
) -> None:
    file = write(tmp_path, "[retman\n")

    document = get_config(file, environ={}).to_dict()

    assert document["config_file"]["exists"] is True
    assert "TOML" in document["config_file"]["error"]
    assert document["keys"]["lang"]["value"] == "pl"


def test_a_missing_file_that_was_named_is_an_error_of_the_report(
    tmp_path: Path,
) -> None:
    document = get_config(tmp_path / "none.toml", environ={}).to_dict()

    assert document["config_file"]["source"] == "option"
    assert document["config_file"]["exists"] is False
    assert document["config_file"]["error"]


def test_keys_that_nothing_reads_are_listed_and_credentials_are_named_as_such(
    tmp_path: Path,
) -> None:
    file = write(
        tmp_path,
        '[retman]\nspeed = 3\n[retman.decision]\napi_key = "x"\nurl = "u"\n'
        "[retman.extra.deeper]\nflag = true\n[retman.decision.thresholds]\n"
        "operation = 0.9\n",
    )

    ignored = get_config(file, environ={}).to_dict()["config_file"]["ignored"]

    assert ignored == [
        {"key": "speed", "reason": "unknown"},
        {"key": "decision.api_key", "reason": "credential"},
        {"key": "extra.deeper.flag", "reason": "unknown"},
    ]


def test_a_credential_is_reported_as_present_or_missing_and_never_by_value(
    tmp_path: Path,
) -> None:
    file = write(tmp_path, '[retman.decision]\napi_key_env = "PROVIDER_API_KEY"\n')
    secret = "s3cret-value"

    present = get_config(file, environ={"PROVIDER_API_KEY": secret})
    missing = get_config(file, environ={})

    assert present.to_dict()["credentials"] == {"PROVIDER_API_KEY": "present"}
    assert missing.to_dict()["credentials"] == {"PROVIDER_API_KEY": "missing"}
    texts = load_core_texts("pl")
    assert secret not in present.to_json() + render_config(present, texts)
    assert get_config(environ={}).to_dict()["credentials"] == {}


def test_retman_has_no_store_of_its_own_and_reports_the_stores_of_the_tools(
    user_environment: Path,
) -> None:
    kartograf = user_environment / "data" / "kartograf"
    (kartograf / "versions").mkdir(parents=True)
    (kartograf / "versions" / "a.bin").write_bytes(b"x" * 100)
    os.link(kartograf / "versions" / "a.bin", kartograf / "current.bin")

    document = get_config(environ={}).to_dict()

    assert document["store"] == {
        "root": None,
        "source": None,
        "name": None,
        "exists": False,
        "size_bytes": None,
    }
    # A hard-linked file is counted once
    assert document["stores"]["kartograf"] == {
        "root": str(kartograf),
        "source": "default",
        "name": None,
        "exists": True,
        "size_bytes": 100,
    }
    assert document["stores"]["imgwtools"]["exists"] is False
    assert document["stores"]["imgwtools"]["size_bytes"] is None


def test_the_text_report_shows_each_key_with_its_source() -> None:
    report = get_config(environ={"RETMAN_LOG_LEVEL": "info"})

    text = render_config(report, load_core_texts("pl"))

    assert "log_level = info" in text
    assert "RETMAN_LOG_LEVEL" in text
    assert all(key.name in text for key in KEYS)

"""Log level of the command line and its handler (DEV-12.2, DEV-18.1)."""

import io
import logging
from pathlib import Path

from retman.environment import cli_options, environment
from retman.logs import configure_logging


def test_the_level_without_a_source_is_warning() -> None:
    assert environment(environ={}).setting("log_level").value == "warning"


def test_the_options_win_over_the_configured_level(tmp_path: Path) -> None:
    file = tmp_path / "nogat.toml"
    file.write_text('[retman]\nlog_level = "warning"\n', encoding="utf-8")

    def level(*, verbose: bool = False, quiet: bool = False) -> str:
        options = cli_options(verbose=verbose, quiet=quiet)
        return str(environment(file, {}, options).setting("log_level").value)

    assert level(verbose=True) == "debug"
    assert level(quiet=True) == "error"
    assert level() == "warning"


def test_the_configured_level_is_the_setting_of_the_environment(tmp_path: Path) -> None:
    file = tmp_path / "nogat.toml"
    file.write_text('[nogat]\nlog_level = "error"\n', encoding="utf-8")

    def configured(environ: dict[str, str]) -> str:
        return str(environment(file, environ).setting("log_level").value)

    # The variable of Retman, then the one the Nogat tools share, then the file
    assert configured({"RETMAN_LOG_LEVEL": "info", "NOGAT_LOG_LEVEL": "debug"}) == (
        "info"
    )
    assert configured({"NOGAT_LOG_LEVEL": " DeBug "}) == "debug"
    assert configured({}) == "error"


def test_configure_logging_sends_library_records_to_the_stream_at_the_level() -> None:
    stream = io.StringIO()

    configure_logging("info", stream)
    logging.getLogger("retman.core.pipeline").debug("hidden")
    logging.getLogger("retman.core.pipeline").info("shown %d", 1)

    assert stream.getvalue() == "INFO retman.core.pipeline: shown 1\n"


def test_configure_logging_twice_keeps_one_handler() -> None:
    first, second = io.StringIO(), io.StringIO()

    configure_logging("warning", first)
    configure_logging("debug", second)
    logging.getLogger("retman.config").debug("once")

    assert first.getvalue() == ""
    assert second.getvalue().count("once") == 1

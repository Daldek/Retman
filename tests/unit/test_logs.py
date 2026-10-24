"""Log level of the command line and its handler (DEV-12.2, DEV-18.1)."""

import io
import logging
from pathlib import Path

import pytest

from retman.environment import environment
from retman.exceptions import UsageError
from retman.logs import configure_logging, resolve_level


def test_resolve_level_without_a_source_is_warning() -> None:
    assert resolve_level(verbose=False, quiet=False) == "warning"


def test_the_options_win_over_the_configured_level() -> None:
    assert resolve_level(verbose=True, quiet=False, configured="warning") == "debug"
    assert resolve_level(verbose=False, quiet=True, configured="debug") == "error"
    assert resolve_level(verbose=False, quiet=False, configured="info") == "info"


def test_resolve_level_rejects_both_options() -> None:
    with pytest.raises(UsageError, match="--verbose"):
        resolve_level(verbose=True, quiet=True)


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

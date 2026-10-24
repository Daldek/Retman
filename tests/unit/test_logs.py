"""Log level precedence and the handler of the command line (DEV-12.2, DEV-18.1)."""

import io
import logging
from collections.abc import Mapping

import pytest

from retman.exceptions import UsageError
from retman.logs import configure_logging, resolve_level


def level(
    *,
    verbose: bool = False,
    quiet: bool = False,
    environ: Mapping[str, str] | None = None,
    configured: str | None = None,
) -> str:
    return resolve_level(
        verbose=verbose, quiet=quiet, environ=environ or {}, configured=configured
    )


def test_resolve_level_without_a_source_is_warning() -> None:
    assert level() == "warning"


def test_resolve_level_takes_the_first_source_that_sets_it() -> None:
    both = {"RETMAN_LOG_LEVEL": "info", "NOGAT_LOG_LEVEL": "error"}

    assert level(verbose=True, environ=both, configured="warning") == "debug"
    assert level(quiet=True, environ=both, configured="debug") == "error"
    assert level(environ=both, configured="debug") == "info"
    assert level(environ={"NOGAT_LOG_LEVEL": "error"}, configured="debug") == "error"
    assert level(configured="debug") == "debug"


def test_resolve_level_reads_the_environment_in_any_case() -> None:
    assert level(environ={"RETMAN_LOG_LEVEL": " DeBug "}) == "debug"


def test_resolve_level_rejects_both_options() -> None:
    with pytest.raises(UsageError, match="--verbose"):
        level(verbose=True, quiet=True)


def test_resolve_level_names_the_variable_and_the_allowed_levels() -> None:
    with pytest.raises(UsageError) as raised:
        level(environ={"RETMAN_LOG_LEVEL": "loud"})

    message = str(raised.value)
    assert "RETMAN_LOG_LEVEL" in message
    assert all(name in message for name in ("debug", "info", "warning", "error"))


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

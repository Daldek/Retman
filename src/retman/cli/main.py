"""The command line ``retman <group> <verb>``: parse, run through the catalog, report.

Every call is one command of the catalog (AGI-3.1): the parser is generated from it
(:mod:`retman.cli.parser`), the command is run by :func:`retman.catalog.execute` and
its result printed by :func:`retman.outcomes.report_outcome` (the envelope with
``--json``, the text of the result otherwise). Only in a terminal, and never with
``--json``, ``plan run`` and ``config init`` ask questions (AGI-3.5).

Exit codes are those of the Nogat registry: ``0``, ``10`` (``partial``) and ``11``
(``failed``) for outcomes that print their result, ``130`` when the user stopped the
call, and the code of the error that ended it; the last line of stderr is then the
``retman-error/1`` document (AGI-3.3).
"""

import contextlib
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from retman.backends.base import DecisionBackend
from retman.catalog import CommandResult, Output, execute, get_command
from retman.cli.conversation import conversation
from retman.cli.parser import build_parser, help_language, options_of
from retman.core.pipeline import Retman
from retman.environment import OptionValue, cli_options, environment
from retman.exceptions import (
    BackendConnectionError,
    ConfigError,
    RetmanError,
    Terminated,
    UsageError,
)
from retman.i18n.loader import Texts, load_core_texts
from retman.initialize import run_init
from retman.logs import configure_logging
from retman.outcomes import (
    EXIT_CANCELLED,
    EXIT_OK,
    report_error,
    report_outcome,
    sigterm_as_exception,
)

logger = logging.getLogger(__name__)


def _config_text(texts: Texts, error: ConfigError) -> str:
    """Return the text for the user: one line per problem of the settings."""
    return "\n".join(
        texts.get(
            f"config.{problem}",
            path=error.path,
            keys=error.problem_details.get(problem, ""),
            error=error.problem_details.get("error", ""),
            backend=error.problem_details.get("backend", "basal"),
        )
        for problem in error.problems
    )


def _session(
    retman: Retman, texts: Texts, *, check: bool, yes: bool, explain: bool
) -> int:
    """Read commands until the user says the end word (a session in a terminal)."""
    while True:
        try:
            command = input(texts.get("cli.command_prompt")).strip()
        except EOFError:
            return EXIT_OK
        if command in texts.lines("answers.end"):
            return EXIT_OK
        if command in texts.lines("answers.cancel"):
            print(texts.get("cli.cancelled"))
            return EXIT_CANCELLED
        if command and (
            conversation(retman, command, texts, check=check, yes=yes, explain=explain)
            == EXIT_CANCELLED
        ):
            return EXIT_CANCELLED


def _dialog(
    command_name: str,
    options: Mapping[str, object],
    backend: DecisionBackend | None,
    project_dir: Path | None,
    overrides: Mapping[str, OptionValue],
    texts: Texts,
) -> int | None:
    """Run the commands that ask questions in a terminal; ``None`` for the others.

    Only ``plan run`` and ``config init`` have a dialog, and only without ``--check``
    for the latter; everything else goes through the catalog alone.
    """
    config = Path(str(options["config"])) if "config" in options else None
    if command_name == "config init" and not options.get("check"):
        stores = options.get("stores_dir")
        collect = options.get("collect_commands")
        return run_init(
            config,
            texts,
            collect_commands=None if collect is None else bool(collect),
            stores_dir=Path(str(stores)) if stores is not None else None,
        )
    if command_name != "plan run":
        return None
    retman = Retman.from_config(
        config, backend=backend, project_dir=project_dir, options=overrides
    )
    flags = {
        "check": bool(options.get("check")),
        "yes": bool(options.get("yes")),
        "explain": bool(options.get("explain")),
    }
    text = options.get("text")
    if text is not None:
        return conversation(retman, str(text), texts, **flags)
    return _session(retman, texts, **flags)


def _cancelled(command_name: str | None, as_json: bool, texts: Texts) -> int:
    """Report a call that the user stopped: the text, or with ``--json`` the result."""
    if as_json and command_name is not None:
        command = get_command(command_name)
        result = CommandResult(
            command.name, command.result_schema, Output(None, cancelled=True)
        )
        return report_outcome(result, as_json=True, texts=texts)
    print(texts.get("cli.cancelled"))
    return EXIT_CANCELLED


def main(
    argv: Sequence[str] | None = None,
    *,
    backend: DecisionBackend | None = None,
    project_dir: Path | None = None,
    **injections: Any,
) -> int:
    """Run one command of the catalog, with a dialog in a terminal where it has one.

    Parameters
    ----------
    argv : sequence of str, optional
        The words after ``retman``; ``sys.argv`` when absent.
    backend : DecisionBackend, optional
        An injected decision backend (offline tests); the configured one when absent.
    project_dir : Path, optional
        The project folder (results and journal); the current one when absent.
    **injections
        Other keyword arguments for the operation of the command that declares them
        (the discovered tools, the readers of the scaffold, a model client...), for
        offline tests.

    Returns
    -------
    int
        ``0``; ``10`` (``partial``) or ``11`` (``failed``) when the result lists units
        that did not all pass; ``130`` when the user cancelled or declined the plan;
        else the exit code of the registry code of the error (the last line of stderr
        is then the ``retman-error/1`` document).
    """
    texts = load_core_texts("pl")
    command_name: str | None = None
    as_json = False
    with sigterm_as_exception():
        try:
            parser = build_parser(load_core_texts(help_language(argv)))
            args = parser.parse_args(argv)
            if args.group is None or args.verb is None:
                raise UsageError(
                    "A command is a group and a verb: `retman <group> <verb>`",
                    details={"option": "command"},
                    hint="Run `retman --help` for the groups and `retman commands "
                    "list` for the commands.",
                )
            command = get_command(f"{args.group} {args.verb}")
            command_name = command.name
            as_json = args.as_json
            overrides = cli_options(
                lang=args.lang, verbose=args.verbose, quiet=args.quiet
            )
            options = options_of(command, args)
            config = Path(str(options["config"])) if "config" in options else None
            env = environment(config, options=overrides)
            configure_logging(str(env.setting("log_level").value))
            texts = load_core_texts(str(env.setting("lang").value))
            given = {
                "backend": backend,
                "project_dir": project_dir,
                "overrides": overrides,
                **injections,
            }
            extras = {name: value for name, value in given.items() if value is not None}
            if not as_json and sys.stdin.isatty():
                outcome = _dialog(
                    command.name, options, backend, project_dir, overrides, texts
                )
                if outcome is not None:
                    return outcome
            result = execute(command, options, extras)
            return report_outcome(result, as_json=as_json, texts=texts)
        except (KeyboardInterrupt, EOFError):
            return _cancelled(command_name, as_json, texts)
        except Terminated as err:
            return report_error(err, command=command_name)
        except BrokenPipeError as err:
            # The reader of the pipe left (``| head``): point stdout at the null
            # device so that the flush at exit stays quiet
            with contextlib.suppress(OSError, ValueError, AttributeError):
                os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            return report_error(err, command=command_name)
        except BackendConnectionError as err:
            text = (
                None if as_json else texts.get("errors.backend_connection", url=err.url)
            )
            return report_error(err, text=text, command=command_name)
        except ConfigError as err:
            text = None if as_json else _config_text(texts, err)
            return report_error(err, text=text, command=command_name)
        except RetmanError as err:
            text = (
                None if as_json else texts.get("errors.retman", error=err.text or err)
            )
            return report_error(err, text=text, command=command_name)
        except Exception as err:  # a defect: the document says so, debug has the trace
            logger.debug("Unexpected error", exc_info=True)
            text = None
            if not as_json:
                text = texts.get(
                    "errors.unexpected", error=f"{type(err).__name__}: {err}"
                )
            return report_error(err, text=text, command=command_name)


if __name__ == "__main__":
    sys.exit(main())

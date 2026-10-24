"""The command line, generated from the catalog (AGI-1.1, AGI-3.1, AGI-3.7).

``retman <group> <verb> [--option value ...]``: every group and verb is a command of
the catalog and every option an option of it, flagged as its kebab-case name. The
presentation options ``--json``, ``--lang``, ``--verbose`` and ``--quiet`` belong to
every verb and are no options of the catalog (AGI-3.4). A booleans is a bare flag, a
list is given by repeating the flag. The ``--help`` texts come from the translation
files and lead with one sentence, name the meanings of choices and end with examples.
A mistake in the call is a :class:`~retman.exceptions.UsageError`.
"""

import argparse
from collections.abc import Sequence
from typing import Any, NoReturn

from retman import __version__
from retman.catalog import Command, Option, data_commands
from retman.catalog.describe import (
    command_help,
    option_help,
    summary_of,
)
from retman.environment import LANGUAGES, environment
from retman.exceptions import UsageError
from retman.i18n.loader import Texts

PRESENTATION: tuple[str, ...] = ("as_json", "lang", "verbose", "quiet")
"""``dest`` of the options that every verb has and the catalog does not."""


class _Parser(argparse.ArgumentParser):
    """An argument parser whose mistakes are errors of the registry (AGI-3.3)."""

    def error(self, message: str) -> NoReturn:
        raise UsageError(message, hint="Run `retman --help` for the commands.")


def help_language(argv: Sequence[str] | None) -> str:
    """Return the language of the ``--help`` texts before the call is parsed.

    ``--lang`` of the call if it is there, else the setting ``lang``.
    """
    words = list(argv) if argv is not None else []
    for index, word in enumerate(words):
        if word == "--lang" and index + 1 < len(words):
            return words[index + 1]
        if word.startswith("--lang="):
            return word.partition("=")[2]
    return str(environment().setting("lang").value)


def _escaped(text: str) -> str:
    """Return ``text`` for an argparse ``help`` (a ``%`` would be a format)."""
    return text.replace("%", "%%")


def _add_option(
    parser: argparse.ArgumentParser, command: Command, option: Option, texts: Texts
) -> None:
    help_text = _escaped(option_help(command, option, texts))
    if option.type == "boolean":
        parser.add_argument(
            option.flag,
            dest=option.name,
            action="store_true",
            default=None,
            help=help_text,
        )
        return
    kwargs: dict[str, Any] = {
        "dest": option.name,
        "default": None,
        "help": help_text,
        "metavar": option.name.upper(),
    }
    if option.type == "integer":
        kwargs["type"] = int
    elif option.type == "number":
        kwargs["type"] = float
    elif option.type == "choice":
        kwargs["metavar"] = "{" + ",".join(option.choices) + "}"
    if option.type == "string_list":
        kwargs["action"] = "append"
    parser.add_argument(option.flag, **kwargs)


def _add_presentation(parser: argparse.ArgumentParser, texts: Texts) -> None:
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help=texts.get("cli.help_json"),
    )
    parser.add_argument(
        "--lang",
        dest="lang",
        choices=LANGUAGES,
        default=None,
        help=texts.get("cli.help_lang"),
    )
    parser.add_argument(
        "--verbose", action="store_true", help=texts.get("cli.help_verbose")
    )
    parser.add_argument(
        "--quiet", action="store_true", help=texts.get("cli.help_quiet")
    )


def build_parser(texts: Texts) -> argparse.ArgumentParser:
    """Build the parser of ``retman`` from the catalog.

    Parameters
    ----------
    texts : Texts
        The translated texts of the ``--help`` output.

    Returns
    -------
    argparse.ArgumentParser
        A parser whose result has ``group``, ``verb``, the options of the verb under
        their catalog names (``None`` when not given) and the presentation options
        ``as_json``, ``lang``, ``verbose`` and ``quiet``.
    """
    parser = _Parser(
        prog="retman",
        description=texts.get("cli.description"),
        epilog=texts.get("cli.epilog"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"retman {__version__}")
    groups = parser.add_subparsers(dest="group", metavar="<group>")
    verbs: dict[str, Any] = {}
    for command in data_commands():
        if command.group not in verbs:
            group_parser = groups.add_parser(
                command.group,
                help=_escaped(texts.get(f"cli.group_{command.group}")),
                formatter_class=argparse.RawDescriptionHelpFormatter,
            )
            verbs[command.group] = group_parser.add_subparsers(
                dest="verb", metavar="<verb>"
            )
        description, epilog = command_help(command, texts)
        verb_parser = verbs[command.group].add_parser(
            command.verb,
            help=_escaped(summary_of(command, texts)),
            description=_escaped(description),
            epilog=_escaped(epilog),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        for option in command.options:
            _add_option(verb_parser, command, option, texts)
        _add_presentation(verb_parser, texts)
    return parser


def options_of(command: Command, args: argparse.Namespace) -> dict[str, object]:
    """Return the options of ``command`` that the call gave, by catalog name."""
    return {
        option.name: getattr(args, option.name)
        for option in command.options
        if getattr(args, option.name) is not None
    }

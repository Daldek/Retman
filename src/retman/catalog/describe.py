"""The catalog as text for people: ``--help`` and the terminal view of ``commands``.

The texts of a command are English in its declaration (AGI-9.1) and Polish in the
translation file, ``[catalog.<operation_id>]`` of ``pl.toml`` (AGI-3.7); the option
names, flags, values and the examples are the machine names of the catalog,
identical in every language (AGI-1.6).
"""

from collections.abc import Sequence

from retman.catalog.spec import Command, Option
from retman.i18n.loader import Texts

# The language of the declarations
_DECLARED = "en"


def _base(command: Command) -> str:
    return f"catalog.{command.operation_id}"


def summary_of(command: Command, texts: Texts) -> str:
    """Return the one-line summary of ``command`` in the language of ``texts``."""
    if texts.language == _DECLARED:
        return command.summary
    return texts.get(f"{_base(command)}.summary")


def description_of(command: Command, texts: Texts) -> str:
    """Return the description of ``command`` in the language of ``texts``."""
    if texts.language == _DECLARED:
        return command.description
    return texts.get(f"{_base(command)}.description")


def rules_of(command: Command, texts: Texts) -> list[str]:
    """Return the rules for agents of ``command`` in the language of ``texts``."""
    if texts.language == _DECLARED:
        return list(command.rules)
    return texts.lines(f"{_base(command)}.rules")


def option_description(command: Command, option: Option, texts: Texts) -> str:
    """Return the description of ``option`` in the language of ``texts``."""
    if texts.language == _DECLARED:
        return option.description
    return texts.get(f"{_base(command)}.options.{option.name}.description")


def meaning_of(command: Command, option: Option, value: str, texts: Texts) -> str:
    """Return the meaning of one value of a ``choice`` option."""
    if texts.language == _DECLARED:
        return option.meanings[value]
    return texts.get(f"{_base(command)}.options.{option.name}.meanings.{value}")


def _kind(option: Option, texts: Texts) -> str:
    if option.type == "boolean":
        return ""
    return " " + texts.get(f"commands_view.type_{option.type}")


def _option_lines(command: Command, texts: Texts, indent: str = "  ") -> list[str]:
    lines: list[str] = []
    for option in command.options:
        marks = []
        if option.required:
            marks.append(texts.get("commands_view.required"))
        if option.default is not None:
            marks.append(texts.get("commands_view.default", value=option.default))
        if option.unit is not None:
            marks.append(option.unit)
        suffix = f" ({', '.join(marks)})" if marks else ""
        lines.append(
            f"{indent}{option.flag}{_kind(option, texts)}{suffix}: "
            f"{option_description(command, option, texts)}"
        )
        if option.type == "choice":
            lines += [
                f"{indent}    {value}: {meaning_of(command, option, value, texts)}"
                for value in option.choices
            ]
    return lines


def _effects(command: Command, texts: Texts) -> str:
    effects = command.effects
    names = []
    if effects.read_only:
        names.append(texts.get("commands_view.effect_read_only"))
    else:
        names.append(texts.get(f"commands_view.effect_writes_{effects.writes}"))
    if effects.network:
        names.append(texts.get("commands_view.effect_network"))
    if effects.destructive:
        names.append(texts.get("commands_view.effect_destructive"))
    return ", ".join(names)


def examples_of(command: Command) -> list[str]:
    """Return the complete CLI calls of the examples of ``command``."""
    return [command.command_line(example) for example in command.examples]


def command_help(command: Command, texts: Texts) -> tuple[str, str]:
    """Return the ``--help`` description and epilog of ``command`` (AGI-3.7).

    The description starts with one sentence of what the command does; the epilog
    ends the help with the examples.

    Returns
    -------
    tuple of str
        The description and the epilog, plain text.
    """
    description = summary_of(command, texts) + "\n\n" + description_of(command, texts)
    epilog = "\n".join(
        [texts.get("commands_view.examples"), *(f"  {c}" for c in examples_of(command))]
    )
    return description, epilog


def option_help(command: Command, option: Option, texts: Texts) -> str:
    """Return the ``--help`` text of ``option``: description and meanings of values."""
    text = option_description(command, option, texts)
    if option.type == "choice":
        meanings = "; ".join(
            f"{value}: {meaning_of(command, option, value, texts)}"
            for value in option.choices
        )
        text += f" ({meanings})"
    if option.default is not None:
        text += " " + texts.get("commands_view.default_note", value=option.default)
    return text


def describe_command(command: Command, texts: Texts) -> list[str]:
    """Return the lines that describe ``command`` for the terminal.

    Parameters
    ----------
    command : Command
        The declaration.
    texts : Texts
        Translated texts (core).

    Returns
    -------
    list of str
        Name and summary, description, options with the meanings of their values,
        the document and cardinality of the result, effects, the rules for agents,
        the errors and the examples.
    """
    lines = [
        texts.get(
            "commands_view.heading",
            name=command.name,
            summary=summary_of(command, texts),
        ),
        description_of(command, texts),
        "",
    ]
    if command.options:
        lines += [texts.get("commands_view.options"), *_option_lines(command, texts)]
    else:
        lines.append(texts.get("commands_view.no_options"))
    lines += [
        texts.get(
            "commands_view.result",
            schema=command.result_schema,
            cardinality=texts.get(f"commands_view.cardinality_{command.cardinality}"),
        ),
        texts.get("commands_view.effects", effects=_effects(command, texts)),
    ]
    if command.rules:
        lines += [
            texts.get("commands_view.rules"),
            *(f"  - {rule}" for rule in rules_of(command, texts)),
        ]
    if command.errors:
        lines.append(
            texts.get("commands_view.errors", errors=", ".join(command.errors))
        )
    lines += [
        texts.get("commands_view.examples"),
        *(f"  {c}" for c in examples_of(command)),
    ]
    return lines


def list_lines(commands: Sequence[Command], texts: Texts) -> list[str]:
    """Return one line per command: its name and summary."""
    width = max((len(command.name) for command in commands), default=0)
    return [
        f"{command.name.ljust(width)}  {summary_of(command, texts)}"
        for command in commands
    ]

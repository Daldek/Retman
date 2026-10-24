"""``commands list``, ``commands schema`` and ``commands guide``: the catalog itself."""

from pathlib import Path
from typing import Any

from retman.agent_guide import GuideFormat, agent_guide, inject_block
from retman.catalog import (
    Output,
    command_schema,
    data_commands,
    get_command,
    list_commands,
    paginate,
)
from retman.catalog.describe import describe_command, list_lines
from retman.catalog.document import catalog_document
from retman.exceptions import InvalidValueError
from retman.i18n.loader import Texts
from retman.operations.documents import (
    check_targets,
    conflicts,
    sequence_view,
    targets_output,
)


def _more(texts: Texts, page: dict[str, Any] | None) -> list[str]:
    if page is not None and page["truncated"]:
        return [texts.get("cli.more", cursor=page["next_cursor"])]
    return []


def commands_list(*, limit: int | None = None, cursor: str | None = None) -> Output:
    """List the commands of the catalog: name, ``operation_id``, summary, read-only.

    Parameters
    ----------
    limit : int, optional
        Commands per page; all of them when absent.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.

    Returns
    -------
    Output
        The ``retman-command-list/1`` document, with its page when ``limit`` is given.
    """
    document = list_commands(limit=limit, cursor=cursor).to_dict()
    page = document.pop("page", None)
    listed = [get_command(entry["name"]) for entry in document["commands"]]
    return Output(
        document,
        page=page,
        view=sequence_view(
            lambda texts: [*list_lines(listed, texts), *_more(texts, page)]
        ),
    )


def commands_schema(
    *,
    command: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Output:
    """Describe one command, or every command page by page.

    Parameters
    ----------
    command : str, optional
        Command name or ``operation_id``; every command when absent.
    limit : int, optional
        Commands per page when no ``command`` is given.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.

    Returns
    -------
    Output
        The ``retman-commands/1`` document.

    Raises
    ------
    CommandNotFoundError
        ``command`` is not in the catalog.
    InvalidValueError
        ``command`` is given together with ``limit`` or ``cursor``.
    """
    if command is not None:
        for name, value in (("limit", limit), ("cursor", cursor)):
            if value is not None:
                raise InvalidValueError(
                    f"Option {name!r} pages the whole catalog and cannot be used with "
                    "'command'",
                    details={
                        "reason": "one_of",
                        "option": name,
                        "given": ["command", name],
                    },
                    hint="Give 'command', or the page options, not both.",
                )
        selected = [get_command(command)]
        document = command_schema(command).to_dict()
        page = None
    else:
        chosen, page = paginate(data_commands(), limit, cursor)
        selected = list(chosen)
        document = catalog_document(chosen)

    def lines(texts: Texts) -> list[str]:
        blocks: list[str] = []
        for entry in selected:
            blocks += [*describe_command(entry, texts), ""]
        return [*blocks[:-1], *_more(texts, page)]

    return Output(document, page=page, view=sequence_view(lines))


def commands_guide(
    *,
    format: GuideFormat = "agents",
    output: str | None = None,
    inject: str | None = None,
    check: bool = False,
    force: bool = False,
) -> Output:
    """Render a guide for agents; print it, write it or inject it into an AGENTS.md.

    Parameters
    ----------
    format : {"agents", "llms", "agents-md-block"}, optional
        Which guide.
    output : str, optional
        File to write instead of printing.
    inject : str, optional
        AGENTS.md of a consumer repository whose Retman block is replaced; needs the
        format ``agents-md-block``.
    check : bool, optional
        Plan the write of ``output`` or ``inject`` without making it.
    force : bool, optional
        Replace an existing ``output`` file.

    Returns
    -------
    Output
        The ``retman-guide/1`` document (with the ``text`` unless a file is written),
        or the plan of the write.

    Raises
    ------
    InvalidValueError
        ``inject`` without the format ``agents-md-block``.
    RetmanError
        ``output`` exists and ``force`` is not given (``conflict``, ``output_exists``).
    """
    text = agent_guide(format)
    if inject is not None and format != "agents-md-block":
        raise InvalidValueError(
            "Option 'inject' replaces the block of the AGENTS.md of another "
            "repository and needs the format 'agents-md-block'",
            details={
                "reason": "inject_format",
                "option": "inject",
                "value": format,
                "allowed": ["agents-md-block"],
            },
            hint="Give --format agents-md-block.",
        )
    if inject is not None:
        path = Path(inject)
        existed = path.is_file()
        existing = path.read_text(encoding="utf-8") if existed else ""
        new = inject_block(existing, text)
        # Injecting is meant to be repeated: the file is replaced, never in conflict
        targets = check_targets([("inject", path)], force=True)
        if check:
            return targets_output(targets)
        if new != existing:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8", newline="\n")
        return _written(format, new, path, replaced=existed)
    if output is not None:
        path = Path(output)
        targets = check_targets([("output", path)], force=force)
        if check:
            return targets_output(targets)
        if (failure := conflicts(targets)) is not None:
            raise failure
        replaced = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return _written(format, text, path, replaced=replaced)
    if check:
        return targets_output([])
    return Output(
        {"format": format, "text": text},
        view=lambda texts: text,
    )


def _written(format: str, text: str, path: Path, *, replaced: bool) -> Output:
    """Return the result of a guide that was written to ``path``."""
    return Output(
        {
            "format": format,
            "lines": len(text.splitlines()),
            "bytes": len(text.encode()),
        },
        files=[path],
        replaced=[path] if replaced else [],
        view=lambda texts: texts.get("commands_view.guide_written", path=path) + "\n",
    )

"""``results list`` and ``journal show``: what the project folder remembers."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from retman.catalog.document import paginate
from retman.catalog.envelope import Output
from retman.config import load_settings
from retman.core.journal import Journal
from retman.core.workspace import Workspace
from retman.environment import OptionValue
from retman.i18n.loader import Texts


def _workspace(
    config: str | None,
    project_dir: Path | None,
    overrides: Mapping[str, OptionValue] | None,
) -> tuple[Workspace, bool]:
    """Return the workspace of the project folder and whether it journals commands."""
    settings = load_settings(Path(config) if config else None, options=overrides)
    folder = project_dir if project_dir is not None else Path.cwd()
    return Workspace(folder, settings.results_dir), settings.journal_commands


def _more(texts: Texts, page: Mapping[str, Any] | None) -> list[str]:
    """Return the line that names the cursor of the next page, if there is one."""
    if page is not None and page["truncated"]:
        return [texts.get("cli.more", cursor=page["next_cursor"])]
    return []


def results_list(
    *,
    config: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    project_dir: Path | None = None,
    overrides: Mapping[str, OptionValue] | None = None,
) -> Output:
    """List the numbered results of the project folder, in numeric order.

    Parameters
    ----------
    config : str, optional
        The settings file (it names the results folder).
    limit : int, optional
        Results per page.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.
    project_dir, overrides
        Injections of the caller: the project folder (the current one by default)
        and the settings that command-line options give.

    Returns
    -------
    Output
        The ``retman-results/1`` document and its page.
    """
    workspace, _ = _workspace(config, project_dir, overrides)
    page_rows, page = paginate(workspace.list_results(), limit, cursor)
    rows = [
        {
            "number": row["number"],
            "operation": row["operation"],
            "ok": row["ok"],
            "summary": row["summary"],
            "finished_at": (row.get("timing") or {}).get("end"),
        }
        for row in page_rows
    ]

    def view(texts: Texts) -> str:
        lines = [texts.get("cli.results_line", summary=row["summary"]) for row in rows]
        lines = lines or [texts.get("cli.no_results")]
        return "\n".join([*lines, *_more(texts, page)]) + "\n"

    return Output(
        {"directory": str(workspace.root), "results": rows}, page=page, view=view
    )


def _detail(event: Mapping[str, Any], texts: Texts) -> str:
    """Return what a journal line says about an event, in the user's language."""
    detail = event.get(
        "command",
        event.get(
            "question",
            event.get("answer", event.get("status", event.get("number", ""))),
        ),
    )
    if event["event"] == "plan" and detail:
        return texts.get(f"journal.{detail}")
    if event["event"] == "check":
        return texts.get(f"journal.check_{event['status']}")
    return str(detail)


def journal_show(
    *,
    config: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    project_dir: Path | None = None,
    overrides: Mapping[str, OptionValue] | None = None,
) -> Output:
    """Show the events of the journal of the project folder, oldest first.

    Parameters
    ----------
    config : str, optional
        The settings file (it names the results folder).
    limit : int, optional
        Events per page.
    cursor : str, optional
        ``page.next_cursor`` of the previous page.
    project_dir, overrides
        Injections of the caller: the project folder (the current one by default)
        and the settings that command-line options give.

    Returns
    -------
    Output
        The ``retman-journal/1`` document and its page.
    """
    workspace, journal_commands = _workspace(config, project_dir, overrides)
    journal = Journal(workspace.root, "", journal_commands)
    events, page = paginate(journal.entries(), limit, cursor)

    def view(texts: Texts) -> str:
        lines = [
            texts.get(
                "cli.log_line",
                time=event["time"],
                event=texts.get(f"journal.{event['event']}"),
                detail=_detail(event, texts),
            )
            for event in events
        ]
        lines = lines or [texts.get("cli.no_events")]
        return "\n".join([*lines, *_more(texts, page)]) + "\n"

    return Output(
        {"file": str(journal.path), "events": [dict(event) for event in events]},
        page=page,
        view=view,
    )

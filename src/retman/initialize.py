"""``retman init``: the ``[retman]`` tables, the store folders and the IMGWTools store.

Questions are asked only in a terminal; without one the tables are written with the
visible default paths and nothing else is created (ADR-010 for the command
collection, the same rule here for the folders and the IMGWTools store).
"""

import sys
from pathlib import Path

from retman.config import (
    ToolPaths,
    default_collect_path,
    default_stores_dir,
    init_config,
    init_target,
    tool_paths,
)
from retman.environment import Environment, environment
from retman.exceptions import RetmanError
from retman.i18n.loader import Texts
from retman.outcomes import report_error
from retman.stores import hardlink_error, init_imgw_store, tool_installed

_YES = ("t", "tak")


def _ask_stores_dir(texts: Texts, env: Environment) -> Path:
    """Ask for the folder that will hold both tool stores; Enter keeps the default."""
    default = default_stores_dir(env).expanduser().resolve()
    paths = tool_paths(env, default)
    print(texts.get("init.stores_question", cache=paths.kartograf_cache))
    while True:
        answer = input(texts.get("init.stores_prompt", path=default)).strip()
        answer = answer.strip("\"'")
        if not answer:
            return default
        chosen = Path(answer).expanduser()
        if chosen.is_absolute() and ".." not in chosen.parts:
            return chosen
        print(texts.get("cli.error", error=texts.get("init.stores_not_absolute")))


def _create_folders(paths: ToolPaths, texts: Texts) -> int | None:
    """Create the folders the settings will name and check the disk for hard links.

    Both stores need hard links; the IMGWTools store itself is left to the tool,
    which creates it only in an empty folder. Returns ``None`` when all is usable,
    else the exit code of the error that was reported (``io_error`` for a folder
    that cannot be made, ``store_unavailable`` for a disk without hard links).
    """
    folders = (
        paths.kartograf_store,
        paths.kartograf_cache.parent,
        paths.imgwtools_reference,
    )
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            text = texts.get("init.folder_failed", path=folder, error=error)
            return report_error(error, text=text)
    try:
        failure = hardlink_error(paths.kartograf_store)
    except OSError as error:
        text = texts.get("init.folder_failed", path=paths.kartograf_store, error=error)
        return report_error(error, text=text)
    if failure is not None:
        reason = failure.strerror or str(failure)
        text = texts.get("init.no_hardlinks", path=paths.kartograf_store, reason=reason)
        refused = RetmanError(
            f"The disk of {paths.kartograf_store} does not support hard links",
            code="store_unavailable",
            details={"reason": "no_hardlinks", "path": str(paths.kartograf_store)},
            hint="Choose a folder on a disk with hard links (not FAT or exFAT).",
        )
        return report_error(refused, text=text)
    return None


def _offer_imgw_store(store: Path, texts: Texts) -> int:
    """Initialise the IMGWTools store after the user's consent (never silently)."""
    if not tool_installed("imgwtools"):
        print(texts.get("init.imgw_not_installed", path=store))
        return 0
    print(texts.get("init.imgw_question", path=store))
    if input(texts.get("init.imgw_prompt")).strip().lower() not in _YES:
        print(texts.get("init.imgw_declined"))
        return 0
    outcome = init_imgw_store(store)
    if outcome.status in ("ok", "existing"):
        print(texts.get(f"init.imgw_{outcome.status}", path=store))
        return 0
    if outcome.status == "tool_missing":
        print(texts.get("init.imgw_not_installed", path=store))
        return 0
    key = "imgw_not_atomic" if outcome.reason == "not_atomic" else "imgw_refused"
    text = texts.get(f"init.{key}", path=store, detail=outcome.detail)
    refused = RetmanError(
        f"IMGWTools refused the store {store}: {outcome.detail}",
        code="store_unavailable",
        details={"reason": outcome.reason or "refused", "path": str(store)},
        hint="Choose a folder on a disk with hard links; both store_dir settings "
        "follow it.",
    )
    return report_error(refused, text=text)


def run_init(config_path: Path | None, texts: Texts) -> int:
    """Write the ``[retman]`` tables; in a terminal also set the tool stores up.

    In a terminal the user is asked whether to collect commands (ADR-010), which
    folder should hold the stores of the tools (Kartograf's and IMGWTools',
    side by side on one disk) and whether to initialise the IMGWTools store now.
    The folders are created before the file is written, so an unusable folder
    leaves no settings behind.

    Parameters
    ----------
    config_path : Path, optional
        The file named by ``--config``; else ``NOGAT_CONFIG``, else the user
        configuration folder of ``nogat``.
    texts : Texts
        Core texts.

    Returns
    -------
    int
        Exit code: ``0``, or the code of the error that was reported when a folder
        or the IMGWTools store could not be created.

    Raises
    ------
    ConfigError
        The file already has a ``[retman]`` table, or cannot be read; it is never
        overwritten.
    """
    env = environment(config_path)
    target = init_target(env)  # before any question: the answers would be lost
    interactive = sys.stdin.isatty()
    collect = False
    stores_dir: Path | None = None
    if interactive:
        print(texts.get("cli.collect_question", path=default_collect_path(env)))
        collect = input(texts.get("cli.collect_prompt")).strip().lower() in _YES
        stores_dir = _ask_stores_dir(texts, env)
    paths = tool_paths(env, stores_dir)
    if interactive and (failed := _create_folders(paths, texts)) is not None:
        return failed
    print(init_config(target, collect_commands=collect, stores_dir=stores_dir))
    print(
        texts.get(
            "cli.collect_on" if collect else "cli.collect_off",
            path=default_collect_path(env),
        )
    )
    print(
        texts.get(
            "init.stores_summary",
            kartograf=paths.kartograf_store,
            imgwtools=paths.imgwtools_store,
        )
    )
    if not interactive:
        print(texts.get("init.not_created"))
        return 0
    return _offer_imgw_store(paths.imgwtools_store, texts)

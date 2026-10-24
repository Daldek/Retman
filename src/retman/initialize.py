"""``retman init``: the config file, the tool store folders and the IMGWTools store.

Questions are asked only in a terminal; without one the file is written with the
visible default paths and nothing else is created (ADR-010 for the command
collection, the same rule here for the folders and the IMGWTools store).
"""

import sys
from pathlib import Path

from retman.config import (
    ToolPaths,
    default_collect_path,
    default_config_path,
    default_stores_dir,
    init_config,
    tool_paths,
)
from retman.exceptions import ConfigError
from retman.i18n.loader import Texts
from retman.stores import hardlink_error, init_imgw_store, tool_installed

_YES = ("t", "tak")


def _ask_stores_dir(texts: Texts) -> Path:
    """The folder that will hold both tool stores; Enter keeps the default."""
    default = default_stores_dir().expanduser().resolve()
    paths = tool_paths(default)
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


def _create_folders(paths: ToolPaths, texts: Texts) -> bool:
    """Create the folders the config will name and check that the chosen disk has
    hard links, which both stores need; the IMGWTools store itself is left to the
    tool, which creates it only in an empty folder. Returns whether all is usable."""
    folders = (
        paths.kartograf_store,
        paths.kartograf_cache.parent,
        paths.imgwtools_reference,
    )
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            print(
                texts.get("init.folder_failed", path=folder, error=error),
                file=sys.stderr,
            )
            return False
    try:
        failure = hardlink_error(paths.kartograf_store)
    except OSError as error:
        text = texts.get("init.folder_failed", path=paths.kartograf_store, error=error)
        print(text, file=sys.stderr)
        return False
    if failure is not None:
        reason = failure.strerror or str(failure)
        text = texts.get("init.no_hardlinks", path=paths.kartograf_store, reason=reason)
        print(text, file=sys.stderr)
        return False
    return True


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
    print(texts.get(f"init.{key}", path=store, detail=outcome.detail), file=sys.stderr)
    return 1


def run_init(config_path: Path | None, texts: Texts) -> int:
    """Write the central config file; in a terminal also set the tool stores up.

    In a terminal the user is asked whether to collect commands (ADR-010), which
    folder should hold the stores of the tools (Kartograf's and IMGWTools',
    side by side on one disk) and whether to initialise the IMGWTools store now.
    The folders are created before the file is written, so an unusable folder
    leaves no config behind.

    Parameters
    ----------
    config_path : Path, optional
        Target file; the system location by default.
    texts : Texts
        Core texts.

    Returns
    -------
    int
        Exit code: ``0``, or ``1`` when a folder or the IMGWTools store could not
        be created.

    Raises
    ------
    ConfigError
        The file already exists; it is never overwritten.
    """
    target = config_path or default_config_path()
    if target.exists():
        # Before any question: the answers would be thrown away
        raise ConfigError(target, ["already_exists"])
    interactive = sys.stdin.isatty()
    collect = False
    stores_dir: Path | None = None
    if interactive:
        print(texts.get("cli.collect_question", path=default_collect_path()))
        collect = input(texts.get("cli.collect_prompt")).strip().lower() in _YES
        stores_dir = _ask_stores_dir(texts)
    paths = tool_paths(stores_dir)
    if interactive and not _create_folders(paths, texts):
        return 1
    print(init_config(target, collect_commands=collect, stores_dir=stores_dir))
    print(
        texts.get(
            "cli.collect_on" if collect else "cli.collect_off",
            path=default_collect_path(),
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

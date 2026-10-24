"""``config show`` and ``config init``: the settings in force, and writing them out."""

from collections.abc import Mapping
from pathlib import Path

from retman.catalog.envelope import Output
from retman.config import (
    ToolPaths,
    default_collect_path,
    init_config,
    init_target,
    tool_paths,
)
from retman.config_show import get_config, render_config
from retman.environment import OptionValue, environment
from retman.exceptions import ConfigError
from retman.i18n.loader import Texts
from retman.operations.documents import sequence_view, targets_output


def config_show(
    *, config: str | None = None, overrides: Mapping[str, OptionValue] | None = None
) -> Output:
    """Report the settings in force and where each comes from (DEV-18.6).

    Parameters
    ----------
    config : str, optional
        The settings file.
    overrides : Mapping[str, OptionValue], optional
        The settings given by command-line options of the call.

    Returns
    -------
    Output
        The ``retman-config/1`` document. A settings file that cannot be used is
        reported in it, not raised, so that this command repairs it.
    """
    report = get_config(Path(config) if config else None, options=overrides)
    return Output(report.to_dict(), view=lambda texts: render_config(report, texts))


def init_lines(
    texts: Texts,
    *,
    target: Path,
    collect_commands: bool,
    collect_path: Path,
    paths: ToolPaths,
    created: bool,
) -> list[str]:
    """Return the lines that say what ``config init`` wrote and what it left to do.

    ``created`` is true when a terminal session created the store folders; without
    one nothing but the settings file was written.
    """
    lines = [
        str(target),
        texts.get(
            "cli.collect_on" if collect_commands else "cli.collect_off",
            path=collect_path,
        ),
        texts.get(
            "init.stores_summary",
            kartograf=paths.kartograf_store,
            imgwtools=paths.imgwtools_store,
        ),
    ]
    if not created:
        lines.append(texts.get("init.not_created"))
    return lines


def config_init(
    *,
    config: str | None = None,
    collect_commands: bool = False,
    stores_dir: str | None = None,
    check: bool = False,
) -> Output:
    """Write the ``[retman]`` tables into ``nogat.toml``; never overwrite them.

    Only the file is written: the store folders are made by the terminal session of
    ``retman config init`` after its questions, never as a side effect here.

    Parameters
    ----------
    config : str, optional
        The settings file to write; the default one when absent.
    collect_commands : bool, optional
        The user's explicit consent to collect commands (ADR-010); off by default.
    stores_dir : str, optional
        Folder that holds both tool stores; the data folder of ``nogat`` by default.
    check : bool, optional
        Plan the write: ``write``, or ``conflict`` when the file has the tables.

    Returns
    -------
    Output
        The ``retman-config-init/1`` document and the written file, or the plan.

    Raises
    ------
    ConfigError
        The file has a ``[retman]`` table (``conflict``, ``output_exists``) or cannot
        be read or parsed, so the tables cannot be appended safely.
    """
    path = Path(config) if config else None
    folder = Path(stores_dir) if stores_dir else None
    env = environment(path)
    if check:
        try:
            target = init_target(env)
            action = "write"
        except ConfigError as error:
            if error.problems != ["already_exists"]:
                raise
            target, action = env.file.path, "conflict"
        return targets_output(
            [{"option": "config", "path": str(target), "action": action}]
        )
    existed = env.file.exists
    target = init_config(path, collect_commands=collect_commands, stores_dir=folder)
    paths = tool_paths(env, folder)
    collect_path = default_collect_path(env)
    document = {
        "config_file": str(target),
        "collect_commands": collect_commands,
        "collect_path": str(collect_path),
        "stores": {
            "kartograf": str(paths.kartograf_store),
            "imgwtools": str(paths.imgwtools_store),
        },
    }
    return Output(
        document,
        files=[target],
        replaced=[target] if existed else [],
        view=sequence_view(
            lambda texts: init_lines(
                texts,
                target=target,
                collect_commands=collect_commands,
                collect_path=collect_path,
                paths=paths,
                created=False,
            )
        ),
    )

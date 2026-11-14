"""The two Obserwator roots and folder comparisons: pure path arithmetic, no writes.

Obserwator keeps a raw root (downloaded archives, station sources, PMAXTP cells)
and a data root (series, station catalogs, analyses built from it; Obserwator
ADR-017). Retman's settings name them ``raw_store_dir`` and ``store_dir``
(ADR-034); the context's ``store_dir`` is the data root.
"""

import os
from pathlib import Path

from retman.adapters.catalog import ToolContext
from retman.exceptions import RetmanError
from retman.stores import ObserwatorRoot


def same_folder(first: object, second: object) -> bool:
    """Whether two paths name the same folder (absolute and normalised)."""
    return os.path.abspath(str(first)) == os.path.abspath(str(second))


def root_dir(ctx: ToolContext, kind: ObserwatorRoot) -> Path:
    """Return the configured folder of the root of ``kind``.

    Raises
    ------
    RetmanError
        If ``[retman.tools.obserwator]`` has no setting for that root.
    """
    if kind == "data":
        return ctx.store_dir
    try:
        return Path(ctx.settings["raw_store_dir"])
    except KeyError:
        raise RetmanError(f"[retman.tools.{ctx.tool}] has no raw_store_dir") from None

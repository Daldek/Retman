"""Tool stores on disk: checks of ``retman doctor check``, set-up by ``config init``.

The tools keep their data in stores outside the project (ARCHITECTURE 9.1). This
module only looks at folders and files; IMGWTools is imported lazily, and only
to initialise a store or to probe whether the tool can write one on this system
(ARCHITECTURE 3.2.5: no tool is imported at start).
"""

import importlib.util
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# IMGWTools marks a folder as its store with this file (schema ``imgw-store/1``)
IMGW_MARKER = "imgw-store.json"
IMGW_SCHEMA = "imgw-store/1"
# The static station locations IMGWTools reads from ``reference_data_dir``
IMGW_REFERENCE_FILE = "hydro_stations_locations.csv"

ImgwStoreState = Literal[
    "missing",
    "not_a_directory",
    "empty",
    "ready",
    "foreign",
    "unreadable",
    "unsupported",
]
Outcome = Literal["ok", "existing", "tool_missing", "refused"]


@dataclass(frozen=True)
class ImgwStore:
    """What a configured IMGWTools store folder holds.

    ``detail`` is the schema named by the marker (``ready`` and ``unsupported``) and
    empty otherwise.
    """

    state: ImgwStoreState
    detail: str = ""


@dataclass(frozen=True)
class ToolOutcome:
    """Result of a call into IMGWTools that Retman makes outside an operation.

    ``tool_missing``: the package cannot be imported (``detail`` says why);
    ``refused``: IMGWTools raised an error, quoted verbatim in ``detail``, with
    the ``details.reason`` it named in ``reason`` (``not_atomic``: the file system
    has no hard links); ``existing``: the store was already initialised
    (``init_imgw_store`` only).
    """

    status: Outcome
    detail: str = ""
    version: str = ""
    reason: str = ""


def _refused(error: Exception, version: object) -> ToolOutcome:
    details = getattr(error, "details", None) or {}
    reason = str(details.get("reason", ""))
    return ToolOutcome("refused", str(error), str(version), reason)


def tool_installed(package: str) -> bool:
    """Whether a Python package can be found; it is not imported."""
    return importlib.util.find_spec(package) is not None


def nearest_existing(path: Path) -> Path:
    """Return the path itself or its closest ancestor that exists."""
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def symlink_component(path: Path) -> Path | None:
    """Return the path or its closest ancestor that is a symbolic link, if any."""
    absolute = path.absolute()
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            return part
    return None


def tree_size(root: Path) -> int:
    """Return the bytes of the files below ``root``; a hard-linked file counts once.

    The stores of the tools keep every version as a hard link, so their size is
    the size of the distinct files. A folder that vanishes or cannot be listed
    during the walk is skipped.
    """
    total = 0
    seen: set[tuple[int, int]] = set()
    pending = [root]
    while pending:
        try:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        info = entry.stat(follow_symlinks=False)
                        if info.st_nlink > 1:
                            identity = (info.st_dev, info.st_ino)
                            if identity in seen:
                                continue
                            seen.add(identity)
                        total += info.st_size
        except OSError:
            continue
    return total


def hardlink_error(folder: Path) -> OSError | None:
    """Create a hard link in ``folder`` and remove it again.

    Returns
    -------
    OSError or None
        ``None`` when hard links work; the error of ``os.link`` otherwise.

    Raises
    ------
    OSError
        A file cannot be created in ``folder`` at all.
    """
    with tempfile.NamedTemporaryFile(
        dir=folder, prefix=".retman-link-test-", delete=False
    ) as handle:
        source = Path(handle.name)
    link = source.with_name(f"{source.name}.link")
    try:
        os.link(source, link)
    except OSError as error:
        return error
    finally:
        link.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
    return None


def imgw_store_state(folder: Path) -> ImgwStore:
    """Whether ``folder`` is an initialised IMGWTools store, judged without the tool.

    IMGWTools creates a store only in an empty folder, so a non-empty folder
    without the marker is ``foreign``.
    """
    if not folder.exists():
        return ImgwStore("missing")
    if not folder.is_dir():
        return ImgwStore("not_a_directory")
    marker = folder / IMGW_MARKER
    if marker.exists():
        try:
            schema = json.loads(marker.read_text(encoding="utf-8"))["schema"]
        except (OSError, ValueError, KeyError, TypeError):
            return ImgwStore("unreadable")
        if schema != IMGW_SCHEMA:
            return ImgwStore("unsupported", str(schema))
        return ImgwStore("ready", IMGW_SCHEMA)
    return ImgwStore("foreign" if any(folder.iterdir()) else "empty")


def init_imgw_store(folder: Path) -> ToolOutcome:
    """Initialise an IMGWTools store in ``folder`` through the tool (``store init``).

    Offline and idempotent: an initialised store is left as it is. IMGWTools
    refuses a folder with other files, a path with a symbolic link, a place
    inside another store and a file system without hard links; the refusal is
    returned, not raised.
    """
    try:
        imgwtools = importlib.import_module("imgwtools")
    except ImportError as error:
        return ToolOutcome("tool_missing", str(error))
    existed = (folder / IMGW_MARKER).exists()
    try:
        imgwtools.run_command("store init", options={"root": str(folder)})
    except (imgwtools.IMGWError, OSError) as error:
        return _refused(error, imgwtools.__version__)
    return ToolOutcome(
        "existing" if existed else "ok", version=str(imgwtools.__version__)
    )


def probe_imgw_write() -> ToolOutcome:
    """Check that IMGWTools can write a store on this system (end to end).

    Lets the tool build its packaged offline fixture store (no network): an
    initialised store, archives, a series and a station catalog, in a temporary
    folder. It shows what a hard-link test cannot: that the installed build
    publishes versions on this operating system.
    """
    try:
        testing = importlib.import_module("imgwtools.testing")
        imgwtools = importlib.import_module("imgwtools")
    except ImportError as error:
        return ToolOutcome("tool_missing", str(error))
    version = str(imgwtools.__version__)
    # A symbolic link in the path would be refused by IMGWTools (macOS: /var, /tmp)
    folder = Path(tempfile.mkdtemp(prefix="retman-imgw-probe-")).resolve()
    try:
        testing.build_fixture_store(folder / "store")
    except (imgwtools.IMGWError, OSError) as error:
        return _refused(error, version)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return ToolOutcome("ok", version=version)

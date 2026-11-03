"""Tool stores on disk: checks of ``retman doctor check``, set-up by ``config init``.

The tools keep their data in stores outside the project (ARCHITECTURE 9.1). This
module only looks at folders and files: the marker states of both stores are judged
here by the rules of each tool, which the tests hold against the tools; Obserwator is
imported lazily, and only to initialise a store or to probe whether the tool can write
one on this system (ARCHITECTURE 3.2.5: no tool is imported at start).
"""

import importlib.util
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# Obserwator marks a folder as its store with this file (schema ``obserwator-store/1``)
OBSERWATOR_MARKER = "obserwator-store.json"
OBSERWATOR_SCHEMA = "obserwator-store/1"
# The trees whose presence is the layout of a store, marked or not (the tool's
# ``_LAYOUT_TREES``): ``store init`` verifies such a folder and writes its marker
OBSERWATOR_LAYOUT_TREES = ("archives", "series", "stations", "pmaxtp")
# State files of the tool's REST server, kept in the default store folder; they are
# not store content, so a folder holding only them counts as empty
OBSERWATOR_STATE_FILES = ("api_keys.json",)
# The static station locations Obserwator reads from ``reference_data_dir``
OBSERWATOR_REFERENCE_FILE = "hydro_stations_locations.csv"

# Kartograf marks a folder as its store with this file (schema ``kartograf-store/1``)
KARTOGRAF_MARKER = "kartograf-store.json"
KARTOGRAF_SCHEMA = "kartograf-store/1"
# The marker files of the stores of the Nogat tools: a tool knows the store of another
# by the file name alone, and a store never lies in, holds or is another one (DEV 19)
STORE_MARKERS = (KARTOGRAF_MARKER, OBSERWATOR_MARKER)
# The top folders Kartograf writes into a store, one per product and ``hsg`` (the
# tool's ``managed_trees()``, which a test holds this set against): files in them are
# the layout of a store, marked or not
KARTOGRAF_TREES = frozenset(
    {
        "boundaries",
        "cadastre",
        "contours",
        "geodesy",
        "hsg",
        "hydro",
        "intensity",
        "landcover",
        "laz",
        "maps",
        "models3d",
        "names",
        "nmpt",
        "nmt",
        "oblique-orto",
        "orto",
        "soil",
        "true-orto",
    }
)
# Where Kartograf stages a version before it publishes it: not store content
KARTOGRAF_STAGING = ".incoming"

ObserwatorStoreState = Literal[
    "missing",
    "not_a_directory",
    "empty",
    "ready",
    "no_marker",
    "foreign",
    "unreadable",
    "unsupported",
]
KartografStoreState = Literal[
    "missing",
    "not_a_directory",
    "empty",
    "ready",
    "no_marker",
    "foreign",
    "unreadable",
    "unsupported",
    "nested",
]
Outcome = Literal["ok", "existing", "tool_missing", "refused"]


@dataclass(frozen=True)
class ObserwatorStore:
    """What a configured Obserwator store folder holds.

    ``detail`` is the schema named by the marker (``ready`` and ``unsupported``) and
    empty otherwise. ``empty`` also covers a folder that holds only the state file of
    the tool's REST server; ``no_marker`` is a folder with the layout of a store and
    no marker (``store init`` verifies the layout and writes it).
    """

    state: ObserwatorStoreState
    detail: str = ""


@dataclass(frozen=True)
class KartografStore:
    """What a configured Kartograf store folder holds.

    ``detail`` is the schema named by the marker (``ready`` and ``unsupported``), the
    folder of the other store (``nested``) and empty otherwise. ``empty`` also covers a
    folder with nothing but empty folders: the first write marks it. ``no_marker`` is a
    folder with files in the product trees of a store and no marker (``store init``
    verifies the layout and writes it); ``nested`` a folder that lies in, is or holds
    the store of another tool or of another place.
    """

    state: KartografStoreState
    detail: str = ""


@dataclass(frozen=True)
class ToolOutcome:
    """Result of a call into Obserwator that Retman makes outside an operation.

    ``tool_missing``: the package cannot be imported (``detail`` says why);
    ``refused``: Obserwator raised an error, quoted verbatim in ``detail``, with
    the ``details.reason`` it named in ``reason`` (``not_atomic``: the file system
    has no hard links); ``existing``: the store was already initialised
    (``init_obserwator_store`` only).
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


def obserwator_store_state(folder: Path) -> ObserwatorStore:
    """Whether ``folder`` is an initialised Obserwator store, judged without the tool.

    The rules are those of ``store init`` (offline, in the tool): it writes the marker
    into an empty folder, where the state files of its REST server do not count, and
    into a folder with the layout of a store (``archives/``, ``series/``,
    ``stations/`` or ``pmaxtp/``) after verifying that layout. Any other folder
    without the marker is ``foreign``. The verification itself is left to the tool.
    """
    if not folder.exists():
        return ObserwatorStore("missing")
    if not folder.is_dir():
        return ObserwatorStore("not_a_directory")
    marker = folder / OBSERWATOR_MARKER
    if marker.exists():
        try:
            schema = json.loads(marker.read_text(encoding="utf-8"))["schema"]
        except (OSError, ValueError, KeyError, TypeError):
            return ObserwatorStore("unreadable")
        if schema != OBSERWATOR_SCHEMA:
            return ObserwatorStore("unsupported", str(schema))
        return ObserwatorStore("ready", OBSERWATOR_SCHEMA)
    if any((folder / tree).is_dir() for tree in OBSERWATOR_LAYOUT_TREES):
        return ObserwatorStore("no_marker")
    content = any(
        entry.name not in OBSERWATOR_STATE_FILES for entry in folder.iterdir()
    )
    return ObserwatorStore("foreign" if content else "empty")


def _holds_files(folder: Path) -> bool:
    """Whether a folder tree holds a file; staging folders of Kartograf do not count."""
    for _, dirs, files in os.walk(folder, followlinks=False):
        if files:
            return True
        dirs[:] = [name for name in dirs if name != KARTOGRAF_STAGING]
    return False


def _kartograf_contents(folder: Path) -> tuple[bool, bool]:
    """Say what a folder without a marker holds: ``(store files, other files)``.

    Store files are files in a product tree. Any other file or link, and any other
    folder with a file in it, is other content. Empty folders and the temporary file of
    a writer that is just writing the marker are neither (``kartograf.marker``).
    """
    store = other = False
    try:
        with os.scandir(folder) as scan:
            entries = list(scan)
    except OSError:
        return False, False
    for entry in entries:
        if entry.name.startswith(f".{KARTOGRAF_MARKER}."):
            continue
        if not entry.is_dir(follow_symlinks=False):
            other = True
        elif entry.name in KARTOGRAF_TREES:
            store = store or _holds_files(Path(entry.path))
        else:
            other = other or _holds_files(Path(entry.path))
    return store, other


def _store_below(folder: Path, skip: frozenset[str]) -> Path | None:
    """Find a store marker below ``folder``; ``skip`` names top trees not entered."""
    for base, dirs, files in os.walk(folder, followlinks=False):
        here = Path(base)
        if here != folder and any(name in files for name in STORE_MARKERS):
            return here
        dirs[:] = [
            name
            for name in dirs
            if not (here / name).is_symlink() and not (here == folder and name in skip)
        ]
    return None


def _other_store(folder: Path, *, below: bool) -> Path | None:
    """Find the other store that ``folder`` lies in, is or holds, by marker names alone.

    Kartograf refuses such a folder (``conflict``, reason ``nested_store``): a marker in
    an ancestor, the marker of another tool in the folder itself and, with ``below``, a
    marker below it outside the product trees of its own store.
    """
    for ancestor in folder.parents:
        if any((ancestor / name).is_file() for name in STORE_MARKERS):
            return ancestor
    if any(
        (folder / name).is_file() for name in STORE_MARKERS if name != KARTOGRAF_MARKER
    ):
        return folder
    if not below:
        return None
    skip = KARTOGRAF_TREES if (folder / KARTOGRAF_MARKER).is_file() else frozenset()
    return _store_below(folder, skip)


def kartograf_store_state(folder: Path) -> KartografStore:
    """Whether ``folder`` is a store Kartograf will use, judged without the tool.

    The rules are those of ``kartograf.marker``: every write marks a missing or empty
    folder by itself, ``store init`` marks a folder with the layout of a store (files in
    the product trees) after verifying that layout, and a folder with other files is
    refused. The marker must be a ``kartograf-store/1`` document, and a store never
    lies in, holds or is the store of another tool (``nested``). The verification of a
    layout, and the search for a store below a folder that is refused anyway, are left
    to the tool.
    """
    path = folder.resolve()
    marker = path / KARTOGRAF_MARKER
    if marker.is_file():
        other = _other_store(path, below=True)
        if other is not None:
            return KartografStore("nested", str(other))
        try:
            schema = json.loads(marker.read_text(encoding="utf-8"))["schema"]
        except (OSError, ValueError, KeyError, TypeError):
            return KartografStore("unreadable")
        if schema != KARTOGRAF_SCHEMA:
            return KartografStore("unsupported", str(schema))
        return KartografStore("ready", KARTOGRAF_SCHEMA)
    if not path.exists():
        other = _other_store(path, below=True)
        if other is not None:
            return KartografStore("nested", str(other))
        return KartografStore("missing")
    if not path.is_dir():
        return KartografStore("not_a_directory")
    has_store_files, has_other_files = _kartograf_contents(path)
    if marker.is_file():
        # A writer marks a folder before it writes its first file: judge it again
        return kartograf_store_state(path)
    other = _other_store(path, below=not (has_store_files or has_other_files))
    if other is not None:
        return KartografStore("nested", str(other))
    if has_store_files:
        return KartografStore("no_marker")
    return KartografStore("foreign" if has_other_files else "empty")


def init_obserwator_store(folder: Path) -> ToolOutcome:
    """Initialise an Obserwator store in ``folder`` through the tool (``store init``).

    Offline and idempotent: an initialised store is left as it is. Obserwator
    refuses a folder with other files, a layout that is not that of its store, a
    path with a symbolic link, a place inside another store and a file system
    without hard links; the refusal is returned, not raised.
    """
    try:
        obserwator = importlib.import_module("obserwator")
    except ImportError as error:
        return ToolOutcome("tool_missing", str(error))
    existed = (folder / OBSERWATOR_MARKER).exists()
    try:
        obserwator.run_command("store init", options={"root": str(folder)})
    except (obserwator.ObserwatorError, OSError) as error:
        return _refused(error, obserwator.__version__)
    return ToolOutcome(
        "existing" if existed else "ok", version=str(obserwator.__version__)
    )


def probe_obserwator_write() -> ToolOutcome:
    """Check that Obserwator can write a store on this system (end to end).

    Lets the tool build its packaged offline fixture store (no network): an
    initialised store, archives, a series and a station catalog, in a temporary
    folder. It shows what a hard-link test cannot: that the installed build
    publishes versions on this operating system.
    """
    try:
        testing = importlib.import_module("obserwator.testing")
        obserwator = importlib.import_module("obserwator")
    except ImportError as error:
        return ToolOutcome("tool_missing", str(error))
    version = str(obserwator.__version__)
    # A symbolic link in the path would be refused by Obserwator (macOS: /var, /tmp)
    folder = Path(tempfile.mkdtemp(prefix="retman-obserwator-probe-")).resolve()
    try:
        testing.build_fixture_store(folder / "store")
    except (obserwator.ObserwatorError, OSError) as error:
        return _refused(error, version)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return ToolOutcome("ok", version=version)

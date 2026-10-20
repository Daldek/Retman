"""Which commands of the IMGWTools catalog the adapter does not offer, and why.

Every data command of the tool is either named in the ``commands`` of some
operation (as a call of its builder or as an offline lookup of its preview) or
listed here with the reason it is left out. The coverage test compares the union
of both with ``imgwtools.data_commands()``, so a command a new IMGWTools release
adds cannot slip through unnoticed. Each exclusion stays reachable through the
tool's own CLI and API.
"""

from typing import Final

EXCLUDED_COMMANDS: Final[dict[str, str]] = {
    "pmaxtp url": (
        "builds one URL and returns no data; the source of a PMAXTP table is "
        "recorded in the audit document of get_pmaxtp"
    ),
    "pmaxtp check": (
        "answers only 'unverifiable' for a cell not downloaded yet; the check of "
        "pmaxtp sync is the tool's own and is not offered for point operations"
    ),
    "series read": (
        "the records of series export as paged JSON for interactive clients; the "
        "file-producing path is export_station_series"
    ),
    "commands schema": (
        "describes the catalog itself; used by retman-scaffold and the drift tests, "
        "not an operation on data"
    ),
    "commands guide": "a guide for AI agents generated from the catalog, not data",
}

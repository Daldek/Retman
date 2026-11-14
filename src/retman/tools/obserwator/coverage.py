"""Which commands of the Obserwator catalog the adapter does not offer, and why.

Every data command of the tool is either named in the ``commands`` of some
operation (as a call of its builder or as an offline lookup of its preview) or
listed here with the reason it is left out. The coverage test compares the union
of both with ``obserwator.data_commands()``, so a command a new Obserwator release
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
    "commands list": (
        "the one-line summary of every catalog command, the first look of an "
        "agent at the tool; not an operation on data"
    ),
    "commands schema": (
        "describes the catalog itself; used by `scaffold` and the drift tests, "
        "not an operation on data"
    ),
    "commands guide": "a guide for AI agents generated from the catalog, not data",
    "stations export": (
        "the current station catalogs of the data root as one GeoJSON or CSV file; "
        "find_obserwator_stations writes the stations a command asks for, and a "
        "whole-catalog export is outside the release scope (PRD 7)"
    ),
    "analyses build": (
        "computes the stored analyses of every station with the hydrolog program "
        "into the data root, a long batch job for Obserwator's GUI; Retman computes "
        "with Hydrolog's own operations, and stored analyses are outside the release "
        "scope (PRD 7)"
    ),
    "analyses list": "lists the stored analyses of analyses build, not offered",
    "analyses read": "reads a stored analysis of analyses build, not offered",
    "analyses export": "exports the stored analyses of analyses build, not offered",
}

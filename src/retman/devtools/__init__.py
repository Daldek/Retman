"""Developer tools: ``retman scaffold`` drafts and the drift check (ARCHITECTURE 3.2.3).

Not for end users. The tools are read through their machine catalogs
(``get_catalog``, ``command_schema``), never through docstrings, and only offline;
every tool is imported lazily, in the small reader of ``retman.devtools.readers``.
"""

"""One small reader per tool: the tool's machine catalog as a ``ToolCatalog``.

``retman/devtools/readers/<tool>.py`` defines ``READER`` (a ``Reader``). The tool
is imported only inside its reader's functions.
"""

"""Read the ``retman-error/1`` document that ends a failed command-line call."""

import json
from typing import Any


def last_line_document(stderr: str) -> dict[str, Any]:
    """Return the last line of ``stderr`` as a document; it must be ``retman-error/1``.

    Parameters
    ----------
    stderr : str
        Everything the call wrote to stderr.

    Returns
    -------
    dict
        The parsed error document.
    """
    lines = stderr.rstrip("\n").splitlines()
    assert lines, "nothing was written to stderr"
    document = json.loads(lines[-1])
    assert isinstance(document, dict) and document["schema"] == "retman-error/1"
    return document

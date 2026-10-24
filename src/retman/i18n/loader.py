"""Loading translation files: every user- and model-facing text lives in TOML."""

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from retman.exceptions import TranslationError


class Texts:
    """
    Texts of one translation file, addressed by dotted keys.

    Parameters
    ----------
    data : dict[str, Any]
        Parsed TOML document.
    source : str
        Where the texts come from (shown in errors).

    Examples
    --------
    >>> texts = Texts({"plan": {"title": "Plan: {name}"}}, "example")
    >>> texts.get("plan.title", name="NMT")
    'Plan: NMT'
    """

    def __init__(self, data: dict[str, Any], source: str) -> None:
        self._data = data
        self.source = source

    def has(self, key: str) -> bool:
        """Whether ``key`` exists (as a text or a table)."""
        return self._lookup(key) is not None

    def get(self, key: str, **args: object) -> str:
        """
        Text under ``key`` with ``{placeholders}`` filled from ``args``.

        Raises
        ------
        TranslationError
            The key is missing or is not a text.
        """
        value = self._lookup(key)
        if not isinstance(value, str):
            raise TranslationError(f"{self.source}: missing text {key!r}")
        return value.format(**args) if args else value

    def table(self, key: str) -> dict[str, Any]:
        """Table under ``key`` (e.g. all options of a parameter)."""
        value = self._lookup(key)
        if not isinstance(value, dict):
            raise TranslationError(f"{self.source}: missing table {key!r}")
        return value

    def _lookup(self, key: str) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


def load_texts(path: Path) -> Texts:
    """Load a translation file from a path."""
    with path.open("rb") as handle:
        return Texts(tomllib.load(handle), str(path))


def load_core_texts(language: str) -> Texts:
    """
    Load core texts (``src/retman/i18n/<language>.toml``).

    Raises
    ------
    TranslationError
        No translation file for ``language``.
    """
    resource = resources.files("retman.i18n").joinpath(f"{language}.toml")
    if not resource.is_file():
        raise TranslationError(f"no core translations for language {language!r}")
    return Texts(tomllib.loads(resource.read_text(encoding="utf-8")), resource.name)

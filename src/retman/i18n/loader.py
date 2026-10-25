"""Loading translation files: every user- and model-facing text lives in TOML."""

import string
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, overload

from retman.exceptions import TranslationError

# The languages that write a decimal comma
_COMMA_LANGUAGES = ("pl",)


class _Formatter(string.Formatter):
    """``str.format`` that writes a float with the decimal mark of the language.

    A float that the template formats with ``e``, ``f`` or ``g`` (``{value:.2f}``) is
    written with a comma in Polish and with a point in English.
    """

    def __init__(self, mark: str) -> None:
        super().__init__()
        self._mark = mark

    def format_field(self, value: Any, format_spec: str) -> str:
        """Format one field; floats with a float format get the decimal mark."""
        text = str(super().format_field(value, format_spec))
        if isinstance(value, float) and format_spec[-1:] in ("e", "f", "g"):
            return text.replace(".", self._mark)
        return text


class Texts:
    """
    Texts of one translation file, addressed by dotted keys.

    Parameters
    ----------
    data : dict[str, Any]
        Parsed TOML document.
    source : str
        Where the texts come from (shown in errors).
    language : str, optional
        The language of the texts (``pl`` or ``en``); it decides the decimal mark of
        the floats that a template formats. ``en`` when absent.

    Examples
    --------
    >>> texts = Texts({"plan": {"title": "Plan: {name}"}}, "example")
    >>> texts.get("plan.title", name="NMT")
    'Plan: NMT'
    >>> Texts({"p": {"n": "{x:.1f}"}}, "example", "pl").get("p.n", x=0.5)
    '0,5'
    """

    def __init__(self, data: dict[str, Any], source: str, language: str = "en") -> None:
        self._data = data
        self.source = source
        self.language = language
        self._formatter = _Formatter("," if language in _COMMA_LANGUAGES else ".")

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
        return self._formatter.format(value, **args) if args else value

    def decimal(self, number: float, spec: str = ".2f") -> str:
        """Write ``number`` in the format ``spec`` with the language's decimal mark.

        Examples
        --------
        >>> Texts({}, "example", "pl").decimal(0.5)
        '0,50'
        """
        return self._formatter.format_field(float(number), spec)

    def table(self, key: str) -> dict[str, Any]:
        """Table under ``key`` (e.g. all options of a parameter)."""
        value = self._lookup(key)
        if not isinstance(value, dict):
            raise TranslationError(f"{self.source}: missing table {key!r}")
        return value

    def lines(self, key: str) -> list[str]:
        """List of texts under ``key`` (a TOML array of strings).

        Raises
        ------
        TranslationError
            The key is missing or is not an array of texts.
        """
        value = self._lookup(key)
        if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
            raise TranslationError(f"{self.source}: missing list of texts {key!r}")
        return list(value)

    def _lookup(self, key: str) -> Any:
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


class Message(str):
    """A text that remembers the key and the values it was made from.

    A machine document carries English texts (AGI-9.2) and the terminal shows them in
    the language of the setting ``lang``: :meth:`localized` writes the same message
    from the texts of that language, so no sentence is translated twice or parsed.

    Parameters
    ----------
    text : str
        The text in the language of the texts that made it.
    key : str
        The dotted key of the text.
    values : dict[str, object]
        The values of its placeholders; a value may be a ``Message`` itself.
    """

    key: str
    values: dict[str, object]

    def __new__(cls, text: str, key: str, values: dict[str, object]) -> "Message":
        """Create the message."""
        message = super().__new__(cls, text)
        message.key = key
        message.values = values
        return message

    def localized(self, texts: Texts) -> str:
        """Return the message written from ``texts``."""
        values = {name: localize(value, texts) for name, value in self.values.items()}
        return texts.get(self.key, **values)


class MessageTexts(Texts):
    """Texts whose :meth:`~Texts.get` returns a :class:`Message`."""

    def get(self, key: str, **args: object) -> Message:
        """Return the text under ``key`` as a :class:`Message`."""
        return Message(super().get(key, **args), key, dict(args))


@overload
def localize(value: str, texts: Texts) -> str: ...
@overload
def localize(value: object, texts: Texts) -> object: ...
def localize(value: object, texts: Texts) -> object:
    """Write ``value`` from ``texts`` when it is a :class:`Message`, else keep it.

    Examples
    --------
    >>> english = MessageTexts({"a": {"b": "Plan {n}"}}, "english")
    >>> polish = Texts({"a": {"b": "Plan nr {n}"}}, "polish", "pl")
    >>> localize(english.get("a.b", n=1), polish)
    'Plan nr 1'
    """
    return value.localized(texts) if isinstance(value, Message) else value


def load_texts(path: Path) -> Texts:
    """Load a translation file from a path (``pl.toml`` holds Polish texts)."""
    with path.open("rb") as handle:
        return Texts(tomllib.load(handle), str(path), path.stem)


def _load_core[T: Texts](language: str, texts: type[T]) -> T:
    resource = resources.files("retman.i18n").joinpath(f"{language}.toml")
    if not resource.is_file():
        raise TranslationError(f"no core translations for language {language!r}")
    return texts(
        tomllib.loads(resource.read_text(encoding="utf-8")), resource.name, language
    )


def load_core_texts(language: str) -> Texts:
    """
    Load core texts (``src/retman/i18n/<language>.toml``).

    Raises
    ------
    TranslationError
        No translation file for ``language``.
    """
    return _load_core(language, Texts)


def machine_texts() -> Texts:
    """Return the texts that machine output carries: English (AGI-9.2)."""
    return load_core_texts("en")


def machine_messages() -> MessageTexts:
    """Return the English texts as :class:`Message`, to be shown in another language."""
    return _load_core("en", MessageTexts)

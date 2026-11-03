"""The one conversion of Python values to JSON values that every document uses."""

from collections.abc import Iterable, Mapping
from pathlib import PurePath
from typing import Any


def to_jsonable(value: object) -> Any:
    """Return ``value`` as a JSON value.

    Paths become text, sets sorted lists, other iterables lists and mappings
    dictionaries with text keys; ``NaN`` and the infinities become ``None``; an
    object that has no JSON form becomes its ``str``.

    Parameters
    ----------
    value : object
        The value to convert.

    Returns
    -------
    object
        ``None``, a ``bool``, an ``int``, a ``float``, a ``str``, a ``list`` or a
        ``dict`` of these.

    Examples
    --------
    >>> to_jsonable({"n": float("nan"), "p": ("a", 1)})
    {'n': None, 'p': ['a', 1]}
    """
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        return sorted((to_jsonable(item) for item in value), key=str)
    if isinstance(value, Iterable):
        return [to_jsonable(item) for item in value]
    return str(value)

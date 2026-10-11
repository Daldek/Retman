"""Manifest schema: how a tool's operations are described (ARCHITECTURE 4.1, 4.3)."""

from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

ParamType = Literal["choice", "free", "bool"]


class ParamSpec(TypedDict):
    """
    One operation parameter.

    ``choice`` values are picked by the decision model from ``options``;
    ``free`` values come from the extractor named in ``extractor``;
    ``bool`` values come from a yes/no question to the model.
    ``accepts`` narrows a multi-type extractor (e.g. ``area``) to the value
    types the operation can use, e.g. ``["sheet"]`` or ``["bbox", "geometry"]``.
    ``depends_on`` makes the parameter apply only when another ``choice``
    parameter has one of the listed values, e.g. ``{"product": ["dem"]}``.
    """

    name: str
    type: ParamType
    options: NotRequired[list[str]]
    extractor: NotRequired[str]
    accepts: NotRequired[list[str]]
    required: NotRequired[bool]
    default: NotRequired[Any]
    multiple: NotRequired[bool]
    range: NotRequired[list[float]]
    depends_on: NotRequired[dict[str, list[str]]]


class InputSpec(TypedDict):
    """An input file of a given data kind (ARCHITECTURE 5.3)."""

    name: str
    kind: str


class OperationSpec(TypedDict):
    """One operation of a tool (ARCHITECTURE 4.3, table of operation fields)."""

    id: str
    category: str
    description: str
    inputs: list[InputSpec]
    outputs: list[str]
    params: list[ParamSpec]
    handler: str


class ManifestSpec(TypedDict):
    """The ``MANIFEST`` dictionary of ``retman/tools/<tool>/manifest.py``."""

    tool: str
    distribution: str
    supported_versions: str
    translations: dict[str, str]
    operations: list[OperationSpec]


class HandlerWarning(TypedDict):
    """A warning reported by a handler; the text lives in the tool's ``pl.toml``.

    ``key`` names an entry of the ``[warnings]`` table of the tool's translation
    file; ``args`` fills its ``{placeholders}``.
    """

    key: str
    args: dict[str, str]


class HandlerOutput(TypedDict):
    """
    What a handler returns (ARCHITECTURE 3.2.4).

    ``files`` maps a data kind (``kind``) to the files of that kind written
    into ``output_dir``; a result may have several files of one kind.
    ``values`` holds short JSON-serializable results (counts, areas).
    """

    values: dict[str, Any]
    files: dict[str, list[Path]]
    warnings: list[HandlerWarning]

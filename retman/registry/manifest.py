"""Manifest schema: how a tool's operations are described (ARCHITECTURE 4.1, 4.3)."""

from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from retman.i18n.loader import Texts

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
    # Requirement for ``uv tool install … --with`` shown by ``retman doctor``
    source: str
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


def validate_manifest(
    manifest: ManifestSpec,
    translations: dict[str, Texts],
    *,
    operation_ids: set[str] | None = None,
) -> None:
    """
    Validate operation contracts and all declared translations.

    ``operation_ids`` is shared across tools so duplicates fail at startup.
    """
    from retman.exceptions import ManifestError, TranslationError
    from retman.extractors import EXTRACTORS
    from retman.kinds import KINDS

    seen = operation_ids if operation_ids is not None else set()
    if (
        not manifest["translations"]
        or not manifest["supported_versions"]
        or not manifest["source"]
    ):
        raise ManifestError(
            f"{manifest['tool']}: missing versions, translations or source"
        )
    for language in manifest["translations"]:
        texts: Texts | None = translations.get(language)
        if texts is None:
            raise ManifestError(f"{manifest['tool']}: missing {language} translations")
    for spec in manifest["operations"]:
        op_id = spec["id"]
        if not op_id or op_id in seen:
            raise ManifestError(f"duplicate or empty operation id: {op_id}")
        seen.add(op_id)
        if not spec["handler"] or ":" not in spec["handler"]:
            raise ManifestError(f"{op_id}: invalid handler")
        for kind in [*(item["kind"] for item in spec["inputs"]), *spec["outputs"]]:
            if kind not in KINDS:
                raise ManifestError(f"{op_id}: unknown kind {kind}")
        params = {param["name"]: param for param in spec["params"]}
        if len(params) != len(spec["params"]):
            raise ManifestError(f"{op_id}: duplicate parameter")
        for param in spec["params"]:
            name = param["name"]
            if param["type"] == "free" and param.get("extractor") not in EXTRACTORS:
                raise ManifestError(f"{op_id}.{name}: unknown extractor")
            if param["type"] == "choice" and (
                not param.get("options") or len(param["options"]) + 1 > 10
            ):
                raise ManifestError(f"{op_id}.{name}: invalid choice options")
            if (
                "default" in param
                and param["type"] == "choice"
                and param["default"] not in param["options"]
            ):
                raise ManifestError(f"{op_id}.{name}: default outside options")
            for dependency, options in param.get("depends_on", {}).items():
                controlling = params.get(dependency)
                if (
                    controlling is None
                    or controlling["type"] != "choice"
                    or any(option not in controlling["options"] for option in options)
                ):
                    raise ManifestError(f"{op_id}.{name}: invalid dependency")
        for language, texts in translations.items():
            if language not in manifest["translations"]:
                continue
            # "label" is shown to the user; "description" (with synonyms and
            # English names) only to the decision model — for operations and
            # options alike; "unspecified" is never shown, so it has no label.
            # Model-decided parameters also have "model_question": what the
            # command states, not the user's question (ARCHITECTURE 4.2)
            required = [
                f"operations.{op_id}.label",
                f"operations.{op_id}.description",
            ]
            for param in spec["params"]:
                prefix = f"operations.{op_id}.params.{param['name']}"
                required.extend((f"{prefix}.label", f"{prefix}.question"))
                if param["type"] == "free":
                    required.append(f"{prefix}.example")
                if param["type"] in ("choice", "bool"):
                    required.append(f"{prefix}.model_question")
                if param["type"] == "choice":
                    for key in param["options"]:
                        required.extend(
                            f"{prefix}.options.{key}.{field}"
                            for field in ("label", "description")
                        )
                    required.append(f"{prefix}.options.unspecified.description")
            for key in required:
                try:
                    texts.get(key)
                except TranslationError as err:
                    raise ManifestError(
                        f"{manifest['tool']} ({language}): missing {key}"
                    ) from err

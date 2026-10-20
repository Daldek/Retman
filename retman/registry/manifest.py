"""Manifest schema: how a tool's operations are described (ARCHITECTURE 4.1, 4.3)."""

import json
import re
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict

from retman.i18n.loader import Texts

ParamType = Literal["choice", "free", "bool"]

# Option keys and categories are parts of dotted translation keys (the loader
# splits on "."), so they are plain snake_case words: "0_5m" with a tool value
# "0.5m", never "0.5m" itself.
_KEY = re.compile(r"[a-z0-9_]+")


class ParamSpec(TypedDict):
    """
    One operation parameter.

    ``choice`` values are picked by the decision model from ``options`` — or,
    with ``extractor``, read by code and mapped through ``option_values``
    (option key → extractor value, e.g. ``{"epsg_2180": "EPSG:2180"}``); then
    the model is never asked and an unclear command leads to a question;
    ``free`` values come from the extractor named in ``extractor``;
    ``bool`` values come from a yes/no question to the model.
    ``accepts`` narrows a multi-type extractor (e.g. ``area``) to the value
    types the operation can use, e.g. ``["sheet"]`` or ``["bbox", "geometry"]``.
    ``depends_on`` makes the parameter apply only when another ``choice``
    parameter has one of the listed values, e.g. ``{"product": ["dem"]}``.
    ``tool_values`` (``choice`` only) maps an option key to the tool's own
    value where they differ, e.g. ``{"0_5m": "0.5m", "evrf2007": "EVRF2007"}``;
    call builders read it with ``ctx.tool_value(param, key)``. ``option_meta``
    (``choice`` only) attaches an opaque JSON dictionary to an option for call
    builders and context-aware extractors, e.g. a dataset's provider and kind.
    """

    name: str
    type: ParamType
    options: NotRequired[list[str]]
    extractor: NotRequired[str]
    option_values: NotRequired[dict[str, Any]]
    accepts: NotRequired[list[str]]
    required: NotRequired[bool]
    default: NotRequired[Any]
    multiple: NotRequired[bool]
    range: NotRequired[list[float]]
    depends_on: NotRequired[dict[str, list[str]]]
    tool_values: NotRequired[dict[str, str]]
    option_meta: NotRequired[dict[str, dict[str, Any]]]


class InputSpec(TypedDict):
    """An input file of a given data kind (ARCHITECTURE 5.3)."""

    name: str
    kind: str


class OperationSpec(TypedDict):
    """
    One operation of a tool (ARCHITECTURE 4.3, table of operation fields).

    An operation declares ``handler``, ``calls`` or both. ``handler``
    (``"module:function"``) is called as ``handler(params, inputs, output_dir,
    ctx)`` and returns a ``HandlerOutput``. ``calls`` (``"module:function"``)
    is a pure builder ``calls(params, ctx) -> list[CatalogCall]``; it is run
    offline at plan time (every call is validated by the tool) and, without a
    ``handler``, executed by the generic runner after confirmation. ``commands``
    lists the catalog commands the builder may use (an inventory for drift
    checks). ``describe`` (``"module:function"``) maps the runs of ``calls`` to
    a ``HandlerOutput``; the generic mapping is used when it is absent.
    ``excluded`` lists deliberately unsupported tool values per ``choice``
    parameter: ``{param: {tool value: reason}}``.

    ``preview`` (``"module:function"``, ``(params, ctx) -> PreviewOutput``) runs
    offline when the plan is complete; ``check`` (``"module:function"``,
    ``(params, ctx) -> CheckOutput``) is an optional network step the user
    confirms separately (ARCHITECTURE 6.5). An operation that uses the network and
    writes but has nothing to ask the source beforehand says why in ``no_check``
    (a reason for maintainers, never shown to the user); the drift check (X7)
    accepts it instead of ``check`` and holds it to account when a command stops
    needing it. ``check`` and ``no_check`` exclude each other.
    """

    id: str
    category: str
    description: str
    inputs: list[InputSpec]
    outputs: list[str]
    params: list[ParamSpec]
    handler: NotRequired[str]
    calls: NotRequired[str]
    commands: NotRequired[list[str]]
    describe: NotRequired[str]
    excluded: NotRequired[dict[str, dict[str, str]]]
    preview: NotRequired[str]
    check: NotRequired[str]
    no_check: NotRequired[str]


class ManifestSpec(TypedDict):
    """
    The ``MANIFEST`` dictionary of ``retman/tools/<tool>/manifest.py``.

    ``client`` (``"module:factory"``) names the tool's command client factory
    ``factory(settings) -> RunClient``, called with the validated
    ``[tools.<tool>]`` table of ``retman.toml``; it is required when an
    operation declares ``calls``.
    """

    tool: str
    distribution: str
    # Requirement for ``uv tool install … --with`` shown by ``retman doctor``
    source: str
    supported_versions: str
    translations: dict[str, str]
    operations: list[OperationSpec]
    client: NotRequired[str]


class HandlerWarning(TypedDict):
    """A warning reported by a handler; the text lives in the tool's ``pl.toml``.

    ``key`` names an entry of the ``[warnings]`` table of the tool's translation
    file (the core's ``[warnings]`` table is the fallback, e.g.
    ``tool_notice``); ``args`` fills its ``{placeholders}``.
    """

    key: str
    args: dict[str, str]


class ToolAuditFile(TypedDict):
    """One file a tool reported: where, its checksum and version label."""

    path: str
    sha256: str | None
    version: str | None
    status: str | None


class ToolAuditCall(TypedDict):
    """One catalog command run for an operation (the ``tool`` audit block)."""

    command: str
    options: dict[str, Any]
    command_line: str
    schema: str
    status: str
    files: list[ToolAuditFile]
    # The tool's whole JSON document, saved in the result folder
    document_file: str
    sha256: str


class ToolAudit(TypedDict):
    """The ``tool`` block of ``result.json``: what was run and with which tool."""

    tool: str
    version: str
    calls: list[ToolAuditCall]


class HandlerOutput(TypedDict):
    """
    What a handler returns (ARCHITECTURE 3.2.4).

    ``files`` maps a data kind (``kind``) to the files of that kind; a result
    may have several files of one kind. They are written into ``output_dir``
    or are files of the tool's own store (``[tools.<tool>] store_dir``),
    which the result references without copying.
    ``values`` holds short JSON-serializable results (counts, areas).
    ``tool`` is the audit block of the catalog commands that were run; the
    generic runner fills it, custom handlers may.
    """

    values: dict[str, Any]
    files: dict[str, list[Path]]
    warnings: list[HandlerWarning]
    tool: NotRequired[ToolAudit]


class PreviewRow(TypedDict):
    """An extra plan row from a preview; text in the tool's ``[preview.<key>]``.

    The table has ``label`` and ``value`` texts; ``args`` fills both.
    """

    key: str
    args: dict[str, str]


class PreviewProblem(TypedDict):
    """Why the plan cannot be confirmed as it is.

    ``params`` names the parameters to ask the user again, ``key`` an entry of
    the tool's ``[problems]`` table, ``args`` fills its ``{placeholders}``. An
    empty ``params`` is a blocking problem no answer can solve (a store that
    does not exist): when nothing else can be asked again, planning stops with
    the text of the problem as its error.
    """

    params: list[str]
    key: str
    args: dict[str, str]


class PreviewOutput(TypedDict):
    """
    What a ``preview`` returns (offline, ARCHITECTURE 6.3).

    ``values`` are JSON-serializable and saved in ``result.json`` only;
    ``rows`` are shown in the plan, marked as a preview; ``problems`` reopen
    parameters (see ``PreviewProblem``).
    """

    values: dict[str, Any]
    rows: list[PreviewRow]
    problems: list[PreviewProblem]


class CheckItem(TypedDict):
    """One line of an availability report; text in the tool's ``[check]`` table."""

    key: str
    args: dict[str, str]


class CheckOutput(TypedDict):
    """
    What a ``check`` returns (a network step, ARCHITECTURE 6.5).

    ``status``: ``available`` = the plan's selection can be served as
    specified, ``partial`` = part of it, ``unavailable`` = none of it,
    ``unknown`` = could not be determined. ``items`` are in display order:
    the plan's own selection first, then alternatives.
    """

    status: Literal["available", "partial", "unavailable", "unknown"]
    items: list[CheckItem]


def _reference_ok(reference: Any) -> bool:
    """A ``"module:attribute"`` string with both parts present."""
    if not isinstance(reference, str):
        return False
    module, separator, attribute = reference.partition(":")
    return bool(separator and module and attribute)


def _validate_param(op_id: str, param: ParamSpec) -> None:
    """Rules of one parameter that do not depend on its siblings."""
    from retman.exceptions import ManifestError

    name = param["name"]
    options = param.get("options", [])
    if param["type"] == "choice" and any(not _KEY.fullmatch(key) for key in options):
        raise ManifestError(f"{op_id}.{name}: option keys must match [a-z0-9_]+")
    for field in ("tool_values", "option_meta"):
        if field in param and param["type"] != "choice":
            raise ManifestError(f"{op_id}.{name}: {field} needs a choice parameter")
    tool_values = param.get("tool_values", {})
    if tool_values:
        resolved = [tool_values.get(key, key) for key in options]
        if (
            set(tool_values) - set(options)
            or any(not isinstance(value, str) or not value for value in resolved)
            or len(set(resolved)) != len(resolved)
        ):
            raise ManifestError(f"{op_id}.{name}: invalid tool_values")
    option_meta = param.get("option_meta", {})
    if option_meta:
        if set(option_meta) - set(options) or not all(
            isinstance(item, dict) for item in option_meta.values()
        ):
            raise ManifestError(f"{op_id}.{name}: invalid option_meta")
        try:
            json.dumps(option_meta)
        except (TypeError, ValueError) as err:
            raise ManifestError(f"{op_id}.{name}: option_meta is not JSON") from err


def _validate_operation_keys(
    manifest: ManifestSpec, spec: OperationSpec, params: dict[str, ParamSpec]
) -> None:
    """Rules of the optional operation keys (handler, calls, preview, check…)."""
    from retman.exceptions import ManifestError

    op_id = spec["id"]
    for key in ("handler", "calls", "describe", "preview", "check"):
        if key in spec and not _reference_ok(spec.get(key)):
            raise ManifestError(f"{op_id}: invalid {key}")
    if "no_check" in spec:
        reason = spec["no_check"]
        if not isinstance(reason, str) or not reason.strip():
            raise ManifestError(f"{op_id}: no_check has no reason")
        if "check" in spec:
            raise ManifestError(f"{op_id}: declares both check and no_check")
    if "handler" not in spec and "calls" not in spec:
        raise ManifestError(f"{op_id}: declares neither handler nor calls")
    if "describe" in spec and "calls" not in spec:
        raise ManifestError(f"{op_id}: describe needs calls")
    commands = spec.get("commands")
    if commands is not None and (
        not commands or any(not isinstance(item, str) or not item for item in commands)
    ):
        raise ManifestError(f"{op_id}: invalid commands")
    if "calls" in spec:
        if not commands:
            raise ManifestError(f"{op_id}: calls need the list of commands")
        if "client" not in manifest:
            raise ManifestError(
                f"{manifest['tool']}: {op_id} declares calls but the manifest "
                "declares no client"
            )
    for name, values in spec.get("excluded", {}).items():
        param = params.get(name)
        if param is None or param["type"] != "choice":
            raise ManifestError(f"{op_id}.{name}: excluded needs a choice parameter")
        tool_values = param.get("tool_values", {})
        offered = {tool_values.get(key, key) for key in param["options"]}
        for value, reason in values.items():
            if not isinstance(reason, str) or not reason.strip():
                raise ManifestError(f"{op_id}.{name}: excluded {value} has no reason")
            if value in offered:
                raise ManifestError(f"{op_id}.{name}: excluded {value} is offered")


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
    from retman.extractors import extractor_known
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
    if "client" in manifest and not _reference_ok(manifest["client"]):
        raise ManifestError(f"{manifest['tool']}: invalid client")
    for language in manifest["translations"]:
        texts: Texts | None = translations.get(language)
        if texts is None:
            raise ManifestError(f"{manifest['tool']}: missing {language} translations")
    for spec in manifest["operations"]:
        op_id = spec["id"]
        if not op_id or op_id in seen:
            raise ManifestError(f"duplicate or empty operation id: {op_id}")
        seen.add(op_id)
        if not _KEY.fullmatch(spec["category"]):
            raise ManifestError(f"{op_id}: category must match [a-z0-9_]+")
        for kind in [*(item["kind"] for item in spec["inputs"]), *spec["outputs"]]:
            if kind not in KINDS:
                raise ManifestError(f"{op_id}: unknown kind {kind}")
        params = {param["name"]: param for param in spec["params"]}
        if len(params) != len(spec["params"]):
            raise ManifestError(f"{op_id}: duplicate parameter")
        _validate_operation_keys(manifest, spec, params)
        for param in spec["params"]:
            name = param["name"]
            _validate_param(op_id, param)
            if param["type"] == "free" and (
                "extractor" not in param or not extractor_known(param["extractor"])
            ):
                raise ManifestError(f"{op_id}.{name}: unknown extractor")
            if param["type"] == "choice" and (
                not param.get("options") or len(param["options"]) + 1 > 10
            ):
                raise ManifestError(f"{op_id}.{name}: invalid choice options")
            if (
                param["type"] == "choice"
                and "extractor" in param
                and (
                    not extractor_known(param["extractor"])
                    or set(param.get("option_values", {})) != set(param["options"])
                )
            ):
                raise ManifestError(f"{op_id}.{name}: invalid choice extractor")
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
            # command states, not the user's question (ARCHITECTURE 4.2).
            # A choice read by an extractor never reaches the model, so it
            # needs only user-facing texts.
            required = [
                f"operations.{op_id}.label",
                f"operations.{op_id}.description",
            ]
            if "check" in spec:
                required.append(f"operations.{op_id}.check.notice")
            for param in spec["params"]:
                prefix = f"operations.{op_id}.params.{param['name']}"
                required.extend((f"{prefix}.label", f"{prefix}.question"))
                if param["type"] == "free":
                    required.append(f"{prefix}.example")
                if not param.get("required") and "default" not in param:
                    # The plan says what leaving it unset means (N-11)
                    required.append(f"{prefix}.unset")
                by_model = param["type"] == "bool" or (
                    param["type"] == "choice" and "extractor" not in param
                )
                if by_model:
                    required.append(f"{prefix}.model_question")
                if param["type"] == "choice":
                    for key in param["options"]:
                        required.append(f"{prefix}.options.{key}.label")
                        if by_model:
                            required.append(f"{prefix}.options.{key}.description")
                    if by_model:
                        required.append(f"{prefix}.options.unspecified.description")
            for key in required:
                try:
                    texts.get(key)
                except TranslationError as err:
                    raise ManifestError(
                        f"{manifest['tool']} ({language}): missing {key}"
                    ) from err

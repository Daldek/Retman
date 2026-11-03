"""Drafts of a manifest entry, a call builder and translations from a tool's catalog.

``retman scaffold draft`` writes what the catalog and the tool's own offline
validation can say: the parameters, the choice options narrowed by probing the
tool (the pairs it accepts, the options that do not apply), the ``tool_values``
and ``depends_on`` that follow. Everything that is a decision of the author stays
a ``TODO`` marker: the category, the data kinds, the extractors, the Polish
texts. A draft is never applied to a reviewed file (ARCHITECTURE 3.2.3).
"""

import itertools
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field

from retman.devtools.model import (
    CommandInfo,
    OptionInfo,
    Reader,
    ScaffoldError,
    ToolCatalog,
)

# The decision model is offered at most this many real options (ARCHITECTURE 3.4)
MAX_OPTIONS = 9
# Choice combinations probed together; above this every choice is probed alone
MAX_COMBINATIONS = 4000
# The options that make up the ``area`` parameter, with the value type each accepts
AREA_ACCEPTS = {
    "sheet": "sheet",
    "teryt": "teryt",
    "bbox": "bbox",
    "geometry": "geometry",
}
# Options that travel with an area option and are no parameter of their own
AREA_COMPANIONS = frozenset({"bbox_crs", "layer"})
# The options an area value of each type sets, and how (for the builder draft)
_AREA_OPTIONS = {
    "sheet": ("sheet",),
    "teryt": ("teryt",),
    "bbox": ("bbox", "bbox_crs"),
    "geometry": ("geometry", "layer"),
}
_AREA_LINES = {
    "sheet": ('options["sheet"] = area["code"]',),
    "teryt": ('options["teryt"] = area["code"]',),
    "bbox": (
        'options["bbox"] = [area["min_x"], area["min_y"], '
        'area["max_x"], area["max_y"]]',
        'options["bbox_crs"] = area["crs"]',
    ),
    "geometry": (
        'options["geometry"] = area["path"]',
        'options["layer"] = area["layer"]',
    ),
}
# Option types that are yes/no switches
_SWITCHES = frozenset({"flag", "bool", "boolean"})
TODO = "TODO"


@dataclass
class _Param:
    """A parameter of the drafted operation, before it is rendered."""

    name: str
    kind: str
    options: list[str] = field(default_factory=list)
    tool_values: dict[str, str] = field(default_factory=dict)
    required: bool = True
    depends_on: dict[str, list[str]] = field(default_factory=dict)
    accepts: list[str] = field(default_factory=list)
    bounds: tuple[float, float] | None = None
    tool_options: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    hint: str = ""


@dataclass(frozen=True)
class Draft:
    """The three parts of a draft: manifest entry, builder, translation skeleton."""

    operation_id: str
    manifest: str
    builder: str
    translations: str

    def python(self) -> str:
        """Return the manifest entry and the builder as one file to read and cut up."""
        return f"{self.manifest}\n\n{self.builder}"


def _slug(value: str) -> str:
    """Build an option key: lower case words joined by ``_`` (dots break lookup)."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "value"


def _keys(values: Sequence[str]) -> tuple[list[str], dict[str, str]]:
    """Option keys of tool values, unique, and the ``tool_values`` where they differ."""
    keys: list[str] = []
    tool_values: dict[str, str] = {}
    for value in values:
        base = _slug(value)
        key, number = base, 2
        while key in keys:
            key, number = f"{base}_{number}", number + 1
        keys.append(key)
        if key != value:
            tool_values[key] = value
    return keys, tool_values


def _literal(value: object) -> str:
    """Render a Python literal for the simple values of a manifest."""
    if isinstance(value, dict):
        inner = ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, list | tuple):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, bool | int | float) or value is None:
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def _example_base(
    info: CommandInfo, fix: Mapping[str, object], kept: set[str]
) -> dict[str, object]:
    """Pick a valid starting call: the documented example nearest to the fixed options.

    Only options the draft exposes or fixes stay (the call must look like what the
    operation will send); the fixed ones always win.
    """
    examples = [dict(item) for item in info.examples]
    chosen = next(
        (
            item
            for item in examples
            if all(item.get(name, value) == value for name, value in fix.items())
        ),
        examples[0] if examples else {},
    )
    base = {name: value for name, value in chosen.items() if name in kept}
    base.update(fix)
    return base


def _domain(option: OptionInfo) -> list[str | None]:
    """List what a probe tries for an option: its values, and none if optional."""
    values: list[str | None] = list(option.allowed or ())
    if not option.required:
        values.append(None)
    return values


def _probe(
    command: str,
    reader: Reader,
    base: Mapping[str, object],
    choices: Sequence[OptionInfo],
) -> tuple[list[dict[str, str | None]], str]:
    """Find the combinations of the choice options that the tool accepts.

    Returns the accepted combinations (an option left out is ``None``) and, when
    none was accepted, the tool's reason for the first rejection.
    """
    domains = {option.name: _domain(option) for option in choices}
    anchor: dict[str, str | None] = {
        name: str(base[name]) if name in base else values[0]
        for name, values in domains.items()
    }
    size = 1
    for values in domains.values():
        size *= len(values)
    combos: Iterator[dict[str, str | None]]
    if size <= MAX_COMBINATIONS:
        names = list(domains)
        combos = (
            dict(zip(names, picked, strict=True))
            for picked in itertools.product(*(domains[name] for name in names))
        )
    else:
        combos = (
            {**anchor, name: value}
            for name, values in domains.items()
            for value in values
        )
    accepted: list[dict[str, str | None]] = []
    reason = ""
    fixed = {k: v for k, v in base.items() if k not in domains}
    for combo in combos:
        options = {**fixed, **{k: v for k, v in combo.items() if v is not None}}
        verdict = reader.validate(command, options)
        if verdict.ok:
            accepted.append(combo)
        elif not reason:
            reason = verdict.detail
    return accepted, reason


def _depends_on(
    params: Sequence[_Param],
    accepted: Sequence[Mapping[str, str | None]],
    options: Mapping[str, Mapping[str, str]],
) -> None:
    """Find the options that do not apply under some value of another option.

    ``P2`` does not apply at ``P1 = v`` when every accepted combination with that
    value leaves ``P2`` out (NMT 100 m takes no vertical CRS); ``P2`` then gets
    ``depends_on`` the values of ``P1`` under which it does apply.
    """
    choices = [param for param in params if param.kind == "choice"]
    for dependent in choices:
        for controller in choices:
            if controller is dependent or dependent.depends_on:
                continue
            applies: dict[str, bool] = {}
            for combo in accepted:
                value = combo.get(controller.name)
                if value is None:
                    continue
                applies[value] = applies.get(value, False) or (
                    combo.get(dependent.name) is not None
                )
            if any(applies.values()) and not all(applies.values()):
                keys = options[controller.name]
                present = {value for value, there in applies.items() if there}
                dependent.depends_on[controller.name] = [
                    keys[value] for value in applies if value in present
                ]
                # Where the option applies the tool needs it, unless an accepted
                # combination leaves it out there
                dependent.required = dependent.required or all(
                    combo.get(dependent.name) is not None
                    for combo in accepted
                    if combo.get(controller.name) in present
                )


def _pair_table(
    first: _Param,
    second: _Param,
    accepted: Sequence[Mapping[str, str | None]],
) -> str:
    """Tabulate the accepted values of the second choice per value of the first."""
    pairs: dict[str, list[str]] = {}
    for combo in accepted:
        head = combo.get(first.name)
        if head is None:
            continue
        tail = combo.get(second.name)
        group = pairs.setdefault(head, [])
        if (tail or "-") not in group:
            group.append(tail or "-")
    cells = "  ".join(f"{head}/{','.join(tails)}" for head, tails in pairs.items())
    return f"valid pairs ({first.name}/{second.name}): {cells}"


def build_draft(
    catalog: ToolCatalog,
    reader: Reader,
    command: str,
    *,
    fix: Mapping[str, object] | None = None,
    only: Sequence[str] | None = None,
    operation_id: str | None = None,
) -> Draft:
    """Draft an operation for one catalog command.

    Parameters
    ----------
    catalog : ToolCatalog
        The tool's catalog.
    reader : Reader
        Gives the tool's own offline validation for the probes.
    command : str
        The catalog command, e.g. ``"elevation download"``.
    fix : Mapping[str, object], optional
        Options the operation always sends with a fixed value; they are no
        parameters (``{"product": "nmt"}``).
    only : Sequence[str], optional
        The options to expose as parameters; all other free options are left out.
    operation_id : str, optional
        The operation's id; the command with ``_`` instead of spaces by default.

    Raises
    ------
    ScaffoldError
        An unknown command or option, or an option both fixed and exposed.
    """
    info = catalog.commands.get(command)
    if info is None:
        known = ", ".join(sorted(catalog.commands))
        raise ScaffoldError(f"unknown command {command!r}; the catalog has: {known}")
    fixed = dict(fix or {})
    names = {option.name for option in info.options}
    for name in [*fixed, *(only or ())]:
        if name not in names:
            raise ScaffoldError(f"{command!r} has no option {name!r}")
    both = sorted(set(fixed) & set(only or ()))
    if both:
        raise ScaffoldError(f"option {both[0]!r} is both fixed and exposed")
    operation = operation_id or _slug(command)
    selected = [
        option
        for option in info.options
        if option.name not in fixed
        and (only is None or option.name in only or option.name in AREA_COMPANIONS)
    ]
    params: list[_Param] = []
    area_options = [option for option in selected if option.name in AREA_ACCEPTS]
    if area_options:
        area = _Param(
            "area",
            "free",
            accepts=[AREA_ACCEPTS[option.name] for option in area_options],
            tool_options=[
                option.name
                for option in selected
                if option.name in AREA_ACCEPTS or option.name in AREA_COMPANIONS
            ],
            hint="; ".join(option.description for option in area_options),
        )
        params.append(area)
    choices = [
        option
        for option in selected
        if option.allowed
        and option.name not in AREA_ACCEPTS
        and option.name not in AREA_COMPANIONS
    ]
    kept = {option.name for option in selected} | set(fixed)
    base = _example_base(info, fixed, kept)
    accepted, reason = _probe(command, reader, base, choices) if choices else ([], "")
    narrowed = bool(accepted)
    mapping: dict[str, dict[str, str]] = {}
    for option in choices:
        values = list(option.allowed or ())
        if narrowed:
            kept_values = [
                value
                for value in values
                if any(c.get(option.name) == value for c in accepted)
            ]
            # An option that no accepted combination uses keeps the whole list
            values = kept_values or values
        keys, tool_values = _keys(values)
        mapping[option.name] = dict(zip(values, keys, strict=True))
        param = _Param(
            option.name,
            "choice",
            options=keys,
            tool_values=tool_values,
            required=option.required
            or (narrowed and not any(c.get(option.name) is None for c in accepted)),
            tool_options=[option.name],
            hint=option.description,
        )
        if len(keys) > MAX_OPTIONS:
            param.notes.append(
                f"SPLIT_REQUIRED: {len(keys)} options, more than the {MAX_OPTIONS} "
                "a decision offers; split the operation or the parameter"
            )
        params.append(param)
    for option in selected:
        if (
            option in choices
            or option.name in AREA_ACCEPTS
            or option.name in AREA_COMPANIONS
        ):
            continue
        free = _Param(
            option.name,
            "bool" if option.kind in _SWITCHES else "free",
            required=option.required,
            tool_options=[option.name],
            hint=option.description,
        )
        if option.minimum is not None and option.maximum is not None:
            free.bounds = (option.minimum, option.maximum)
        params.append(free)
    notes: list[str] = []
    if narrowed:
        _depends_on(params, accepted, mapping)
        pair = [param for param in params if param.kind == "choice"][:2]
        if len(pair) == 2:
            notes.append(_pair_table(pair[0], pair[1], accepted))
    elif choices:
        notes.append(
            "choices not narrowed: the tool rejected every probe"
            + (f" ({reason.strip().splitlines()[0]})" if reason.strip() else "")
            + "; fix the missing options with --fix"
        )
    return Draft(
        operation,
        _render_manifest(catalog.tool, operation, info, params, notes),
        _render_builder(operation, info, fixed, params),
        _render_translations(operation, info, params),
    )


def _render_manifest(
    tool: str,
    operation: str,
    info: CommandInfo,
    params: Sequence[_Param],
    notes: Sequence[str],
) -> str:
    """Render the manifest entry as Python source (a dictionary literal)."""
    lines = [f"# manifest entry (src/retman/tools/{tool}/manifest.py)"]
    lines.extend(f"# {note}" for note in notes)
    lines += [
        "{",
        f'    "id": {_literal(operation)},',
        f'    "category": "{TODO}",  # TODO: category of the first recognition stage',
        f'    "description": "{TODO}",  # catalog: {info.summary}',
        '    "inputs": [],',
        f'    "outputs": ["{TODO}"],  # TODO: data kind(s), see src/retman/kinds.py',
        f'    "commands": [{_literal(info.id)}],',
        f'    "calls": {_literal(f"retman.tools.{tool}.calls:{operation}")},',
        '    "params": [',
    ]
    for param in params:
        for note in param.notes:
            lines.append(f"        # {note}")
        lines.append("        {")
        lines.append(f'            "name": {_literal(param.name)},')
        lines.append(f'            "type": {_literal(param.kind)},')
        if param.kind == "free" and param.name == "area":
            lines.append('            "extractor": "area",')
        elif param.kind == "free":
            lines.append(
                f'            "extractor": "{TODO}",  # see src/retman/extractors'
            )
        if param.accepts:
            lines.append(f'            "accepts": {_literal(param.accepts)},')
        if param.kind == "choice":
            lines.append(f'            "options": {_literal(param.options)},')
        if param.tool_values:
            lines.append(f'            "tool_values": {_literal(param.tool_values)},')
        if param.required:
            lines.append('            "required": True,')
        if param.bounds is not None:
            lines.append(f'            "range": {_literal(list(param.bounds))},')
        if param.depends_on:
            lines.append(f'            "depends_on": {_literal(param.depends_on)},')
        lines.append("        },")
    lines += ["    ],", "}"]
    return "\n".join(lines)


def _render_builder(
    operation: str,
    info: CommandInfo,
    fixed: Mapping[str, object],
    params: Sequence[_Param],
) -> str:
    """Render the call builder as Python source: the options of one catalog call."""
    lines = [
        "# call builder (src/retman/tools/<tool>/calls.py)",
        "from typing import Any",
        "",
        "from retman.adapters.catalog import CatalogCall, ToolContext",
        "",
        "",
        f"def {operation}(",
        "    params: dict[str, Any], ctx: ToolContext",
        ") -> list[CatalogCall]:",
        f'    """{TODO}: what this operation asks the tool for."""',
        f"    options: dict[str, object] = {_literal(dict(fixed))}",
    ]
    routing: dict[str, str] = {}
    for param in params:
        # A parameter that may be unset (optional, or not applicable) is guarded
        guarded = not param.required or bool(param.depends_on)
        indent = "        " if guarded else "    "
        if guarded:
            lines.append(f'    if "{param.name}" in params:')
        if param.name == "area":
            lines.append(f'{indent}area = params["area"]')
            for index, accept in enumerate(param.accepts):
                keyword = "if" if index == 0 else "elif"
                lines.append(f'{indent}{keyword} area["type"] == "{accept}":')
                lines.extend(f"{indent}    {line}" for line in _AREA_LINES[accept])
                routing.update(dict.fromkeys(_AREA_OPTIONS[accept], "area"))
        elif param.kind == "choice":
            lines.append(
                f'{indent}options["{param.name}"] = '
                f'ctx.tool_value("{param.name}", params["{param.name}"])'
            )
        else:
            lines.append(f'{indent}options["{param.name}"] = params["{param.name}"]')
    lines += [
        "    return [",
        "        CatalogCall(",
        f"            {_literal(info.id)},",
        "            options,",
        f'            kind="{TODO}",',
        f"            params={_literal(routing)},",
        "        )",
        "    ]",
    ]
    return "\n".join(lines)


def _render_translations(
    operation: str, info: CommandInfo, params: Sequence[_Param]
) -> str:
    """Render the skeleton of ``pl.toml`` and ``en.toml``: every key the check needs."""
    prefix = f"operations.{operation}"
    lines = [
        "# translation skeleton (src/retman/tools/<tool>/pl.toml and en.toml); "
        f"{info.summary}",
        f"[{prefix}]",
        f'label = "{TODO}"',
        f'description = "{TODO}"  # for the model: synonyms and English names',
    ]
    for param in params:
        lines += ["", f"[{prefix}.params.{param.name}]"]
        if param.hint:
            lines.append(f"# catalog: {param.hint}")
        lines += [f'label = "{TODO}"', f'question = "{TODO}"']
        by_model = param.kind in ("bool", "choice")
        if by_model:
            lines.append(f'model_question = "{TODO}"  # what the command states')
        if param.kind == "free":
            lines.append(f'example = "{TODO}"')
        for key in param.options:
            lines.append(f'options.{key}.label = "{TODO}"')
            lines.append(f'options.{key}.description = "{TODO}"')
        if param.kind == "choice":
            lines.append(f'options.unspecified.description = "{TODO}"')
    return "\n".join(lines)


def classify(info: CommandInfo) -> str:
    """Suggest a use of a catalog command, by what a run does (a text key).

    A command that ``validate_command`` and ``run_command`` do not take can only
    be a helper of the library (``helper``), or a network query (``query``).
    """
    if not info.data:
        return "query" if info.network else "helper"
    if info.network and info.writes:
        return "download"
    if info.network:
        return "live"
    if info.writes:
        return "setup"
    return "lookup"

"""The grid a drift check runs an operation's call builder over.

A *point* is a complete parameter set as the pipeline would hand it to the
builder: every choice and yes/no parameter that applies has a value (an optional
one may also stay unset), the free parameters come from *samples*, the free
values of the operation's complete rows in the ``retman-eval`` dataset. The
choices form a cartesian product pruned by ``depends_on``; this is a superset of
what the tool accepts by construction (a pair like 5 m + KRON86 is in it), which
is why the check classifies rejections instead of failing on them.
"""

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from retman.eval.dataset import EvalCommand
from retman.registry.manifest import OperationSpec, ParamSpec

# Choice combinations of one operation above which the choices are varied one at
# a time (the full product would make the check slow)
MAX_CHOICE_POINTS = 20_000
# Samples of free values kept per operation: per shape of the values, and in all
SAMPLES_PER_SHAPE = 2
MAX_SAMPLES = 12

# Keys of dictionary values that say nothing about the shape of a sample
_VOLATILE_KEYS = frozenset({"name", "river", "raw", "text"})
_ABSENT = object()


def applicable(spec: ParamSpec, values: Mapping[str, Any]) -> bool:
    """Whether the parameter applies, by ``depends_on`` (as the pipeline decides)."""
    return all(
        name in values and values[name] in options
        for name, options in spec.get("depends_on", {}).items()
    )


def _enumerable(spec: ParamSpec) -> bool:
    return spec["type"] in ("choice", "bool")


def _domain(spec: ParamSpec) -> list[Any]:
    """The values a choice or yes/no parameter takes; ``_ABSENT`` if it may stay unset.

    A parameter that is neither required nor has a default is left unset when the
    command does not state it (optional parameters are never asked).
    """
    values: list[Any] = (
        list(spec["options"]) if spec["type"] == "choice" else [False, True]
    )
    if not spec.get("required") and "default" not in spec:
        values.append(_ABSENT)
    return values


def _ordered(params: Sequence[ParamSpec]) -> list[ParamSpec]:
    """Choice and yes/no parameters, controllers before what depends on them."""
    pending = [spec for spec in params if _enumerable(spec)]
    names = {spec["name"] for spec in pending}
    ordered: list[ParamSpec] = []
    placed: set[str] = set()
    while pending:
        ready = next(
            (
                spec
                for spec in pending
                if all(
                    controller in placed or controller not in names
                    for controller in spec.get("depends_on", {})
                )
            ),
            # A dependency cycle: manifest order decides
            pending[0],
        )
        pending.remove(ready)
        ordered.append(ready)
        placed.add(ready["name"])
    return ordered


def _assign(ordered: Sequence[ParamSpec], chosen: dict[str, Any]) -> dict[str, Any]:
    """One value per applicable parameter: from ``chosen``, else its first option."""
    values: dict[str, Any] = {}
    for spec in ordered:
        if not applicable(spec, values):
            continue
        value = chosen.get(spec["name"], _domain(spec)[0])
        if value is not _ABSENT:
            values[spec["name"]] = value
    return values


def _enabling(ordered: Sequence[ParamSpec], name: str) -> dict[str, Any]:
    """Values of the other choices that make a parameter apply (the first allowed).

    The one-at-a-time grid varies a parameter from a base point; a parameter that
    depends on another choice would never be reached from a base that does not
    satisfy it, so its values would look "not offered" to the coverage check.
    """
    by_name = {spec["name"]: spec for spec in ordered}
    needed: dict[str, Any] = {}
    pending = [name]
    while pending:
        spec = by_name.get(pending.pop())
        if spec is None:
            continue
        for controller, options in spec.get("depends_on", {}).items():
            if controller in by_name and controller not in needed:
                needed[controller] = options[0]
                pending.append(controller)
    return needed


def choice_points(
    spec: OperationSpec, *, reduced: bool = False
) -> tuple[list[dict[str, Any]], bool]:
    """Every combination of the operation's choices that a plan can hold.

    Parameters
    ----------
    spec : OperationSpec
        The operation.
    reduced : bool, optional
        Vary one choice at a time from a base point instead of building the
        cartesian product. Also used when the product exceeds
        ``MAX_CHOICE_POINTS``.

    Returns
    -------
    tuple[list[dict[str, Any]], bool]
        The points (choice and yes/no values only) and whether they were
        reduced to one-at-a-time variations.
    """
    ordered = _ordered(spec["params"])
    size = math.prod(len(_domain(item)) for item in ordered)
    reduced = reduced or size > MAX_CHOICE_POINTS
    points: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(values: dict[str, Any]) -> None:
        key = json.dumps(values, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            points.append(values)

    if reduced:
        add(_assign(ordered, {}))
        for item in ordered:
            for value in _domain(item):
                add(
                    _assign(
                        ordered,
                        {**_enabling(ordered, item["name"]), item["name"]: value},
                    )
                )
        return points, size > MAX_CHOICE_POINTS

    def walk(index: int, values: dict[str, Any]) -> None:
        if index == len(ordered):
            add(dict(values))
            return
        item = ordered[index]
        if not applicable(item, values):
            walk(index + 1, values)
            return
        for value in _domain(item):
            if value is _ABSENT:
                walk(index + 1, values)
            else:
                values[item["name"]] = value
                walk(index + 1, values)
                del values[item["name"]]

    walk(0, {})
    return points, False


def _has_geometry(value: Any) -> bool:
    """Whether a free value names a geometry file (it cannot be validated offline)."""
    if isinstance(value, dict):
        return value.get("type") == "geometry"
    if isinstance(value, list):
        return any(_has_geometry(item) for item in value)
    return False


def _shape(value: Any) -> Any:
    """What kind of value this is, not its particulars: ``7.171.21`` is ``9.9.9``."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return re.sub(r"[A-Za-z]+", "a", re.sub(r"\d+", "9", value))
    if isinstance(value, dict):
        return tuple(
            sorted(
                (key, _shape(item))
                for key, item in value.items()
                if key not in _VOLATILE_KEYS
            )
        )
    if isinstance(value, list):
        return ("list", len(value) > 1, _shape(value[0]) if value else None)
    return type(value).__name__


def free_samples(
    spec: OperationSpec, rows: Iterable[EvalCommand], *, limit: int = MAX_SAMPLES
) -> list[dict[str, Any]]:
    """Free values of the operation's complete rows, varied in shape and capped.

    A complete row expects no question, so it states every parameter that applies.
    Only the free parameters are taken (the choices come from the grid). Rows with
    a geometry file are left out: the tool would have to read the file.
    """
    free = {param["name"] for param in spec["params"] if param["type"] == "free"}
    groups: dict[Any, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for row in rows:
        if row.operation != spec["id"] or row.expect_clarify:
            continue
        sample = {name: value for name, value in row.params.items() if name in free}
        key = json.dumps(sample, sort_keys=True, default=str)
        if key in seen or any(_has_geometry(value) for value in sample.values()):
            continue
        seen.add(key)
        shape = tuple(sorted((name, _shape(value)) for name, value in sample.items()))
        groups.setdefault(shape, []).append(sample)
    samples: list[dict[str, Any]] = []
    for rank in range(SAMPLES_PER_SHAPE):
        for members in groups.values():
            if rank < len(members) and len(samples) < limit:
                samples.append(members[rank])
    return samples


def _prune(values: dict[str, Any], params: Sequence[ParamSpec]) -> dict[str, Any]:
    """Drop the values of parameters that do not apply (this may free others)."""
    changed = True
    while changed:
        changed = False
        for spec in params:
            if spec["name"] in values and not applicable(spec, values):
                del values[spec["name"]]
                changed = True
    return values


def _complete(values: Mapping[str, Any], params: Sequence[ParamSpec]) -> bool:
    """Whether every applicable parameter that must have a value has one."""
    return all(
        spec["name"] in values
        or "default" in spec
        or not spec.get("required")
        or not applicable(spec, values)
        for spec in params
    )


def points(
    spec: OperationSpec,
    samples: Sequence[Mapping[str, Any]],
    *,
    reduced: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """The complete parameter sets of the operation: choices times free samples.

    Returns
    -------
    tuple[list[dict[str, Any]], bool]
        The points, and whether the choices were reduced (see ``choice_points``).
        Samples that leave a required parameter without a value yield no point.
    """
    params = spec["params"]
    choices, was_reduced = choice_points(spec, reduced=reduced)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sample in samples[:1] if reduced else samples:
        for choice in choices:
            values: dict[str, Any] = {**choice, **sample}
            for param in params:
                if param["type"] == "free" and "default" in param:
                    values.setdefault(param["name"], param["default"])
            values = _prune(values, params)
            if not _complete(values, params):
                continue
            key = json.dumps(values, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                result.append(values)
    return result, was_reduced


def _describe_free(value: Any) -> str:
    """A free value in a line: its type and, if it has one, its code or path."""
    if isinstance(value, dict):
        detail = value.get("code") or value.get("path")
        return f"{value.get('type')}:{detail}" if detail else str(value.get("type"))
    return str(value)


def describe_point(spec: OperationSpec, values: Mapping[str, Any]) -> str:
    """A point in a line: ``name=value``, a free value by its type and code."""
    parts: list[str] = []
    for param in spec["params"]:
        name = param["name"]
        if name not in values:
            continue
        value = values[name]
        shown = _describe_free(value) if param["type"] == "free" else value
        parts.append(f"{name}={shown}")
    return ", ".join(parts)

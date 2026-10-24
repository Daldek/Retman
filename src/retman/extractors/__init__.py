"""Extractor and validator registries for core parameter resolution.

A parameter's ``extractor`` names exactly one entry of ``EXTRACTORS`` (reads the
text alone) or of ``CONTEXT_EXTRACTORS`` (also needs the offline facts of an
``ExtractionContext``: the dataset's variables, today's date, the station
catalog). The pipeline does not need to know which: it calls ``read_command``,
``read_answer``, ``validate_value``, ``explain_missing`` and ``describe_value``.
"""

from collections.abc import Callable
from typing import Any

from retman.extractors.areas import extract_area, validate_area
from retman.extractors.base import ExtractionContext, Hint, Match, TextSource
from retman.extractors.coordinates import (
    describe_grid_cell,
    describe_point,
    extract_grid_cell,
    extract_point,
    read_grid_cell_answer,
    read_point_answer,
    validate_grid_cell,
    validate_point,
)
from retman.extractors.crs import extract_crs, read_crs_answer, validate_crs
from retman.extractors.dates import (
    describe_period,
    explain_period,
    extract_period,
    extract_year_type,
    extract_years,
    read_period_answer,
    read_year_type_answer,
    read_years_answer,
    validate_period,
    validate_year_type,
    validate_years,
)
from retman.extractors.identifiers import (
    extract_identifiers,
    read_identifier_answer,
    validate_identifier,
)
from retman.extractors.numbers import (
    describe_duration,
    extract_duration,
    read_duration_answer,
    validate_duration,
)
from retman.extractors.paths import extract_paths, validate_path
from retman.extractors.places import (
    describe_place_query,
    describe_synop_station,
    extract_place_query,
    extract_synop_station,
    read_place_query_answer,
    read_synop_station_answer,
    validate_place_query,
    validate_synop_station,
)
from retman.extractors.probability import (
    describe_probability,
    extract_probability,
    read_probability_answer,
    validate_probability,
)
from retman.extractors.results import extract_result_refs, validate_result
from retman.extractors.stations import (
    describe_station,
    explain_station,
    extract_station,
    validate_station,
)
from retman.extractors.variables import (
    describe_variable,
    extract_variables,
    validate_variables,
)

Reader = Callable[[str], list[Match]]
ContextReader = Callable[[str, ExtractionContext], list[Match]]


def _ignoring_context(reader: Reader) -> ContextReader:
    """A text-only reader as a context-aware one (its validator needs ``today``)."""

    def read(text: str, ctx: ExtractionContext) -> list[Match]:
        return reader(text)

    return read


def _explain_period(text: str, ctx: ExtractionContext) -> Hint | None:
    return explain_period(text)


EXTRACTORS: dict[str, Reader] = {
    "area": extract_area,
    "crs": extract_crs,
    "duration": extract_duration,
    "grid_cell": extract_grid_cell,
    "identifier": extract_identifiers,
    "path": extract_paths,
    "place_query": extract_place_query,
    "point": extract_point,
    "probability": extract_probability,
    "result": extract_result_refs,
    "synop_station": extract_synop_station,
    "year_type": extract_year_type,
}
# Answers to a question about one parameter may need laxer reading than the
# whole command (e.g. a bare "2180"); extractors not listed read answers as is.
ANSWER_EXTRACTORS: dict[str, Reader] = {
    "crs": read_crs_answer,
    "duration": read_duration_answer,
    "grid_cell": read_grid_cell_answer,
    "identifier": read_identifier_answer,
    "place_query": read_place_query_answer,
    "point": read_point_answer,
    "probability": read_probability_answer,
    "synop_station": read_synop_station_answer,
    "year_type": read_year_type_answer,
}
VALIDATORS: dict[str, Callable[[Any], str | None]] = {
    "area": validate_area,
    "crs": validate_crs,
    "duration": validate_duration,
    "grid_cell": validate_grid_cell,
    "identifier": validate_identifier,
    "path": validate_path,
    "place_query": validate_place_query,
    "point": validate_point,
    "probability": validate_probability,
    "result": validate_result,
    "synop_station": validate_synop_station,
    "year_type": validate_year_type,
}

CONTEXT_EXTRACTORS: dict[str, ContextReader] = {
    "period": _ignoring_context(extract_period),
    "station": extract_station,
    "variables": extract_variables,
    "years": _ignoring_context(extract_years),
}
CONTEXT_ANSWER_EXTRACTORS: dict[str, ContextReader] = {
    "period": _ignoring_context(read_period_answer),
    "years": _ignoring_context(read_years_answer),
}
CONTEXT_VALIDATORS: dict[str, Callable[[Any, ExtractionContext], str | None]] = {
    "period": validate_period,
    "station": validate_station,
    "variables": validate_variables,
    "years": validate_years,
}
# Why a required parameter got no usable reading (shown with its question).
CONTEXT_HINTS: dict[str, Callable[[str, ExtractionContext], Hint | None]] = {
    "period": _explain_period,
    "station": explain_station,
    "years": _explain_period,
}
# Plan text of a value, by extractor name; extractors not listed are shown as is.
DESCRIBERS: dict[str, Callable[[Any, TextSource], str]] = {
    "duration": describe_duration,
    "grid_cell": describe_grid_cell,
    "period": describe_period,
    "place_query": describe_place_query,
    "point": describe_point,
    "probability": describe_probability,
    "station": describe_station,
    "synop_station": describe_synop_station,
    "variables": describe_variable,
    "years": describe_period,
}


def extractor_known(name: str) -> bool:
    """Whether ``name`` is a registered extractor (plain or context-aware)."""
    return name in EXTRACTORS or name in CONTEXT_EXTRACTORS


def read_command(name: str, text: str, ctx: ExtractionContext) -> list[Match]:
    """Values of extractor ``name`` in the user's command."""
    if name in CONTEXT_EXTRACTORS:
        return CONTEXT_EXTRACTORS[name](text, ctx)
    return EXTRACTORS[name](text)


def read_answer(name: str, text: str, ctx: ExtractionContext) -> list[Match]:
    """Values of extractor ``name`` in an answer to the question about its parameter.

    Uses the extractor's lax answer reader when it has one, otherwise the same
    reader as for commands.
    """
    if name in CONTEXT_EXTRACTORS:
        reader = CONTEXT_ANSWER_EXTRACTORS.get(name, CONTEXT_EXTRACTORS[name])
        return reader(text, ctx)
    return ANSWER_EXTRACTORS.get(name, EXTRACTORS[name])(text)


def validate_value(name: str, value: Any, ctx: ExtractionContext) -> str | None:
    """Translation key of the problem with ``value``, or None if it is valid."""
    if name in CONTEXT_VALIDATORS:
        return CONTEXT_VALIDATORS[name](value, ctx)
    return VALIDATORS[name](value)


def explain_missing(name: str, text: str, ctx: ExtractionContext) -> Hint | None:
    """Hint for the question about a required parameter nothing was read for."""
    explain = CONTEXT_HINTS.get(name)
    return explain(text, ctx) if explain is not None else None


def describe_value(extractor: str, value: Any, texts: TextSource) -> str | None:
    """Plan text of one value of ``extractor``; None if it has no special text."""
    describe = DESCRIBERS.get(extractor)
    return describe(value, texts) if describe is not None else None

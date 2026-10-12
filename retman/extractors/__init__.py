"""Extractor and validator registries for core parameter resolution."""

from collections.abc import Callable
from typing import Any

from retman.extractors.areas import extract_area, validate_area
from retman.extractors.base import Match
from retman.extractors.crs import extract_crs, read_crs_answer, validate_crs
from retman.extractors.paths import extract_paths, validate_path
from retman.extractors.results import extract_result_refs, validate_result

EXTRACTORS: dict[str, Callable[[str], list[Match]]] = {
    "area": extract_area,
    "crs": extract_crs,
    "path": extract_paths,
    "result": extract_result_refs,
}
# Answers to a question about one parameter may need laxer reading than the
# whole command (e.g. a bare "2180"); extractors not listed read answers as is.
ANSWER_EXTRACTORS: dict[str, Callable[[str], list[Match]]] = {
    "crs": read_crs_answer,
}
VALIDATORS: dict[str, Callable[[Any], str | None]] = {
    "area": validate_area,
    "crs": validate_crs,
    "path": validate_path,
    "result": validate_result,
}

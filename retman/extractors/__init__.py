"""Extractor and validator registries for core parameter resolution."""

from collections.abc import Callable
from typing import Any

from retman.extractors.areas import extract_area, validate_area
from retman.extractors.base import Match
from retman.extractors.paths import extract_paths, validate_path
from retman.extractors.results import extract_result_refs, validate_result

EXTRACTORS: dict[str, Callable[[str], list[Match]]] = {
    "area": extract_area,
    "path": extract_paths,
    "result": extract_result_refs,
}
VALIDATORS: dict[str, Callable[[Any], str | None]] = {
    "area": validate_area,
    "path": validate_path,
    "result": validate_result,
}

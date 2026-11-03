"""Discover supported tools without importing their runtime libraries or handlers."""

import importlib
import importlib.metadata
import logging
import tomllib
from collections.abc import Callable, Iterable
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from retman.exceptions import ManifestError
from retman.i18n.loader import load_texts
from retman.registry.manifest import ManifestSpec, validate_manifest
from retman.registry.operation import (
    MAX_OPTIONS,
    Operation,
    category_groups,
    category_text,
    two_stage,
)

logger = logging.getLogger(__name__)


def version_matches(version: str, specifier: str) -> bool:
    """Tell whether an installed version lies in a manifest's supported range.

    The range is a PEP 440 specifier set; development versions count (REL-5.6), so
    ``0.8.0.dev0`` lies in ``>=0.8.0.dev0,<0.9``. A version that is no PEP 440 version
    is outside every range.

    Raises
    ------
    ManifestError
        If ``specifier`` is no PEP 440 specifier set.
    """
    try:
        supported = SpecifierSet(specifier)
    except InvalidSpecifier as err:
        raise ManifestError(f"invalid supported_versions: {specifier}") from err
    try:
        installed = Version(version)
    except InvalidVersion:
        return False
    return supported.contains(installed, prereleases=True)


def discover_manifests() -> Iterable[tuple[ManifestSpec, Path]]:
    """Yield descriptions in ``src/retman/tools/*/manifest.py``."""
    tools_dir = Path(__file__).resolve().parents[1] / "tools"
    if not tools_dir.is_dir():
        return
    for manifest_file in sorted(tools_dir.glob("*/manifest.py")):
        module = importlib.import_module(
            f"retman.tools.{manifest_file.parent.name}.manifest"
        )
        manifest: ManifestSpec = module.MANIFEST
        yield manifest, manifest_file.parent


def load_operations(
    language: str,
    enabled_tools: tuple[str, ...] | None = None,
    *,
    manifests: Iterable[tuple[ManifestSpec, Path]] | None = None,
    version_lookup: Callable[[str], str] = importlib.metadata.version,
) -> dict[str, Operation]:
    """Validate descriptions, then expose only installed, enabled tool versions."""
    operation_ids: set[str] = set()
    operations: dict[str, Operation] = {}
    for manifest, directory in (
        manifests if manifests is not None else discover_manifests()
    ):
        translations = {}
        for lang, filename in manifest["translations"].items():
            try:
                translations[lang] = load_texts(directory / filename)
            except (OSError, tomllib.TOMLDecodeError) as err:
                raise ManifestError(
                    f"{manifest['tool']}: cannot load {lang} translation {filename}"
                ) from err
        validate_manifest(manifest, translations, operation_ids=operation_ids)
        tool = manifest["tool"]
        if enabled_tools is not None and tool not in enabled_tools:
            continue
        if language not in translations:
            raise ManifestError(f"{tool}: missing translations for {language}")
        try:
            version = version_lookup(manifest["distribution"])
        except importlib.metadata.PackageNotFoundError:
            logger.debug("Tool %s is not installed", tool)
            continue
        if not version_matches(version, manifest["supported_versions"]):
            logger.warning(
                "Tool %s %s is outside the supported range %s; its operations are "
                "not offered",
                tool,
                version,
                manifest["supported_versions"],
            )
            continue
        for spec in manifest["operations"]:
            op = Operation(
                spec, tool, version, translations[language], manifest.get("client")
            )
            operations[op.id] = op
    _check_category_limits(operations)
    return operations


def _check_category_limits(operations: dict[str, Operation]) -> None:
    """More operations than one question offers need categories (ARCHITECTURE 3.4).

    The model then chooses a category and afterwards an operation of it, each
    among at most ``MAX_OPTIONS`` options besides "out of scope".
    """
    if not two_stage(operations):
        return
    groups = category_groups(operations.values())
    if len(groups) > MAX_OPTIONS:
        raise ManifestError(f"more than {MAX_OPTIONS} operation categories")
    for category, members in groups.items():
        if len(members) > MAX_OPTIONS:
            raise ManifestError(
                f"category {category}: more than {MAX_OPTIONS} operations"
            )
        for suffix in ("label", "description"):
            category_text(members, category, suffix)

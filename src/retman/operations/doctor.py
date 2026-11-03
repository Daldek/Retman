"""``doctor check``: what works, what does not and how to fix it."""

import importlib.metadata
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from retman.backends.base import DecisionBackend
from retman.catalog.envelope import Output
from retman.doctor import run_doctor
from retman.environment import OptionValue
from retman.registry.manifest import ManifestSpec
from retman.stores import ToolOutcome, probe_imgw_write

if TYPE_CHECKING:
    from retman.devtools.light import LightCheck


def doctor_check(
    *,
    config: str | None = None,
    deep: bool = False,
    backend: DecisionBackend | None = None,
    client: httpx.Client | None = None,
    manifests: Iterable[tuple[ManifestSpec, Path]] | None = None,
    version_lookup: Callable[[str], str] = importlib.metadata.version,
    probe: Callable[[], ToolOutcome] = probe_imgw_write,
    conformance: "LightCheck | None" = None,
    project_dir: Path | None = None,
    overrides: Mapping[str, OptionValue] | None = None,
) -> Output:
    """Check the settings, the model server, the tools and the stores.

    Each check that passed is an ``ok`` unit of the result and each blocking one a
    ``failed`` unit with its registry code; warnings are notices. So the outcome is
    ``ok``, ``partial`` (some blocking checks) or ``failed`` (nothing passed).

    Parameters
    ----------
    config : str, optional
        The settings file.
    deep : bool, optional
        Also run the slow checks (a trial write to the IMGWTools store).
    backend, client, manifests, version_lookup, probe, conformance, project_dir
        Injections of the caller for offline tests: see
        :func:`retman.doctor.run_doctor`.
    overrides : Mapping[str, OptionValue], optional
        The settings given by command-line options of the call.

    Returns
    -------
    Output
        The ``retman-doctor/1`` document, the units and the notices.
    """
    report, _ = run_doctor(
        Path(config) if config else None,
        project_dir if project_dir is not None else Path.cwd(),
        backend=backend,
        client=client,
        manifests=manifests,
        version_lookup=version_lookup,
        deep=deep,
        probe=probe,
        conformance=conformance,
        options=overrides,
    )
    return Output(
        report.document(),
        items=report.items(),
        notices=report.notices(),
        view=report.to_text,
    )

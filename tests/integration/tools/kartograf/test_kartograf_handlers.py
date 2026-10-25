"""The handler of the hierarchy: DEM/DSM through the command layer, the orthophoto by
colour.

Kartograf's network classes are replaced by recorders that answer with real
``DownloadResult``/``VersionedFile`` objects; what is tested is what Retman asks of
them and what it makes of the answer. The store is made by the real tool, offline.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import kartograf
import pytest
from kartograf.testing import make_sidecar
from kartograf_support import (
    OfflineClient,
    context,
    geometry,
    settings,
    sheets,
)

from retman.adapters.catalog import ToolError
from retman.testing import FakeToolClient
from retman.tools.kartograf.handlers import (
    download_sheet_hierarchy,
)

PARENT_1992 = {"type": "sheet", "code": "N-34-130-D-d-2"}
PARENT_2000 = {"type": "sheet", "code": "7.171.21"}
ORTHOPHOTO = {"product": "orthophoto", "target_scale": "scale_10000", "color": "cir"}


class Recorder:
    """What the replaced provider and manager were asked, and the answer they give."""

    def __init__(self) -> None:
        self.providers: list[dict[str, Any]] = []
        self.managers: list[dict[str, Any]] = []
        self.requests: list[tuple[Any, ...]] = []
        self.answer: Any = None


def install(monkeypatch: pytest.MonkeyPatch, answer: Any) -> Recorder:
    recorder = Recorder()
    recorder.answer = answer

    class Provider:
        def __init__(self, session: Any = None, cache: Any = None, *, color: str):
            recorder.providers.append({"cache": cache, "color": color})

    class Manager:
        def __init__(self, provider: Any, *, root: Path, workers: int = 1):
            recorder.managers.append(
                {"root": root, "provider": provider, "workers": workers}
            )

        def _respond(self) -> Any:
            if isinstance(recorder.answer, Exception):
                raise recorder.answer
            return recorder.answer

        def download_sheet(self, sheet: str, *, update: Any = None) -> Any:
            recorder.requests.append(("sheet", sheet, update))
            return self._respond()

        def download_hierarchy(
            self, sheet: str, target_scale: str, *, update: Any = None
        ) -> Any:
            recorder.requests.append(("hierarchy", sheet, target_scale, update))
            return self._respond()

    monkeypatch.setattr(kartograf, "GugikOrtoProvider", Provider)
    monkeypatch.setattr(kartograf, "DownloadManager", Manager)
    return recorder


def delivered(store: Path, sheets: list[str], label: str = "2025-04-26_82712") -> Any:
    """A ``DownloadResult`` whose sheets are GeoTIFFs in the store."""
    files: dict[str, tuple[Any, ...]] = {}
    paths: list[Path] = []
    for sheet in sheets:
        path = store / "orto" / "pl_1992_cir" / f"{sheet}.tif"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"II*\x00" + bytes(12))
        files[sheet] = (
            kartograf.VersionedFile(
                path=path,
                status="new",
                label=label,
                sha256="0" * 64,
                size_bytes=path.stat().st_size,
                version_path=path,
            ),
        )
        paths.append(path)
    return kartograf.DownloadResult(succeeded=paths, files=files)


def run(
    tmp_path: Path, params: dict[str, Any], *, client: Any = None, **overrides: Any
) -> Any:
    output_dir = tmp_path / "result"
    output_dir.mkdir(exist_ok=True)
    ctx = context(
        "download_sheet_hierarchy",
        client or OfflineClient(settings(tmp_path)),
        root=tmp_path,
        output_dir=output_dir,
    )
    if overrides:
        ctx = ctx.__class__(
            **{**ctx.__dict__, "settings": {**ctx.settings, **overrides}}
        )
    return download_sheet_hierarchy(params, {}, output_dir, ctx)


def test_dem_and_dsm_run_through_the_command_layer_never_the_provider_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = sheets("one_of_four", tmp_path / "store")
    recorder = install(monkeypatch, AssertionError("the provider route was used"))
    client = OfflineClient(settings(tmp_path), runs={"elevation download": doc})
    params = {
        "product": "dem",
        "area": {"type": "sheet", "code": "N-34-139-C-a-3"},
        "target_scale": "scale_10000",
        "resolution": "1m",
        "vertical_crs": "evrf2007",
    }

    output = run(tmp_path, params, client=client)

    assert [call.command for _, call in client.network] == ["elevation download"]
    assert recorder.providers == [] and recorder.requests == []
    assert list(output["files"]) == ["dem"]
    assert output["tool"]["calls"][0]["schema"] == "kartograf-result/1"


def test_orthophoto_is_asked_of_the_provider_in_the_colour_the_user_chose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "store"
    recorder = install(monkeypatch, delivered(store, ["N-34-130-D-d-2-1"]))
    client = FakeToolClient()

    run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992}, client=client)

    cache = recorder.providers[0]["cache"]
    assert recorder.providers[0]["color"] == "CIR"
    # The cache is the configured file, never Kartograf's default in the cwd
    assert isinstance(cache, kartograf.MetadataCache)
    assert str(settings(tmp_path)["cache_file"]) in repr(vars(cache).values())
    assert recorder.managers == [
        {
            "root": store,
            "provider": recorder.managers[0]["provider"],
            "workers": 2,
        }
    ]
    assert client.calls == []  # the command client is not used for this product


@pytest.mark.parametrize(
    ("area", "expected"),
    [
        (PARENT_1992, ("sheet", "N-34-130-D-d-2", None)),
        (PARENT_2000, ("hierarchy", "7.171.21", "1:2000", None)),
    ],
)
def test_pl1992_parent_expands_by_itself_and_pl2000_needs_its_target_scale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    area: dict[str, Any],
    expected: tuple[Any, ...],
) -> None:
    recorder = install(monkeypatch, delivered(tmp_path / "store", ["x"]))
    scale = "scale_2000" if area is PARENT_2000 else "scale_10000"

    run(tmp_path, {**ORTHOPHOTO, "area": area, "target_scale": scale})

    assert recorder.requests == [expected]


@pytest.mark.parametrize("mode", ["upgrade", "force"])
def test_the_update_mode_of_the_settings_reaches_the_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    recorder = install(monkeypatch, delivered(tmp_path / "store", ["x"]))

    run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992}, update=mode)

    assert recorder.requests[0][-1] == mode


def test_missing_and_failed_sheets_are_counted_exactly_and_the_rest_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "store"
    result = delivered(store, ["s1", "s2"])
    result.failed = ["s3", "s4"]
    result.no_coverage = ["s3"]
    result.errors = {"s3": "Brak ortofotomapy CIR", "s4": "siec"}
    install(monkeypatch, result)

    output = run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992})

    assert list(output["files"]) == ["orthophoto"]
    assert [path.stem for path in output["files"]["orthophoto"]] == ["s1", "s2"]
    assert output["values"] == {
        "color": "CIR",
        "file_count": 2,
        "sheet_count": 2,
        "expected_sheets": 4,
        "data_dates": ["2025-04-26"],
        "bytes": 32,
    }
    assert output["warnings"] == [
        {"key": "no_coverage_sheets", "args": {"count": "1", "total": "4"}},
        {"key": "failed_sheets", "args": {"count": "1", "total": "4", "units": "s4"}},
    ]


def test_a_flight_the_index_calls_incomplete_is_a_warning_from_the_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = delivered(tmp_path / "store", ["s1"])
    path = result.succeeded[0]
    sidecar = make_sidecar(extra={"source": {"full_sheet": False}})
    Path(f"{path}.meta.json").write_text(json.dumps(sidecar), encoding="utf-8")
    install(monkeypatch, result)

    output = run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992})

    assert {"key": "incomplete_campaign", "args": {}} in output["warnings"]


def test_the_audit_block_records_the_colour_the_command_could_not_say(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = delivered(tmp_path / "store", ["s1"])
    install(monkeypatch, result)

    output = run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992})

    audit = output["tool"]
    call = audit["calls"][0]
    saved = (tmp_path / "result" / call["document_file"]).read_bytes()
    assert audit["tool"] == "kartograf"
    assert call["command"] == "imagery download"
    assert call["options"] == {
        "product": "orto",
        "sheet": "N-34-130-D-d-2",
        "color": "CIR",
    }
    assert call["sha256"] == hashlib.sha256(saved).hexdigest()
    assert json.loads(saved)["color"] == "CIR"
    # The files of the summary have the shape of the files[] of the tool's documents
    (entry,) = json.loads(saved)["files"]
    assert entry["status"] == "new" and entry["size_bytes"] == 16
    assert entry["unit"] == "s1" and entry["label"] == "2025-04-26_82712"
    assert call["files"][0]["version"] == "2025-04-26_82712"


@pytest.mark.parametrize(
    ("no_coverage", "code", "reason"),
    [
        (["s1", "s2"], "no_data", "no_coverage"),
        (["s1"], "source_unavailable", None),
    ],
)
def test_when_no_sheet_is_delivered_the_error_says_whether_the_data_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_coverage: list[str],
    code: str,
    reason: str | None,
) -> None:
    result = kartograf.DownloadResult(
        failed=["s1", "s2"],
        no_coverage=no_coverage,
        errors={"s1": "Brak ortofotomapy CIR dla s1", "s2": "siec"},
    )
    install(monkeypatch, result)

    with pytest.raises(ToolError) as caught:
        run(tmp_path, {**ORTHOPHOTO, "area": PARENT_1992})

    assert caught.value.tool_code == code
    assert caught.value.details.get("reason") == reason
    assert "Brak ortofotomapy CIR dla s1" in caught.value.detail


def test_a_single_sheet_without_the_variant_raises_kartografs_own_error_as_a_tool_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, kartograf.NoCoverageError("Brak ortofotomapy CIR", sheet="s"))

    with pytest.raises(ToolError) as caught:
        run(
            tmp_path,
            {**ORTHOPHOTO, "area": {"type": "sheet", "code": "N-34-130-D-d-2-4"}},
        )

    assert caught.value.tool_code == "no_data"


def test_an_orthophoto_is_not_made_of_a_geometry_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = install(monkeypatch, AssertionError("must not be reached"))

    with pytest.raises(ToolError) as caught:
        run(tmp_path, {**ORTHOPHOTO, "area": geometry(tmp_path / "geo")})

    assert caught.value.tool_code == "orthophoto_needs_sheet"
    assert recorder.requests == []

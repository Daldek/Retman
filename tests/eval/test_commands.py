"""Offline validation and coverage of the packaged command corpus."""

import importlib
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import retman.eval.dataset as dataset
from retman.eval.dataset import (
    DEFAULT_COMMANDS,
    EvalCommand,
    load_commands,
    validate_commands,
)
from retman.exceptions import EvalDatasetError
from retman.registry.loader import discover_manifests

SHEET = {"type": "sheet", "code": "N-34-130-D-d-2-4"}


def sample(**changes: Any) -> EvalCommand:
    entry = EvalCommand(
        "sample-001",
        "Pobierz NMT 1 m EVRF2007 dla arkusza N-34-130-D-d-2-4",
        "download_dem_sheet",
        {"area": SHEET, "resolution": "1m", "vertical_crs": "evrf2007"},
        [],
        ["complete"],
        None,
    )
    return replace(entry, **changes)


def test_packaged_commands_cover_build_rules() -> None:
    commands = load_commands(DEFAULT_COMMANDS)
    validate_commands(commands)
    by_operation: dict[str, list[EvalCommand]] = defaultdict(list)
    for command in commands:
        by_operation[command.operation].append(command)
    specs = {
        operation["id"]: operation
        for manifest, _ in discover_manifests()
        for operation in manifest["operations"]
    }
    for operation in specs:
        entries = by_operation[operation]
        assert len(entries) >= 15, operation
        assert (
            sum(
                "complete" in entry.tags and not entry.expect_clarify
                for entry in entries
            )
            >= 3
        ), operation
        assert (
            sum(
                bool({"incomplete", "ambiguous"} & set(entry.tags)) for entry in entries
            )
            >= 3
        ), operation
        assert (
            sum(bool({"colloquial", "typo"} & set(entry.tags)) for entry in entries)
            >= 3
        ), operation
        for param in specs[operation]["params"]:
            if param["type"] == "choice":
                used = {
                    entry.params[param["name"]]
                    for entry in entries
                    if param["name"] in entry.params
                }
                assert set(param["options"]) <= used, (operation, param["name"])
            if "accepts" in param:
                forms = Counter(
                    entry.params[param["name"]]["type"]
                    for entry in entries
                    if param["name"] in entry.params
                )
                assert all(forms[form] >= 2 for form in param["accepts"]), (
                    operation,
                    forms,
                )
    out_of_scope = by_operation["out_of_scope"]
    assert sum("out_of_scope" in entry.tags for entry in out_of_scope) >= 10
    assert sum("near_miss" in entry.tags for entry in out_of_scope) >= 5


def test_loader_rejects_bad_json_and_format_with_line_reference(tmp_path: Path) -> None:
    file = tmp_path / "commands.jsonl"
    file.write_text('{"id": "broken"}\n{not-json}\n', encoding="utf-8")
    with pytest.raises(EvalDatasetError) as caught:
        load_commands(file)
    assert "broken" in str(caught.value)
    assert "line 2" in str(caught.value)


@pytest.mark.parametrize(
    ("entries", "reason"),
    [
        ([sample(), sample()], "duplicate"),
        ([sample(operation="not_registered")], "unknown operation"),
        (
            [
                sample(
                    params={
                        "area": SHEET,
                        "resolution": "1m",
                        "vertical_crs": "evrf2007",
                        "unlisted": 1,
                    }
                )
            ],
            "unknown parameter",
        ),
        (
            [
                sample(
                    params={
                        "area": SHEET,
                        "resolution": "8m",
                        "vertical_crs": "evrf2007",
                    }
                )
            ],
            "choice options",
        ),
        (
            [
                sample(
                    params={
                        "area": {"type": "sheet", "code": "N-34-130-D-d-2-3"},
                        "resolution": "1m",
                        "vertical_crs": "evrf2007",
                    }
                )
            ],
            "not extracted",
        ),
        ([sample(expect_clarify=["resolution"])], "both supplied"),
        ([sample(params={"area": SHEET, "resolution": "1m"})], "missing applicable"),
        (
            [
                sample(
                    params={
                        "area": SHEET,
                        "resolution": "1m",
                        "vertical_crs": "evrf2007",
                    },
                    expect_clarify=["unknown"],
                )
            ],
            "unknown parameter",
        ),
        (
            [
                sample(
                    operation="download_elevation_cutout",
                    params={"product": "dem", "area": SHEET},
                    expect_clarify=["target_crs", "vertical_crs"],
                )
            ],
            "outside accepts",
        ),
    ],
)
def test_rejects_inconsistent_expectations(
    entries: list[EvalCommand], reason: str
) -> None:
    with pytest.raises(EvalDatasetError, match=reason) as caught:
        validate_commands(entries)
    assert entries[0].id in str(caught.value)


def test_dependency_does_not_require_inapplicable_params() -> None:
    valid = sample(
        operation="download_sheet_hierarchy",
        command="Pobierz ortofotomapę RGB z arkuszy potomnych N-34-130-D-d-2 w 1:10000",
        params={
            "product": "orthophoto",
            "area": {"type": "sheet", "code": "N-34-130-D-d-2"},
            "target_scale": "scale_10000",
            "color": "rgb",
        },
    )
    validate_commands([valid])
    with pytest.raises(EvalDatasetError, match="inapplicable"):
        validate_commands([replace(valid, expect_clarify=["resolution"])])
    with pytest.raises(EvalDatasetError, match="missing applicable"):
        validate_commands([replace(valid, params={**valid.params, "product": "dem"})])


def test_default_does_not_require_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "fixtures"))
    manifest = importlib.import_module("dummy_tool.manifest").MANIFEST

    monkeypatch.setattr(
        dataset, "discover_manifests", lambda: iter([(manifest, Path("dummy_tool"))])
    )
    command = sample(
        operation="make_dem",
        params={"area": SHEET, "style": "smooth"},
    )
    validate_commands([command])
    with pytest.raises(EvalDatasetError, match="default parameter"):
        validate_commands([replace(command, expect_clarify=["detail"])])
    with pytest.raises(EvalDatasetError, match="inapplicable"):
        validate_commands(
            [
                replace(
                    command, params={**command.params, "style": "raw", "detail": "low"}
                )
            ]
        )

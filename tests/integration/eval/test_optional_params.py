"""Optional parameters in eval commands: left unset, stated, never clarified."""

from dataclasses import replace
from pathlib import Path

import pytest

import retman.eval.dataset as dataset
from retman.eval.dataset import EvalCommand, validate_commands
from retman.exceptions import EvalDatasetError
from retman.registry.manifest import ManifestSpec

MANIFEST: ManifestSpec = {
    "tool": "optional_tool",
    "distribution": "optional-tool",
    "source": "optional-tool",
    "supported_versions": ">=1,<2",
    "translations": {"pl": "pl.toml"},
    "operations": [
        {
            "id": "list_things",
            "category": "test",
            "description": "List things",
            "inputs": [],
            "outputs": [],
            "params": [
                {
                    "name": "style",
                    "type": "choice",
                    "options": ["raw", "smooth"],
                    "required": True,
                },
                {"name": "detail", "type": "choice", "options": ["high", "low"]},
                {
                    "name": "years",
                    "type": "free",
                    "extractor": "years",
                    "accepts": ["years", "year_list"],
                },
            ],
            "handler": "optional_tool.handlers:list_things",
        }
    ],
}

COMMAND = "Pokaż rzeczy z lat 2000-2002, styl surowy"
YEARS = {"type": "years", "first": 2000, "last": 2002}


@pytest.fixture(autouse=True)
def optional_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate against a tool that has optional parameters (Kartograf has none)."""
    monkeypatch.setattr(
        dataset, "discover_manifests", lambda: iter([(MANIFEST, Path("optional_tool"))])
    )


def entry(**changes: object) -> EvalCommand:
    base = EvalCommand(
        "optional-001",
        COMMAND,
        "list_things",
        {"style": "raw", "years": YEARS},
        [],
        ["complete"],
        None,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_an_unstated_optional_parameter_is_not_an_expectation() -> None:
    validate_commands([entry(params={"style": "raw"}, command="Pokaż rzeczy, surowe")])


def test_a_stated_optional_parameter_is_checked_like_any_other() -> None:
    validate_commands([entry(params={"style": "raw", "detail": "low", "years": YEARS})])
    with pytest.raises(EvalDatasetError, match="choice options"):
        validate_commands([entry(params={"style": "raw", "detail": "huge"})])
    with pytest.raises(EvalDatasetError, match="not extracted"):
        validate_commands(
            [entry(params={"style": "raw", "years": {**YEARS, "last": 2005}})]
        )


@pytest.mark.parametrize("name", ["detail", "years"])
def test_an_optional_parameter_is_never_a_clarification(name: str) -> None:
    params = {key: value for key, value in entry().params.items() if key != name}
    with pytest.raises(EvalDatasetError, match="never asked") as caught:
        validate_commands([entry(params=params, expect_clarify=[name])])
    assert f"optional parameter {name}" in str(caught.value)


def test_a_required_parameter_is_still_expected() -> None:
    with pytest.raises(EvalDatasetError, match="missing applicable parameter style"):
        validate_commands([entry(params={"years": YEARS})])
    validate_commands([entry(params={"years": YEARS}, expect_clarify=["style"])])

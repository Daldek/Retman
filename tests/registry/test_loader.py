"""Manifest completeness, global IDs and numeric version boundaries."""

import tomllib
from copy import deepcopy
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from retman.exceptions import ManifestError
from retman.i18n.loader import Texts, load_texts
from retman.registry.loader import load_operations, version_matches
from retman.registry.manifest import validate_manifest


@pytest.fixture
def dummy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_dir))
    from dummy_tool.manifest import MANIFEST

    return deepcopy(MANIFEST), fixture_dir / "dummy_tool"


@pytest.mark.parametrize(
    ("version", "accepted"),
    [
        ("1.1.99", False),
        ("1.2", True),
        ("1.2.0", True),
        ("1.99.4", True),
        ("2", False),
        ("1.2rc1", False),
    ],
)
def test_version_matches_numeric_range_boundaries(version, accepted):
    assert version_matches(version, ">=1.2,<2") is accepted


def test_version_matches_equality_and_inequality_with_padding():
    assert version_matches("1.2.0", "==1.2,!=1.2.1")
    assert not version_matches("1.2.1", "==1.2.1,!=1.2.1")
    assert version_matches("1.2.2", ">1.2.1,<=1.2.2")
    with pytest.raises(ManifestError):
        version_matches("1.2", "~=1.2")


def test_load_operations_disables_absent_out_of_range_and_disabled(dummy):
    manifest, folder = dummy

    def unavailable(_: str) -> str:
        raise PackageNotFoundError("dummy-tool")

    missing = load_operations(
        "pl", manifests=[(manifest, folder)], version_lookup=unavailable
    )
    old = load_operations(
        "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.1.9"
    )
    disabled = load_operations(
        "pl",
        enabled_tools=("other",),
        manifests=[(manifest, folder)],
        version_lookup=lambda _: "1.2.1",
    )
    available = load_operations(
        "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.2.1"
    )

    assert missing == old == disabled == {}
    assert set(available) == {"make_dem", "copy_dem", "broken_dem", "escape_dem"}


def test_validate_manifest_detects_unknown_kind_extractor_and_duplicate_id(dummy):
    manifest, folder = dummy
    texts = {"pl": load_texts(folder / "pl.toml")}
    bad_kind = deepcopy(manifest)
    bad_kind["operations"][0]["outputs"] = ["mystery"]
    bad_extractor = deepcopy(manifest)
    bad_extractor["operations"][0]["params"][0]["extractor"] = "fictional"
    duplicate = deepcopy(manifest)
    duplicate["operations"][1]["id"] = "make_dem"

    for invalid in (bad_kind, bad_extractor, duplicate):
        with pytest.raises(ManifestError):
            validate_manifest(invalid, texts)
    with pytest.raises(ManifestError):
        load_operations(
            "pl",
            manifests=[(manifest, folder), (manifest, folder)],
            version_lookup=lambda _: "1.2",
        )


def test_validate_manifest_reports_missing_language_option_and_example(dummy):
    manifest, folder = dummy
    texts = load_texts(folder / "pl.toml")
    missing_option = Texts(
        {"operations": {"make_dem": {"label": "NMT", "description": "Opis"}}},
        "incomplete",
    )
    missing_language = deepcopy(manifest)
    missing_language["translations"]["en"] = "en.toml"
    data = tomllib.loads((folder / "pl.toml").read_text(encoding="utf-8"))
    data["operations"]["make_dem"]["params"]["style"]["options"]["raw"] = "Surowy"
    flat_option = Texts(data, "flat option")

    with pytest.raises(ManifestError, match="params.area.label"):
        validate_manifest(manifest, {"pl": missing_option})
    with pytest.raises(ManifestError, match="missing en translations"):
        validate_manifest(missing_language, {"pl": texts})
    # One text per option cannot serve both the user and the model
    with pytest.raises(ManifestError, match="params.style.options.raw.label"):
        validate_manifest(manifest, {"pl": flat_option})


def test_load_operations_missing_translation_file_is_manifest_error(dummy):
    manifest, folder = dummy
    manifest["translations"]["pl"] = "nonexistent.toml"

    with pytest.raises(ManifestError, match="cannot load pl translation"):
        load_operations(
            "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.2"
        )


def test_load_operations_rejects_more_than_ten_operation_options(
    dummy, monkeypatch: pytest.MonkeyPatch
):
    manifest, folder = dummy
    for index in range(6):
        operation = deepcopy(manifest["operations"][1])
        operation["id"] = f"copy_dem_{index}"
        manifest["operations"].append(operation)
    translations = {
        "operations": {
            item["id"]: {
                "label": f"Operacja {item['id']}",
                "description": f"Operacja {item['id']}",
            }
            for item in manifest["operations"]
        }
    }
    translations["operations"]["make_dem"] = load_texts(folder / "pl.toml").table(
        "operations.make_dem"
    )
    custom_texts = Texts(translations, "test")
    monkeypatch.setattr("retman.registry.loader.load_texts", lambda _: custom_texts)

    with pytest.raises(ManifestError, match="more than 10"):
        load_operations(
            "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.2"
        )

"""Manifest completeness, global IDs, numeric version boundaries and categories."""

import tomllib
from copy import deepcopy
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest

from retman.exceptions import ManifestError
from retman.i18n.loader import Texts, load_texts
from retman.registry.loader import load_operations, version_matches
from retman.registry.manifest import validate_manifest
from retman.registry.operation import two_stage


@pytest.fixture
def dummy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fixture_dir = Path(__file__).resolve().parents[2] / "fixtures"
    monkeypatch.syspath_prepend(str(fixture_dir))
    from dummy_tool.manifest import MANIFEST

    return deepcopy(MANIFEST), fixture_dir / "dummy_tool"


def _operation(manifest, operation_id: str):
    return next(item for item in manifest["operations"] if item["id"] == operation_id)


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
    assert version_matches("1.2.5", "~=1.2.1")
    assert not version_matches("1.3", "~=1.2.1")


@pytest.mark.parametrize(
    ("version", "accepted"),
    [
        ("0.8.0.dev0", True),
        ("0.8.0.dev7", True),
        ("0.8.0rc1", True),
        ("0.8.0", True),
        ("0.8.4", True),
        ("0.7.9", False),
        ("0.7.9.dev3", False),
        ("0.9.0.dev0", False),
        ("0.9", False),
    ],
)
def test_version_matches_admits_the_development_versions_of_the_pending_release(
    version, accepted
):
    # REL-5.6: PEP 440 puts 0.8.0.dev0 below 0.8.0, so the range starts at .dev0
    assert version_matches(version, ">=0.8.0.dev0,<0.9") is accepted


def test_version_matches_refuses_the_development_version_below_a_release_range():
    assert not version_matches("0.8.0.dev0", ">=0.8.0,<0.9")


def test_version_matches_takes_a_local_version_as_its_public_version():
    assert version_matches("3.0.0+g7b11755", ">=3.0.0.dev0,<4")


def test_version_matches_refuses_a_version_that_is_no_pep_440_version():
    assert not version_matches("not-a-version", ">=1,<2")


def test_version_matches_rejects_a_malformed_range():
    with pytest.raises(ManifestError, match="invalid supported_versions"):
        version_matches("1.2", ">=1.2,<")
    with pytest.raises(ManifestError, match="invalid supported_versions"):
        version_matches("1.2", "newer than 1")


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
    assert {item["id"] for item in manifest["operations"]} == set(available)
    # The tool's client reference travels with each of its operations
    assert {op.client for op in available.values()} == {
        "dummy_tool.client:create_client"
    }


def test_validate_manifest_detects_unknown_kind_extractor_and_duplicate_id(dummy):
    manifest, folder = dummy
    texts = {"pl": load_texts(folder / "pl.toml")}
    bad_kind = deepcopy(manifest)
    bad_kind["operations"][0]["outputs"] = ["mystery"]
    bad_extractor = deepcopy(manifest)
    bad_extractor["operations"][0]["params"][0]["extractor"] = "fictional"
    duplicate = deepcopy(manifest)
    duplicate["operations"][1]["id"] = "make_dem"
    # A choice read by code must map every option to an extractor value
    partial_mapping = deepcopy(manifest)
    partial_mapping["operations"][0]["params"][1].update(
        extractor="crs", option_values={"raw": "EPSG:2180"}
    )

    for invalid in (bad_kind, bad_extractor, duplicate, partial_mapping):
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
    no_model_question = tomllib.loads((folder / "pl.toml").read_text(encoding="utf-8"))
    del no_model_question["operations"]["make_dem"]["params"]["style"]["model_question"]

    with pytest.raises(ManifestError, match="params.area.label"):
        validate_manifest(manifest, {"pl": missing_option})
    with pytest.raises(ManifestError, match="missing en translations"):
        validate_manifest(missing_language, {"pl": texts})
    # One text per option cannot serve both the user and the model
    with pytest.raises(ManifestError, match="params.style.options.raw.label"):
        validate_manifest(manifest, {"pl": flat_option})
    # The user's question is not what the model is asked
    with pytest.raises(ManifestError, match="params.style.model_question"):
        validate_manifest(
            manifest, {"pl": Texts(no_model_question, "no model question")}
        )
    # An optional parameter the plan cannot explain when left unset (N-11)
    no_unset = tomllib.loads((folder / "pl.toml").read_text(encoding="utf-8"))
    del no_unset["operations"]["cut_dem"]["params"]["name"]["unset"]
    with pytest.raises(ManifestError, match="params.name.unset"):
        validate_manifest(manifest, {"pl": Texts(no_unset, "no unset text")})


def test_load_operations_missing_translation_file_is_manifest_error(dummy):
    manifest, folder = dummy
    manifest["translations"]["pl"] = "nonexistent.toml"

    with pytest.raises(ManifestError, match="cannot load pl translation"):
        load_operations(
            "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.2"
        )


def _fetch_param(manifest, name: str):
    return next(
        p for p in _operation(manifest, "fetch_dem")["params"] if p["name"] == name
    )


# Each declaration of the command layer that must fail at load time, with the reason
BROKEN_DECLARATIONS = {
    "calls without commands": (
        "calls need the list of commands",
        lambda m: _operation(m, "fetch_dem").pop("commands"),
    ),
    "calls without a tool client": ("declares no client", lambda m: m.pop("client")),
    "neither handler nor calls": (
        "neither handler nor calls",
        lambda m: _operation(m, "make_dem").pop("handler"),
    ),
    "describe without calls": (
        "describe needs calls",
        lambda m: _operation(m, "make_dem").update(describe="dummy_tool.calls:x"),
    ),
    "reference without a colon": (
        "invalid preview",
        lambda m: _operation(m, "fetch_dem").update(preview="no_colon"),
    ),
    "client without an attribute": (
        "invalid client",
        lambda m: m.update(client="dummy_tool.client:"),
    ),
    "option key with a dot": (
        "option keys must match",
        lambda m: _fetch_param(m, "resolution").update(
            options=["0.5m", "1m", "5m"], tool_values={}
        ),
    ),
    "tool value for an unknown option": (
        "invalid tool_values",
        lambda m: _fetch_param(m, "resolution").update(tool_values={"2m": "2m"}),
    ),
    "tool values that collide": (
        "invalid tool_values",
        lambda m: _fetch_param(m, "resolution").update(tool_values={"0_5m": "1m"}),
    ),
    "excluded value that is offered": (
        "excluded 0.5m is offered",
        lambda m: _operation(m, "fetch_dem").update(
            excluded={"resolution": {"0.5m": "reason"}}
        ),
    ),
    "excluded without a reason": (
        "has no reason",
        lambda m: _operation(m, "fetch_dem").update(
            excluded={"resolution": {"100m": " "}}
        ),
    ),
    "excluded for a free parameter": (
        "excluded needs a choice parameter",
        lambda m: _operation(m, "fetch_dem").update(excluded={"area": {"x": "why"}}),
    ),
    "no_check without a reason": (
        "no_check has no reason",
        lambda m: _operation(m, "make_dem").update(no_check=" "),
    ),
    "check and no_check together": (
        "declares both check and no_check",
        lambda m: _operation(m, "fetch_dem").update(no_check="nothing to ask"),
    ),
    "option_meta that is not JSON": (
        "option_meta is not JSON",
        lambda m: _fetch_param(m, "resolution").update(
            option_meta={"1m": {"x": object()}}
        ),
    ),
    "option_meta for an unknown option": (
        "invalid option_meta",
        lambda m: _fetch_param(m, "resolution").update(option_meta={"2m": {}}),
    ),
    "category with a dot": (
        "category must match",
        lambda m: _operation(m, "make_dem").update(category="a.b"),
    ),
}


@pytest.mark.parametrize(
    ("pattern", "change"),
    list(BROKEN_DECLARATIONS.values()),
    ids=list(BROKEN_DECLARATIONS),
)
def test_validate_manifest_rejects_broken_command_layer_declarations(
    dummy, pattern, change
):
    manifest, folder = dummy
    texts = {"pl": load_texts(folder / "pl.toml")}
    change(manifest)

    with pytest.raises(ManifestError, match=pattern):
        validate_manifest(manifest, texts)


def test_check_needs_the_notice_text_the_user_confirms(dummy):
    manifest, folder = dummy
    data = tomllib.loads((folder / "pl.toml").read_text(encoding="utf-8"))
    del data["operations"]["fetch_dem"]["check"]

    with pytest.raises(ManifestError, match="fetch_dem.check.notice"):
        validate_manifest(manifest, {"pl": Texts(data, "no notice")})


def _crowded(manifest, folder, monkeypatch, layout: dict[str, int], *, texts=True):
    """A tool with ``layout`` = operations per category (and category texts)."""
    template = _operation(manifest, "copy_dem")
    data: dict = {"operations": {}, "categories": {}}
    operations = []
    for category, count in layout.items():
        for index in range(count):
            operation = deepcopy(template)
            operation["id"] = f"{category}_{index}"
            operation["category"] = category
            operations.append(operation)
            data["operations"][operation["id"]] = {
                "label": f"Operacja {operation['id']}",
                "description": f"Opis {operation['id']}",
            }
        if texts:
            data["categories"][category] = {
                "label": f"Grupa {category}",
                "description": f"Opis grupy {category}",
            }
    manifest["operations"] = operations
    monkeypatch.setattr(
        "retman.registry.loader.load_texts", lambda _: Texts(data, "crowded")
    )
    return load_operations(
        "pl", manifests=[(manifest, folder)], version_lookup=lambda _: "1.2"
    )


def test_more_operations_than_one_question_offers_are_grouped_by_category(
    dummy, monkeypatch: pytest.MonkeyPatch
):
    manifest, folder = dummy

    loaded = _crowded(manifest, folder, monkeypatch, {"a": 4, "b": 4, "c": 4})

    assert len(loaded) == 12 and two_stage(loaded)


def test_nine_operations_need_no_categories(dummy, monkeypatch: pytest.MonkeyPatch):
    manifest, folder = dummy

    loaded = _crowded(manifest, folder, monkeypatch, {"a": 9}, texts=False)

    assert len(loaded) == 9 and not two_stage(loaded)


@pytest.mark.parametrize(
    ("layout", "texts", "message"),
    [
        ({"a": 10}, True, "category a: more than 9 operations"),
        ({f"c{index}": 1 for index in range(10)}, True, "more than 9 operation"),
        ({"a": 5, "b": 5}, False, "missing category text categories.a.label"),
    ],
)
def test_category_limits_and_texts_are_enforced_when_grouping_is_needed(
    dummy, monkeypatch: pytest.MonkeyPatch, layout, texts, message
):
    manifest, folder = dummy

    with pytest.raises(ManifestError, match=message):
        _crowded(manifest, folder, monkeypatch, layout, texts=texts)

"""The JSON Schemas of the domain documents (AGI-4.1): shipped, current and loose.

Each command declares the id of its result document; the schemas in
``src/retman/schemas`` are written by ``scripts/generate_result_schemas.py`` and are
package data, so they are read through :mod:`importlib.resources`. Documents that need
a model server or a tool are validated where they are produced (``tests/integration``).
"""

import importlib.util
from importlib import resources
from pathlib import Path

import pytest
from document_schemas import schema_file, shipped_schema, violations
from jsonschema import Draft202012Validator
from nogat_schemas import ROOT

import retman
from retman.catalog import data_commands
from retman.catalog.document import COMMANDS_SCHEMA
from retman.operations.documents import TARGETS_SCHEMA

COMMANDS = data_commands()
IDS = sorted({c.result_schema for c in COMMANDS} - {COMMANDS_SCHEMA} | {TARGETS_SCHEMA})
SHIPPED = resources.files("retman") / "schemas"


def test_every_result_document_of_the_catalog_has_a_shipped_schema() -> None:
    shipped = {e.name for e in SHIPPED.iterdir() if e.name.endswith(".schema.json")}

    assert shipped == {schema_file(schema_id) for schema_id in IDS}


@pytest.mark.parametrize("schema_id", IDS)
def test_each_schema_is_valid_and_names_itself(schema_id: str) -> None:
    schema = shipped_schema(schema_id)

    Draft202012Validator.check_schema(schema)
    assert schema["title"] == schema_id
    assert schema["$id"].endswith("/" + schema_file(schema_id))
    assert schema["properties"]["schema"] == {"const": schema_id}
    assert "schema" in schema["required"]


def test_the_shipped_schemas_are_what_the_generator_writes() -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_result_schemas", ROOT / "scripts" / "generate_result_schemas.py"
    )
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    assert generator.main(["--check"]) == 0


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A folder with a settings file, as the offline examples assume."""
    monkeypatch.chdir(tmp_path)
    retman.run_command("config init", config="nogat.toml")
    return tmp_path


@pytest.mark.parametrize(
    ("name", "options"),
    [
        ("config show", {"config": "nogat.toml"}),
        ("results list", {"config": "nogat.toml"}),
        ("journal show", {"config": "nogat.toml"}),
        ("commands list", {}),
        ("commands guide", {"format": "llms"}),
    ],
)
def test_the_result_of_an_offline_command_obeys_its_schema(
    name: str, options: dict[str, object], project: Path
) -> None:
    command = next(c for c in COMMANDS if c.name == name)

    result = retman.run_command(name, **options).to_dict()["result"]

    assert violations(command.result_schema, result) == []
    # A field added later keeps the version (AGI-4.1): unknown fields are allowed
    assert violations(command.result_schema, {**result, "added_later": [1]}) == []


def test_a_written_file_is_listed_in_the_document_and_obeys_the_schema(
    tmp_path: Path,
) -> None:
    target = tmp_path / "llms.txt"

    result = retman.run_command(
        "commands guide", format="llms", output=str(target)
    ).to_dict()["result"]

    assert violations("retman-guide/1", result) == []
    assert [item["status"] for item in result["files"]] == ["written"]


def test_the_plan_of_a_check_run_obeys_its_schema(tmp_path: Path) -> None:
    """``commands guide`` plans its write; the other writers are checked where run."""
    (tmp_path / "taken.out").write_text("x", encoding="utf-8")
    for target, action in (("fresh.out", "write"), ("taken.out", "conflict")):
        plan = retman.check_command(
            "commands guide", output=str(tmp_path / target)
        ).to_dict()["result"]

        assert violations(TARGETS_SCHEMA, plan) == []
        assert [item["action"] for item in plan["targets"]] == [action]


def test_the_plan_schema_accepts_every_action_and_rejects_an_unknown_one() -> None:
    target = {"option": "output", "path": "/tmp/a", "action": "replace"}

    assert (
        violations(TARGETS_SCHEMA, {"schema": TARGETS_SCHEMA, "targets": [target]})
        == []
    )
    bad = {**target, "action": "delete"}
    assert violations(TARGETS_SCHEMA, {"schema": TARGETS_SCHEMA, "targets": [bad]})


def test_a_schema_is_not_vacuous() -> None:
    document = retman.run_command("commands list").to_dict()["result"]
    schema_id = "retman-command-list/1"

    assert violations(schema_id, document) == []
    missing = {k: v for k, v in document.items() if k != "commands"}
    assert violations(schema_id, missing)
    assert violations(schema_id, {**document, "commands": "all"})
    assert violations(schema_id, {**document, "schema": "retman-guide/1"})

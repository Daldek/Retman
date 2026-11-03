"""Contract tests of the public Python API (AGI-2.1, AGI-7.1, AGI-7.3)."""

import importlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
from mypy import api

import retman
from retman.catalog import execute
from retman.exceptions import CommandNotFoundError, InvalidValueError

CONSUMER = """
import retman

options = retman.validate_command("results list", limit=5)
listing = retman.list_commands(limit=3)
schema = retman.command_schema("plan run")
plan = retman.check_command("config init", config="nogat.toml")
result = retman.run_command("commands list")
document = result.to_dict()
text = result.to_json()
exit_code = result.exit_code
reveal_type(options)
reveal_type(listing.to_dict())
reveal_type(schema.to_json())
reveal_type(document)
reveal_type(text)
reveal_type(exit_code)
reveal_type(plan.check)
"""

WRONG = """
import retman

retman.command_schema(3)
retman.list_commands(limit="x")
retman.validate_command()
"""


def _mypy(source: str, folder: Path) -> tuple[str, int]:
    snippet = folder / "consumer.py"
    snippet.write_text(textwrap.dedent(source), encoding="utf-8")
    stdout, _, status = api.run(
        [
            "--strict",
            "--no-incremental",
            "--cache-dir",
            str(folder / "mypy-cache"),
            "--config-file",
            "",
            str(snippet),
        ]
    )
    return stdout, status


def _python(code: str, **kwargs: Any) -> "subprocess.CompletedProcess[str]":
    done: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )
    return done


class TestAll:
    """``retman.__all__`` is the public API."""

    @pytest.mark.parametrize("name", retman.__all__)
    def test_every_name_is_importable(self, name: str) -> None:
        assert getattr(importlib.import_module("retman"), name) is not None

    def test_there_are_no_duplicates(self) -> None:
        assert len(set(retman.__all__)) == len(retman.__all__)

    def test_the_five_functions_of_the_interface_are_exported(self) -> None:
        assert {
            "list_commands",
            "command_schema",
            "validate_command",
            "check_command",
            "run_command",
        } <= set(retman.__all__)

    def test_the_error_classes_and_the_registry_are_exported(self) -> None:
        assert issubclass(retman.InvalidValueError, retman.RetmanError)
        assert issubclass(retman.CommandNotFoundError, retman.RetmanError)
        assert "validation_error" in retman.ERROR_CODES
        assert retman.error_document(retman.UsageError("x"))["code"] == (
            "validation_error"
        )

    def test_the_conversation_classes_are_exported(self) -> None:
        assert {"Retman", "Plan", "Result", "CheckReport"} <= set(retman.__all__)


class TestImport:
    """Importing the package is cheap: no heavy library, no file, no network."""

    HEAVY = (
        "numpy",
        "scipy",
        "pandas",
        "rasterio",
        "pyarrow",
        "geopandas",
        "matplotlib",
        "osgeo",
        "kartograf",
        "imgwtools",
    )

    def test_importing_the_package_loads_no_heavy_library_and_no_tool(self) -> None:
        done = _python(
            f"""
            import sys
            import retman
            loaded = [m for m in {self.HEAVY!r} if m in sys.modules]
            assert not loaded, loaded
            """
        )

        assert done.returncode == 0, done.stderr

    def test_importing_the_package_prints_nothing_and_writes_no_file(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        work = tmp_path / "work"
        home.mkdir()
        work.mkdir()
        environment = {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_DATA_HOME": str(home / "data"),
            "XDG_CACHE_HOME": str(home / "cache"),
            "PATH": "",
        }

        done = _python("import retman", cwd=work, env=environment)

        assert done.returncode == 0, done.stderr
        assert (done.stdout, done.stderr) == ("", "")
        assert list(work.iterdir()) == [] and list(home.iterdir()) == []

    def test_the_catalog_is_loaded_when_a_function_first_needs_it(self) -> None:
        done = _python(
            """
            import sys
            import retman
            assert "retman.catalog" not in sys.modules
            retman.list_commands()
            assert "retman.catalog" in sys.modules
            """
        )

        assert done.returncode == 0, done.stderr


class TestTypes:
    """A consumer that calls the five functions type-checks under ``--strict``."""

    def test_the_consumer_snippet_passes_mypy_strict(self, tmp_path: Path) -> None:
        stdout, status = _mypy(CONSUMER, tmp_path)

        errors = [line for line in stdout.splitlines() if ": error:" in line]
        assert errors == [], stdout
        revealed = [
            line.split('"')[1]
            for line in stdout.splitlines()
            if "Revealed type" in line
        ]
        assert revealed == [
            "dict[str, Any]",
            "dict[str, Any]",
            "str",
            "dict[str, Any]",
            "str",
            "int",
            "bool",
        ]
        assert status == 0

    def test_a_wrong_call_is_rejected_by_mypy(self, tmp_path: Path) -> None:
        """The check is real: misuse of the API is a type error."""
        stdout, status = _mypy(WRONG, tmp_path)

        assert status == 1
        assert stdout.count("error:") == 3


class TestBehaviour:
    """The five functions at work."""

    def test_run_command_takes_the_options_as_keywords(self) -> None:
        envelope = retman.run_command("commands list", limit=2).to_dict()

        assert [c["name"] for c in envelope["result"]["commands"]] == [
            "plan run",
            "config show",
        ]
        assert envelope["page"]["truncated"] is True

    def test_the_cursor_of_a_page_fetches_the_next_one(self) -> None:
        first = retman.run_command("commands list", limit=2).to_dict()

        second = retman.run_command(
            "commands list", limit=2, cursor=first["page"]["next_cursor"]
        ).to_dict()

        assert second["result"]["commands"][0]["name"] == "config init"

    def test_validate_command_applies_the_defaults_and_does_not_run(self) -> None:
        assert retman.validate_command("results list") == {"limit": 50}

    def test_validate_command_refuses_an_unknown_option_and_names_the_allowed(
        self,
    ) -> None:
        with pytest.raises(InvalidValueError) as caught:
            retman.validate_command("results list", nonsense=1)

        assert caught.value.code == "validation_error"
        assert caught.value.details["reason"] == "unknown_option"
        assert "limit" in caught.value.details["allowed"]

    def test_an_unknown_command_is_not_found_and_suggests_the_nearest(self) -> None:
        with pytest.raises(CommandNotFoundError) as caught:
            retman.validate_command("plan runn")

        assert caught.value.code == "not_found"
        assert caught.value.details["suggestions"] == ["plan run"]

    def test_the_operation_id_names_a_command_as_well(self) -> None:
        assert retman.command_schema("retman_plan_run").to_dict()["commands"][0][
            "name"
        ] == ("plan run")

    def test_list_commands_and_command_schema_return_documents(self) -> None:
        listing = retman.list_commands(limit=2).to_dict()
        schema = retman.command_schema("plan run").to_dict()

        assert listing["schema"] == "retman-command-list/1"
        assert listing["page"]["total"] == len(
            retman.list_commands().to_dict()["commands"]
        )
        assert schema["schema"] == "retman-commands/1"
        assert [c["name"] for c in schema["commands"]] == ["plan run"]
        assert json.loads(retman.command_schema("plan run").to_json()) == schema

    def test_check_command_of_a_writing_command_returns_the_plan(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "AGENTS.md"

        plan = retman.check_command(
            "commands guide", format="agents", output=str(target)
        ).to_dict()

        assert plan["check"] is True and plan["status"] == "ok"
        assert plan["result"]["schema"] == "retman-targets/1"
        assert plan["result"]["targets"] == [
            {"option": "output", "path": str(target), "action": "write"}
        ]
        assert not target.exists()

    def test_check_command_names_a_conflict_and_still_succeeds(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "AGENTS.md"
        target.write_text("mine", encoding="utf-8")

        plan = retman.check_command("commands guide", output=str(target)).to_dict()

        assert plan["status"] == "ok"
        assert plan["result"]["targets"][0]["action"] == "conflict"
        assert target.read_text(encoding="utf-8") == "mine"

    def test_check_command_of_a_read_only_command_is_a_validation_error(self) -> None:
        with pytest.raises(InvalidValueError) as caught:
            retman.check_command("commands list")

        assert caught.value.code == "validation_error"
        assert caught.value.details["reason"] == "no_check"

    def test_an_injection_cannot_take_the_place_of_an_option(self) -> None:
        """An injection never overrides an option: the CLI passes only the others."""
        envelope = execute("commands list", {"limit": 2}, {"limit": 1}).to_dict()

        assert len(envelope["result"]["commands"]) == 2

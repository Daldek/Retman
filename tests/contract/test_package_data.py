"""Package data is read from the package itself (DEV-5.4, DEV-7.4)."""

import json
import tomllib
from importlib import resources

import pytest

from retman.registry.loader import discover_manifests

TOOLS = [folder.name for _, folder in discover_manifests()]


def test_package_marks_itself_as_typed() -> None:
    assert resources.files("retman").joinpath("py.typed").is_file()


def test_config_template_is_package_data() -> None:
    text = resources.files("retman").joinpath("config_template.toml").read_text("utf-8")

    assert "[retman.decision]" in text


def test_agent_guide_templates_are_package_data() -> None:
    folder = resources.files("retman").joinpath("_data", "agents")

    for name in ("agents.md", "llms.md", "agents-md-block.md"):
        assert folder.joinpath(name).read_text("utf-8").startswith(("#", "<!--"))


def test_core_translations_are_package_data() -> None:
    text = resources.files("retman.i18n").joinpath("pl.toml").read_text("utf-8")

    assert "cli" in tomllib.loads(text)


def test_eval_command_set_is_package_data() -> None:
    text = resources.files("retman.eval").joinpath("commands.jsonl").read_text("utf-8")

    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    assert all("command" in row for row in rows)


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_translations_are_package_data(tool: str) -> None:
    folder = resources.files(f"retman.tools.{tool}")

    text = folder.joinpath("pl.toml").read_text("utf-8")

    assert "operations" in tomllib.loads(text)

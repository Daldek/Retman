"""Central settings consumed by the core and safely rejected at startup."""

from pathlib import Path

import pytest

from retman import Retman
from retman.config import init_config, load_config
from retman.exceptions import ConfigError
from retman.testing import FakeDecisionBackend


def test_from_config_injected_backend_uses_explicit_project_folder(tmp_path: Path):
    config_path = init_config(tmp_path / "settings.toml")
    project = tmp_path / "project"
    project.mkdir()

    app = Retman.from_config(
        config_path, backend=FakeDecisionBackend(), project_dir=project
    )

    assert app.workspace.root == project / load_config(config_path).results_dir
    assert not app.workspace.root.exists()


def test_from_config_rejects_non_basal_auto_threshold(tmp_path: Path):
    config_path = init_config(tmp_path / "settings.toml")
    content = (
        config_path.read_text()
        .replace(
            'backend = "basal"                   #',
            'backend = "openai_compatible"       #',
            1,
        )
        .replace('# confidence = "auto"', 'confidence = "consistency"')
        .replace("# consistency_runs = 3", "consistency_runs = 3")
    )
    config_path.write_text(content)

    with pytest.raises(ConfigError) as error:
        Retman.from_config(
            config_path, backend=FakeDecisionBackend(), project_dir=tmp_path
        )

    assert "auto_threshold_without_basal" in error.value.problems


@pytest.mark.parametrize("directory", ["/elsewhere", "../outside", "nested/../outside"])
def test_from_config_rejects_results_folder_outside_project(
    tmp_path: Path, directory: str
):
    config_path = init_config(tmp_path / "settings.toml")
    config_path.write_text(
        config_path.read_text().replace(
            'results_dir = "retman-output"', f'results_dir = "{directory}"'
        )
    )

    with pytest.raises(ConfigError) as error:
        Retman.from_config(
            config_path, backend=FakeDecisionBackend(), project_dir=tmp_path
        )

    assert error.value.details["invalid_value"] == "output.results_dir"

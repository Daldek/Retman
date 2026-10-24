"""Configured backend selection and unsupported-service errors."""

from pathlib import Path

import pytest

from retman.backends import build_decision_backend
from retman.config import Config, DecisionConfig, Thresholds
from retman.exceptions import ConfigError
from retman.i18n.loader import load_core_texts


def test_build_decision_backend_rejects_unavailable_basal_service():
    config = Config(
        path=Path("/tmp/retman-test.toml"),
        decision=DecisionConfig(
            backend="basal",
            url="http://127.0.0.1:8000",
            model="basal-1.5-mini",
            timeout_s=7,
            thresholds=Thresholds(operation="auto", parameter="auto"),
            api_key_env=None,
            confidence=None,
            consistency_runs=None,
        ),
        text_backend="none",
        language="pl",
        results_dir="retman-output",
        enabled_tools=None,
        journal_commands=False,
        diagnostic_level="info",
        collect_commands=False,
        collect_path=Path("/tmp/retman-collected.jsonl"),
    )

    with pytest.raises(ConfigError) as caught:
        build_decision_backend(config, load_core_texts("pl"))

    assert caught.value.path == config.path
    assert caught.value.problems == ["backend_unavailable"]
    assert caught.value.problem_details == {"backend": "basal"}

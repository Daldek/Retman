"""Optional live check against the configured OpenAI-compatible server."""

import pytest

from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.config import DecisionConfig, Thresholds
from retman.i18n.loader import load_core_texts


@pytest.mark.live
def test_choose_live_model_returns_allowed_option(pytestconfig: pytest.Config):
    """Make a genuine constrained decision without storing server details."""
    url = pytestconfig.getoption("--live-openai-url")
    model = pytestconfig.getoption("--live-openai-model")
    if not url or not model:
        pytest.skip("provide --live-openai-url and --live-openai-model")
    config = DecisionConfig(
        backend="openai_compatible",
        url=url,
        model=model,
        timeout_s=90,
        thresholds=Thresholds(operation=0.6, parameter=0.6),
        api_key_env=None,
        confidence="logprobs",
        consistency_runs=3,
    )
    options = {
        "a_sheet": "Pobierz NMT dla arkusza mapy",
        "b_cutout": "Pobierz wycinek NMT dla prostokąta",
        "c_out_of_scope": "Żadna z powyższych operacji",
    }
    backend = OpenAICompatibleBackend(config, load_core_texts("pl"))
    try:
        decision = backend.choose(
            "Pobierz NMT dla arkusza N-34-130-D-d-2-4",
            "Którą operację wybrać?",
            options,
        )
    finally:
        backend.close()
    assert decision.key in options
    assert decision.confidence_method == "logprobs"
    assert decision.confidence is not None and 0 <= decision.confidence <= 1

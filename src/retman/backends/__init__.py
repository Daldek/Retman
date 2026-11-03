"""Construction of decision backends from the central configuration."""

from retman.backends.base import DecisionBackend
from retman.backends.openai_compatible import OpenAICompatibleBackend
from retman.config import Config
from retman.exceptions import ConfigError
from retman.i18n.loader import Texts


def build_decision_backend(config: Config, texts: Texts) -> DecisionBackend:
    """Build the decision backend selected in ``[retman.decision]``.

    Parameters
    ----------
    config : Config
        Central configuration, including its path for diagnostics.
    texts : Texts
        Translations of model-facing prompts.

    Returns
    -------
    DecisionBackend
        Configured backend for operation and parameter choices.

    Raises
    ------
    ConfigError
        The selected backend cannot yet be connected to a real service.
    """
    if config.decision.backend == "openai_compatible":
        return OpenAICompatibleBackend(config.decision, texts)
    raise ConfigError(
        config.path,
        ["backend_unavailable"],
        {"backend": config.decision.backend},
    )

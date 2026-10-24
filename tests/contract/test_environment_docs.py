"""Every variable Retman reads is documented where DEV-18.3 wants it."""

import re
from pathlib import Path

from retman.environment import CONFIG_ENV, KEYS, SHARED_PREFIX

ROOT = Path(__file__).resolve().parents[2]


def variables() -> set[str]:
    """Every variable of the environment: the tool's, the shared ones and the file."""
    names = {key.variable for key in KEYS}
    names |= {SHARED_PREFIX + key.name.upper() for key in KEYS if key.shared}
    return names | {CONFIG_ENV}


def test_env_example_lists_exactly_the_variables_retman_reads() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    listed = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))

    assert listed == variables()


def test_readme_lists_every_variable() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    missing = sorted(name for name in variables() if f"`{name}`" not in text)

    assert missing == []

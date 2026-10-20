"""No command of the IMGWTools catalog is silently left out of the adapter."""

import imgwtools

from retman.tools.imgwtools.coverage import EXCLUDED_COMMANDS
from retman.tools.imgwtools.manifest import MANIFEST


def mapped_commands() -> set[str]:
    return {
        command
        for operation in MANIFEST["operations"]
        for command in operation["commands"]
    }


def test_every_command_of_the_catalog_is_offered_or_excluded_with_a_reason():
    catalog = {command.name for command in imgwtools.data_commands()}
    mapped = mapped_commands()

    assert catalog == mapped | set(EXCLUDED_COMMANDS)
    assert not mapped & set(EXCLUDED_COMMANDS)
    assert all(reason.strip() for reason in EXCLUDED_COMMANDS.values())


def test_the_catalog_still_has_the_37_commands_the_adapter_was_designed_for():
    # A release that adds or drops a command must make someone decide about it
    assert len(imgwtools.data_commands()) == 37

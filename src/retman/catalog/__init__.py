"""The command catalog of Retman: one declaration for every interface (AGI §2).

The catalog (:mod:`retman.catalog.commands`) lists the commands the CLI, the Python
functions of AGI-2.1 and the guides for agents offer; :mod:`retman.catalog.spec`
holds the declarations, :mod:`retman.catalog.dispatch` the lookup, validation and
execution, :mod:`retman.catalog.envelope` the result envelope ``retman-result/1`` and
:mod:`retman.catalog.document` the catalog documents ``retman-commands/1`` and
``retman-command-list/1``. Importing the top-level package does not import this one:
the five functions of :mod:`retman` import it when they are first called.
"""

from retman.catalog.dispatch import (
    check_command,
    command_schema,
    data_commands,
    execute,
    get_command,
    list_commands,
    run_command,
    validate_command,
)
from retman.catalog.document import Document, paginate
from retman.catalog.envelope import (
    CommandResult,
    Item,
    Notice,
    Output,
    status_of,
)
from retman.catalog.spec import Command, Effects, Option

__all__ = [
    "Command",
    "CommandResult",
    "Document",
    "Effects",
    "Item",
    "Notice",
    "Option",
    "Output",
    "check_command",
    "command_schema",
    "data_commands",
    "execute",
    "get_command",
    "list_commands",
    "paginate",
    "run_command",
    "status_of",
    "validate_command",
]

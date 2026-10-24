"""The operations of the catalog commands (``Command.function``).

Each function takes keyword-only parameters named like the options of its command
(AGI-7.2), plus injections that only a caller who replaces a part of Retman uses (the
decision backend, the project folder, the discovered tools), and returns an
:class:`~retman.catalog.Output`. Call them through :func:`retman.run_command`: it
validates the options, applies the defaults and wraps the result in the envelope.
"""

from retman.operations.config import config_init, config_show
from retman.operations.doctor import doctor_check
from retman.operations.evaluation import eval_run
from retman.operations.history import journal_show, results_list
from retman.operations.meta import commands_guide, commands_list, commands_schema
from retman.operations.plan import plan_run
from retman.operations.scaffold import scaffold_check, scaffold_draft, scaffold_list

__all__ = [
    "commands_guide",
    "commands_list",
    "commands_schema",
    "config_init",
    "config_show",
    "doctor_check",
    "eval_run",
    "journal_show",
    "plan_run",
    "results_list",
    "scaffold_check",
    "scaffold_draft",
    "scaffold_list",
]

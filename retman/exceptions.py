"""Exception hierarchy of Retman; every error derives from ``RetmanError``."""

from pathlib import Path


class RetmanError(Exception):
    """Base class of all Retman errors."""


class ConfigError(RetmanError):
    """The central config file is missing or invalid.

    Parameters
    ----------
    path : Path
        Config file that was read (or expected).
    problems : list[str]
        Translation keys under ``config`` in ``retman/i18n/pl.toml``,
        e.g. ``"missing_file"``.
    details : dict[str, str]
        Per problem: the config keys concerned (or other values for the text).
    """

    def __init__(
        self,
        path: Path,
        problems: list[str],
        details: dict[str, str] | None = None,
    ) -> None:
        self.path = path
        self.problems = problems
        self.details = details or {}
        super().__init__(f"{path}: {', '.join(problems)}")


class ManifestError(RetmanError):
    """A tool manifest or its translations are invalid (programmer error)."""


class TranslationError(RetmanError):
    """A translation key is missing (programmer error)."""


class KindValidationError(RetmanError):
    """A file does not match its declared data kind (ARCHITECTURE 3.2.6).

    Parameters
    ----------
    kind : str
        Declared data kind.
    path : Path
        Checked file.
    reason : str
        Translation key under ``kinds.errors`` in ``retman/i18n/pl.toml``.
    """

    def __init__(self, kind: str, path: Path, reason: str) -> None:
        self.kind = kind
        self.path = path
        self.reason = reason
        super().__init__(f"{path} is not a valid {kind}: {reason}")


class BackendError(RetmanError):
    """The decision or text backend failed.

    Parameters
    ----------
    url : str
        Server address of the backend (shown by ``retman doctor``).
    """

    def __init__(self, url: str, message: str = "") -> None:
        self.url = url
        super().__init__(f"{url}: {message}" if message else url)


class BackendConnectionError(BackendError):
    """The model server did not respond (connection error or timeout)."""


class InvalidModelAnswerError(BackendError):
    """The model answered with something that is not one of the allowed keys."""


class PlanNotConfirmedError(RetmanError):
    """``execute()`` was called with a plan that was not confirmed."""


class PlanIncompleteError(RetmanError):
    """``confirm()`` or ``execute()`` was called while questions are still open."""

"""A guard for checks that must stay offline and effect-free (PRD N-12).

While it is active every connection or name lookup beyond the loopback is
recorded and refused, the working folder is a scratch folder, and the files that
appear below the watched folder are listed afterwards. A tool may swallow the
refusal (turning it into its own error), so the verdict is read from the record.
"""

import ipaddress
import os
import socket
from contextlib import ExitStack
from pathlib import Path
from types import TracebackType
from typing import Any
from unittest import mock


def _is_local(host: object) -> bool:
    try:
        return ipaddress.ip_address(str(host)).is_loopback
    except ValueError:
        return host in (None, "", "localhost")


def _listing(root: Path | None) -> set[Path]:
    return set(root.rglob("*")) if root is not None and root.exists() else set()


class OfflineGuard:
    """Context manager recording network attempts and files created.

    Parameters
    ----------
    watch : Path, optional
        A folder whose new files are listed in ``created`` on exit (relative
        paths); the folder may not exist yet.
    cwd : Path, optional
        Working folder for the duration (an existing scratch folder), so that a
        write to the "current folder" cannot reach the project.

    Attributes
    ----------
    attempts : list[str]
        Hosts and addresses something tried to reach, in order of first attempt.
    created : list[str]
        Files and folders that appeared below ``watch``.
    """

    def __init__(self, watch: Path | None = None, *, cwd: Path | None = None) -> None:
        self.attempts: list[str] = []
        self.created: list[str] = []
        self._watch = watch
        self._cwd = cwd
        self._stack = ExitStack()
        self._before: set[Path] = set()
        self._previous_cwd: str | None = None

    def _refuse(self, target: object) -> None:
        text = str(target)
        if text not in self.attempts:
            self.attempts.append(text)
        raise OSError(f"network access is refused during an offline check: {text}")

    def __enter__(self) -> "OfflineGuard":
        """Refuse network access and enter the scratch folder, if one is given."""
        if self._cwd is not None:
            self._previous_cwd = os.getcwd()
            os.chdir(self._cwd)
        self._before = _listing(self._watch)
        connect = socket.socket.connect
        connect_ex = socket.socket.connect_ex
        getaddrinfo = socket.getaddrinfo

        def guarded_connect(sock: socket.socket, address: Any) -> Any:
            # A tuple is an internet address; anything else is a local socket
            if isinstance(address, tuple) and not _is_local(address[0]):
                self._refuse(address[0])
            return connect(sock, address)

        def guarded_connect_ex(sock: socket.socket, address: Any) -> Any:
            if isinstance(address, tuple) and not _is_local(address[0]):
                self._refuse(address[0])
            return connect_ex(sock, address)

        def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
            if not _is_local(host):
                self._refuse(host)
            return getaddrinfo(host, *args, **kwargs)

        patch = mock.patch.object
        self._stack.enter_context(patch(socket.socket, "connect", guarded_connect))
        self._stack.enter_context(
            patch(socket.socket, "connect_ex", guarded_connect_ex)
        )
        self._stack.enter_context(patch(socket, "getaddrinfo", guarded_getaddrinfo))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Restore network access and the folder; list what appeared below ``watch``."""
        self._stack.close()
        if self._watch is not None:
            self.created = sorted(
                str(path.relative_to(self._watch))
                for path in _listing(self._watch) - self._before
            )
        if self._previous_cwd is not None:
            os.chdir(self._previous_cwd)

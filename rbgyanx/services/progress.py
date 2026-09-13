"""
Progress reporting seam (v2 Phase 4 · Slice 1).

The orchestration layer must not import a UI toolkit. It reports progress through this
protocol instead, so the same code drives the Tkinter app, the Qt app, a CLI run, or a test.

PHI note: reporters receive human-readable status text only. Callers must not pass patient
identifiers or clinical values into ``log``/``status`` — the orchestrator passes counts,
step names and file *counts*, never patient data.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ProgressReporter", "NullReporter", "CollectingReporter", "CallbackReporter"]


@runtime_checkable
class ProgressReporter(Protocol):
    """Anything that can surface pipeline progress."""

    def log(self, message: str) -> None:
        """Append a line to the run log."""

    def status(self, message: str) -> None:
        """Set the current one-line status."""

    def progress(self, fraction: float) -> None:
        """Report overall completion in [0.0, 1.0]."""


class NullReporter:
    """Discards everything — the default for headless/library use."""

    def log(self, message: str) -> None:  # noqa: D102
        return None

    def status(self, message: str) -> None:  # noqa: D102
        return None

    def progress(self, fraction: float) -> None:  # noqa: D102
        return None


class CollectingReporter:
    """Records calls in memory. Used by tests and by the Qt run view."""

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.statuses: list[str] = []
        self.progresses: list[float] = []

    def log(self, message: str) -> None:  # noqa: D102
        self.logs.append(str(message))

    def status(self, message: str) -> None:  # noqa: D102
        self.statuses.append(str(message))

    def progress(self, fraction: float) -> None:  # noqa: D102
        self.progresses.append(float(fraction))


class CallbackReporter:
    """Adapts plain callables to the protocol (bridges an existing GUI's log/status)."""

    def __init__(self, log=None, status=None, progress=None) -> None:
        self._log = log
        self._status = status
        self._progress = progress

    def log(self, message: str) -> None:  # noqa: D102
        if self._log is not None:
            self._log(message)

    def status(self, message: str) -> None:  # noqa: D102
        if self._status is not None:
            self._status(message)

    def progress(self, fraction: float) -> None:  # noqa: D102
        if self._progress is not None:
            self._progress(float(fraction))

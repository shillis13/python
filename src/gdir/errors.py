"""Error hierarchy for gdir."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GDirError(Exception):
    """Base exception that carries an exit code."""

    message: str
    exit_code: int

    def __str__(self) -> str:  # pragma: no cover - simple string repr
        return self.message


class UsageError(GDirError):
    """Raised when a command is used incorrectly."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=64)


class InvalidSelectionError(GDirError):
    """Raised when the requested mapping or history selection is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=2)


class InternalError(GDirError):
    """Raised for unexpected internal failures."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, exit_code=70)


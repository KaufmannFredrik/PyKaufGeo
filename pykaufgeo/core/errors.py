"""Error hierarchy. Every message is written for the user and shown verbatim."""

from __future__ import annotations


class PKGError(Exception):
    """Base class for all user-facing errors."""

    def __init__(self, message: str, position: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        return self.message


class ParseError(PKGError):
    """Input text could not be parsed."""


class EvalError(PKGError):
    """An expression could not be evaluated (structural problem, not a numeric one)."""


class UndefinedVariableError(EvalError):
    pass


class CommandError(EvalError):
    """Wrong arguments for a command."""


class CycleError(PKGError):
    """A definition would make an object depend on itself."""


class LabelError(PKGError):
    """Invalid, reserved, or duplicate label."""


class RedefineError(PKGError):
    """A redefinition was rejected and rolled back."""


class FileFormatError(PKGError):
    """A document file could not be read."""

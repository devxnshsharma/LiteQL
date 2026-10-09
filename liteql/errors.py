"""Error classes, one per compiler phase.

Every error says which phase caught it, so a viva answer to "where was this
mistake detected?" is always visible in the message itself.

Note: ``SyntaxError`` and ``TypeError`` deliberately reuse the names from the
project specification. Inside LiteQL modules, import them through this module
(``from . import errors``) so Python's built-in exceptions are never shadowed.
"""

from __future__ import annotations


class LiteQLError(Exception):
    """Base class for every user-facing LiteQL error."""

    phase = "LiteQL"

    def __init__(self, message: str, position: int | None = None):
        super().__init__(message)
        self.message = message
        # Character offset in the query text (only for lexical/syntax errors).
        self.position = position
        # Whatever compiler stages finished before the error (set by compile_query).
        self.compilation = None

    def __str__(self) -> str:
        return f"{self.phase} Error: {self.message}"


class LexicalError(LiteQLError):
    """The query contains a character sequence that is not a valid token."""

    phase = "Lexical"


class SyntaxError(LiteQLError):  # noqa: A001 - name required by the project spec
    """The tokens do not follow the LiteQL grammar."""

    phase = "Syntax"


class SemanticError(LiteQLError):
    """The query is grammatical but does not make sense for the data file."""

    phase = "Semantic"


class TypeError(LiteQLError):  # noqa: A001 - name required by the project spec
    """A comparison mixes incompatible types (for example NUMBER and TEXT)."""

    phase = "Type"


class ExecutionError(LiteQLError):
    """The data file could not be found or read."""

    phase = "Execution"

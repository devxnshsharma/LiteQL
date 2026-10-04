class LiteQLError(Exception):
    """Base class for user-facing LiteQL errors."""

    phase = "LiteQL"

    def __str__(self):
        return f"{self.phase} Error: {self.args[0]}"


class LexicalError(LiteQLError):
    phase = "Lexical"


class SyntaxError(LiteQLError):
    phase = "Syntax"


class SemanticError(LiteQLError):
    phase = "Semantic"


class TypeError(LiteQLError):
    phase = "Type"


class ExecutionError(LiteQLError):
    phase = "Execution"

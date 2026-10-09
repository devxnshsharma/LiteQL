"""Token definitions: the vocabulary produced by the lexer."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Keywords
    SELECT = auto()
    FROM = auto()
    WHERE = auto()
    ORDER = auto()
    BY = auto()
    ASC = auto()
    DESC = auto()
    LIMIT = auto()
    AND = auto()
    OR = auto()
    # Names and literals
    IDENTIFIER = auto()
    STRING = auto()      # 'text' or "text"
    NUMBER = auto()      # 20, 3.5, -4
    FILENAME = auto()    # bare data file name such as titanic.csv (only valid after FROM)
    # Punctuation
    STAR = auto()
    COMMA = auto()
    SEMICOLON = auto()   # optional end-of-query marker
    # Comparison operators
    EQUAL = auto()
    NOT_EQUAL = auto()
    GREATER = auto()
    LESS = auto()
    GREATER_EQUAL = auto()
    LESS_EQUAL = auto()
    # End of input
    EOF = auto()


COMPARISON_OPERATORS = (
    TokenType.EQUAL,
    TokenType.NOT_EQUAL,
    TokenType.GREATER,
    TokenType.LESS,
    TokenType.GREATER_EQUAL,
    TokenType.LESS_EQUAL,
)


@dataclass(frozen=True)
class Token:
    type: TokenType
    text: str        # the characters of the token (quotes removed for STRING)
    position: int    # character offset in the query text

    def __str__(self) -> str:
        if self.type is TokenType.EOF or self.text == self.type.name:
            return self.type.name      # SELECT, EOF
        return f"{self.type.name}({self.text})"

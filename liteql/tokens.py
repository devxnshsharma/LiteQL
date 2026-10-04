from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    SELECT = auto(); FROM = auto(); WHERE = auto(); ORDER = auto(); BY = auto()
    ASC = auto(); DESC = auto(); LIMIT = auto(); AND = auto(); OR = auto()
    IDENTIFIER = auto(); STRING = auto(); NUMBER = auto(); STAR = auto(); COMMA = auto()
    EQUAL = auto(); NOT_EQUAL = auto(); GREATER = auto(); LESS = auto()
    GREATER_EQUAL = auto(); LESS_EQUAL = auto(); EOF = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    text: str
    position: int

    def __str__(self):
        return f"{self.type.name}({self.text})"

import re

from .errors import LexicalError
from .tokens import Token, TokenType

KEYWORDS = {name: getattr(TokenType, name) for name in
            ("SELECT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC", "LIMIT", "AND", "OR")}
OPERATORS = {"!=": TokenType.NOT_EQUAL, ">=": TokenType.GREATER_EQUAL, "<=": TokenType.LESS_EQUAL,
             "=": TokenType.EQUAL, ">": TokenType.GREATER, "<": TokenType.LESS,
             ",": TokenType.COMMA, "*": TokenType.STAR}


def tokenize(source: str) -> list[Token]:
    """Turn query characters into tokens. This phase knows nothing about files or types."""
    tokens, i = [], 0
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            i += 1; continue
        if ch in "\"'":
            quote, start = ch, i; i += 1; value = []
            while i < len(source) and source[i] != quote:
                value.append(source[i]); i += 1
            if i == len(source):
                raise LexicalError(f"Unterminated string starting at position {start}")
            tokens.append(Token(TokenType.STRING, "".join(value), start)); i += 1; continue
        match = re.match(r"\d+(?:\.\d+)?", source[i:])
        if match:
            text = match.group(); tokens.append(Token(TokenType.NUMBER, text, i)); i += len(text); continue
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[i:])
        if match:
            text = match.group(); tokens.append(Token(KEYWORDS.get(text.upper(), TokenType.IDENTIFIER), text, i)); i += len(text); continue
        op = next((value for value in ("!=", ">=", "<=", "=", ">", "<", ",", "*") if source.startswith(value, i)), None)
        if op:
            tokens.append(Token(OPERATORS[op], op, i)); i += len(op); continue
        raise LexicalError(f"Unexpected character {ch!r} at position {i}")
    tokens.append(Token(TokenType.EOF, "", len(source)))
    return tokens

"""Phase 1 - Lexical analysis.

The lexer reads the query left to right and groups characters into tokens.
It knows nothing about files, columns or types: ``age`` is just an IDENTIFIER
here, and whether such a column exists is decided much later.
"""

import re

from .errors import LexicalError
from .tokens import Token, TokenType

KEYWORDS = {
    "SELECT": TokenType.SELECT,
    "FROM": TokenType.FROM,
    "WHERE": TokenType.WHERE,
    "ORDER": TokenType.ORDER,
    "BY": TokenType.BY,
    "ASC": TokenType.ASC,
    "DESC": TokenType.DESC,
    "LIMIT": TokenType.LIMIT,
    "AND": TokenType.AND,
    "OR": TokenType.OR,
}

# Longest operators first so that ">=" is not read as ">" followed by "=".
OPERATORS = [
    ("!=", TokenType.NOT_EQUAL),
    (">=", TokenType.GREATER_EQUAL),
    ("<=", TokenType.LESS_EQUAL),
    ("=", TokenType.EQUAL),
    (">", TokenType.GREATER),
    ("<", TokenType.LESS),
    (",", TokenType.COMMA),
    ("*", TokenType.STAR),
    (";", TokenType.SEMICOLON),
]

# A bare file name must end in .csv or .json, e.g. titanic.csv or data/people.json.
FILENAME_RE = re.compile(r"[A-Za-z0-9_./~][A-Za-z0-9_./~\\-]*\.(?:csv|json)(?![A-Za-z0-9_])", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def tokenize(source: str) -> list[Token]:
    """Convert query text into a list of tokens ending with EOF."""
    tokens: list[Token] = []
    i = 0
    while i < len(source):
        ch = source[i]

        if ch.isspace():
            i += 1
            continue

        # Quoted text: a file name after FROM, or a string value in WHERE.
        if ch in "'\"":
            end = source.find(ch, i + 1)
            if end == -1:
                raise LexicalError(f"Unterminated string starting at position {i}", i)
            tokens.append(Token(TokenType.STRING, source[i + 1:end], i))
            i = end + 1
            continue

        # Bare file name (must be tried before NUMBER/IDENTIFIER, which would
        # otherwise stop at the dot).
        match = FILENAME_RE.match(source, i)
        if match:
            tokens.append(Token(TokenType.FILENAME, match.group(), i))
            i = match.end()
            continue

        match = NUMBER_RE.match(source, i)
        if match:
            end = match.end()
            if end < len(source) and (source[end].isalpha() or source[end] == "_"):
                bad = re.match(r"\S+", source[i:]).group()
                raise LexicalError(f"Malformed number '{bad}' at position {i}", i)
            tokens.append(Token(TokenType.NUMBER, match.group(), i))
            i = end
            continue

        match = IDENTIFIER_RE.match(source, i)
        if match:
            text = match.group()
            tokens.append(Token(KEYWORDS.get(text.upper(), TokenType.IDENTIFIER), text, i))
            i = match.end()
            continue

        for text, token_type in OPERATORS:
            if source.startswith(text, i):
                tokens.append(Token(token_type, text, i))
                i += len(text)
                break
        else:
            hint = " (LiteQL has no parentheses or function calls)" if ch in "()" else ""
            raise LexicalError(f"Unexpected character {ch!r} at position {i}{hint}", i)

    tokens.append(Token(TokenType.EOF, "", len(source)))
    return tokens

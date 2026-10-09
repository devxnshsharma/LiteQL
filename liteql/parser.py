"""Phase 2 - Syntax analysis: a hand-written recursive-descent parser.

Each grammar rule in docs/grammar.md has one method here, so the code can be
read side by side with the grammar. The parser only looks at tokens: it never
opens the data file and never checks whether columns exist.
"""

from __future__ import annotations

from . import errors
from .ast import (And, Column, ColumnReference, Comparison, NumberLiteral, Or, OrderBy,
                  Query, StringLiteral)
from .tokens import COMPARISON_OPERATORS, Token, TokenType

# Words that exist in real SQL but are outside LiteQL's scope. Naming them in
# the error message is friendlier than a generic "unexpected token".
UNSUPPORTED_WORDS = {
    "JOIN", "GROUP", "HAVING", "UNION", "DISTINCT", "LIKE", "IN", "NOT", "BETWEEN", "IS",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "INSERT", "UPDATE", "DELETE", "AS", "OFFSET",
}


# The condition tree is processed recursively, so a pathological WHERE clause
# could overflow Python's recursion limit. 100 comparisons is far beyond real use.
MAX_COMPARISONS = 100


def describe(token: Token) -> str:
    """Human-readable description of a token for error messages."""
    if token.type is TokenType.EOF:
        return "end of query"
    if token.type is TokenType.STRING:
        return f"string '{token.text}'"
    return f"'{token.text}'"


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.index = 0
        self.comparisons = 0

    # --- token helpers ------------------------------------------------------

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        if token.type is not TokenType.EOF:
            self.index += 1
        return token

    def match(self, *kinds: TokenType) -> Token | None:
        """Consume and return the current token if it has one of the given types."""
        if self.current.type in kinds:
            return self.advance()
        return None

    def fail(self, message: str):
        token = self.current
        found = describe(token)
        if token.text.upper() in UNSUPPORTED_WORDS:
            found += f" - {token.text.upper()} is not supported by LiteQL"
        raise errors.SyntaxError(f"{message}, but found {found} at position {token.position}",
                                 token.position)

    def expect(self, kind: TokenType, message: str) -> Token:
        token = self.match(kind)
        if token is None:
            self.fail(message)
        return token

    # --- grammar rules ------------------------------------------------------

    def parse_query(self) -> Query:
        """query ::= SELECT column_list FROM file [where] [order] [limit]"""
        self.expect(TokenType.SELECT, "Expected SELECT at the start of the query")
        columns = self.parse_column_list()
        self.expect(TokenType.FROM, "Expected FROM after SELECT column list")
        source = self.parse_source()

        where = None
        if self.match(TokenType.WHERE):
            where = self.parse_condition()

        order_by = None
        if self.current.type is TokenType.ORDER:
            order_by = self.parse_order_clause()

        limit = None
        if self.current.type is TokenType.LIMIT:
            limit = self.parse_limit_clause()

        self.match(TokenType.SEMICOLON)
        if self.current.type is not TokenType.EOF:
            hint = ""
            if self.current.type in (TokenType.WHERE, TokenType.ORDER, TokenType.LIMIT, TokenType.FROM):
                hint = " (clauses must appear in the order WHERE, ORDER BY, LIMIT, each at most once)"
            self.fail("Expected end of query" + hint)
        return Query(columns, source, where, order_by, limit)

    def parse_source(self) -> str:
        """file ::= STRING | FILENAME   (FILENAME is a bare name like titanic.csv)"""
        token = self.match(TokenType.STRING, TokenType.FILENAME)
        if token is None:
            self.fail("Expected a file name after FROM, quoted (\"data.csv\") or bare (data.csv)")
        return token.text

    def parse_column_list(self):
        """column_list ::= "*" | column ("," column)*   (None stands for *)"""
        if self.match(TokenType.STAR):
            return None
        columns = [self.parse_column("Expected a column name or * after SELECT")]
        while self.match(TokenType.COMMA):
            columns.append(self.parse_column("Expected a column name after ','"))
        return columns

    def parse_column(self, message: str) -> Column:
        return Column(self.expect(TokenType.IDENTIFIER, message).text)

    def parse_condition(self):
        """condition ::= and_term ("OR" and_term)*

        The documented grammar writes `comparison (("AND"|"OR") comparison)*`
        without saying which connector binds tighter. LiteQL follows SQL: AND
        binds tighter than OR, which is expressed by splitting the rule in two.
        Both forms accept exactly the same queries.
        """
        condition = self.parse_and_term()
        while self.match(TokenType.OR):
            condition = Or(condition, self.parse_and_term())
        return condition

    def parse_and_term(self):
        """and_term ::= comparison ("AND" comparison)*"""
        condition = self.parse_comparison()
        while self.match(TokenType.AND):
            condition = And(condition, self.parse_comparison())
        return condition

    def parse_comparison(self) -> Comparison:
        """comparison ::= column OP value"""
        self.comparisons += 1
        if self.comparisons > MAX_COMPARISONS:
            self.fail(f"A WHERE clause may contain at most {MAX_COMPARISONS} comparisons")
        column = self.parse_column("Expected a column name in the condition")
        if self.current.type not in COMPARISON_OPERATORS:
            self.fail(f"Expected a comparison operator (= != > < >= <=) after column '{column.name}'")
        operator = self.advance().text
        return Comparison(column, operator, self.parse_value())

    def parse_value(self):
        """value ::= STRING | NUMBER | column"""
        token = self.match(TokenType.STRING, TokenType.NUMBER, TokenType.IDENTIFIER)
        if token is None:
            self.fail("Expected a string, number or column name after the comparison operator")
        if token.type is TokenType.STRING:
            return StringLiteral(token.text)
        if token.type is TokenType.NUMBER:
            return NumberLiteral(float(token.text) if "." in token.text else int(token.text))
        return ColumnReference(token.text)

    def parse_order_clause(self) -> OrderBy:
        """order_clause ::= "ORDER" "BY" column ["ASC" | "DESC"]"""
        self.expect(TokenType.ORDER, "Expected ORDER")
        self.expect(TokenType.BY, "Expected BY after ORDER")
        column = self.parse_column("Expected a column name after ORDER BY")
        direction = "ASC"
        if self.match(TokenType.DESC):
            direction = "DESC"
        else:
            self.match(TokenType.ASC)
        return OrderBy(column, direction)

    def parse_limit_clause(self) -> int:
        """limit_clause ::= "LIMIT" INTEGER"""
        self.expect(TokenType.LIMIT, "Expected LIMIT")
        token = self.expect(TokenType.NUMBER, "Expected a whole number after LIMIT")
        if "." in token.text:
            raise errors.SyntaxError(f"LIMIT must be a whole number, not '{token.text}' "
                                     f"(position {token.position})", token.position)
        return int(token.text)


def parse(tokens: list[Token]) -> Query:
    """Parse a token list into a Query AST."""
    return Parser(tokens).parse_query()

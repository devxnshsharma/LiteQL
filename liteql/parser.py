from .ast import BinaryCondition, Column, ColumnReference, Comparison, NumberLiteral, OrderBy, Query, StringLiteral
from .errors import SyntaxError
from .tokens import Token, TokenType

OPS = {TokenType.EQUAL, TokenType.NOT_EQUAL, TokenType.GREATER, TokenType.LESS, TokenType.GREATER_EQUAL, TokenType.LESS_EQUAL}


class Parser:
    def __init__(self, tokens): self.tokens, self.index = tokens, 0
    @property
    def current(self): return self.tokens[self.index]
    def accept(self, kind):
        if self.current.type == kind:
            token = self.current; self.index += 1; return token
        return None
    def expect(self, kind, message):
        token = self.accept(kind)
        if not token: raise SyntaxError(f"{message} at position {self.current.position}; found {self.current.type.name}")
        return token
    def parse(self):
        self.expect(TokenType.SELECT, "Expected SELECT")
        columns = self.parse_column_list()
        self.expect(TokenType.FROM, "Expected FROM after SELECT column list")
        source = self.expect(TokenType.STRING, "Expected quoted file name after FROM").text
        where = self.parse_condition() if self.accept(TokenType.WHERE) else None
        order = self.parse_order() if self.accept(TokenType.ORDER) else None
        limit = None
        if self.accept(TokenType.LIMIT):
            text = self.expect(TokenType.NUMBER, "Expected integer after LIMIT").text
            if "." in text: raise SyntaxError("LIMIT must be a whole number")
            limit = int(text)
        self.expect(TokenType.EOF, "Unexpected token after complete query")
        return Query(columns, source, where, order, limit)
    def parse_column_list(self):
        if self.accept(TokenType.STAR): return None
        columns = [Column(self.expect(TokenType.IDENTIFIER, "Expected column name after SELECT").text)]
        while self.accept(TokenType.COMMA): columns.append(Column(self.expect(TokenType.IDENTIFIER, "Expected column name after comma").text))
        return columns
    def parse_condition(self):
        condition = self.parse_comparison()
        # The documented grammar has no precedence hierarchy, so connectors associate left-to-right.
        while self.current.type in (TokenType.AND, TokenType.OR):
            operator = self.current.text.upper(); self.index += 1
            condition = BinaryCondition(condition, operator, self.parse_comparison())
        return condition
    def parse_comparison(self):
        column = Column(self.expect(TokenType.IDENTIFIER, "Expected column name in WHERE").text)
        if self.current.type not in OPS: raise SyntaxError(f"Expected comparison operator after column '{column.name}'")
        operator = self.current.text; self.index += 1
        token = self.current
        if self.accept(TokenType.STRING): value = StringLiteral(token.text)
        elif self.accept(TokenType.NUMBER): value = NumberLiteral(float(token.text) if "." in token.text else int(token.text))
        elif self.accept(TokenType.IDENTIFIER): value = ColumnReference(token.text)
        else: raise SyntaxError("Expected string, number, or column after comparison operator")
        return Comparison(column, operator, value)
    def parse_order(self):
        self.expect(TokenType.BY, "Expected BY after ORDER")
        column = Column(self.expect(TokenType.IDENTIFIER, "Expected column after ORDER BY").text)
        direction = "ASC"
        if self.accept(TokenType.ASC): direction = "ASC"
        elif self.accept(TokenType.DESC): direction = "DESC"
        return OrderBy(column, direction)


def parse(tokens): return Parser(tokens).parse()

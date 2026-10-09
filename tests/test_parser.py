"""Phase 2: the recursive-descent parser checks structure and builds the AST."""

import pytest

from liteql import ast
from liteql.errors import SyntaxError as LiteSyntaxError
from liteql.lexer import tokenize
from liteql.parser import parse


def parse_text(text):
    return parse(tokenize(text))


def test_minimal_query():
    q = parse_text('SELECT name FROM "students.csv"')
    assert q.columns == [ast.Column("name")]
    assert (q.source, q.where, q.order_by, q.limit) == ("students.csv", None, None, None)


def test_select_star_is_none():
    assert parse_text('SELECT * FROM "x.csv"').columns is None


def test_multiple_columns_keep_order():
    q = parse_text('SELECT c, a, b FROM "x.csv"')
    assert [c.name for c in q.columns] == ["c", "a", "b"]


def test_where_with_each_value_kind():
    q = parse_text("SELECT a FROM x.csv WHERE a = 'x'")
    assert q.where == ast.Comparison(ast.Column("a"), "=", ast.StringLiteral("x"))
    q = parse_text("SELECT a FROM x.csv WHERE a >= 2.5")
    assert q.where.value == ast.NumberLiteral(2.5)
    q = parse_text("SELECT a FROM x.csv WHERE a != b")
    assert q.where.value == ast.ColumnReference("b")


def test_integer_and_decimal_literal_types():
    assert isinstance(parse_text("SELECT a FROM x.csv WHERE a = 3").where.value.value, int)
    assert isinstance(parse_text("SELECT a FROM x.csv WHERE a = 3.0").where.value.value, float)


def test_negative_number_literal():
    assert parse_text("SELECT a FROM x.csv WHERE a > -5").where.value == ast.NumberLiteral(-5)


@pytest.mark.parametrize("op", ["=", "!=", ">", "<", ">=", "<="])
def test_all_comparison_operators(op):
    assert parse_text(f"SELECT a FROM x.csv WHERE a {op} 1").where.operator == op


def test_and_or_build_binary_nodes():
    q = parse_text("SELECT a FROM x.csv WHERE a = 1 AND b = 2")
    assert isinstance(q.where, ast.And)
    q = parse_text("SELECT a FROM x.csv WHERE a = 1 OR b = 2")
    assert isinstance(q.where, ast.Or)


def test_and_binds_tighter_than_or():
    # a OR b AND c  ==  a OR (b AND c)
    q = parse_text("SELECT x FROM f.csv WHERE a = 1 OR b = 2 AND c = 3")
    assert isinstance(q.where, ast.Or)
    assert isinstance(q.where.right, ast.And)
    # a AND b OR c  ==  (a AND b) OR c
    q = parse_text("SELECT x FROM f.csv WHERE a = 1 AND b = 2 OR c = 3")
    assert isinstance(q.where, ast.Or)
    assert isinstance(q.where.left, ast.And)


def test_chained_connectors_are_left_associative():
    q = parse_text("SELECT x FROM f.csv WHERE a = 1 AND b = 2 AND c = 3")
    assert isinstance(q.where.left, ast.And) and isinstance(q.where.right, ast.Comparison)


@pytest.mark.parametrize("tail, direction", [("", "ASC"), (" ASC", "ASC"), (" DESC", "DESC"), (" desc", "DESC")])
def test_order_by_direction(tail, direction):
    q = parse_text(f"SELECT a FROM x.csv ORDER BY a{tail}")
    assert q.order_by == ast.OrderBy(ast.Column("a"), direction)


def test_limit():
    assert parse_text("SELECT a FROM x.csv LIMIT 7").limit == 7
    assert parse_text("SELECT a FROM x.csv LIMIT 0").limit == 0


def test_all_clauses_together():
    q = parse_text(
        'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5')
    assert [c.name for c in q.columns] == ["name", "age"]
    assert q.order_by.direction == "DESC" and q.limit == 5 and q.where is not None


def test_optional_trailing_semicolon():
    assert parse_text("SELECT a FROM x.csv;").source == "x.csv"


def test_bare_and_quoted_file_names_give_same_ast():
    assert parse_text("SELECT a FROM x.csv") == parse_text('SELECT a FROM "x.csv"')


def test_parser_never_touches_the_filesystem():
    parse_text('SELECT a FROM "does/not/exist.csv"')   # no error: files are checked later


@pytest.mark.parametrize("query, message", [
    ('FROM "students.csv" SELECT name', "Expected SELECT"),
    ('SELECT name "students.csv"', "Expected FROM after SELECT column list"),
    ('SELECT name, age "students.csv"', "Expected FROM after SELECT column list"),
    ('SELECT name WHERE age > 20', "Expected FROM"),
    ('SELECT FROM "x.csv"', "Expected a column name or \\*"),
    ('SELECT name, FROM "x.csv"', "Expected a column name after ','"),
    ('SELECT name FROM', "Expected a file name after FROM"),
    ('SELECT name FROM students', "Expected a file name after FROM"),
    ('SELECT name FROM "x.csv" LIMIT', "Expected a whole number after LIMIT"),
    ('SELECT name FROM "x.csv" LIMIT five', "Expected a whole number after LIMIT"),
    ('SELECT name FROM "x.csv" LIMIT 2.5', "LIMIT must be a whole number"),
    ('SELECT name FROM "x.csv" WHERE', "Expected a column name in the condition"),
    ('SELECT name FROM "x.csv" WHERE age', "Expected a comparison operator"),
    ('SELECT name FROM "x.csv" WHERE age 20', "Expected a comparison operator"),
    ('SELECT name FROM "x.csv" WHERE age >', "Expected a string, number or column name"),
    ('SELECT name FROM "x.csv" WHERE age > > 5', "Expected a string, number or column name"),
    ('SELECT name FROM "x.csv" WHERE age == 5', "Expected a string, number or column name"),
    ('SELECT name FROM "x.csv" WHERE age > 5 AND', "Expected a column name in the condition"),
    ('SELECT name FROM "x.csv" WHERE 5 > age', "Expected a column name in the condition"),
    ('SELECT name FROM "x.csv" ORDER age', "Expected BY after ORDER"),
    ('SELECT name FROM "x.csv" ORDER BY', "Expected a column name after ORDER BY"),
    ('SELECT name FROM "x.csv" ORDER BY age, name', "Expected end of query"),
    ('SELECT name FROM "x.csv" LIMIT 5 ORDER BY age', "clauses must appear in the order"),
    ('SELECT name FROM "x.csv" ORDER BY age WHERE age > 1', "clauses must appear in the order"),
    ('SELECT name FROM "x.csv" WHERE a = 1 WHERE b = 2', "Expected end of query"),
    ('SELECT name FROM "x.csv" extra', "Expected end of query"),
    ('', "Expected SELECT"),
    ('SELECT', "Expected a column name or \\*"),
])
def test_syntax_errors(query, message):
    with pytest.raises(LiteSyntaxError, match=message):
        parse_text(query)


@pytest.mark.parametrize("word", ["JOIN", "GROUP", "HAVING", "LIKE"])
def test_unsupported_sql_is_named_in_the_error(word):
    with pytest.raises(LiteSyntaxError, match=f"{word} is not supported"):
        parse_text(f'SELECT a FROM "x.csv" {word} b')


def test_syntax_error_carries_position_and_phase():
    with pytest.raises(LiteSyntaxError) as info:
        parse_text('SELECT name "students.csv"')
    assert info.value.position == 12
    assert str(info.value).startswith("Syntax Error:")

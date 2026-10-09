"""The AST holds structure, and the printer draws it as a tree."""

from liteql import ast
from liteql.lexer import tokenize
from liteql.parser import parse
from liteql.printer import format_ast

from conftest import MAIN_QUERY


def tree(text):
    return format_ast(parse(tokenize(text)))


def test_ast_for_main_query_has_the_right_structure():
    q = parse(tokenize(MAIN_QUERY))
    assert q == ast.Query(
        columns=[ast.Column("name"), ast.Column("age")],
        source="students.csv",
        where=ast.Comparison(ast.Column("age"), ">", ast.NumberLiteral(20)),
        order_by=ast.OrderBy(ast.Column("age"), "DESC"),
        limit=5,
    )


def test_ast_contains_no_tokens_or_punctuation():
    q = parse(tokenize(MAIN_QUERY))
    assert not hasattr(q, "tokens")
    assert all(isinstance(c, ast.Column) for c in q.columns)   # commas are gone


def test_ast_nodes_are_immutable():
    q = parse(tokenize(MAIN_QUERY))
    try:
        q.limit = 9
    except Exception as error:
        assert type(error).__name__ == "FrozenInstanceError"
    else:
        raise AssertionError("AST node should be frozen")


def test_tree_printer_matches_the_report_layout():
    assert tree(MAIN_QUERY) == "\n".join([
        "Query",
        "├── Select: name, age",
        "├── From: students.csv",
        "├── Where",
        "│   └── age > 20",
        "├── Order By: age DESC",
        "└── Limit: 5",
    ])


def test_tree_printer_minimal_query_and_star():
    assert tree('SELECT * FROM "x.csv"') == "Query\n├── Select: *\n└── From: x.csv"


def test_tree_printer_shows_and_or_structure():
    text = tree("SELECT a FROM x.csv WHERE a = 1 OR b = 'x' AND c >= 2")
    assert text.splitlines()[3:] == [
        "└── Where",
        "    └── OR",
        "        ├── a = 1",
        "        └── AND",
        "            ├── b = 'x'",
        "            └── c >= 2",
    ]


def test_column_to_column_comparison_prints_plainly():
    assert "a < b" in tree("SELECT a FROM x.csv WHERE a < b")

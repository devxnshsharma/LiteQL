"""Phase 3: semantic analysis and type checking, using the file's symbol table."""

import pytest

from liteql import compile_query
from liteql.errors import SemanticError, TypeError as LiteTypeError, SyntaxError as LiteSyntaxError


def check(query, file_path):
    return compile_query(query, file_path)


def test_valid_query_passes(students_csv):
    result = check('SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age', students_csv)
    assert result.checked_ast is not None


def test_missing_select_column(students_csv):
    with pytest.raises(SemanticError) as info:
        check('SELECT name, score FROM "students.csv"', students_csv)
    text = str(info.value)
    assert "Column 'score' does not exist" in text
    assert "Available columns: name, age, city" in text


@pytest.mark.parametrize("query", [
    'SELECT name FROM "students.csv" WHERE salary > 3',
    'SELECT name FROM "students.csv" WHERE age > salary',
    'SELECT name FROM "students.csv" WHERE age > 3 AND salary = 1',
    'SELECT name FROM "students.csv" WHERE city = M',            # unquoted word is a column reference
    'SELECT name FROM "students.csv" ORDER BY salary',
])
def test_missing_column_anywhere_in_the_query(students_csv, query):
    with pytest.raises(SemanticError, match="does not exist"):
        check(query, students_csv)


def test_syntactically_valid_query_can_still_fail_semantics(students_csv):
    query = 'SELECT salary FROM "students.csv"'
    from liteql.lexer import tokenize
    from liteql.parser import parse
    parse(tokenize(query))                                  # the parser accepts it ...
    with pytest.raises(SemanticError):                       # ... the semantic phase rejects it
        check(query, students_csv)


def test_syntax_errors_come_before_semantic_errors(students_csv):
    with pytest.raises(LiteSyntaxError):
        check('SELECT salary "students.csv"', students_csv)


def test_valid_numeric_comparison(students_csv):
    check('SELECT name FROM "students.csv" WHERE age >= 20.5', students_csv)


def test_valid_text_comparison(students_csv):
    check('SELECT name FROM "students.csv" WHERE city = "Delhi" AND name != "Riya"', students_csv)
    check('SELECT name FROM "students.csv" WHERE name > "M"', students_csv)       # TEXT ordering is allowed


def test_number_column_vs_text_literal(students_csv):
    with pytest.raises(LiteTypeError) as info:
        check('SELECT name FROM "students.csv" WHERE age > "hello"', students_csv)
    assert str(info.value) == "Type Error: Cannot compare NUMBER column 'age' with TEXT value 'hello'"


def test_text_column_vs_number_literal(students_csv):
    with pytest.raises(LiteTypeError, match="Cannot compare TEXT column 'city' with NUMBER value 20"):
        check('SELECT name FROM "students.csv" WHERE city = 20', students_csv)


def test_number_string_is_still_text(students_csv):
    with pytest.raises(LiteTypeError):
        check("SELECT name FROM \"students.csv\" WHERE age = '20'", students_csv)


def test_column_to_column_types_must_match(students_csv):
    check('SELECT name FROM "students.csv" WHERE city = name', students_csv)
    with pytest.raises(LiteTypeError, match="NUMBER column 'age' with TEXT column 'city'"):
        check('SELECT name FROM "students.csv" WHERE age = city', students_csv)


def test_type_error_inside_or_branch(students_csv):
    with pytest.raises(LiteTypeError):
        check('SELECT name FROM "students.csv" WHERE age > 1 OR city > 2', students_csv)


def test_limit_zero_ok_negative_rejected(students_csv):
    check('SELECT name FROM "students.csv" LIMIT 0', students_csv)
    with pytest.raises(SemanticError, match="LIMIT must not be negative"):
        check('SELECT name FROM "students.csv" LIMIT -1', students_csv)


def test_duplicate_select_column(students_csv):
    with pytest.raises(SemanticError, match="selected more than once"):
        check('SELECT name, NAME FROM "students.csv"', students_csv)


def test_column_names_are_case_insensitive_and_resolved(titanic_csv):
    result = check("SELECT name, AGE FROM titanic.csv WHERE sex = 'male' ORDER BY age", titanic_csv)
    ast = result.checked_ast
    assert [c.name for c in ast.columns] == ["Name", "Age"]
    assert ast.where.column.name == "Sex" and ast.order_by.column.name == "Age"
    assert result.ast.columns[0].name == "name"            # the parsed AST keeps what the user typed


def test_empty_file_has_no_columns(write_file):
    path = write_file("e.json", "[]")
    with pytest.raises(SemanticError, match=r"Available columns: \(none\)"):
        check("SELECT a FROM e.json", path)


def test_semantic_phase_reads_no_data_rows(students_csv, monkeypatch):
    from liteql.data_source import DataSource
    def boom(*args, **kwargs):
        raise AssertionError("rows were scanned during compilation")
    monkeypatch.setattr(DataSource, "scan", boom)
    check(MAIN, students_csv)
    with pytest.raises(SemanticError):
        check('SELECT salary FROM "students.csv"', students_csv)


MAIN = 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'


def test_unquoted_text_value_gets_a_hint(students_csv):
    with pytest.raises(SemanticError, match=r"put it in quotes: 'Delhi'"):
        check('SELECT name FROM "students.csv" WHERE city = Delhi', students_csv)

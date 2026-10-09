"""Shared fixtures and helpers for the LiteQL test suite."""

from pathlib import Path

import pytest

from liteql import compile_query

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MAIN_QUERY = 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'


@pytest.fixture
def students_csv():
    return str(EXAMPLES / "students.csv")


@pytest.fixture
def students_json():
    return str(EXAMPLES / "students.json")


@pytest.fixture
def titanic_csv():
    return str(EXAMPLES / "titanic.csv")


@pytest.fixture
def write_file(tmp_path):
    """write_file("x.csv", text) -> path of a new temporary data file."""
    def write(name, text, encoding="utf-8"):
        path = tmp_path / name
        path.write_bytes(text.encode(encoding))
        return str(path)
    return write


def rows_of(query, file_path=None, optimized=True):
    """Compile and run `query`; return the result rows."""
    rows, _ = compile_query(query, file_path).run(optimized=optimized)
    return rows

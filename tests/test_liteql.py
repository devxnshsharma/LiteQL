from pathlib import Path
import pytest

from liteql.compiler import compile_query
from liteql.errors import LexicalError, SemanticError, SyntaxError, TypeError
from liteql.executor import execute
from liteql.lexer import tokenize
from liteql.optimizer import optimize
from liteql.tokens import TokenType

ROOT = Path(__file__).parent.parent
CSV = str(ROOT / "examples" / "students.csv")
JSON = str(ROOT / "examples" / "students.json")
QUERY = 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'


def test_lexer_keywords_operators_and_literals():
    tokens = tokenize('select name FROM "x.csv" WHERE age >= 20')
    assert [t.type for t in tokens] == [TokenType.SELECT, TokenType.IDENTIFIER, TokenType.FROM, TokenType.STRING, TokenType.WHERE, TokenType.IDENTIFIER, TokenType.GREATER_EQUAL, TokenType.NUMBER, TokenType.EOF]


def test_lexer_rejects_unknown_character():
    with pytest.raises(LexicalError): tokenize("SELECT @ FROM \"x.csv\"")


def test_parser_builds_full_ast():
    result = compile_query(QUERY, CSV)
    assert [c.name for c in result.ast.columns] == ["name", "age"]
    assert result.ast.order_by.direction == "DESC" and result.ast.limit == 5


@pytest.mark.parametrize("query", ['FROM "students.csv" SELECT name', 'SELECT name "students.csv"', 'SELECT name FROM "students.csv" LIMIT'])
def test_parser_rejects_malformed_queries(query):
    with pytest.raises(SyntaxError): compile_query(query, CSV)


def test_schema_and_semantic_missing_column():
    result = compile_query('SELECT name FROM "students.csv"', CSV)
    assert result.schema.columns["age"].value == "NUMBER"
    with pytest.raises(SemanticError): compile_query('SELECT salary FROM "students.csv"', CSV)


@pytest.mark.parametrize("query", ['SELECT name FROM "students.csv" WHERE age > "hello"', 'SELECT name FROM "students.csv" WHERE city > 20'])
def test_type_checking(query):
    with pytest.raises(TypeError): compile_query(query, CSV)


def test_csv_execution_and_projection():
    result = compile_query(QUERY, CSV)
    rows = execute(result.optimized_plan)
    assert rows == [{"name": "Vihaan", "age": "31"}, {"name": "Meera", "age": "28"}, {"name": "Arjun", "age": "26"}, {"name": "Diya", "age": "24"}, {"name": "Kabir", "age": "22"}]


def test_json_execution():
    result = compile_query('SELECT name FROM "students.json" WHERE age >= 28 ORDER BY age ASC', JSON)
    assert execute(result.optimized_plan) == [{"name": "Meera"}, {"name": "Vihaan"}]


def test_select_star_and_or():
    result = compile_query('SELECT * FROM "students.csv" WHERE city = "Delhi" OR age = 31', CSV)
    assert [row["name"] for row in execute(result.optimized_plan)] == ["Aarav", "Arjun", "Vihaan"]


def test_optimization_pushes_predicate_and_projection_and_preserves_result():
    result = compile_query(QUERY, CSV)
    scan = result.optimized_plan.child.child.child
    assert scan.predicate is not None and set(scan.columns) == {"name", "age"}
    assert execute(result.plan) == execute(result.optimized_plan)

"""Whole-pipeline tests: example files, error phases, the CLI, and an independent oracle."""

import csv
import itertools
from pathlib import Path

import pytest

from liteql import compile_query
from liteql import cli
from liteql.errors import (ExecutionError, LexicalError, LiteQLError, SemanticError,
                           SyntaxError as LiteSyntaxError, TypeError as LiteTypeError)

from conftest import EXAMPLES, MAIN_QUERY, rows_of

PHASES = {"Lexical": LexicalError, "Syntax": LiteSyntaxError, "Semantic": SemanticError,
          "Type": LiteTypeError, "Execution": ExecutionError}


def example_lines(name):
    for line in (EXAMPLES / name).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            yield line


# --- the shipped example query files ---------------------------------------------

@pytest.mark.parametrize("query", list(example_lines("valid_queries.txt")))
def test_every_valid_example_runs_and_optimizes_correctly(query, monkeypatch):
    monkeypatch.chdir(EXAMPLES)
    optimized = rows_of(query, optimized=True)
    assert optimized == rows_of(query, optimized=False)


@pytest.mark.parametrize("line", list(example_lines("invalid_queries.txt")))
def test_every_invalid_example_fails_in_the_stated_phase(line, monkeypatch):
    monkeypatch.chdir(EXAMPLES)
    phase, query = (part.strip() for part in line.split("|", 1))
    with pytest.raises(PHASES[phase]):
        compile_query(query)


# --- the five cases from the project plan ------------------------------------------

def test_valid_query(students_csv):
    rows, compilation = cli_free_run(MAIN_QUERY, students_csv)
    assert [r["name"] for r in rows] == ["Vihaan", "Meera", "Arjun", "Diya", "Kabir"]
    assert all(stage is not None for stage in (compilation.tokens, compilation.ast, compilation.schema,
                                               compilation.plan, compilation.optimized_plan))


def cli_free_run(query, path):
    compilation = compile_query(query, path)
    return compilation.run()[0], compilation


def test_syntax_error(students_csv):
    with pytest.raises(LiteSyntaxError) as info:
        compile_query('SELECT name, age "students.csv"', students_csv)
    assert info.value.compilation.tokens is not None and info.value.compilation.ast is None


def test_missing_column(students_csv):
    with pytest.raises(SemanticError) as info:
        compile_query('SELECT name, salary FROM "students.csv"', students_csv)
    assert info.value.compilation.schema is not None and info.value.compilation.plan is None


def test_type_error(students_csv):
    with pytest.raises(LiteTypeError):
        compile_query('SELECT name FROM "students.csv" WHERE age > "hello"', students_csv)


def test_optimized_result(students_csv):
    compilation = compile_query(MAIN_QUERY, students_csv)
    assert compilation.run(True)[0] == compilation.run(False)[0]


def test_invalid_queries_never_reach_the_data_rows(students_csv, monkeypatch):
    from liteql.data_source import DataSource
    monkeypatch.setattr(DataSource, "scan", lambda *a, **k: pytest.fail("a row was scanned"))
    for query in ['SELECT name "x"', 'SELECT salary FROM "students.csv"',
                  'SELECT name FROM "students.csv" WHERE age > "x"', "SELECT @ FROM x"]:
        with pytest.raises(LiteQLError):
            compile_query(query, students_csv)


def test_missing_data_file_is_an_execution_error():
    with pytest.raises(ExecutionError, match="Unable to read file 'nope.csv'"):
        compile_query('SELECT a FROM "nope.csv"')


# --- queries a teacher is likely to type -------------------------------------------------

@pytest.mark.parametrize("query, expected_count", [
    ("SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' order by age desc limit 10", 10),
    ("select * from titanic.csv where age > 20 and sex = 'M' order by age desc limit 10", 0),
    ('SELECT * FROM "titanic.csv" LIMIT 5', 5),
    ("SELECT name, fare FROM titanic.csv WHERE pclass = 1 ORDER BY fare DESC LIMIT 3;", 3),
    ("SELECT Name FROM titanic.csv WHERE Survived = 1 AND Pclass != 3 AND Age < 40", None),
    ("SELECT * FROM titanic.csv WHERE age >= 18 OR age < 18", None),
    ("SELECT cabin FROM titanic.csv WHERE cabin != 'x'", None),
    ("SELECT   *   FROM   titanic.csv\n  WHERE   age>20\n  LIMIT   2", 2),
])
def test_titanic_style_queries(query, expected_count, titanic_csv):
    rows = rows_of(query, titanic_csv)
    assert rows == rows_of(query, titanic_csv, optimized=False)
    if expected_count is not None:
        assert len(rows) == expected_count


def test_user_query_returns_adult_males_oldest_first(titanic_csv):
    rows = rows_of("SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' order by age desc limit 10", titanic_csv)
    ages = [r["Age"] for r in rows]
    assert ages == sorted(ages, reverse=True) and all(a > 20 for a in ages)
    assert {r["Sex"] for r in rows} == {"male"}
    assert set(rows[0]) == set(open_header(titanic_csv))     # SELECT * keeps every column


def open_header(path):
    return next(csv.reader(open(path, encoding="utf-8")))


def test_file_name_forms_are_equivalent(titanic_csv, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    a = rows_of("SELECT Name FROM titanic.csv LIMIT 3")                       # examples/ fallback
    b = rows_of('SELECT Name FROM "titanic.csv" LIMIT 3', titanic_csv)          # --file
    c = rows_of(f'SELECT Name FROM "{titanic_csv}" LIMIT 3')                    # explicit path
    assert a == b == c and len(a) == 3


def test_from_file_wins_over_unrelated_file_option(students_csv, students_json):
    # FROM names students.json; --file points at a different file in the same folder: FROM is honoured
    rows = rows_of('SELECT name FROM "students.json" LIMIT 1', students_csv)
    assert rows == [{"name": "Aarav"}]


# --- independent oracle: compare against plain Python on the raw CSV --------------------

def load_titanic(path):
    with open(path, newline="", encoding="utf-8") as handle:
        out = []
        for raw in csv.DictReader(handle):
            row = dict(raw)
            for key in ("Age", "Fare", "Pclass", "SibSp", "Parch", "Survived"):
                row[key] = float(raw[key]) if raw[key] != "" else None
            out.append(row)
        return out


ATOMS = [  # (LiteQL text, python predicate); None never matches, like a SQL NULL
    ("Age > 30", lambda r: r["Age"] is not None and r["Age"] > 30),
    ("Age <= 25", lambda r: r["Age"] is not None and r["Age"] <= 25),
    ("Age != 22", lambda r: r["Age"] is not None and r["Age"] != 22),
    ("Sex = 'female'", lambda r: r["Sex"] == "female"),
    ("Sex != 'female'", lambda r: r["Sex"] != "female"),
    ("Pclass >= 2", lambda r: r["Pclass"] >= 2),
    ("Fare < 20", lambda r: r["Fare"] < 20),
    ("Cabin = 'C85'", lambda r: r["Cabin"] == "C85"),
    ("Embarked > 'Q'", lambda r: r["Embarked"] != "" and r["Embarked"] > "Q"),
    ("SibSp > Parch", lambda r: r["SibSp"] > r["Parch"]),
]


def test_results_match_a_plain_python_oracle(titanic_csv):
    data = load_titanic(titanic_csv)
    checked = 0
    for (t1, p1), (t2, p2) in itertools.product(ATOMS, repeat=2):
        for text, predicate in [
            (f"{t1}", p1),
            (f"{t1} AND {t2}", lambda r, p1=p1, p2=p2: p1(r) and p2(r)),
            (f"{t1} OR {t2}", lambda r, p1=p1, p2=p2: p1(r) or p2(r)),
        ]:
            for order, key, desc in [("", None, False), ("ORDER BY Age", "Age", False), ("ORDER BY Fare DESC", "Fare", True)]:
                expected = [r for r in data if predicate(r)]
                if key:
                    present = [r for r in expected if r[key] is not None]
                    missing = [r for r in expected if r[key] is None]
                    expected = sorted(present, key=lambda r: r[key], reverse=desc) + missing
                expected_ids = [int(r["PassengerId"]) for r in expected][:7]
                rows = rows_of(f"SELECT PassengerId, Age, Fare FROM titanic.csv WHERE {text} {order} LIMIT 7", titanic_csv)
                assert [r["PassengerId"] for r in rows] == expected_ids, (text, order)
                checked += 1
    assert checked == 10 * 10 * 3 * 3


def test_and_or_precedence_against_oracle(titanic_csv):
    data = load_titanic(titanic_csv)
    query = "SELECT PassengerId FROM titanic.csv WHERE Sex = 'female' OR Pclass = 1 AND Age > 40"
    expected = [int(r["PassengerId"]) for r in data if r["Sex"] == "female" or (r["Pclass"] == 1 and r["Age"] is not None and r["Age"] > 40)]
    assert [r["PassengerId"] for r in rows_of(query, titanic_csv)] == expected


# --- the command-line interface ---------------------------------------------------------------

def run_cli(capsys, *args):
    code = cli.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_default_prints_only_the_result(capsys, students_csv):
    code, out, err = run_cli(capsys, "--file", students_csv, "--query", MAIN_QUERY)
    assert code == 0 and err == ""
    assert out.splitlines()[0].split() == ["name", "age"] and "Vihaan  31" in out and "(5 rows)" in out
    assert "Tokens" not in out


def test_cli_all_shows_every_stage(capsys, students_csv):
    code, out, _ = run_cli(capsys, "--file", students_csv, "--query", MAIN_QUERY, "--all")
    assert code == 0
    for heading in ("Tokens:", "AST:", "Symbol Table:", "Logical Plan:", "Optimized Plan:", "Work done by the Scan:", "Result:"):
        assert heading in out
    assert "Results identical: yes" in out


@pytest.mark.parametrize("flag, heading", [("--tokens", "Tokens:"), ("--ast", "AST:"), ("--schema", "Symbol Table:"),
                                           ("--plan", "Logical Plan:"), ("--optimized-plan", "Optimized Plan:")])
def test_cli_single_stage_flags(capsys, students_csv, flag, heading):
    _, out, _ = run_cli(capsys, "--file", students_csv, "--query", MAIN_QUERY, flag)
    assert heading in out
    assert sum(h in out for h in ("Tokens:", "AST:", "Symbol Table:", "Logical Plan:", "Optimized Plan:")) == 1


def test_cli_works_with_json(capsys, students_json):
    code, out, _ = run_cli(capsys, "--file", students_json, "--query", 'SELECT name FROM "students.json" WHERE age >= 28 ORDER BY age')
    assert code == 0 and out.split() == ["name", "------", "Meera", "Vihaan", "(2", "rows)"]


@pytest.mark.parametrize("query, message", [
    ('SELECT name "students.csv"', "Syntax Error: Expected FROM after SELECT column list"),
    ('SELECT name, salary FROM "students.csv"', "Semantic Error: Column 'salary' does not exist."),
    ('SELECT name FROM "students.csv" WHERE age > "hello"', "Type Error: Cannot compare NUMBER column 'age' with TEXT value 'hello'"),
    ('SELECT @ FROM "students.csv"', "Lexical Error: Unexpected character '@'"),
    ('SELECT a FROM "missing.csv"', "Execution Error: Unable to read file 'missing.csv'"),
])
def test_cli_errors_use_exit_code_2_and_name_the_phase(capsys, students_csv, query, message):
    code, out, err = run_cli(capsys, "--file", students_csv, "--query", query)
    assert code == 2 and out == "" and message in err


def test_cli_error_points_at_the_problem(capsys, students_csv):
    _, _, err = run_cli(capsys, "--file", students_csv, "--query", 'SELECT name "students.csv"')
    lines = err.splitlines()
    assert lines[1].strip() == 'SELECT name "students.csv"' and lines[2].index("^") == lines[1].index('"')


def test_cli_shows_finished_stages_before_an_error(capsys, students_csv):
    code, out, err = run_cli(capsys, "--file", students_csv, "--query", 'SELECT name, salary FROM "students.csv"', "--all")
    assert code == 2 and "Tokens:" in out and "Symbol Table:" in out and "Logical Plan:" not in out
    assert "Semantic Error" in err


def test_cli_without_query_is_a_usage_error(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main([])
    assert info.value.code == 2


def test_cli_zero_row_result_still_prints_the_header(capsys, students_csv):
    _, out, _ = run_cli(capsys, "--file", students_csv, "--query", 'SELECT name, age FROM "students.csv" WHERE age > 99')
    assert out.splitlines()[0].split() == ["name", "age"] and "(0 rows)" in out


def test_demo_runs_cleanly_and_covers_all_five_demonstrations(capsys):
    code, out, err = run_cli(capsys, "--demo")
    assert code == 0 and err == ""
    for marker in ("DEMO 1 ", "DEMO 2", "DEMO 3", "DEMO 4", "DEMO 5", "Syntax Error:", "Semantic Error:", "Type Error:",
                   "Results identical: yes", "Scan students.csv  (predicate: age > 20; columns: name, age)"):
        assert marker in out
    assert "Traceback" not in out


def test_module_entry_point(students_csv):
    import subprocess, sys
    done = subprocess.run([sys.executable, "-m", "liteql", "--file", students_csv, "--query", MAIN_QUERY],
                          capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert done.returncode == 0 and "Vihaan" in done.stdout

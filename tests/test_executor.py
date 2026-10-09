"""Phase 5: the executor runs plans against CSV and JSON data."""

import pytest

from liteql import compile_query
from liteql.ast import Column, Comparison, NumberLiteral
from liteql.executor import ExecutionStats, execute
from liteql.logical_plan import Filter, Limit, Project, Scan, Sort

from conftest import MAIN_QUERY, rows_of


def names(rows, key="name"):
    return [row[key] for row in rows]


# --- one operator at a time ----------------------------------------------------

def test_scan_returns_every_row_with_typed_values(students_csv):
    rows = execute(Scan(students_csv))
    assert len(rows) == 8 and rows[0] == {"name": "Aarav", "age": 19, "city": "Delhi"}


def test_scan_with_columns_and_predicate(students_csv):
    predicate = Comparison(Column("age"), ">", NumberLiteral(26))
    rows = execute(Scan(students_csv, ("name", "age"), predicate))
    assert rows == [{"name": "Meera", "age": 28}, {"name": "Vihaan", "age": 31}]


def test_filter(students_csv):
    condition = Comparison(Column("age"), "<", NumberLiteral(21))
    assert names(execute(Filter(Scan(students_csv), condition))) == ["Aarav", "Sara"]


def test_project_keeps_requested_order(students_csv):
    rows = execute(Project(Scan(students_csv), ("city", "name")))
    assert list(rows[0]) == ["city", "name"]


def test_sort_ascending_and_descending(students_csv):
    asc = execute(Sort(Scan(students_csv), "age", "ASC"))
    desc = execute(Sort(Scan(students_csv), "age", "DESC"))
    assert [r["age"] for r in asc] == [19, 20, 21, 22, 24, 26, 28, 31]
    assert [r["age"] for r in desc] == [31, 28, 26, 24, 22, 21, 20, 19]


def test_sort_text_column(students_csv):
    assert names(execute(Sort(Scan(students_csv), "name", "ASC")))[:3] == ["Aarav", "Arjun", "Diya"]


def test_limit(students_csv):
    assert len(execute(Limit(Scan(students_csv), 3))) == 3
    assert execute(Limit(Scan(students_csv), 0)) == []
    assert len(execute(Limit(Scan(students_csv), 100))) == 8


def test_stats_are_recorded(students_csv):
    stats = ExecutionStats()
    execute(Limit(Scan(students_csv), 2), stats)
    assert (stats.rows_scanned, stats.rows_from_scan, stats.cells_from_scan, stats.rows_returned) == (8, 8, 24, 2)


# --- whole queries --------------------------------------------------------------

def test_main_query_exact_result(students_csv):
    assert rows_of(MAIN_QUERY, students_csv) == [
        {"name": "Vihaan", "age": 31}, {"name": "Meera", "age": 28}, {"name": "Arjun", "age": 26},
        {"name": "Diya", "age": 24}, {"name": "Kabir", "age": 22},
    ]


def test_same_query_on_json_gives_same_rows(students_csv, students_json):
    assert rows_of(MAIN_QUERY, students_json) == rows_of(MAIN_QUERY, students_csv)


def test_result_is_deterministic(students_csv):
    assert rows_of(MAIN_QUERY, students_csv) == rows_of(MAIN_QUERY, students_csv)


def test_select_star_returns_all_columns_in_file_order(students_csv):
    rows = rows_of('SELECT * FROM "students.csv" WHERE city = "Pune"', students_csv)
    assert rows == [{"name": "Kabir", "age": 22, "city": "Pune"}, {"name": "Vihaan", "age": 31, "city": "Pune"}]


def test_order_by_a_column_that_is_not_selected_still_sorts(students_csv):
    assert rows_of('SELECT name FROM "students.csv" ORDER BY age DESC LIMIT 3', students_csv) == [
        {"name": "Vihaan"}, {"name": "Meera"}, {"name": "Arjun"}]


def test_where_on_a_column_that_is_not_selected(students_csv):
    assert names(rows_of('SELECT name FROM "students.csv" WHERE age > 28', students_csv)) == ["Vihaan"]


@pytest.mark.parametrize("op, expected", [
    ("=", ["Kabir"]), ("!=", ["Aarav", "Diya", "Meera", "Riya", "Arjun", "Sara", "Vihaan"]),
    (">", ["Diya", "Meera", "Arjun", "Vihaan"]), (">=", ["Diya", "Kabir", "Meera", "Arjun", "Vihaan"]),
    ("<", ["Aarav", "Riya", "Sara"]), ("<=", ["Aarav", "Kabir", "Riya", "Sara"]),
])
def test_each_comparison_operator(students_csv, op, expected):
    assert names(rows_of(f'SELECT name FROM "students.csv" WHERE age {op} 22', students_csv)) == expected


def test_and_binds_tighter_than_or(students_csv):
    # SQL grouping: age < 20 OR (age > 25 AND city = 'Pune')  -> Aarav, Vihaan
    # (strict left-to-right would give (age < 20 OR age > 25) AND city = 'Pune' -> Vihaan only)
    q = 'SELECT name FROM "students.csv" WHERE age < 20 OR age > 25 AND city = "Pune"'
    assert names(rows_of(q, students_csv)) == ["Aarav", "Vihaan"]
    q = 'SELECT name FROM "students.csv" WHERE city = "Pune" AND age > 25 OR age < 20'
    assert names(rows_of(q, students_csv)) == ["Aarav", "Vihaan"]


def test_column_to_column_comparison(write_file):
    path = write_file("c.csv", "a,b\n1,2\n5,3\n4,4\n")
    assert rows_of("SELECT a FROM c.csv WHERE a >= b", path) == [{"a": 5}, {"a": 4}]


def test_text_comparisons_are_case_sensitive(students_csv):
    assert rows_of('SELECT name FROM "students.csv" WHERE city = "delhi"', students_csv) == []
    assert names(rows_of('SELECT name FROM "students.csv" WHERE name < "B"', students_csv)) == ["Aarav", "Arjun"]


def test_no_matching_rows(students_csv):
    assert rows_of('SELECT name FROM "students.csv" WHERE age > 1000', students_csv) == []


def test_negative_and_decimal_literals(write_file):
    path = write_file("n.csv", "v\n-5\n-0.5\n0\n2.25\n")
    assert [r["v"] for r in rows_of("SELECT v FROM n.csv WHERE v > -1 ORDER BY v", path)] == [-0.5, 0, 2.25]


# --- messy data -----------------------------------------------------------------

def test_missing_values_never_match_and_never_crash(titanic_csv):
    all_rows = rows_of("SELECT Age FROM titanic.csv", titanic_csv)
    missing = [r for r in all_rows if r["Age"] is None]
    assert missing, "the sample file is meant to contain blank ages"
    kept = rows_of("SELECT Age FROM titanic.csv WHERE Age > 0", titanic_csv)
    assert len(kept) == len(all_rows) - len(missing)
    # even != is false for a missing value, so  = and != do not cover every row
    eq = rows_of("SELECT Age FROM titanic.csv WHERE Age = 30", titanic_csv)
    ne = rows_of("SELECT Age FROM titanic.csv WHERE Age != 30", titanic_csv)
    assert len(eq) + len(ne) == len(all_rows) - len(missing)


def test_order_by_puts_missing_values_last_in_both_directions(titanic_csv):
    for direction in ("ASC", "DESC"):
        ages = [r["Age"] for r in rows_of(f"SELECT Age FROM titanic.csv ORDER BY Age {direction}", titanic_csv)]
        first_missing = ages.index(None)
        assert all(a is None for a in ages[first_missing:])
        present = ages[:first_missing]
        assert present == sorted(present, reverse=direction == "DESC")


def test_sort_is_stable_for_ties(students_csv):
    # people in the same city keep their file order, in both directions
    asc = rows_of('SELECT name FROM "students.csv" ORDER BY city', students_csv)
    assert names(asc) == ["Meera", "Riya", "Aarav", "Arjun", "Diya", "Sara", "Kabir", "Vihaan"]
    desc = rows_of('SELECT name FROM "students.csv" ORDER BY city DESC', students_csv)
    assert names(desc) == ["Kabir", "Vihaan", "Diya", "Sara", "Aarav", "Arjun", "Riya", "Meera"]


def test_json_with_missing_keys_and_mixed_types(write_file):
    path = write_file("m.json", '[{"n": "a", "v": 3}, {"n": "b"}, {"n": "c", "v": 1}, {"n": "d", "v": null}]')
    assert names(rows_of("SELECT n FROM m.json WHERE v >= 1 ORDER BY v", path), "n") == ["c", "a"]
    assert names(rows_of("SELECT n FROM m.json ORDER BY v DESC", path), "n") == ["a", "c", "b", "d"]


def test_executor_reads_file_only_after_compilation_succeeds(students_csv, monkeypatch):
    from liteql.data_source import DataSource
    calls = []
    original = DataSource.scan
    monkeypatch.setattr(DataSource, "scan", lambda self, *a, **k: calls.append(1) or original(self, *a, **k))
    compilation = compile_query(MAIN_QUERY, students_csv)
    assert calls == []                      # compiling scans nothing
    compilation.run()
    assert calls == [1]

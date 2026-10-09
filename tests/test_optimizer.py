"""Phase 4: predicate pushdown and projection pushdown - and proof they change nothing."""

import itertools

import pytest

from liteql import compile_query
from liteql.logical_plan import Filter, Scan
from liteql.printer import format_plan

from conftest import MAIN_QUERY, rows_of


def scan_of(plan):
    while not isinstance(plan, Scan):
        plan = plan.child
    return plan


def optimized_scan(query, path):
    return scan_of(compile_query(query, path).optimized_plan)


def has_filter(plan):
    while not isinstance(plan, Scan):
        if isinstance(plan, Filter):
            return True
        plan = plan.child
    return False


# --- predicate pushdown --------------------------------------------------------

def test_predicate_moves_into_scan(students_csv):
    result = compile_query(MAIN_QUERY, students_csv)
    assert has_filter(result.plan) and not has_filter(result.optimized_plan)
    filter_node = result.plan.child.child.child
    assert scan_of(result.optimized_plan).predicate == filter_node.condition


def test_printed_plan_shows_the_filter_happening_in_the_scan(students_csv):
    text = format_plan(compile_query(MAIN_QUERY, students_csv).optimized_plan)
    assert text == "\n".join([
        "Limit 5",
        "  Sort age DESC",
        "    Project name, age",
        "      Scan students.csv  (predicate: age > 20; columns: name, age)",
    ])


def test_no_where_means_no_predicate(students_csv):
    assert optimized_scan('SELECT name FROM "students.csv"', students_csv).predicate is None


def test_compound_predicate_moves_as_a_whole(students_csv):
    scan = optimized_scan('SELECT name FROM "students.csv" WHERE age > 20 AND city = "Delhi" OR age < 20', students_csv)
    assert scan.predicate is not None


def test_limit_stays_above_the_scan_filter_is_never_moved_below_it(students_csv):
    plan = compile_query('SELECT name FROM "students.csv" WHERE age > 20 LIMIT 2', students_csv).optimized_plan
    assert type(plan).__name__ == "Limit"


# --- projection pushdown -------------------------------------------------------

def test_main_query_reads_only_name_and_age(students_csv):
    assert optimized_scan(MAIN_QUERY, students_csv).columns == ("name", "age")


def test_city_is_never_read_when_not_needed(students_csv):
    assert "city" not in optimized_scan(MAIN_QUERY, students_csv).columns


def test_where_column_is_kept_even_though_it_is_not_selected(students_csv):
    scan = optimized_scan('SELECT name FROM "students.csv" WHERE age > 20', students_csv)
    assert set(scan.columns) == {"name", "age"}


def test_order_by_column_is_kept_even_though_it_is_not_selected(students_csv):
    scan = optimized_scan('SELECT name FROM "students.csv" ORDER BY age', students_csv)
    assert set(scan.columns) == {"name", "age"}


def test_both_sides_of_a_column_comparison_are_kept(titanic_csv):
    scan = optimized_scan("SELECT Name FROM titanic.csv WHERE SibSp > Parch", titanic_csv)
    assert set(scan.columns) == {"Name", "SibSp", "Parch"}


def test_all_clauses_columns_are_unioned(titanic_csv):
    scan = optimized_scan("SELECT Name FROM titanic.csv WHERE Age > 1 AND Sex = 'male' ORDER BY Fare", titanic_csv)
    assert scan.columns == ("Name", "Age", "Sex", "Fare")


def test_select_star_needs_every_column(students_csv):
    assert optimized_scan('SELECT * FROM "students.csv" WHERE age > 20 ORDER BY age', students_csv).columns is None


def test_optimizer_notes_are_recorded(students_csv):
    notes = compile_query(MAIN_QUERY, students_csv).optimizations
    assert any(n.startswith("Predicate pushdown") for n in notes)
    assert any("name, age" in n for n in notes)


# --- the optimizer must never change the result ----------------------------------

QUERIES = [
    MAIN_QUERY,
    'SELECT * FROM "students.csv"',
    'SELECT * FROM "students.csv" WHERE age > 20 ORDER BY age DESC',
    'SELECT name FROM "students.csv" WHERE age > 20',
    'SELECT name FROM "students.csv" ORDER BY age DESC LIMIT 3',
    'SELECT city FROM "students.csv" WHERE city != "Delhi" ORDER BY name',
    'SELECT name, city FROM "students.csv" WHERE age > 20 AND city = "Mumbai" OR age < 20',
    'SELECT name FROM "students.csv" WHERE age >= 100',
    'SELECT name FROM "students.csv" LIMIT 0',
    "SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' order by age desc limit 10",
    "SELECT Name, Fare FROM titanic.csv WHERE Age > 30 ORDER BY Fare",
    "SELECT Name FROM titanic.csv WHERE Cabin = 'C85' OR Embarked = 'Q' ORDER BY Age DESC LIMIT 4",
    "SELECT Name FROM titanic.csv WHERE SibSp >= Parch ORDER BY Name",
]


@pytest.mark.parametrize("query", QUERIES)
def test_optimized_result_equals_unoptimized_result(query):
    assert rows_of(query, optimized=True) == rows_of(query, optimized=False)


def test_exhaustive_equivalence_over_generated_queries(titanic_csv):
    """Every combination of select list x filter x order x limit gives identical results."""
    selects = ["*", "Name", "Name, Age", "Fare, Name", "Age"]
    wheres = ["", "WHERE Age > 30", "WHERE Sex = 'female' AND Age <= 25", "WHERE Pclass = 1 OR Fare < 10",
              "WHERE Age != 22 AND Pclass >= 2 OR Sex = 'male'", "WHERE SibSp > Parch", "WHERE Cabin = 'C85'"]
    orders = ["", "ORDER BY Age", "ORDER BY Fare DESC", "ORDER BY Name ASC", "ORDER BY Cabin DESC"]
    limits = ["", "LIMIT 3", "LIMIT 0", "LIMIT 1000"]
    count = 0
    for select, where, order, limit in itertools.product(selects, wheres, orders, limits):
        query = f"SELECT {select} FROM titanic.csv {where} {order} {limit}"
        assert rows_of(query, titanic_csv, True) == rows_of(query, titanic_csv, False), query
        count += 1
    assert count == 5 * 7 * 5 * 4


def test_optimization_reduces_scan_work_without_changing_rows(students_csv):
    compilation = compile_query(MAIN_QUERY, students_csv)
    rows_before, before = compilation.run(optimized=False)
    rows_after, after = compilation.run(optimized=True)
    assert rows_before == rows_after
    assert after.rows_scanned == before.rows_scanned == 8      # the file is read either way
    assert after.rows_from_scan < before.rows_from_scan        # but fewer rows leave the Scan
    assert after.cells_from_scan < before.cells_from_scan      # and fewer fields per row
    assert (before.rows_from_scan, before.cells_from_scan) == (8, 24)
    assert (after.rows_from_scan, after.cells_from_scan) == (6, 12)


# --- each optimization is correct on its own ---------------------------------------

def test_projection_pushdown_alone_keeps_where_columns(students_csv):
    """Run projection pushdown on a plan whose Filter has NOT been pushed into the Scan."""
    from liteql.optimizer import push_predicate, push_projection
    plan = compile_query('SELECT name FROM "students.csv" WHERE age > 20 ORDER BY city', students_csv).plan
    only_projection = push_projection(plan, [])
    assert has_filter(only_projection)                                   # predicate pushdown did not run
    assert scan_of(only_projection).columns == ("name", "age", "city")


def test_predicate_pushdown_alone_leaves_columns_unrestricted(students_csv):
    from liteql.optimizer import push_predicate
    plan = compile_query(MAIN_QUERY, students_csv).plan
    only_predicate = push_predicate(plan, [])
    assert scan_of(only_predicate).columns is None and scan_of(only_predicate).predicate is not None
    from liteql.executor import execute
    assert execute(only_predicate) == execute(plan)

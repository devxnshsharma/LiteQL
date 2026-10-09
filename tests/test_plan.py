"""The logical plan (LiteQL's intermediate representation)."""

from liteql import compile_query
from liteql.logical_plan import Filter, Limit, Project, Scan, Sort
from liteql.printer import format_plan

from conftest import MAIN_QUERY


def shape(plan):
    names = []
    while True:
        names.append(type(plan).__name__)
        if isinstance(plan, Scan):
            return names
        plan = plan.child


def test_main_query_plan_matches_the_report(students_csv):
    plan = compile_query(MAIN_QUERY, students_csv).plan
    assert shape(plan) == ["Limit", "Sort", "Project", "Filter", "Scan"]
    assert format_plan(plan) == "\n".join([
        "Limit 5",
        "  Sort age DESC",
        "    Project name, age",
        "      Filter age > 20",
        "        Scan students.csv",
    ])


def test_fresh_plan_has_nothing_pushed_into_scan(students_csv):
    scan = compile_query(MAIN_QUERY, students_csv).plan.child.child.child.child
    assert scan.columns is None and scan.predicate is None


def test_minimal_query_is_project_over_scan(students_csv):
    assert shape(compile_query('SELECT name FROM "students.csv"', students_csv).plan) == ["Project", "Scan"]


def test_select_star_has_no_project(students_csv):
    plan = compile_query('SELECT * FROM "students.csv" WHERE age > 1', students_csv).plan
    assert shape(plan) == ["Filter", "Scan"]


def test_each_clause_adds_exactly_its_operator(students_csv):
    assert shape(compile_query('SELECT name FROM "students.csv" LIMIT 2', students_csv).plan) == ["Limit", "Project", "Scan"]
    assert shape(compile_query('SELECT name FROM "students.csv" ORDER BY name', students_csv).plan) == ["Sort", "Project", "Scan"]


def test_sort_goes_below_project_when_order_column_is_not_selected(students_csv):
    plan = compile_query('SELECT name FROM "students.csv" ORDER BY age LIMIT 3', students_csv).plan
    assert shape(plan) == ["Limit", "Project", "Sort", "Scan"]


def test_plan_nodes_are_immutable_so_the_original_survives_optimization(students_csv):
    result = compile_query(MAIN_QUERY, students_csv)
    assert isinstance(result.plan.child.child.child, Filter)       # still unoptimized
    assert result.plan != result.optimized_plan


def test_plan_uses_the_resolved_file(students_csv):
    result = compile_query(MAIN_QUERY, students_csv)
    scan = result.plan
    while not isinstance(scan, Scan):
        scan = scan.child
    assert scan.source == students_csv

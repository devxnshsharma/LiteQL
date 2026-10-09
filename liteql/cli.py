"""Command-line interface.

    python -m liteql.cli --query 'SELECT ...' [--file data.csv] [--tokens --ast --schema --plan
                                               --optimized-plan --stats | --all]
    python -m liteql.cli --demo

With no stage flag only the result is printed. Stage flags reveal the
intermediate representation of each compiler phase.
"""

from __future__ import annotations

import argparse
import sys

from .compiler import Compilation, compile_query
from .errors import LiteQLError
from .data_source import EXAMPLES_DIR
from .printer import format_ast, format_plan, format_table, format_tokens

MAIN_QUERY = 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'
ALL_STAGES = ("tokens", "ast", "schema", "plan", "optimized", "stats")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m liteql.cli",
        description="LiteQL - a small SQL-like compiler for CSV and JSON files")
    parser.add_argument("--query", help="the LiteQL query to compile and run")
    parser.add_argument("--file", help="data file; the FROM name is also looked up in this file's folder")
    parser.add_argument("--tokens", action="store_true", help="show the token stream")
    parser.add_argument("--ast", action="store_true", help="show the abstract syntax tree")
    parser.add_argument("--schema", action="store_true", help="show the symbol table")
    parser.add_argument("--plan", action="store_true", help="show the unoptimized logical plan")
    parser.add_argument("--optimized-plan", action="store_true", help="show the optimized logical plan")
    parser.add_argument("--stats", action="store_true", help="compare rows/fields processed with and without optimization")
    parser.add_argument("--all", action="store_true", help="show every stage")
    parser.add_argument("--demo", action="store_true", help="run the full demonstration")
    args = parser.parse_args(argv)

    if args.demo:
        return demo()
    if not args.query:
        parser.error("provide --query, or use --demo")

    wanted = set(ALL_STAGES) if args.all else {
        stage for stage, flag in (("tokens", args.tokens), ("ast", args.ast), ("schema", args.schema),
                                  ("plan", args.plan), ("optimized", args.optimized_plan),
                                  ("stats", args.stats)) if flag}
    return run(args.query, args.file, wanted, sys.stdout, sys.stderr)


def run(query: str, file_path: str | None, wanted: set, out, err, echo: bool = False) -> int:
    """Compile and execute one query, printing the requested stages. Returns the exit code."""
    if wanted or echo:
        print("Query:\n" + query, file=out)
    try:
        compilation = compile_query(query, file_path)
    except LiteQLError as error:
        if error.compilation is not None:
            show_stages(error.compilation, wanted, out)      # whatever finished before the error
        report_error(error, query, err)
        return 2
    show_stages(compilation, wanted, out)
    try:
        rows, _ = compilation.run()
    except LiteQLError as error:
        report_error(error, query, err)
        return 2
    print(("\nResult:\n" if wanted or echo else "") + format_table(rows, compilation.output_columns), file=out)
    return 0


def show_stages(c: Compilation, wanted: set, out) -> None:
    def section(title, body):
        print(f"\n{title}:\n{body}", file=out)

    if "tokens" in wanted and c.tokens:
        section("Tokens", format_tokens(c.tokens))
    if "ast" in wanted and c.ast:
        section("AST", format_ast(c.ast))
    if "schema" in wanted and c.schema:
        section("Symbol Table", str(c.schema))
    if "plan" in wanted and c.plan:
        section("Logical Plan", format_plan(c.plan))
    if "optimized" in wanted and c.optimized_plan:
        notes = "\n".join("  * " + note for note in c.optimizations)
        section("Optimized Plan", format_plan(c.optimized_plan) + "\n\nOptimizer notes:\n" + notes)
    if "stats" in wanted and c.optimized_plan:
        section("Work done by the Scan", format_stats(c))


def format_stats(c: Compilation) -> str:
    """Compare unoptimized and optimized execution (no invented percentages)."""
    rows_before, before = c.run(optimized=False)
    rows_after, after = c.run(optimized=True)
    lines = [
        f"{'':34}{'unoptimized':>12}{'optimized':>12}",
        f"{'rows read from file':34}{before.rows_scanned:>12}{after.rows_scanned:>12}",
        f"{'rows passed up by Scan':34}{before.rows_from_scan:>12}{after.rows_from_scan:>12}",
        f"{'fields passed up by Scan':34}{before.cells_from_scan:>12}{after.cells_from_scan:>12}",
        f"{'rows in final result':34}{before.rows_returned:>12}{after.rows_returned:>12}",
        "Results identical: " + ("yes" if rows_before == rows_after else "NO - optimizer bug!"),
    ]
    return "\n".join(lines)


def report_error(error: LiteQLError, query: str, out) -> None:
    """Print the error; for lexical/syntax errors also point at the offending spot."""
    print(error, file=out)
    if error.position is not None:
        start = query.rfind("\n", 0, error.position) + 1
        end = query.find("\n", error.position)
        line = query[start:end if end != -1 else len(query)]
        print("  " + line, file=out)
        print("  " + " " * (error.position - start) + "^", file=out)


# --- demonstration ------------------------------------------------------------------

def demo() -> int:
    """Walk through the five demonstrations from the project plan."""
    def title(text):
        print("\n" + "=" * 72 + f"\n{text}\n" + "=" * 72)

    everything = set(ALL_STAGES) - {"stats"}
    students = str(EXAMPLES_DIR / "students.csv")

    title("DEMO 1 - A valid query through every compiler phase")
    run(MAIN_QUERY, students, everything, sys.stdout, sys.stdout)

    title("DEMO 1b - The same idea on a JSON file, and with a bare file name")
    run('SELECT name, city FROM "students.json" WHERE city = "Delhi" OR age >= 28 ORDER BY name',
        str(EXAMPLES_DIR / "students.json"), {"ast"}, sys.stdout, sys.stdout)
    print()
    run("SELECT name, sex, age FROM titanic.csv WHERE age > 30 AND sex = 'female' ORDER BY age DESC LIMIT 3",
        None, set(), sys.stdout, sys.stdout, echo=True)

    title("DEMO 2 - Syntax error: caught by the parser (tokens exist, but the structure is wrong)")
    run('SELECT name, age "students.csv"', students, {"tokens"}, sys.stdout, sys.stdout)

    title("DEMO 3 - Missing column: grammatical, but caught by semantic analysis before execution")
    run('SELECT name, salary FROM "students.csv"', students, {"ast", "schema"}, sys.stdout, sys.stdout)

    title("DEMO 4 - Type error: age is NUMBER, 'hello' is TEXT")
    run('SELECT name FROM "students.csv" WHERE age > "hello"', students, {"schema"}, sys.stdout, sys.stdout)

    title("DEMO 5 - Optimization: before vs after")
    run(MAIN_QUERY, students, {"plan", "optimized", "stats"}, sys.stdout, sys.stdout)
    print("\nPredicate pushdown : the WHERE test moved into Scan, so rows are rejected while reading.")
    print("Projection pushdown: Scan reads only name and age (age is needed for WHERE and ORDER BY too).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

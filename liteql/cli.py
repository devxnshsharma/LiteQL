import argparse
from pathlib import Path

from .compiler import compile_query
from .errors import LiteQLError
from .executor import execute
from .printer import format_ast, format_plan

MAIN_QUERY = 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'


def main():
    parser = argparse.ArgumentParser(description="LiteQL small SQL-like compiler")
    parser.add_argument("--file", help="CSV or JSON data file (overrides FROM text)")
    parser.add_argument("--query", help="LiteQL query")
    parser.add_argument("--tokens", action="store_true"); parser.add_argument("--ast", action="store_true")
    parser.add_argument("--schema", action="store_true"); parser.add_argument("--plan", action="store_true")
    parser.add_argument("--optimized-plan", action="store_true"); parser.add_argument("--all", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo: return demo()
    if not args.query: parser.error("provide --query or use --demo")
    show(args.query, args.file, args)


def show(query, file_path, args):
    try:
        result = compile_query(query, file_path)
        all_stages = args.all or not any((args.tokens, args.ast, args.schema, args.plan, args.optimized_plan))
        print("Query:\n" + query)
        if args.tokens or all_stages: print("\nTokens:\n" + "\n".join(map(str, result.tokens)))
        if args.ast or all_stages: print("\nAST:\n" + format_ast(result.ast))
        if args.schema or all_stages: print("\nSymbol Table:\n" + str(result.schema))
        if args.plan or all_stages: print("\nLogical Plan:\n" + format_plan(result.plan))
        if args.optimized_plan or all_stages: print("\nOptimized Plan:\n" + format_plan(result.optimized_plan))
        print("\nResult:")
        for row in execute(result.optimized_plan): print(row)
    except LiteQLError as error: print(error); return 2
    return 0


def demo():
    root = Path(__file__).resolve().parent.parent
    print("=== LiteQL valid query demonstration ===")
    show(MAIN_QUERY, str(root / "examples" / "students.csv"), argparse.Namespace(tokens=False, ast=False, schema=False, plan=False, optimized_plan=False, all=True))
    for title, query in (("Syntax error", 'SELECT name "students.csv"'), ("Missing column", 'SELECT name, salary FROM "students.csv"'), ("Type error", 'SELECT name FROM "students.csv" WHERE age > "hello"')):
        print(f"\n=== {title} ===")
        show(query, str(root / "examples" / "students.csv"), argparse.Namespace(tokens=False, ast=False, schema=False, plan=False, optimized_plan=False, all=False))


if __name__ == "__main__": main()

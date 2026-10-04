# LiteQL

LiteQL is a small SQL-like compiler for querying one CSV or JSON file. It is a Compiler Design mini-project for BCSE307L by Shivaansh Aggarwal and Devansh Sharma under Dr. R Banupriya. It deliberately demonstrates compilation stages instead of trying to be a database system.

## What it does

LiteQL accepts `SELECT`, `FROM`, `WHERE`, `AND`, `OR`, comparison operators, `ORDER BY`, and `LIMIT`. It supports named columns and `SELECT *` on CSV files or a JSON top-level array of objects. Unsupported by design: joins, aggregates, grouping, subqueries, writes, functions, and arithmetic expressions.

## Compiler pipeline

`Query -> Lexer -> Tokens -> Recursive-descent parser -> AST -> Semantic analysis and symbol table -> Logical plan -> Optimizer -> Executor -> Results`

The semantic phase checks every referenced column and infers basic `NUMBER` or `TEXT` types. A valid parse can therefore still fail before execution. The logical plan is the intermediate representation and has `Scan`, `Filter`, `Project`, `Sort`, and `Limit` nodes.

The optimizer applies exactly two rules: predicate pushdown places the condition on `Scan`; projection pushdown reads all and only columns needed by SELECT, WHERE, and ORDER BY. Tests verify the optimized and unoptimized plans return the same rows.

## Install and run

Python 3.10+ is sufficient for the compiler. Install tests with:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Main demonstration:

```bash
python -m liteql.cli --demo
```

Run the main example with all representations:

```bash
python -m liteql.cli --file examples/students.csv --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5' --all
```

JSON example:

```bash
python -m liteql.cli --file examples/students.json --query 'SELECT name FROM "students.json" WHERE age >= 28 ORDER BY age ASC'
```

Error demonstrations:

```bash
python -m liteql.cli --file examples/students.csv --query 'SELECT name "students.csv"'
python -m liteql.cli --file examples/students.csv --query 'SELECT name, salary FROM "students.csv"'
python -m liteql.cli --file examples/students.csv --query 'SELECT name FROM "students.csv" WHERE age > "hello"'
```

## Assumptions and limitations

Quoted strings use either quote character without escapes. JSON must be an array of objects. CSV values are displayed as their source text, while numeric comparison and sorting convert them internally. The grammar does not define `AND`/`OR` precedence, so LiteQL evaluates mixed chains left-to-right. It is an educational compiler demonstration, not a replacement for SQL engines such as DuckDB.

## Viva notes

- It is a compiler project because each query becomes tokens, an AST, a checked symbol table, a logical-plan IR, an optimized plan, then results.
- The lexer labels character sequences; the parser checks their grammatical structure.
- The AST preserves query structure; the symbol table maps file columns to inferred types.
- Predicate pushdown rejects rows at scan time; projection pushdown limits fields read while preserving fields required for filtering and sorting.

# LiteQL: Small SQL-Like Compiler for CSV and JSON Files

**BCSE307L Compiler Design mini-project**  
* **Authors:** Devansh Sharma, Shivaansh Aggarwal
* **Faculty:** Dr. R Banupriya  

LiteQL is a small SQL-like compiler for querying one CSV or JSON file. It is a Compiler Design mini-project that deliberately demonstrates compilation stages instead of trying to be a database system.

LiteQL treats a query as *source code*. Instead of running the text straight away, it tokenizes it, parses it, checks it against the real data file, builds an intermediate plan, optimizes the plan, and only then executes it. An invalid query fails **before** any data row is read.



```
Query text → Lexer → Tokens → Parser → AST → Semantic analysis (symbol table + type check) → Logical plan (IR) → Optimizer → Optimized plan → Executor → Result
```

LiteQL is **not** a database and does not claim to be faster than one. It demonstrates how
classical compiler phases apply to a small, realistic problem.

---

## Contents
1. [Problem](#1-problem)
2. [Objectives](#2-objectives)
3. [Scope](#3-scope)
4. [Architecture](#4-architecture) 
5. [Grammar](#5-grammar)
6. [Compiler phases](#6-compiler-phases)
7. [Install](#7-install) 
8. [Run](#8-run) 
9. [Tests](#9-tests)
10. [Demo](#10-demo-commands)
11. [Example queries](#11-example-queries) 
12. [Design decisions](#12-design-decisions-and-assumptions)
13. [Limitations](#13-limitations) 
14. [Future extensions](#14-future-extensions)
15. [Literature context](#15-literature-context)

---

## 1. Problem
To filter or sort a CSV/JSON file you normally learn a data library or hand-write loops.
That allows mistakes — a column that does not exist, a number compared with text, a
malformed query — that only show up when the program runs, sometimes after it has already
read part of the file. LiteQL catches them first.

## 2. Objectives
Build a small SQL-like language and a working compiler for it, with an explicit
lexer, recursive-descent parser, AST, semantic analyzer with symbol table and type checking,
logical-plan IR, two optimizations, and an executor, such that every phase is visible and
inspectable from the command line.

## 3. Scope

| Supported | Not supported (intentionally) |
|---|---|
| One CSV or JSON file per query | joins, multiple files, subqueries, CTEs |
| `SELECT` (names or `*`), `FROM`, `WHERE`, `ORDER BY` (`ASC`/`DESC`), `LIMIT` | `COUNT/SUM/AVG`, `GROUP BY`, `HAVING`, window functions |
| `AND`, `OR`; `=  !=  >  <  >=  <=` | arithmetic expressions, string functions, parentheses, `LIKE`, `IN`, `NOT` |
| Column-to-value and column-to-column comparisons | `INSERT/UPDATE/DELETE`, transactions, indexes |
| NUMBER and TEXT types | dates, booleans, NULL literals |
| Predicate pushdown, projection pushdown | any other optimization |

## 4. Architecture

| Phase | Module | Input → Output | Fails with |
|---|---|---|---|
| Lexical analysis | `lexer.py`, `tokens.py` | text → tokens | `LexicalError` |
| Syntax analysis | `parser.py`, `ast.py` | tokens → AST | `SyntaxError` |
| Schema inference | `schema.py`, `data_source.py` | data file → symbol table | `ExecutionError` |
| Semantic analysis + type checking | `semantic.py` | AST + symbol table → checked AST | `SemanticError`, `TypeError` |
| IR construction | `logical_plan.py` | checked AST → logical plan | — |
| Optimization | `optimizer.py` | plan → optimized plan | — |
| Execution | `executor.py` | plan + file → rows | `ExecutionError` |
| Driver / output | `compiler.py`, `printer.py`, `cli.py` | | |

`compiler.py` chains the phases and keeps every intermediate result. If a phase fails, the
error carries what had been produced so far, so the CLI can show e.g. the tokens of a query
that then failed to parse.

## 5. Grammar
```
query        ::= "SELECT" column_list "FROM" file [where_clause] [order_clause] [limit_clause] [";"]
column_list  ::= "*" | column ("," column)*
column       ::= IDENTIFIER
where_clause ::= "WHERE" condition
condition    ::= comparison (("AND" | "OR") comparison)*
comparison   ::= column OP value
OP           ::= "=" | "!=" | ">" | "<" | ">=" | "<="
order_clause ::= "ORDER" "BY" column ["ASC" | "DESC"]
limit_clause ::= "LIMIT" INTEGER
value        ::= STRING | NUMBER | column
file         ::= STRING | FILENAME          (extension — see §12)
```
Keywords are case-insensitive. Full notes (precedence, tokens) are in [docs/grammar.md](docs/grammar.md).

## 6. Compiler phases

**Lexer** (`lexer.py`) scans left to right and labels character groups: `age > 20` becomes
`IDENTIFIER(age) GREATER(>) NUMBER(20) EOF`. It knows nothing about files or types.

**Parser** (`parser.py`) is hand-written recursive descent — one method per grammar rule
(`parse_query`, `parse_column_list`, `parse_condition`, `parse_comparison`, `parse_order_clause`,
`parse_limit_clause`, `parse_value`). It checks token order and builds the AST. It never opens the file.

**AST** (`ast.py`) holds structure only — `Query`, `Column`, `Comparison`, `And`, `Or`,
`OrderBy`, `StringLiteral`, `NumberLiteral`, `ColumnReference`:
```
Query
├── Select: name, age
├── From: students.csv
├── Where
│   └── age > 20
├── Order By: age DESC
└── Limit: 5
```

**Schema inference / symbol table** (`schema.py`, `data_source.py`). The file is read to learn
its columns and infer `NUMBER` or `TEXT` for each from *all* of its non-blank values:
```
name -> TEXT
age  -> NUMBER
city -> TEXT
```

**Semantic analysis** (`semantic.py`) answers "does this grammatical query make sense for *this*
file?" — every column must exist (`Column 'score' does not exist. Available columns: name, age, city`),
`LIMIT` must be non-negative, and no column may be selected twice. This is why a syntactically
valid query can still be rejected: the parser checks *shape*, the semantic phase checks *meaning*.

**Type checking** is part of semantic analysis: both sides of every comparison must have the same
type. `age > "hello"` → `Type Error: Cannot compare NUMBER column 'age' with TEXT value 'hello'`.

**Logical plan / IR** (`logical_plan.py`). Five operators: `Scan, Filter, Project, Sort, Limit`.
```
Limit 5
  Sort age DESC
    Project name, age
      Filter age > 20
        Scan students.csv
```
It is an intermediate representation: simpler than the query, not yet a result, and easy to rewrite.
Nodes are immutable, so the plan before and after optimization can both be printed.

**Optimizer** (`optimizer.py`) — exactly two rewrites, and neither may change the result:

* *Predicate pushdown*: a `Filter` directly above `Scan` is merged into the `Scan`, so non-matching
  rows are rejected while the file is read.
* *Projection pushdown*: the `Scan` is told which columns the plan needs — the SELECT list **plus**
  the WHERE columns **plus** the ORDER BY column. `SELECT name … WHERE age > 20` therefore still reads
  `age`. `SELECT *` needs every column, so nothing is removed.

```
Limit 5
  Sort age DESC
    Project name, age
      Scan students.csv  (predicate: age > 20; columns: name, age)
```
No speed-up percentage is claimed. `--stats` instead *measures* the work done by the Scan
(rows and fields passed upward) for the unoptimized and optimized plans and checks the results are identical.

**Executor** (`executor.py`) interprets the plan recursively — each node runs its child, then applies
its operator. It is the only phase that reads data rows.

**Error handling** (`errors.py`). One class per phase, always printed with the phase name:
`LexicalError`, `SyntaxError`, `SemanticError`, `TypeError`, `ExecutionError` (all subclass `LiteQLError`).
Lexical and syntax errors also show the query with a `^` under the offending position.

---

## 7. Install
Needs Python 3.9 or newer. The compiler uses only the standard library; `pytest` is only for the tests.
```bash
cd LiteQL
python3 -m venv .venv && source .venv/bin/activate     # optional
python3 -m pip install -r requirements.txt
```

## 8. Run
```bash
python3 -m liteql.cli --file examples/students.csv --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'
```
| Flag | Shows |
|---|---|
| *(none)* | the result only |
| `--tokens` `--ast` `--schema` `--plan` `--optimized-plan` | that phase's output |
| `--stats` | rows/fields processed by the Scan, unoptimized vs optimized |
| `--all` | everything above |
| `--demo` | the complete guided demonstration |

`FROM` accepts a quoted name (`"students.csv"`) or a bare name (`students.csv`). The file is found by
trying: the name as written → the folder of `--file` → the `examples/` folder. Exit code is `0` on success, `2` on any LiteQL error.

## 9. Tests
```bash
python3 -m pytest
```
The suite has one file per phase plus end-to-end, CLI and robustness tests. Beyond example-based tests it
(a) runs 700 generated query combinations (select list × WHERE × ORDER BY × LIMIT) comparing optimized vs
unoptimized results, (b) compares 900 queries with an independent plain-Python implementation working on the raw CSV,
and (c) fuzzes about 8,600 random or corrupted queries to check that only clean `LiteQLError`s ever escape
(and that optimized = unoptimized whenever a query runs).

## 10. Demo commands
```bash
python3 -m liteql.cli --demo                                    # all five demonstrations

# Demo 1 – valid query, every stage
python3 -m liteql.cli --file examples/students.csv --all --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'

# Demo 2 – syntax error
python3 -m liteql.cli --file examples/students.csv --tokens --query 'SELECT name, age "students.csv"'

# Demo 3 – missing column (semantic error, before execution)
python3 -m liteql.cli --file examples/students.csv --schema --query 'SELECT name, salary FROM "students.csv"'

# Demo 4 – type error
python3 -m liteql.cli --file examples/students.csv --query 'SELECT name FROM "students.csv" WHERE age > "hello"'

# Demo 5 – before vs after optimization
python3 -m liteql.cli --file examples/students.csv --plan --optimized-plan --stats --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'
```
A talking-points script is in [docs/demo.md](docs/demo.md).

## 11. Example queries
`examples/valid_queries.txt` and `examples/invalid_queries.txt` (each invalid query is tagged with the phase
that must reject it) are executed by the test suite. A few:
```sql
SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' ORDER BY age DESC LIMIT 10
SELECT name FROM "students.json" WHERE city = "Delhi" OR age >= 28 ORDER BY name
SELECT Name, Fare FROM titanic.csv WHERE Pclass = 1 ORDER BY Fare DESC LIMIT 5
```
`examples/titanic.csv` is a **small synthetic sample** with the usual Titanic column names (blank ages, names containing
commas) written to exercise messy data; it is not the real dataset. Its `Sex` values are `male`/`female`, so `sex = 'M'`
is valid but matches no rows.

---

## 12. Design decisions and assumptions
These are choices where the documents were silent or ambiguous.

1. **`AND` binds tighter than `OR`** (as in SQL): `a OR b AND c` means `a OR (b AND c)`. The documented grammar does not
   state precedence; the parser expresses it with two rules (`condition`, `and_term`) that accept the *same* queries.
   No parentheses (out of scope).
2. **Bare file names** (`FROM titanic.csv`) are accepted in addition to quoted ones. The grammar says `FROM STRING`; this
   extension is limited to names ending in `.csv`/`.json`.
3. **Column names are case-insensitive** (`age` finds `Age`); an exact match wins. Semantic analysis rewrites the AST with the
   file's own spelling. String *values* are case-sensitive.
4. **Type inference reads all rows**, not a small sample, so a late stray text value cannot make a NUMBER column crash.
   A column is NUMBER only if every non-blank value is a number. In JSON, the string `"20"` stays TEXT.
5. **Missing values** (blank CSV cell, absent/`null` JSON key): any comparison with a missing value is false (including `!=`),
   and `ORDER BY` puts them last in both directions. They print as `NULL`.
6. **TEXT columns allow `> < >= <=`** (plain character-by-character order, case-sensitive). Only NUMBER-vs-TEXT is a type error.
7. **Sort placement**: the plan is `Limit → Sort → Project → Filter → Scan` as in the report. If `ORDER BY` names a column that is
   *not* selected, `Sort` is placed below `Project` (otherwise the column would already be gone).
8. **`--file` is a lookup hint**, not an override: `FROM` decides which file is read. This avoids silently querying a different
   file than the one named in the query.
9. A trailing `;` and negative number literals (`age > -5`) are accepted.
10. A `WHERE` clause may have at most 100 comparisons (guards Python's recursion limit); beyond that is a syntax error.
11. The type system (`DataType`) lives in `schema.py` rather than a separate `types.py`; the dependency-free `compiler.py` driver is an addition to the suggested layout.

## 13. Limitations
* Everything in the "not supported" column of §3. LiteQL is not SQL-compatible.
* Column names that are keywords (`order`, `limit`, …) or contain spaces/punctuation (`Siblings/Spouses Aboard`) cannot be
  named in a query. `SELECT *` still returns them.
* Quoted strings have no escape sequences. JSON must be a top-level array of objects; nested values are shown as JSON text.
* The whole file is read into memory when it is opened (and once more when executed). Suitable for demo-sized files, not big data.
  Predicate/projection pushdown reduce what flows *between operators*, which `--stats` reports; they do not make the file read lazier.
* Numeric text such as ZIP codes (`01234`) in a CSV column is treated as a number.
* Optimizer is a fixed two-rule pipeline over a one-table plan; it is not cost-based.

## 14. Future extensions
Parentheses in conditions, `LIKE`, `IS NULL`, a date type, streaming (row-at-a-time) execution so pushdown also saves reading,
a rule that merges adjacent `Limit`/`Sort` into top-N, and (clearly beyond this project's scope) aggregates and joins.

## 15. Literature context
LiteQL is educational and architectural: it makes no claim of a new optimization algorithm or of competing with existing systems.

* Aho, Lam, Sethi, Ullman — *Compilers: Principles, Techniques, and Tools*: lexer, parser, semantic analysis, IR, optimization.
* Levy, Mumick, Sagiv — *Query Optimization by Predicate Move-Around*, VLDB 1994: foundational work on moving predicates.
* Yan, Lin, He — *Predicate Pushdown for Data Science Pipelines*, SIGMOD 2023, doi:10.1145/3589281: predicate pushdown in modern data pipelines.
* Zhang, Campbell, Tang, Dillig — *Optimal Predicate Pushdown Synthesis*, PLDI 2026 (PACMPL), doi:10.1145/3808312: predicate pushdown as an active research problem.
* Raasveldt, Mühleisen — *DuckDB: An Embeddable Analytical Database*, SIGMOD 2019, doi:10.1145/3299869.3320212: a mature analytical engine, as a comparison point.

Research gaps LiteQL addresses (as a teaching artifact, not a new technique): (1) production engines such as DuckDB are too large to
serve as a transparent demonstration of every compiler stage; (2) predicate pushdown is normally an internal component of large systems,
whereas LiteQL shows it as an observable before/after rewrite in a small pipeline; (3) schema-aware semantic checking and type checking are
usually bundled inside engines, whereas LiteQL isolates them as explicit, inspectable stages.

## Viva cheat sheet
| Question | Answer from this code |
|---|---|
| Why a compiler? | The query is never run directly: lex → parse → check → IR → optimize → execute (`compiler.py`). |
| Lexer vs parser? | Lexer: characters → flat labelled tokens (`lexer.py`). Parser: checks order, builds the tree (`parser.py`). |
| AST? | `Query` with columns, source, `And/Or/Comparison` tree, `OrderBy`, `limit` (`ast.py`). |
| Syntax vs semantic error? | `SELECT salary FROM "students.csv"` parses fine; `semantic.py` rejects it using the file's symbol table. |
| Symbol table? | `Schema`: column name → `NUMBER`/`TEXT`, inferred from the file (`schema.py`). |
| Type checking? | `_check_comparison` in `semantic.py`: both sides must have the same `DataType`. |
| Why is the plan an IR? | Five simple operators between query text and execution; easy to print, rewrite and run. |
| Predicate pushdown? | `push_predicate`: `Filter(Scan)` → `Scan(predicate)`; rows rejected during reading. |
| Projection pushdown? | `push_projection`: Scan reads SELECT ∪ WHERE ∪ ORDER BY columns only (`SELECT *` → all). |
| How do you know it is safe? | Tests compare optimized vs unoptimized results on 700 generated combinations plus thousands of fuzzed queries. |
| Why no joins? | They add grammar and plan complexity without adding a new compiler phase. |
| Why Python? | `csv`/`json` in the standard library, so effort goes into the compiler. |

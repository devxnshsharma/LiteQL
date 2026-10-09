# Architecture

```
Query text
  → Lexer                      lexer.py, tokens.py
  → Tokens
  → Parser (recursive descent) parser.py
  → AST                        ast.py
  → Semantic analysis          semantic.py  ←  Symbol table  (schema.py ← data_source.py ← the file)
  → Checked AST                (column names resolved to the file's spelling, types verified)
  → Logical plan (IR)          logical_plan.py
  → Optimizer                  optimizer.py
  → Optimized plan
  → Executor                   executor.py  ←  data_source.py
  → Result rows
```

`compiler.py` runs the compile-time phases in order and stores every intermediate result in a `Compilation`
object; `Compilation.run()` then executes. `cli.py` and `printer.py` only format what `Compilation` holds.

## Module responsibilities

| Module | Responsibility | May read the data file? |
|---|---|---|
| `tokens.py` / `lexer.py` | characters → tokens | no |
| `ast.py` / `parser.py` | tokens → tree; syntax errors | no |
| `schema.py` | `DataType`, `Schema` (the symbol table), type inference | no (receives values) |
| `data_source.py` | CSV/JSON reading, typing of cells, scan with projection + predicate | yes |
| `semantic.py` | column existence, type compatibility, LIMIT | only through the `Schema` |
| `logical_plan.py` | plan node classes; checked AST → plan | no |
| `optimizer.py` | predicate pushdown, projection pushdown | no |
| `executor.py` | run plan nodes, comparison semantics | yes (the only data-row reader) |
| `errors.py` | one error class per phase | — |

Only the first access (header/columns + type inference) happens at compile time; **no data row is delivered to the
query** until `run()`. Tests assert this (patching `DataSource.scan` to fail during compilation).

## Intermediate representations

* **Tokens** – flat list: `IDENTIFIER(age) GREATER(>) NUMBER(20) EOF`.
* **AST** – tree of frozen dataclasses; conditions are a binary tree of `And` / `Or` / `Comparison`, so precedence is visible.
* **Symbol table** – `{column: NUMBER | TEXT}` in file order.
* **Logical plan** – chain of `Limit → Sort → Project → Filter → Scan`, each node holding its single `child`.
  All nodes are immutable; optimization returns a new tree.

## Optimizer in detail

```
before                             after predicate pushdown            after projection pushdown
Limit 5                            Limit 5                             Limit 5
  Sort age DESC                      Sort age DESC                       Sort age DESC
    Project name, age                  Project name, age                   Project name, age
      Filter age > 20                    Scan students.csv                   Scan students.csv
        Scan students.csv                  (predicate: age > 20)               (predicate: age > 20; columns: name, age)
```

**Why the rewrites are safe**

* A `Filter` only decides which rows survive, and `Scan` is the first operator, so evaluating the same condition
  during the scan keeps exactly the same rows. A filter is never moved below `Limit` (that would change which rows
  the limit keeps); LiteQL plans never contain a filter above anything but `Scan`.
* `required_columns` returns the SELECT list, then the WHERE columns (both sides of column-to-column comparisons),
  then the ORDER BY column. With `SELECT *` there is no `Project`, so `None` ("all columns") is returned and nothing is dropped.

**Measuring instead of claiming.** `ExecutionStats` counts rows read, rows and fields passed up by the `Scan`,
and rows returned. `--stats` prints them for both plans and verifies the results are equal. For the main query on
`students.csv` it reports 8 → 6 rows and 24 → 12 fields leaving the scan (the file itself is read in full either way).

## Error flow

Each phase raises its own `LiteQLError` subclass. `compile_query` attaches the partially-filled `Compilation` to the
exception, which is how `--tokens`, `--ast`, `--schema` can still print what completed before a failure.

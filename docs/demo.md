# Demonstration script

Run from the repository root. `python3 -m liteql.cli --demo` performs all five steps below in one go; the individual
commands let you pause and explain. Main query used throughout:

```
SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5
```

## Demo 1 — valid query through every phase
```bash
python3 -m liteql.cli --file examples/students.csv --all \
  --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'
```
Say: *tokens* (lexer) → *AST* (parser) → *symbol table* (inferred from the file) → *logical plan* (IR) → *optimized plan* → *result*.
Expected result: Vihaan 31, Meera 28, Arjun 26, Diya 24, Kabir 22.

## Demo 2 — syntax error (parser)
```bash
python3 -m liteql.cli --file examples/students.csv --tokens --query 'SELECT name, age "students.csv"'
```
Tokens are produced (lexing is fine) but the *structure* is wrong: `FROM` is missing. A `^` marks the position. Nothing is read from the file's rows.

## Demo 3 — missing column (semantic analysis)
```bash
python3 -m liteql.cli --file examples/students.csv --schema --query 'SELECT name, salary FROM "students.csv"'
```
The query parses; the symbol table (`name, age, city`) shows `salary` is not there. Semantic error, listing the available columns.

## Demo 4 — type error
```bash
python3 -m liteql.cli --file examples/students.csv --schema --query 'SELECT name FROM "students.csv" WHERE age > "hello"'
```
`age` is NUMBER in the symbol table, `"hello"` is TEXT → rejected before any plan is built.

## Demo 5 — optimization, before vs after
```bash
python3 -m liteql.cli --file examples/students.csv --plan --optimized-plan --stats \
  --query 'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5'
```
* **Predicate pushdown** — `Filter age > 20` disappears from the tree and reappears as the Scan's `predicate`.
* **Projection pushdown** — Scan reads `name, age` only (`city` is never touched). Point out that `age` is kept because
  WHERE and ORDER BY need it, even in `SELECT name … WHERE age > 20`.
* The *Work done by the Scan* table shows 8 → 6 rows and 24 → 12 fields leaving the scan, and `Results identical: yes`.
  We report counts, not a speed-up percentage.

## Extra: queries a teacher might type
```bash
python3 -m liteql.cli --query "SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' order by age desc limit 10"
python3 -m liteql.cli --query "SELECT Name, Age FROM titanic.csv WHERE Pclass = 1 OR Fare > 50 ORDER BY Age" --optimized-plan
python3 -m liteql.cli --file examples/students.json --query 'SELECT name FROM "students.json" WHERE age >= 28 ORDER BY age'
python3 -m liteql.cli --query "SELECT * FROM titanic.csv WHERE sex = M"        # unquoted text -> semantic error with a hint
```
Notes for questions: keywords and column names are case-insensitive; `AND` binds tighter than `OR`; blank cells never match a
comparison and sort last; `examples/titanic.csv` is a synthetic sample, with `male`/`female` in `Sex`.

# LiteQL grammar

## Baseline grammar (from the project report)

```
query        ::= "SELECT" column_list "FROM" STRING [where_clause] [order_clause] [limit_clause]
column_list  ::= "*" | column ("," column)*
column       ::= IDENTIFIER
where_clause ::= "WHERE" condition
condition    ::= comparison (("AND" | "OR") comparison)*
comparison   ::= column OP value
OP           ::= "=" | "!=" | ">" | "<" | ">=" | "<="
order_clause ::= "ORDER BY" column ["ASC" | "DESC"]
limit_clause ::= "LIMIT" INTEGER
value        ::= STRING | NUMBER | column
```

## Grammar as implemented

```
query        ::= "SELECT" column_list "FROM" file [where_clause] [order_clause] [limit_clause] [";"]
column_list  ::= "*" | column ("," column)*
where_clause ::= "WHERE" condition
condition    ::= and_term ("OR" and_term)*
and_term     ::= comparison ("AND" comparison)*
comparison   ::= column OP value
order_clause ::= "ORDER" "BY" column ["ASC" | "DESC"]
limit_clause ::= "LIMIT" INTEGER
file         ::= STRING | FILENAME
value        ::= STRING | NUMBER | column
```

Each rule is one method of `Parser` in `liteql/parser.py`.

### Differences from the baseline, and why

| Change | Reason |
|---|---|
| `condition` split into `condition` / `and_term` | The baseline does not say whether `AND` or `OR` binds tighter. Both forms accept exactly the same token sequences; the split fixes the **meaning** as in SQL: `a OR b AND c` = `a OR (b AND c)`. |
| `file ::= STRING \| FILENAME` | So `FROM titanic.csv` works as well as `FROM "titanic.csv"`. A `FILENAME` must end in `.csv` or `.json`. |
| optional `";"` | Common habit when typing queries. |
| `ORDER BY` as two keywords | Lexing is word-by-word; the parser requires `BY` after `ORDER`. |

## Lexical rules

| Token | Pattern |
|---|---|
| keywords | `SELECT FROM WHERE ORDER BY ASC DESC LIMIT AND OR` (case-insensitive) |
| `IDENTIFIER` | letter or `_`, then letters, digits, `_` |
| `NUMBER` | optional `-`, digits, optional `.digits` (`20`, `3.5`, `-4`) |
| `STRING` | any text in `'…'` or `"…"`; no escape sequences |
| `FILENAME` | name/path ending `.csv` or `.json`, no quotes |
| operators / punctuation | `=  !=  >  <  >=  <=  ,  *  ;` |

Whitespace (including newlines) separates tokens and is otherwise ignored.

## Examples checked by hand

| Query | Valid? | Why |
|---|---|---|
| `SELECT name FROM "students.csv"` | yes | minimal query |
| `FROM "students.csv" SELECT name` | no | must start with `SELECT` |
| `SELECT name "students.csv"` | no | `FROM` missing |
| `SELECT name FROM "students.csv" LIMIT` | no | `LIMIT` needs an integer |
| `SELECT name WHERE age > 20` | no | `FROM` missing |
| `SELECT name FROM "x.csv" LIMIT 5 ORDER BY age` | no | clauses out of order |
| `SELECT a FROM "x.csv" WHERE a > 1 AND b = 'x' OR c < 2` | yes | `(a>1 AND b='x') OR c<2` |

The grammar only decides whether the *shape* is right. Whether columns exist and types fit is decided later, by semantic analysis.

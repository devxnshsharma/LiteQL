# Architecture

`Query text -> Lexer -> Tokens -> Parser -> AST -> Semantic analysis -> Logical plan -> Optimizer -> Executor -> Result`

The lexer and recursive-descent parser are hand-written. Schema inference builds a symbol table from CSV headers or JSON object keys. Semantic analysis checks columns and types before a plan is built. The plan is the intermediate representation: `Scan`, `Filter`, `Project`, `Sort`, and `Limit`.

The optimizer performs only the two Review 1 transformations: it stores a filter predicate on `Scan` (predicate pushdown) and asks `Scan` for the select, filter, and sort columns it requires (projection pushdown).

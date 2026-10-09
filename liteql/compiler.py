"""The compiler driver: runs the phases in order and keeps every intermediate result.

    query text -> tokens -> AST -> (symbol table) -> checked AST
               -> logical plan -> optimized plan          [then: execute]

Nothing is executed until every earlier phase has succeeded. If a phase fails,
the error carries a partial `Compilation` holding the stages that did finish
(for example the tokens of a query with a syntax error), which the CLI can show.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .data_source import open_source, resolve_path
from .errors import LiteQLError
from .executor import ExecutionStats, execute
from .lexer import tokenize
from .logical_plan import build_plan
from .optimizer import optimize
from .parser import parse
from .semantic import analyze


@dataclass
class Compilation:
    query_text: str
    tokens: Optional[list] = None
    ast: Optional[object] = None              # as parsed (names exactly as the user typed them)
    path: Optional[str] = None                # the data file FROM resolved to
    schema: Optional[object] = None           # the symbol table
    checked_ast: Optional[object] = None      # after semantic analysis (real column names)
    plan: Optional[object] = None             # unoptimized logical plan
    optimized_plan: Optional[object] = None
    optimizations: list = field(default_factory=list)

    @property
    def output_columns(self) -> list:
        """Column names of the result, also needed to print a result with zero rows."""
        if self.checked_ast.columns is None:
            return list(self.schema.columns)
        return [column.name for column in self.checked_ast.columns]

    def run(self, optimized: bool = True):
        """Execute the plan. Returns (rows, stats)."""
        stats = ExecutionStats()
        rows = execute(self.optimized_plan if optimized else self.plan, stats)
        return rows, stats


def compile_query(query_text: str, file_path: str | None = None) -> Compilation:
    """Compile `query_text`. `file_path` (the CLI's --file) only helps locate the FROM file."""
    result = Compilation(query_text)
    try:
        result.tokens = tokenize(query_text)                        # lexical analysis
        result.ast = parse(result.tokens)                           # syntax analysis
        result.path = resolve_path(result.ast.source, file_path)
        result.schema = open_source(result.path).schema             # schema inference / symbol table
        result.checked_ast = analyze(result.ast, result.schema)     # semantic analysis + type checking
        result.plan = build_plan(result.checked_ast, result.path)   # intermediate representation
        result.optimized_plan = optimize(result.plan, result.optimizations)
    except LiteQLError as error:
        error.compilation = result
        raise
    return result


def run_query(query_text: str, file_path: str | None = None):
    """Compile and execute. Returns (rows, compilation)."""
    compilation = compile_query(query_text, file_path)
    rows, _ = compilation.run()
    return rows, compilation

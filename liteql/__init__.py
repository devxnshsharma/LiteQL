"""LiteQL: a small SQL-like compiler for CSV and JSON files.

Pipeline: query text -> lexer -> parser -> semantic analysis -> logical plan
-> optimizer -> executor. See README.md and docs/architecture.md.
"""

from .compiler import Compilation, compile_query, run_query

__all__ = ["Compilation", "compile_query", "run_query"]

from __future__ import annotations

from dataclasses import dataclass, replace

from .data_source import schema_for
from .executor import execute
from .lexer import tokenize
from .logical_plan import build_plan
from .optimizer import optimize
from .parser import parse
from .semantic import analyze


@dataclass
class Compilation:
    tokens: list
    ast: object
    schema: object
    plan: object
    optimized_plan: object


def compile_query(query_text: str, file_path: str | None = None) -> Compilation:
    tokens = tokenize(query_text)
    ast = parse(tokens)
    if file_path: ast = replace(ast, source=file_path)
    schema = schema_for(ast.source)
    analyze(ast, schema)
    plan = build_plan(ast)
    return Compilation(tokens, ast, schema, plan, optimize(plan))


def run_query(query_text: str, file_path: str | None = None):
    compilation = compile_query(query_text, file_path)
    return compilation, execute(compilation.optimized_plan)

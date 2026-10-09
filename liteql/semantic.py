"""Phase 3 - Semantic analysis and type checking.

A query that parsed successfully is only *grammatically* valid. This phase asks
whether it makes sense for the actual data file, using the symbol table:

  1. every column named anywhere in the query must exist,
  2. every comparison must compare compatible types (NUMBER with NUMBER,
     TEXT with TEXT),
  3. LIMIT must not be negative.

On success it returns the AST with every column name replaced by the file's own
spelling (so `age` becomes `Age` if that is the header). Nothing here reads
data rows or runs the query.
"""

from dataclasses import replace

from . import errors
from .ast import And, Column, ColumnReference, Comparison, NumberLiteral, Or, OrderBy, Query
from .schema import DataType, Schema


def analyze(query: Query, schema: Schema) -> Query:
    """Check `query` against `schema` and return the name-resolved, type-checked AST."""
    columns = query.columns
    if columns is not None:
        columns = [Column(_resolve(column.name, schema)) for column in columns]
        names = [column.name for column in columns]
        for name in names:
            if names.count(name) > 1:
                raise errors.SemanticError(f"Column '{name}' is selected more than once")

    where = _check_condition(query.where, schema) if query.where is not None else None

    order_by = query.order_by
    if order_by is not None:
        order_by = OrderBy(Column(_resolve(order_by.column.name, schema)), order_by.direction)

    if query.limit is not None and query.limit < 0:
        raise errors.SemanticError(f"LIMIT must not be negative (got {query.limit})")

    return replace(query, columns=columns, where=where, order_by=order_by)


def _resolve(name: str, schema: Schema, hint: str = "") -> str:
    """Column-existence check (the symbol-table lookup)."""
    real_name = schema.resolve(name)
    if real_name is None:
        available = ", ".join(schema.columns) or "(none)"
        raise errors.SemanticError(
            f"Column '{name}' does not exist.\n  Available columns: {available}{hint}")
    return real_name


def _check_condition(node, schema: Schema):
    if isinstance(node, (And, Or)):
        return type(node)(_check_condition(node.left, schema), _check_condition(node.right, schema))
    return _check_comparison(node, schema)


def _check_comparison(node: Comparison, schema: Schema) -> Comparison:
    left_name = _resolve(node.column.name, schema)
    left_type = schema.type_of(left_name)

    value = node.value
    if isinstance(value, ColumnReference):
        right_name = _resolve(value.name, schema,
                              f"\n  (If '{value.name}' is a text value, put it in quotes: '{value.name}')")
        value = ColumnReference(right_name)
        right_type = schema.type_of(right_name)
        right_description = f"{right_type.value} column '{right_name}'"
    elif isinstance(value, NumberLiteral):
        right_type = DataType.NUMBER
        right_description = f"NUMBER value {value.value}"
    else:
        right_type = DataType.TEXT
        right_description = f"TEXT value '{value.value}'"

    if left_type is not right_type:
        raise errors.TypeError(
            f"Cannot compare {left_type.value} column '{left_name}' with {right_description}")
    return Comparison(Column(left_name), node.operator, value)

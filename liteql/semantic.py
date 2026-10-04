from .ast import BinaryCondition, ColumnReference, NumberLiteral, StringLiteral
from .errors import SemanticError, TypeError
from .schema import DataType, Schema


def analyze(query, schema: Schema):
    for column in query.columns or []: _require(column.name, schema)
    if query.order_by: _require(query.order_by.column.name, schema)
    if query.limit is not None and query.limit < 0: raise SemanticError("LIMIT must not be negative")
    if query.where: _check_condition(query.where, schema)
    return schema


def _require(name, schema):
    if not schema.require(name):
        raise SemanticError(f"Column '{name}' does not exist. Available columns: {', '.join(schema.columns)}")


def _check_condition(node, schema):
    if isinstance(node, BinaryCondition):
        _check_condition(node.left, schema); _check_condition(node.right, schema); return
    left_type = schema.require(node.column.name)
    _require(node.column.name, schema)
    if isinstance(node.value, ColumnReference):
        _require(node.value.name, schema); right_type = schema.require(node.value.name)
    elif isinstance(node.value, NumberLiteral): right_type = DataType.NUMBER
    else: right_type = DataType.TEXT
    if left_type != right_type:
        raise TypeError(f"Cannot compare {left_type.value} column '{node.column.name}' with {right_type.value} value")
    if left_type == DataType.TEXT and node.operator in (">", "<", ">=", "<="):
        raise TypeError(f"Cannot use '{node.operator}' with TEXT column '{node.column.name}'; use = or !=")

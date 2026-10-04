from .ast import BinaryCondition, ColumnReference, NumberLiteral
from .data_source import load_rows
from .logical_plan import Filter, Limit, Project, Scan, Sort


def execute(plan):
    if isinstance(plan, Scan):
        rows = load_rows(plan.source, set(plan.columns) if plan.columns else None)
        return [row for row in rows if plan.predicate is None or _matches(plan.predicate, row)]
    if isinstance(plan, Filter): return [row for row in execute(plan.child) if _matches(plan.condition, row)]
    if isinstance(plan, Project):
        rows = execute(plan.child)
        return rows if plan.columns is None else [{key: row.get(key) for key in plan.columns} for row in rows]
    if isinstance(plan, Sort):
        return sorted(execute(plan.child), key=lambda row: _value(row.get(plan.column)), reverse=plan.direction == "DESC")
    if isinstance(plan, Limit): return execute(plan.child)[:plan.count]
    raise RuntimeError(f"Unknown plan node: {type(plan).__name__}")


def _value(value):
    try: return float(value)
    except (ValueError, TypeError): return str(value)


def _matches(node, row):
    if isinstance(node, BinaryCondition):
        return (_matches(node.left, row) and _matches(node.right, row)) if node.operator == "AND" else (_matches(node.left, row) or _matches(node.right, row))
    left = _value(row.get(node.column.name))
    right = _value(row.get(node.value.name) if isinstance(node.value, ColumnReference) else node.value.value)
    return {"=": left == right, "!=": left != right, ">": left > right, "<": left < right, ">=": left >= right, "<=": left <= right}[node.operator]

from .ast import BinaryCondition, ColumnReference, NumberLiteral, StringLiteral
from .logical_plan import Filter, Limit, Project, Scan, Sort


def format_ast(query):
    lines = ["Query", f"  Select: {', '.join(c.name for c in query.columns) if query.columns else '*'}", f"  From: {query.source}"]
    if query.where: lines += ["  Where:", f"    {_condition(query.where)}"]
    if query.order_by: lines.append(f"  Order By: {query.order_by.column.name} {query.order_by.direction}")
    if query.limit is not None: lines.append(f"  Limit: {query.limit}")
    return "\n".join(lines)


def format_plan(plan, indent=0):
    pad = "  " * indent
    if isinstance(plan, Scan):
        details = [plan.source]
        if plan.columns: details.append("columns=" + ", ".join(plan.columns))
        if plan.predicate: details.append("predicate=" + _condition(plan.predicate))
        return pad + "Scan " + " | ".join(details)
    if isinstance(plan, Filter): label, child = f"Filter {_condition(plan.condition)}", plan.child
    elif isinstance(plan, Project): label, child = "Project " + (", ".join(plan.columns) if plan.columns else "*"), plan.child
    elif isinstance(plan, Sort): label, child = f"Sort {plan.column} {plan.direction}", plan.child
    elif isinstance(plan, Limit): label, child = f"Limit {plan.count}", plan.child
    else: return pad + repr(plan)
    return pad + label + "\n" + format_plan(child, indent + 1)


def _condition(node):
    if isinstance(node, BinaryCondition): return f"({_condition(node.left)} {node.operator} {_condition(node.right)})"
    value = node.value.name if isinstance(node.value, ColumnReference) else (repr(node.value.value) if isinstance(node.value, StringLiteral) else str(node.value.value))
    return f"{node.column.name} {node.operator} {value}"

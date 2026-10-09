"""Readable text output for every compiler representation."""

from __future__ import annotations

from pathlib import Path

from .ast import And, ColumnReference, NumberLiteral, Or, StringLiteral
from .logical_plan import Filter, Limit, Project, Scan, Sort


# --- Tokens -------------------------------------------------------------------

def format_tokens(tokens: list) -> str:
    return "\n".join(str(token) for token in tokens)


# --- AST ----------------------------------------------------------------------

def format_condition(node) -> str:
    """One-line form of a condition, e.g. (age > 20 AND sex = 'male')."""
    if isinstance(node, (And, Or)):
        word = "AND" if isinstance(node, And) else "OR"
        return f"({format_condition(node.left)} {word} {format_condition(node.right)})"
    value = node.value
    if isinstance(value, ColumnReference):
        text = value.name
    elif isinstance(value, StringLiteral):
        text = repr(value.value)
    else:
        text = str(value.value)
    return f"{node.column.name} {node.operator} {text}"


def format_ast(query) -> str:
    """Draw the AST as a tree with box-drawing characters."""
    children = [
        ("Select: " + (", ".join(c.name for c in query.columns) if query.columns else "*"), []),
        (f"From: {query.source}", []),
    ]
    if query.where is not None:
        children.append(("Where", [_condition_tree(query.where)]))
    if query.order_by is not None:
        children.append((f"Order By: {query.order_by.column.name} {query.order_by.direction}", []))
    if query.limit is not None:
        children.append((f"Limit: {query.limit}", []))
    return "\n".join(["Query"] + _draw(children))


def _condition_tree(node):
    """(label, children) pairs; AND/OR become inner nodes, comparisons are leaves."""
    if isinstance(node, (And, Or)):
        label = "AND" if isinstance(node, And) else "OR"
        return (label, [_condition_tree(node.left), _condition_tree(node.right)])
    return (format_condition(node), [])


def _draw(children, prefix: str = "") -> list:
    lines = []
    for i, (label, grandchildren) in enumerate(children):
        last = i == len(children) - 1
        lines.append(prefix + ("└── " if last else "├── ") + label)
        lines += _draw(grandchildren, prefix + ("    " if last else "│   "))
    return lines


# --- Logical plan ---------------------------------------------------------------

def format_plan(plan, indent: int = 0) -> str:
    """Print the plan root-first, each child indented under its parent."""
    pad = "  " * indent
    if isinstance(plan, Scan):
        return pad + _scan_label(plan)
    if isinstance(plan, Filter):
        label = f"Filter {format_condition(plan.condition)}"
    elif isinstance(plan, Project):
        label = "Project " + ", ".join(plan.columns)
    elif isinstance(plan, Sort):
        label = f"Sort {plan.column} {plan.direction}"
    elif isinstance(plan, Limit):
        label = f"Limit {plan.count}"
    else:
        raise ValueError(f"Unknown plan node: {type(plan).__name__}")
    return pad + label + "\n" + format_plan(plan.child, indent + 1)


def _scan_label(scan: Scan) -> str:
    label = "Scan " + Path(scan.source).name
    details = []
    if scan.predicate is not None:
        details.append("predicate: " + format_condition(scan.predicate))
    if scan.columns is not None:
        details.append("columns: " + ", ".join(scan.columns))
    return label + (f"  ({'; '.join(details)})" if details else "")


# --- Result table -----------------------------------------------------------------

def format_table(rows: list, columns: list) -> str:
    """Aligned text table followed by a row count."""
    def show(value):
        return "NULL" if value is None else str(value)

    cells = [[show(row[name]) for name in columns] for row in rows]
    widths = [max([len(name)] + [len(line[i]) for line in cells]) for i, name in enumerate(columns)]
    header = "  ".join(name.ljust(width) for name, width in zip(columns, widths))
    rule = "  ".join("-" * width for width in widths)
    body = ["  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip() for line in cells]
    count = f"({len(rows)} row{'' if len(rows) == 1 else 's'})"
    return "\n".join([header.rstrip(), rule] + body + [count])

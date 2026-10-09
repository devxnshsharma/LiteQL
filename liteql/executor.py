"""Phase 5 - Execution: run a logical plan against the data file.

The executor is the only phase that reads data rows. It is a simple recursive
interpreter: to run a node, first run its child, then apply the node's operator
to the child's rows.

Rules for missing values (blank CSV cell, absent JSON key): a comparison with a
missing value is never true, and ORDER BY puts missing values last.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass

from .ast import And, ColumnReference, Or
from .data_source import open_source
from .logical_plan import Filter, Limit, Project, Scan, Sort

COMPARE = {
    "=": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


@dataclass
class ExecutionStats:
    """How much work the Scan did - used to compare an unoptimized and optimized plan."""
    rows_scanned: int = 0       # rows read from the file
    rows_from_scan: int = 0     # rows the Scan passed up to the next operator
    cells_from_scan: int = 0    # fields (cells) those rows carried
    rows_returned: int = 0      # rows in the final result


def execute(plan, stats: ExecutionStats | None = None) -> list:
    """Run `plan` and return the result rows (a list of dicts)."""
    stats = stats if stats is not None else ExecutionStats()
    rows = _run(plan, stats)
    stats.rows_returned = len(rows)
    return rows


def _run(node, stats: ExecutionStats) -> list:
    if isinstance(node, Scan):
        source = open_source(node.source)
        predicate = (lambda row: evaluate(node.predicate, row)) if node.predicate is not None else None
        return list(source.scan(node.columns, predicate, stats))

    rows = _run(node.child, stats)

    if isinstance(node, Filter):
        return [row for row in rows if evaluate(node.condition, row)]
    if isinstance(node, Project):
        return [{name: row[name] for name in node.columns} for row in rows]
    if isinstance(node, Sort):
        present = [row for row in rows if row[node.column] is not None]
        missing = [row for row in rows if row[node.column] is None]
        # sort() is stable, even with reverse=True, so ties keep file order.
        present.sort(key=lambda row: row[node.column], reverse=node.direction == "DESC")
        return present + missing
    if isinstance(node, Limit):
        return rows[:node.count]
    raise ValueError(f"Unknown plan node: {type(node).__name__}")


def evaluate(condition, row: dict) -> bool:
    """Evaluate a WHERE condition for one row. `row` must contain every column it uses."""
    if isinstance(condition, And):
        return evaluate(condition.left, row) and evaluate(condition.right, row)
    if isinstance(condition, Or):
        return evaluate(condition.left, row) or evaluate(condition.right, row)

    left = row[condition.column.name]
    value = condition.value
    right = row[value.name] if isinstance(value, ColumnReference) else value.value
    if left is None or right is None:
        return False
    return COMPARE[condition.operator](left, right)

"""Phase 4 - Optimization: exactly the two transformations promised in the project.

  A. Predicate pushdown  - a Filter directly above a Scan is merged into the
     Scan, so non-matching rows are rejected while the file is being read.
  B. Projection pushdown - the Scan is told which columns the query really
     needs, so other columns are never read.

Both rewrites must not change the query result. In particular the columns kept
by projection pushdown are *everything* any operator uses: the SELECT list,
the WHERE columns and the ORDER BY column. (SELECT * needs every column.)
"""

from __future__ import annotations

from dataclasses import replace

from .ast import And, ColumnReference, Comparison, Or
from .logical_plan import Filter, Project, Scan, Sort


def optimize(plan, trace: list | None = None):
    """Return the optimized plan. Human-readable notes about each rewrite go into `trace`."""
    trace = trace if trace is not None else []
    plan = push_predicate(plan, trace)
    return push_projection(plan, trace)


# --- A. Predicate pushdown ----------------------------------------------------

def push_predicate(node, trace: list):
    """Merge Filter-over-Scan into a single Scan carrying the predicate.

    Only this one pattern is rewritten. A Filter is never moved below Limit
    (that would change which rows survive the limit), and LiteQL plans never
    put a Filter above Sort or Project, so there is nothing else to move.
    """
    if isinstance(node, Scan):
        return node
    child = push_predicate(node.child, trace)
    if isinstance(node, Filter) and isinstance(child, Scan) and child.predicate is None:
        trace.append("Predicate pushdown: the WHERE condition now filters rows inside Scan "
                     "(rows are rejected as soon as they are read)")
        return replace(child, predicate=node.condition)
    return replace(node, child=child)


# --- B. Projection pushdown ---------------------------------------------------

def push_projection(plan, trace: list):
    """Tell the Scan to read only the columns the rest of the plan needs."""
    needed = required_columns(plan)
    if needed is None:
        trace.append("Projection pushdown: not applicable (SELECT * needs every column)")
        return plan
    trace.append("Projection pushdown: Scan reads only " + ", ".join(needed))
    return _set_scan_columns(plan, tuple(needed))


def required_columns(plan):
    """Columns the plan needs from the file, in first-use order; None means all of them."""
    projects = _find(plan, Project)
    if projects is None:
        return None            # no Project node means SELECT *
    needed = list(projects.columns)                       # 1. SELECT list
    for node in _walk(plan):                              # 2. WHERE columns
        if isinstance(node, Filter):
            needed += condition_columns(node.condition)
        elif isinstance(node, Scan) and node.predicate is not None:
            needed += condition_columns(node.predicate)
    for node in _walk(plan):                              # 3. ORDER BY column
        if isinstance(node, Sort):
            needed.append(node.column)
    return list(dict.fromkeys(needed))                    # remove duplicates, keep order


def condition_columns(condition) -> list:
    """All column names a condition reads (both sides of each comparison)."""
    if isinstance(condition, (And, Or)):
        return condition_columns(condition.left) + condition_columns(condition.right)
    names = [condition.column.name]
    if isinstance(condition.value, ColumnReference):
        names.append(condition.value.name)
    return names


def _walk(plan):
    while True:
        yield plan
        if isinstance(plan, Scan):
            return
        plan = plan.child


def _find(plan, kind):
    return next((node for node in _walk(plan) if isinstance(node, kind)), None)


def _set_scan_columns(node, columns):
    if isinstance(node, Scan):
        return replace(node, columns=columns)
    return replace(node, child=_set_scan_columns(node.child, columns))

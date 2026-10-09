"""Logical plan: LiteQL's intermediate representation (IR).

A plan is a small tree of five operators. Data flows from the leaf (Scan) up to
the root:

    Limit 5
      Sort age DESC
        Project name, age
          Filter age > 20
            Scan students.csv

Every node except Scan has a `child`. Nodes are immutable, so the optimizer
builds a new tree instead of editing the old one - which lets us keep and print
the plan before and after optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Scan:
    """Read the data file.

    `columns` and `predicate` are empty in a fresh plan. The optimizer fills
    them in: `predicate` (predicate pushdown) rejects rows while reading, and
    `columns` (projection pushdown) limits which fields are read.
    columns=None means "all columns".
    """
    source: str
    columns: Optional[tuple] = None
    predicate: Optional[object] = None


@dataclass(frozen=True)
class Filter:
    child: object
    condition: object


@dataclass(frozen=True)
class Project:
    child: object
    columns: tuple


@dataclass(frozen=True)
class Sort:
    child: object
    column: str
    direction: str


@dataclass(frozen=True)
class Limit:
    child: object
    count: int


def build_plan(query, source_path: str):
    """Translate a checked AST into the unoptimized logical plan."""
    plan = Scan(source_path)
    if query.where is not None:
        plan = Filter(plan, query.where)

    selected = tuple(column.name for column in query.columns) if query.columns is not None else None
    order = query.order_by

    # Normal shape (as in the project report): Sort above Project.
    # But if ORDER BY uses a column that is not selected, Project would throw
    # that column away before Sort could use it, so Sort must go below Project.
    sort_below_project = order is not None and selected is not None and order.column.name not in selected

    if order is not None and sort_below_project:
        plan = Sort(plan, order.column.name, order.direction)
    if selected is not None:
        plan = Project(plan, selected)
    if order is not None and not sort_below_project:
        plan = Sort(plan, order.column.name, order.direction)

    if query.limit is not None:
        plan = Limit(plan, query.limit)
    return plan

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Scan:
    source: str
    columns: tuple[str, ...] | None = None
    predicate: object | None = None
@dataclass(frozen=True)
class Filter: child: object; condition: object
@dataclass(frozen=True)
class Project: child: object; columns: tuple[str, ...] | None
@dataclass(frozen=True)
class Sort: child: object; column: str; direction: str
@dataclass(frozen=True)
class Limit: child: object; count: int


def build_plan(query):
    plan = Scan(query.source)
    if query.where: plan = Filter(plan, query.where)
    if query.columns is not None: plan = Project(plan, tuple(column.name for column in query.columns))
    if query.order_by: plan = Sort(plan, query.order_by.column.name, query.order_by.direction)
    if query.limit is not None: plan = Limit(plan, query.limit)
    return plan

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column: name: str
@dataclass(frozen=True)
class StringLiteral: value: str
@dataclass(frozen=True)
class NumberLiteral: value: float | int
@dataclass(frozen=True)
class ColumnReference: name: str
@dataclass(frozen=True)
class Comparison: column: Column; operator: str; value: StringLiteral | NumberLiteral | ColumnReference
@dataclass(frozen=True)
class BinaryCondition: left: object; operator: str; right: Comparison
@dataclass(frozen=True)
class OrderBy: column: Column; direction: str = "ASC"
@dataclass(frozen=True)
class Query:
    columns: list[Column] | None  # None represents SELECT *
    source: str
    where: Comparison | BinaryCondition | None = None
    order_by: OrderBy | None = None
    limit: int | None = None

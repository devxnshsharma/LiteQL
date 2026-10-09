"""Abstract Syntax Tree (AST) node definitions.

The AST describes the *structure* of a query, not its raw tokens: commas,
keywords and quotes are gone; clauses and conditions remain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union


@dataclass(frozen=True)
class Column:
    name: str


# --- Values on the right-hand side of a comparison --------------------------

@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class NumberLiteral:
    value: Union[int, float]


@dataclass(frozen=True)
class ColumnReference:
    name: str


Value = Union[StringLiteral, NumberLiteral, ColumnReference]


# --- Conditions (WHERE) -----------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    column: Column
    operator: str        # one of = != > < >= <=
    value: Value


@dataclass(frozen=True)
class And:
    left: "Condition"
    right: "Condition"


@dataclass(frozen=True)
class Or:
    left: "Condition"
    right: "Condition"


Condition = Union[Comparison, And, Or]


# --- Whole query ------------------------------------------------------------

@dataclass(frozen=True)
class OrderBy:
    column: Column
    direction: str = "ASC"   # "ASC" or "DESC"


@dataclass(frozen=True)
class Query:
    columns: Optional[list]            # list of Column; None means SELECT *
    source: str                        # file name exactly as written after FROM
    where: Optional[Condition] = None
    order_by: Optional[OrderBy] = None
    limit: Optional[int] = None

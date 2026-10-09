"""Schema inference and the symbol table.

The *symbol table* of LiteQL maps each column name found in the data file to an
inferred type:

    name -> TEXT
    age  -> NUMBER
    city -> TEXT

The semantic analyzer uses it to check columns and comparisons.
(The type system lives here instead of a separate types.py: it is only two types.)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class DataType(Enum):
    NUMBER = "NUMBER"
    TEXT = "TEXT"


@dataclass(frozen=True)
class Schema:
    columns: dict            # column name -> DataType, in file order

    def resolve(self, name: str) -> str | None:
        """Return the real column name for `name`, or None if there is no such column.

        An exact match wins; otherwise the match is case-insensitive, so `age`
        finds a header called `Age` (as in the usual Titanic CSV files).
        """
        if name in self.columns:
            return name
        matches = [column for column in self.columns if column.lower() == name.lower()]
        return matches[0] if matches else None

    def type_of(self, name: str) -> DataType:
        return self.columns[name]

    def __str__(self) -> str:
        if not self.columns:
            return "(no columns)"
        width = max(len(name) for name in self.columns)
        return "\n".join(f"{name.ljust(width)} -> {kind.value}" for name, kind in self.columns.items())


def infer_schema(column_names: list, rows: list, to_number: Callable) -> Schema:
    """Infer NUMBER or TEXT for every column by looking at all non-missing values.

    A column is NUMBER only if every non-missing value is a number; one stray
    text value makes the whole column TEXT. Columns with no values are TEXT.
    `to_number(value)` returns a number or None, so CSV (where everything is a
    string) and JSON (which has real numbers) can share this function.
    """
    columns = {}
    for name in column_names:
        values = [row.get(name) for row in rows if not is_missing(row.get(name))]
        all_numeric = bool(values) and all(to_number(value) is not None for value in values)
        columns[name] = DataType.NUMBER if all_numeric else DataType.TEXT
    return Schema(columns)


def is_missing(value) -> bool:
    """None (absent JSON key / short CSV row) and blank CSV cells count as missing."""
    return value is None or (isinstance(value, str) and value.strip() == "")

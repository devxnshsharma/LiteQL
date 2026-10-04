from dataclasses import dataclass
from enum import Enum


class DataType(Enum):
    NUMBER = "NUMBER"
    TEXT = "TEXT"


@dataclass(frozen=True)
class Schema:
    columns: dict[str, DataType]
    def require(self, name: str): return self.columns.get(name)
    def __str__(self): return "\n".join(f"{name} -> {kind.value}" for name, kind in self.columns.items())


def infer_schema(rows: list[dict]) -> Schema:
    keys = list(dict.fromkeys(key for row in rows for key in row))
    result = {}
    for key in keys:
        values = [row.get(key) for row in rows[:100] if row.get(key) not in (None, "")]
        numeric = bool(values) and all(_is_number(value) for value in values)
        result[key] = DataType.NUMBER if numeric else DataType.TEXT
    return Schema(result)


def _is_number(value):
    if isinstance(value, bool): return False
    if isinstance(value, (int, float)): return True
    try: float(str(value)); return True
    except (ValueError, TypeError): return False

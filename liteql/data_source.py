from __future__ import annotations

import csv
import json
from pathlib import Path

from .errors import ExecutionError
from .schema import infer_schema


def load_rows(path: str, required_columns: set[str] | None = None) -> list[dict]:
    file = Path(path)
    if not file.exists(): raise ExecutionError(f"Unable to read file '{path}'")
    try:
        if file.suffix.lower() == ".csv":
            with file.open(newline="", encoding="utf-8") as handle: rows = list(csv.DictReader(handle))
        elif file.suffix.lower() == ".json":
            with file.open(encoding="utf-8") as handle: rows = json.load(handle)
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise ExecutionError("JSON source must be a top-level array of objects")
        else: raise ExecutionError("Only .csv and .json files are supported")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ExecutionError): raise
        raise ExecutionError(f"Unable to read file '{path}': {exc}") from exc
    if required_columns is not None:
        rows = [{key: row.get(key) for key in required_columns} for row in rows]
    return rows


def schema_for(path: str): return infer_schema(load_rows(path))

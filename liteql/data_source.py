"""Data sources: all file-specific logic lives here, away from the compiler phases.

A DataSource can
  * report its schema (column names and inferred types),
  * scan its rows, reading only the requested columns (projection-aware),
  * drop non-matching rows while scanning (predicate-aware).

Values handed to the rest of the system are already typed: NUMBER columns give
int/float, TEXT columns give str, and missing values are None.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .errors import ExecutionError
from .schema import DataType, infer_schema, is_missing

NUMBER_TEXT_RE = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
INTEGER_TEXT_RE = re.compile(r"[+-]?\d+$")
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


class DataSource:
    """Base class: subclasses only implement `_load()` to produce column names and rows."""

    # CSV cells are all strings, so "22" must be recognised as a number.
    # JSON has real numbers, so the string "22" there stays text.
    strings_can_be_numbers = False

    def __init__(self, path: str):
        self.path = path
        self.column_names, self.rows = self._load()
        self.schema = infer_schema(self.column_names, self.rows, self.to_number)

    def _load(self):
        raise NotImplementedError

    def to_number(self, value):
        """Return `value` as int/float, or None if it is not a number."""
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        if self.strings_can_be_numbers and isinstance(value, str):
            text = value.strip()
            if INTEGER_TEXT_RE.match(text):
                return int(text)
            if NUMBER_TEXT_RE.match(text):
                return float(text)
        return None

    def typed(self, name: str, value):
        """Convert a raw cell to its column's type (None if missing)."""
        if is_missing(value):
            return None
        if self.schema.type_of(name) is DataType.NUMBER:
            return self.to_number(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value if isinstance(value, str) else str(value)

    def scan(self, columns=None, predicate=None, stats=None):
        """Yield typed rows.

        columns   - names to read (projection pushdown); None means every column.
        predicate - function(row) -> bool applied while scanning (predicate pushdown).
                    It sees only the columns that were read.
        stats     - optional ExecutionStats to record how much work the scan did.
        """
        names = list(columns) if columns is not None else list(self.column_names)
        for raw in self.rows:
            if stats is not None:
                stats.rows_scanned += 1
            row = {name: self.typed(name, raw.get(name)) for name in names}
            if predicate is not None and not predicate(row):
                continue
            if stats is not None:
                stats.rows_from_scan += 1
                stats.cells_from_scan += len(names)
            yield row


class CSVDataSource(DataSource):
    strings_can_be_numbers = True

    def _load(self):
        try:
            # utf-8-sig silently drops the byte-order mark some spreadsheet exports add.
            with open(self.path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    raise ExecutionError(f"CSV file '{self.path}' has no header row")
                header = [name.strip() for name in header]
                rows = [dict(zip(header, cells)) for cells in reader if cells]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise ExecutionError(f"Unable to read file '{self.path}': {exc}") from exc
        return [name for name in header if name], rows


class JSONDataSource(DataSource):
    def _load(self):
        try:
            with open(self.path, encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:   # ValueError covers bad JSON and bad encoding
            raise ExecutionError(f"Unable to read file '{self.path}': {exc}") from exc
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ExecutionError(f"JSON file '{self.path}' must be a top-level array of objects")
        names = list(dict.fromkeys(key for item in data for key in item))   # union of keys, in order
        return names, data


def resolve_path(name: str, hint_file: str | None = None) -> str:
    """Find the data file named after FROM.

    Search order: the name as written (relative to the current directory), then
    the folder of the --file option, then the project's examples/ folder.
    If --file itself has the same file name, it is used directly.
    """
    if hint_file and Path(hint_file).name == Path(name).name and Path(hint_file).is_file():
        return hint_file
    candidates = [Path(name)]
    if hint_file:
        candidates.append(Path(hint_file).parent / name)
    candidates.append(EXAMPLES_DIR / name)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ExecutionError(f"Unable to read file '{name}' (file not found)")


def open_source(path: str) -> DataSource:
    """Pick the right DataSource from the file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return CSVDataSource(path)
    if suffix == ".json":
        return JSONDataSource(path)
    raise ExecutionError(f"Unsupported file type '{suffix or path}': only .csv and .json files are supported")

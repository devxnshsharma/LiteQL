"""Schema inference, the symbol table, and the CSV/JSON data sources."""

import pytest

from liteql.data_source import open_source, resolve_path
from liteql.errors import ExecutionError
from liteql.schema import DataType as D

NUM, TXT = D.NUMBER, D.TEXT


def test_students_csv_symbol_table(students_csv):
    schema = open_source(students_csv).schema
    assert schema.columns == {"name": TXT, "age": NUM, "city": TXT}
    assert str(schema) == "name -> TEXT\nage  -> NUMBER\ncity -> TEXT"


def test_students_json_gives_the_same_schema(students_json):
    assert open_source(students_json).schema.columns == {"name": TXT, "age": NUM, "city": TXT}


def test_titanic_schema_handles_missing_values(titanic_csv):
    cols = open_source(titanic_csv).schema.columns
    assert cols["Age"] == NUM          # blank ages are ignored, not treated as text
    assert cols["Fare"] == NUM
    assert cols["Name"] == TXT and cols["Sex"] == TXT
    assert cols["Cabin"] == TXT        # mostly blank


def test_csv_numbers_include_decimals_negatives_exponents(write_file):
    path = write_file("n.csv", "a,b,c\n1,-2.5,1e3\n+4,.5,2E-2\n")
    assert set(open_source(path).schema.columns.values()) == {NUM}


def test_one_text_value_makes_the_whole_column_text(write_file):
    path = write_file("m.csv", "a\n1\n2\nthree\n")
    assert open_source(path).schema.columns["a"] == TXT


def test_inference_looks_at_all_rows_not_just_a_sample(write_file):
    rows = "\n".join(str(i) for i in range(500)) + "\nx\n"
    assert open_source(write_file("late.csv", "a\n" + rows)).schema.columns["a"] == TXT


@pytest.mark.parametrize("cell", ["nan", "inf", "1,5", "12abc", "0x10", "1.2.3", "--1"])
def test_non_numbers_are_text(write_file, cell):
    path = write_file("t.csv", f'a\n"{cell}"\n')
    assert open_source(path).schema.columns["a"] == TXT


def test_all_blank_column_is_text(write_file):
    assert open_source(write_file("b.csv", "a,b\n1,\n2,\n")).schema.columns["b"] == TXT


def test_header_only_csv_has_columns_and_no_rows(write_file):
    source = open_source(write_file("h.csv", "a,b\n"))
    assert source.schema.columns == {"a": TXT, "b": TXT} and list(source.scan()) == []


def test_csv_quoted_commas_bom_blank_lines_and_short_rows(write_file):
    path = write_file("q.csv", '﻿name,age\n"Smith, Jo",30\n\nLee\n', encoding="utf-8")
    source = open_source(path)
    assert source.schema.columns == {"name": TXT, "age": NUM}
    assert list(source.scan()) == [{"name": "Smith, Jo", "age": 30}, {"name": "Lee", "age": None}]


def test_csv_header_whitespace_is_stripped(write_file):
    assert list(open_source(write_file("w.csv", " a , b \n1,2\n")).schema.columns) == ["a", "b"]


def test_csv_values_are_typed_when_scanned(students_csv):
    first = next(open_source(students_csv).scan())
    assert first == {"name": "Aarav", "age": 19, "city": "Delhi"}
    assert isinstance(first["age"], int)


def test_json_missing_keys_become_none_and_columns_are_unioned(write_file):
    path = write_file("m.json", '[{"a": 1}, {"a": 2, "b": "x"}, {"b": "y"}]')
    source = open_source(path)
    assert source.schema.columns == {"a": NUM, "b": TXT}
    assert list(source.scan()) == [{"a": 1, "b": None}, {"a": 2, "b": "x"}, {"a": None, "b": "y"}]


def test_json_value_types(write_file):
    path = write_file("t.json", '[{"n": 1, "f": 2.5, "s": "7", "b": true, "x": null, "o": {"k": 1}}]')
    cols = open_source(path).schema.columns
    assert cols == {"n": NUM, "f": NUM, "s": TXT, "b": TXT, "x": TXT, "o": TXT}
    row = next(open_source(path).scan())
    assert (row["s"], row["b"], row["x"], row["o"]) == ("7", "true", None, '{"k": 1}')


def test_json_number_column_with_a_string_becomes_text(write_file):
    path = write_file("x.json", '[{"a": 1}, {"a": "two"}]')
    source = open_source(path)
    assert source.schema.columns["a"] == TXT
    assert [r["a"] for r in source.scan()] == ["1", "two"]


def test_empty_json_array_has_no_columns(write_file):
    assert open_source(write_file("e.json", "[]")).schema.columns == {}


def test_scan_projection_and_predicate(students_csv):
    source = open_source(students_csv)
    rows = list(source.scan(columns=("name", "age"), predicate=lambda r: r["age"] > 25))
    assert rows == [{"name": "Meera", "age": 28}, {"name": "Arjun", "age": 26}, {"name": "Vihaan", "age": 31}]


def test_resolve_case_insensitive_but_exact_match_wins(write_file):
    schema = open_source(write_file("c.csv", "Age,age\n1,2\n")).schema
    assert schema.resolve("age") == "age" and schema.resolve("Age") == "Age"
    assert schema.resolve("AGE") == "Age" and schema.resolve("nope") is None


@pytest.mark.parametrize("name, text, message", [
    ("empty.csv", "", "no header row"),
    ("bad.json", "{not json", "Unable to read file"),
    ("obj.json", '{"a": 1}', "top-level array of objects"),
    ("nums.json", "[1, 2, 3]", "top-level array of objects"),
])
def test_unreadable_files(write_file, name, text, message):
    with pytest.raises(ExecutionError, match=message):
        open_source(write_file(name, text))


def test_undecodable_csv(write_file):
    with pytest.raises(ExecutionError, match="Unable to read file"):
        open_source(write_file("latin.csv", "name\ncaf\xe9\n", encoding="latin-1"))


def test_unsupported_extension(write_file):
    with pytest.raises(ExecutionError, match="only .csv and .json"):
        open_source(write_file("data.txt", "a\n1\n"))


def test_missing_file():
    with pytest.raises(ExecutionError, match="Unable to read file 'nowhere.csv'"):
        resolve_path("nowhere.csv")


def test_resolve_path_search_order(students_csv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_path("students.csv", students_csv) == students_csv   # --file with same name
    assert resolve_path("titanic.csv").endswith("examples/titanic.csv")  # examples/ fallback
    local = tmp_path / "titanic.csv"
    local.write_text("a\n1\n")
    assert resolve_path("titanic.csv") == "titanic.csv"                  # current directory wins

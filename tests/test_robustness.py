"""Fuzzing: nothing a user types may crash LiteQL with a Python exception.

For thousands of random and corrupted queries, the only acceptable outcomes are
a result, or a LiteQLError. Whenever a result is produced, the optimized and
unoptimized plans must agree.
"""

import random

import pytest

from liteql import compile_query
from liteql.errors import LiteQLError

WORDS = ["SELECT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC", "LIMIT", "AND", "OR", "*", ",", ";",
         "=", "!=", ">", "<", ">=", "<=", "name", "age", "city", "Age", "Sex", "Fare", "Cabin", "zzz",
         "0", "5", "-3", "2.5", "20", "'male'", '"Delhi"', "''", "titanic.csv", '"students.csv"',
         "students.json", "(", ")", "@", "'"]
VALID = [
    'SELECT name, age FROM "students.csv" WHERE age > 20 ORDER BY age DESC LIMIT 5',
    "SELECT * FROM titanic.csv WHERE age > 20 AND sex = 'male' order by age desc limit 10",
    'SELECT name FROM "students.json" WHERE city = "Delhi" OR age >= 28 ORDER BY name',
]
MESSY_CSV = 'a,b,c\n1,x,\n,y,3\n"q,r",,-2.5\n7\n\n9,z,1e2\n'
MESSY_JSON = '[{"a": 1, "b": "x"}, {"b": null, "c": [1, 2]}, {"a": "str", "c": true}, {}]'


def attempt(query, path):
    try:
        compilation = compile_query(query, path)
    except LiteQLError:
        return
    assert compilation.run(True)[0] == compilation.run(False)[0], query


def corrupt(rng, text):
    chars = list(text)
    for _ in range(rng.randint(1, 3)):
        i = rng.randrange(len(chars) + 1)
        action = rng.choice(["delete", "insert", "swap"])
        if action == "delete" and chars:
            del chars[min(i, len(chars) - 1)]
        elif action == "insert":
            chars.insert(i, rng.choice("()@#'\" ,;=<>!*-.x1"))
        elif len(chars) > 1:
            j = min(i, len(chars) - 2)
            chars[j], chars[j + 1] = chars[j + 1], chars[j]
    return "".join(chars)


def test_random_token_soup(students_csv, titanic_csv):
    rng = random.Random(2024)
    for _ in range(2500):
        query = " ".join(rng.choice(WORDS) for _ in range(rng.randint(0, 14)))
        attempt(query, rng.choice([students_csv, titanic_csv]))


def test_structured_random_queries(titanic_csv):
    """Mostly-valid queries so the executor, not just the parser, is exercised."""
    rng = random.Random(7)
    columns = ["PassengerId", "Survived", "Pclass", "Name", "Sex", "Age", "SibSp", "Parch", "Ticket", "Fare", "Cabin", "Embarked", "age", "SEX", "zzz"]
    values = ["0", "1", "30", "-1", "2.5", "'male'", "'C85'", "''", "Age", "Fare", "Name"]
    ops = ["=", "!=", ">", "<", ">=", "<="]
    for _ in range(2500):
        select = "*" if rng.random() < 0.3 else ", ".join(rng.sample(columns, rng.randint(1, 3)))
        query = f"SELECT {select} FROM titanic.csv"
        if rng.random() < 0.8:
            comparisons = [f"{rng.choice(columns)} {rng.choice(ops)} {rng.choice(values)}" for _ in range(rng.randint(1, 3))]
            query += " WHERE " + f" {rng.choice(['AND', 'OR'])} ".join(comparisons)
        if rng.random() < 0.5:
            query += f" ORDER BY {rng.choice(columns)} {rng.choice(['', 'ASC', 'DESC'])}"
        if rng.random() < 0.5:
            query += f" LIMIT {rng.choice(['0', '1', '5', '999', '-2', '1.5'])}"
        attempt(query, titanic_csv)


@pytest.mark.parametrize("seed", range(3))
def test_corrupted_valid_queries(seed, students_csv):
    rng = random.Random(seed)
    for _ in range(800):
        attempt(corrupt(rng, rng.choice(VALID)), students_csv)


def test_messy_files_never_crash(write_file):
    csv_path = write_file("messy.csv", MESSY_CSV)
    json_path = write_file("messy.json", MESSY_JSON)
    rng = random.Random(11)
    for path, columns in ((csv_path, ["a", "b", "c", "A", "d"]), (json_path, ["a", "b", "c", "d"])):
        name = path.rsplit("/", 1)[1]
        for _ in range(600):
            query = f"SELECT {'*' if rng.random() < 0.3 else rng.choice(columns)} FROM \"{name}\""
            if rng.random() < 0.8:
                value = rng.choice(["1", "'x'", "-2.5", "''", rng.choice(columns)])
                query += f" WHERE {rng.choice(columns)} {rng.choice(['=', '!=', '>', '<=', '>='])} {value}"
            if rng.random() < 0.6:
                query += f" ORDER BY {rng.choice(columns)} {rng.choice(['ASC', 'DESC'])}"
            if rng.random() < 0.4:
                query += f" LIMIT {rng.randint(0, 5)}"
            attempt(query, path)


@pytest.mark.parametrize("text", ["", " ", "\n\n", "\t", "SELECT\x00", "SELECT é FROM x.csv", "SELECT 名前 FROM x.csv",
                                  "😀", "SELECT " * 500, "'" * 100, "(" * 100])
def test_odd_input_is_a_clean_error(text):
    with pytest.raises(LiteQLError):
        compile_query(text)


def test_where_chain_at_the_limit_works_and_beyond_it_is_a_clean_error(students_csv):
    def query(n):
        return 'SELECT name FROM "students.csv" WHERE ' + " OR ".join(f"age = {i}" for i in range(n))
    assert len(compile_query(query(100), students_csv).run()[0]) == 8
    with pytest.raises(LiteQLError, match="at most 100 comparisons"):
        compile_query(query(101), students_csv)
    with pytest.raises(LiteQLError):
        compile_query(query(5000), students_csv)


def test_long_and_chain(students_csv):
    query = 'SELECT name FROM "students.csv" WHERE ' + " AND ".join(["age > 0"] * 100)
    assert len(compile_query(query, students_csv).run()[0]) == 8

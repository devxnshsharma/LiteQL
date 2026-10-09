"""Phase 1: the lexer turns characters into labelled tokens and does nothing else."""

import pytest

from liteql.errors import LexicalError
from liteql.lexer import tokenize
from liteql.tokens import TokenType as T


def types(text):
    return [t.type for t in tokenize(text)]


def test_age_greater_than_20_matches_the_report_example():
    tokens = tokenize("age > 20")
    assert [str(t) for t in tokens] == ["IDENTIFIER(age)", "GREATER(>)", "NUMBER(20)", "EOF"]


def test_every_keyword_is_recognised_case_insensitively():
    text = "select FROM Where order BY asc DESC limit and OR"
    assert types(text) == [T.SELECT, T.FROM, T.WHERE, T.ORDER, T.BY, T.ASC, T.DESC, T.LIMIT,
                           T.AND, T.OR, T.EOF]


def test_keyword_text_is_preserved():
    assert tokenize("select")[0].text == "select"


def test_identifiers_including_underscores_and_digits():
    tokens = tokenize("name _tmp col_2 Age")
    assert [t.type for t in tokens[:-1]] == [T.IDENTIFIER] * 4
    assert [t.text for t in tokens[:-1]] == ["name", "_tmp", "col_2", "Age"]


def test_keyword_prefix_is_still_an_identifier():
    assert types("selection orders")[:2] == [T.IDENTIFIER, T.IDENTIFIER]


@pytest.mark.parametrize("text", ["0", "20", "3.5", "-4", "-0.25", "007"])
def test_numbers(text):
    token = tokenize(text)[0]
    assert (token.type, token.text) == (T.NUMBER, text)


@pytest.mark.parametrize("quote", ["'", '"'])
def test_strings_with_either_quote(quote):
    token = tokenize(f"{quote}hello world{quote}")[0]
    assert (token.type, token.text) == (T.STRING, "hello world")


def test_other_quote_character_inside_a_string():
    assert tokenize("\"it's\"")[0].text == "it's"


def test_empty_string():
    assert tokenize("''")[0].text == ""


@pytest.mark.parametrize("text, expected", [
    ("=", T.EQUAL), ("!=", T.NOT_EQUAL), (">", T.GREATER), ("<", T.LESS),
    (">=", T.GREATER_EQUAL), ("<=", T.LESS_EQUAL), (",", T.COMMA), ("*", T.STAR), (";", T.SEMICOLON),
])
def test_operators_and_punctuation(text, expected):
    assert types(text) == [expected, T.EOF]


def test_two_character_operators_are_not_split():
    assert types("a>=1") == [T.IDENTIFIER, T.GREATER_EQUAL, T.NUMBER, T.EOF]


def test_whitespace_tabs_and_newlines_are_skipped():
    assert types("SELECT\n\t name  ,\r\n age") == [T.SELECT, T.IDENTIFIER, T.COMMA, T.IDENTIFIER, T.EOF]


def test_no_spaces_needed_around_operators():
    assert types("age>20") == [T.IDENTIFIER, T.GREATER, T.NUMBER, T.EOF]


@pytest.mark.parametrize("name", ["titanic.csv", "data/people.json", "../x/Data_1.CSV", "examples/students.csv"])
def test_bare_file_names(name):
    token = tokenize(name)[0]
    assert (token.type, token.text) == (T.FILENAME, name)


def test_empty_input_gives_only_eof():
    assert types("") == [T.EOF]


def test_token_positions():
    tokens = tokenize("SELECT  name")
    assert [t.position for t in tokens] == [0, 8, 12]


def test_lexer_never_checks_meaning():
    # Nonsense names and a file that does not exist are fine at this phase.
    assert types("SELECT zzz FROM 'nowhere.csv'")[1] == T.IDENTIFIER


@pytest.mark.parametrize("bad", ["@", "#", "$", "%", "!", "?", "&", "^"])
def test_unexpected_character(bad):
    with pytest.raises(LexicalError, match=r"Unexpected character"):
        tokenize(f"SELECT {bad} FROM x")


def test_lone_bang_is_not_an_operator():
    with pytest.raises(LexicalError):
        tokenize("age ! 20")


def test_unterminated_string():
    with pytest.raises(LexicalError, match="Unterminated string"):
        tokenize("name = 'oops")


def test_malformed_number():
    with pytest.raises(LexicalError, match="Malformed number '20abc'"):
        tokenize("age > 20abc")


def test_parentheses_hint():
    with pytest.raises(LexicalError, match="no parentheses"):
        tokenize("SELECT COUNT(*) FROM x.csv")


def test_error_reports_position():
    with pytest.raises(LexicalError) as info:
        tokenize("SELECT @")
    assert info.value.position == 7
    assert str(info.value).startswith("Lexical Error:")

"""
Tests for SQLAlchemy execute_sql_query tool
"""

import pytest
from sqlalchemy import create_engine

from tidewave.sqlalchemy import execute_sql_query as esq


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def execute_sql_query(engine):
    """Create the execute_sql_query function with the test engine."""
    return esq(engine)


def test_execute_simple_select_query(execute_sql_query):
    """Test executing a simple SELECT query with parameter."""
    result = execute_sql_query("SELECT 123 + ?", [456])

    expected = {"columns": ["123 + ?"], "num_rows": 1, "rows": [(579,)]}
    assert result == repr(expected)


def test_execute_select_query_multiple_columns(execute_sql_query):
    """Test executing a SELECT query with multiple columns."""
    result = execute_sql_query("SELECT 42 as answer, 'hello' as greeting, ? as param", ["world"])

    expected = {
        "columns": ["answer", "greeting", "param"],
        "num_rows": 1,
        "rows": [(42, "hello", "world")],
    }
    assert result == repr(expected)


def test_execute_query_no_results(execute_sql_query):
    """Test executing a SELECT query that returns no results."""
    result = execute_sql_query("SELECT 1 WHERE 1 = 0")

    expected = {"columns": ["1"], "num_rows": 0, "rows": []}
    assert result == repr(expected)


def test_execute_query_result_limit(execute_sql_query):
    """Test that results are limited to 50 rows."""
    # Create a table with more than 50 rows
    execute_sql_query("CREATE TABLE test_limit (id INTEGER)")

    # Insert 60 rows
    for i in range(60):
        execute_sql_query("INSERT INTO test_limit (id) VALUES (?)", [i])

    result = execute_sql_query("SELECT * FROM test_limit ORDER BY id")

    assert "Query returned 60 rows. Only the first 50 rows" in result
    assert "Use LIMIT + OFFSET" in result
    assert "'num_rows': 50" in result


def test_execute_query_with_invalid_sql(execute_sql_query):
    """Test executing an invalid SQL query."""
    with pytest.raises(Exception):  # noqa: B017
        execute_sql_query("INVALID SQL QUERY")


def test_execute_command_with_no_results(execute_sql_query):
    """Test executing a command that returns no results."""
    result = execute_sql_query("CREATE TABLE test_no_results (id INTEGER)")
    assert result == "OK"

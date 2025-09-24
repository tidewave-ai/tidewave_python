"""
Tests for Django execute_sql_query tool
"""

from django.test import TestCase

from tidewave.django.tools import execute_sql_query


class TestDjangoExecuteSqlQuery(TestCase):
    def test_execute_simple_select_query(self):
        """Test executing a simple SELECT query with parameter."""
        result = execute_sql_query("SELECT 123 + %s", [456])

        expected = {"columns": ["123 + ?"], "num_rows": 1, "rows": [(579,)]}
        self.assertEqual(result, repr(expected))

    def test_execute_select_query_multiple_columns(self):
        """Test executing a SELECT query with multiple columns."""
        result = execute_sql_query(
            "SELECT 42 as answer, 'hello' as greeting, %s as param", ["world"]
        )

        expected = {
            "columns": ["answer", "greeting", "param"],
            "num_rows": 1,
            "rows": [(42, "hello", "world")],
        }
        self.assertEqual(result, repr(expected))

    def test_execute_query_no_results(self):
        """Test executing a SELECT query that returns no results."""
        result = execute_sql_query("SELECT 1 WHERE 1 = 0")

        expected = {"columns": ["1"], "num_rows": 0, "rows": []}
        self.assertEqual(result, repr(expected))

    def test_execute_query_result_limit(self):
        """Test that results are limited to 50 rows."""

        result = execute_sql_query("""
            WITH RECURSIVE numbers(n) AS (
                SELECT 0
                UNION ALL
                SELECT n+1 FROM numbers WHERE n < 59
            )
            SELECT n FROM numbers
        """)

        self.assertIn("Query returned 60 rows. Only the first 50 rows", result)
        self.assertIn("Use LIMIT + OFFSET", result)
        self.assertIn("'num_rows': 50", result)

    def test_execute_query_with_invalid_sql(self):
        """Test executing an invalid SQL query."""
        with self.assertRaises(Exception):  # noqa: B017
            execute_sql_query("INVALID SQL QUERY")

    def test_execute_query_with_wrong_parameter_count(self):
        """Test executing a query with wrong number of parameters."""
        with self.assertRaises(Exception):  # noqa: B017
            execute_sql_query("SELECT %s + %s", [1])  # Missing one parameter

    def test_execute_command_with_no_results(self):
        """Test executing a command that returns no results."""
        result = execute_sql_query("CREATE TABLE test_no_results (id INTEGER)")
        self.assertEqual(result, "OK")

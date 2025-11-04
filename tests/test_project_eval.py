import json
import sys
import unittest

import pytest

from tidewave.tools.project_eval import project_eval


class TestPythonEvalTool(unittest.TestCase):
    def _collect_output(self, result):
        if isinstance(result, str):
            try:
                return json.loads(result)
            except Exception:
                return result
        return result

    def test_successful_python_execution(self):
        """Test code execution (expression)"""
        result = project_eval("1 + 2", json=True)
        output = self._collect_output(result)
        self.assertEqual(output["result"], 3)
        self.assertTrue(output["success"])
        self.assertIsNone(output["error"])

    def test_successful_python_exec_statement(self):
        """Test code execution (statement)"""
        code = "result = 5 * 7"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertEqual(output["result"], 35)
        self.assertTrue(output["success"])
        self.assertIsNone(output["error"])

    def test_python_execution_exception(self):
        """Test execution with exception"""
        code = "raise ValueError('fail')"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertIn("fail", output["result"])
        self.assertFalse(output["success"])
        self.assertIn("fail", output["error"])

    @pytest.mark.skipif(
        sys.version_info >= (3, 11),
        reason="Test only for Python < 3.11",
    )
    def test_python_execution_legacy_syntax_error(self):
        """Test execution with syntax error"""
        code = "def bad:"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertIn("invalid syntax", output["result"])
        self.assertFalse(output["success"])
        self.assertIn("invalid syntax", output["error"])

    @pytest.mark.skipif(
        sys.version_info < (3, 11),
        reason="Improved error messages in 3.11+",
    )
    def test_python_execution_syntax_error(self):
        """Test execution with syntax error"""
        code = "def bad:"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertIn("expected '('", output["result"])
        self.assertFalse(output["success"])
        self.assertIn("expected '('", output["error"])

    def test_python_execution_timeout(self):
        """Test execution timeout"""
        code = "while True: pass"
        result = project_eval(code, timeout=1, json=True)
        output = self._collect_output(result)
        self.assertIn("timed out", output["result"])
        self.assertFalse(output["success"])
        self.assertIn("timed out", output["error"])

    def test_non_json_output(self):
        """Test non-JSON output"""
        code = "print('hello world')\nresult = 42"
        result = project_eval(code, json=False)
        expected_output = "STDOUT:\nhello world\n\nSTDERR:\n\nResult:\n42"
        self.assertEqual(result, expected_output)

    def test_large_output(self):
        """Test large output"""
        code = "'a' * 1_000_000"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertEqual(len(output["result"]), 1_000_000)

    def test_multiline_code_execution(self):
        """Test multi-line Python code"""
        code = "a = 10\nb = 20\nresult = a + b"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertEqual(output["result"], 30)
        self.assertTrue(output["success"])
        self.assertIsNone(output["error"])

    def test_import_django_and_get_version(self):
        """Test importing Django and getting its version"""
        code = "import django;\nresult = django.get_version()"
        result = project_eval(code, json=True)
        output = self._collect_output(result)
        self.assertTrue(isinstance(output["result"], str))
        self.assertRegex(output["result"], r"^\d+\.\d+(\.\d+)?$")
        self.assertTrue(output["success"])
        self.assertIsNone(output["error"])

    def test_project_eval_with_arguments(self):
        """Test passing arguments to project_eval and using them in code"""
        code = "result = arguments[0] + arguments[1]"
        result = project_eval(code, arguments=[10, 32], json=True)
        output = self._collect_output(result)
        self.assertEqual(output["result"], 42)
        self.assertTrue(output["success"])
        self.assertIsNone(output["error"])

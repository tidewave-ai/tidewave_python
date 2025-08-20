"""
Tests for individual math tools
"""

import unittest
from tidewave.tools.base import MCPTool
from tidewave.tools.math_tools import add, multiply


class TestAddTool(unittest.TestCase):
    """Test the add tool"""

    def setUp(self):
        self.tool = MCPTool(add)

    def test_add_integers(self):
        """Test adding integers"""
        result = self.tool.validate_and_call({"a": 10, "b": 5})
        self.assertIn("content", result)
        self.assertIn("15.0", result["content"][0]["text"])

    def test_add_floats(self):
        """Test adding floating point numbers"""
        result = self.tool.validate_and_call({"a": 3.14, "b": 2.86})
        self.assertIn("content", result)
        self.assertIn("6.0", result["content"][0]["text"])

    def test_add_mixed_types(self):
        """Test adding integer and float"""
        result = self.tool.validate_and_call({"a": 5, "b": 2.5})
        self.assertIn("content", result)
        self.assertIn("7.5", result["content"][0]["text"])

    def test_add_missing_argument(self):
        """Test add tool with missing arguments"""
        result = self.tool.validate_and_call({"a": 5})
        self.assertIn("error", result)
        self.assertIn("Invalid arguments", result["error"])

    def test_add_invalid_types(self):
        """Test add tool with invalid argument types"""
        result = self.tool.validate_and_call({"a": "not_a_number", "b": 5})
        self.assertIn("error", result)
        self.assertIn("Invalid arguments", result["error"])

    def test_add_schema(self):
        """Test add tool schema"""
        schema = self.tool.input_schema
        self.assertEqual(len(schema["properties"]), 2)
        self.assertIn("a", schema["properties"])
        self.assertIn("b", schema["properties"])
        self.assertEqual(schema["required"], ["a", "b"])
        self.assertEqual(schema["properties"]["a"]["type"], "number")
        self.assertEqual(schema["properties"]["b"]["type"], "number")


class TestMultiplyTool(unittest.TestCase):
    """Test the multiply tool"""

    def setUp(self):
        self.tool = MCPTool(multiply)

    def test_multiply_basic(self):
        """Test basic multiplication"""
        result = self.tool.validate_and_call({"x": 4, "y": 5})
        self.assertIn("content", result)
        self.assertIn("20.0", result["content"][0]["text"])

    def test_multiply_with_precision(self):
        """Test multiplication with custom precision"""
        result = self.tool.validate_and_call({"x": 3.14159, "y": 2, "precision": 3})
        self.assertIn("content", result)
        self.assertIn("6.283", result["content"][0]["text"])

    def test_multiply_zero_precision(self):
        """Test multiplication with zero precision (integer result)"""
        result = self.tool.validate_and_call({"x": 3.7, "y": 2, "precision": 0})
        self.assertIn("content", result)
        # Should show integer result without decimal
        text = result["content"][0]["text"]
        self.assertIn("7", text)
        self.assertNotIn(".", text.split(" is ")[1])  # No decimal in result part

    def test_multiply_default_precision(self):
        """Test multiplication with default precision (2)"""
        result = self.tool.validate_and_call({"x": 1.234, "y": 2})
        self.assertIn("content", result)
        self.assertIn(
            "2.47", result["content"][0]["text"]
        )  # Rounded to 2 decimal places

    def test_multiply_schema(self):
        """Test multiply tool schema"""
        schema = self.tool.input_schema
        self.assertEqual(len(schema["properties"]), 3)
        self.assertIn("x", schema["properties"])
        self.assertIn("y", schema["properties"])
        self.assertIn("precision", schema["properties"])
        self.assertEqual(schema["required"], ["x", "y"])  # precision is optional
        self.assertEqual(schema["properties"]["precision"]["default"], 2)

    def test_multiply_invalid_precision_type(self):
        """Test multiply with invalid precision type"""
        result = self.tool.validate_and_call({"x": 3, "y": 4, "precision": "not_int"})
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()

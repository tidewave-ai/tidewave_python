"""
Tests for MCPTool base class
"""

import json
import unittest
from typing import Optional

from tidewave.tools.base import MCPTool


class TestMCPTool(unittest.TestCase):
    """Test MCPTool class functionality"""

    def test_tool_with_docstring_and_types(self):
        """Test tool creation with proper docstring and type hints"""

        def sample_tool(x: int, y: str = "default") -> str:
            """
            This is a sample tool.
            It does sample things.
            """
            return f"{x}: {y}"

        tool = MCPTool(sample_tool)

        # Test basic properties
        self.assertEqual(tool.name, "sample_tool")
        self.assertEqual(tool.description, "This is a sample tool.")

        # Test schema generation
        schema = tool.input_schema
        self.assertEqual(schema["type"], "object")
        self.assertIn("x", schema["properties"])
        self.assertIn("y", schema["properties"])
        self.assertEqual(schema["required"], ["x"])

        # Test that x is integer type
        self.assertEqual(schema["properties"]["x"]["type"], "integer")
        # Test that y has default value
        self.assertEqual(schema["properties"]["y"]["default"], "default")

    def test_tool_definition_format(self):
        """Test MCP tool definition format"""

        def test_func(a: float, b: int) -> str:
            """Test function description"""
            return str(a + b)

        tool = MCPTool(test_func)
        definition = tool.to_mcp_tool()

        # Test structure
        self.assertIn("name", definition)
        self.assertIn("description", definition)
        self.assertIn("inputSchema", definition)

        self.assertEqual(definition["name"], "test_func")
        self.assertEqual(definition["description"], "Test function description")

        # Test schema is valid JSON
        schema_json = json.dumps(definition["inputSchema"])
        self.assertIsInstance(json.loads(schema_json), dict)

    def test_requires_type_hints(self):
        """Test that functions without type hints fail"""

        def no_types(a, b):
            """Function without type hints"""
            return a + b

        with self.assertRaises(ValueError) as context:
            MCPTool(no_types)

        self.assertIn("missing type hint", str(context.exception))
        self.assertIn("explicit type annotations", str(context.exception))

    def test_requires_docstring(self):
        """Test that functions without docstrings get default description"""

        def no_docstring(x: int) -> str:
            return str(x)

        tool = MCPTool(no_docstring)
        self.assertEqual(tool.description, "Execute no_docstring function")

    def test_validation_success(self):
        """Test successful argument validation"""

        def add_numbers(a: int, b: int) -> str:
            """Add two numbers"""
            return f"Result: {a + b}"

        tool = MCPTool(add_numbers)
        result = tool.validate_and_call({"a": 5, "b": 3})

        self.assertIn("content", result)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("Result: 8", result["content"][0]["text"])

    def test_validation_error(self):
        """Test validation error handling"""

        def strict_func(x: int) -> str:
            """Requires integer"""
            return str(x)

        tool = MCPTool(strict_func)
        result = tool.validate_and_call({"x": "not_an_int"})

        self.assertIn("error", result)
        self.assertIn("Invalid arguments", result["error"])

    def test_missing_required_args(self):
        """Test missing required arguments"""

        def requires_both(a: int, b: int) -> str:
            """Requires both args"""
            return str(a + b)

        tool = MCPTool(requires_both)
        result = tool.validate_and_call({"a": 5})  # Missing 'b'

        self.assertIn("error", result)
        self.assertIn("Invalid arguments", result["error"])

    def test_optional_args(self):
        """Test optional arguments with defaults"""

        def with_optional(required: int, optional: str = "default") -> str:
            """Has optional arg"""
            return f"{required}-{optional}"

        tool = MCPTool(with_optional)

        # Test with only required arg
        result1 = tool.validate_and_call({"required": 42})
        self.assertIn("42-default", result1["content"][0]["text"])

        # Test with both args
        result2 = tool.validate_and_call({"required": 42, "optional": "custom"})
        self.assertIn("42-custom", result2["content"][0]["text"])

    def test_function_execution_error(self):
        """Test handling of function execution errors"""

        def failing_func(x: int) -> str:
            """This function fails"""
            raise ValueError("Something went wrong")

        tool = MCPTool(failing_func)
        result = tool.validate_and_call({"x": 5})

        self.assertIn("error", result)
        self.assertIn("Error executing failing_func", result["error"])

    def test_tool_with_no_arguments(self):
        """Test tool with no arguments"""

        def get_current_time() -> str:
            """Get the current timestamp"""
            return "2024-01-01 12:00:00"

        tool = MCPTool(get_current_time)

        # Test schema generation
        schema = tool.input_schema
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"], {})
        self.assertEqual(schema["required"], [])

        # Test calling with empty args
        result = tool.validate_and_call({})
        self.assertIn("content", result)
        self.assertEqual(result["content"][0]["type"], "text")
        self.assertIn("2024-01-01 12:00:00", result["content"][0]["text"])

    def test_tool_with_optional_type(self):
        """Test tool with Optional type annotation"""

        def greet_user(name: Optional[str] = None) -> str:
            """Greet a user by name or generically"""
            if name:
                return f"Hello, {name}!"
            return "Hello there!"

        tool = MCPTool(greet_user)

        # Test schema generation - Optional should allow null
        schema = tool.input_schema
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertEqual(schema["required"], [])  # Optional with default

        # The schema should allow both string and null
        name_prop = schema["properties"]["name"]
        self.assertIn("anyOf", name_prop)
        types = [item["type"] for item in name_prop["anyOf"]]
        self.assertIn("string", types)
        self.assertIn("null", types)

        # Test calling with no args
        result1 = tool.validate_and_call({})
        self.assertIn("Hello there!", result1["content"][0]["text"])

        # Test calling with name
        result2 = tool.validate_and_call({"name": "Alice"})
        self.assertIn("Hello, Alice!", result2["content"][0]["text"])

        # Test calling with explicit None
        result3 = tool.validate_and_call({"name": None})
        self.assertIn("Hello there!", result3["content"][0]["text"])

    def test_tool_with_list_type(self):
        """Test tool with List type annotation"""

        def process_items(items: list[str]) -> str:
            """Process a list of string items"""
            return f"Processed {len(items)} items: {', '.join(items)}"

        tool = MCPTool(process_items)

        # Test schema generation
        schema = tool.input_schema
        self.assertEqual(schema["type"], "object")
        self.assertIn("items", schema["properties"])
        self.assertEqual(schema["required"], ["items"])

        # Check array type in schema
        items_prop = schema["properties"]["items"]
        self.assertEqual(items_prop["type"], "array")
        self.assertIn("items", items_prop)
        self.assertEqual(items_prop["items"]["type"], "string")

        # Test calling with list
        result1 = tool.validate_and_call({"items": ["apple", "banana", "cherry"]})
        self.assertIn(
            "Processed 3 items: apple, banana, cherry", result1["content"][0]["text"]
        )

        # Test calling with empty list
        result2 = tool.validate_and_call({"items": []})
        self.assertIn("Processed 0 items:", result2["content"][0]["text"])

        # Test validation error with wrong type
        result3 = tool.validate_and_call({"items": "not_a_list"})
        self.assertIn("error", result3)
        self.assertIn("Invalid arguments", result3["error"])

    def test_hidden_parameters(self):
        """Test function with mix of visible, hidden, and optional parameters"""

        def complex_func(
            required_visible: str,
            optional_visible: int = 42,
            *,
            hidden_optional: bool = True,
        ) -> str:
            """Complex function with mixed parameter types"""
            return f"{required_visible}-{optional_visible}-{hidden_optional}"

        tool = MCPTool(complex_func)

        # Schema should only show visible parameters
        schema = tool.input_schema
        self.assertIn("required_visible", schema["properties"])
        self.assertIn("optional_visible", schema["properties"])
        self.assertNotIn("hidden_optional", schema["properties"])
        self.assertEqual(schema["required"], ["required_visible"])

        result = tool.validate_and_call(
            {
                "required_visible": "test",
                "optional_visible": 99,
            }
        )

        self.assertIn("content", result)
        self.assertIn("test-99-True", result["content"][0]["text"])

        result = tool.validate_and_call(
            {
                "required_visible": "test",
                "optional_visible": 99,
                "hidden_optional": False,
            }
        )

        self.assertIn("content", result)
        self.assertIn("test-99-False", result["content"][0]["text"])

    def test_hidden_parameter_requires_default(self):
        """Test that hidden parameters without defaults raise an error"""

        def func_with_required_hidden(visible: str, *, hidden_param: int) -> str:
            """Function with required hidden parameter (should fail)"""
            return f"visible: {visible}, hidden: {hidden_param}"

        with self.assertRaises(ValueError) as context:
            MCPTool(func_with_required_hidden)

        self.assertIn(
            "Hidden parameter 'hidden_param' must have a default value",
            str(context.exception),
        )
        self.assertIn("Hidden parameters cannot be required", str(context.exception))

"""
Base MCP Tool functionality
"""

import inspect
from typing import Any, Callable, get_type_hints

from pydantic import ValidationError, create_model


class MCPTool:
    """
    Base class for MCP tools that auto-generates JSON schema from Python
    function signatures
    """

    def __init__(self, func: Callable):
        self.func = func
        self.name = func.__name__
        self.description = self._get_description()
        self.input_schema = self._generate_schema()

    def _get_description(self) -> str:
        """Extract description from function docstring"""
        if self.func.__doc__:
            # Get the first line of the docstring, cleaned up
            lines = self.func.__doc__.strip().split("\n")
            return lines[0].strip()
        return f"Execute {self.name} function"

    def _generate_schema(self) -> dict[str, Any]:
        """Generate JSON schema from function signature using pydantic"""
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)

        # Build field definitions for pydantic model
        fields = {}
        required_fields = []

        for param_name, param in sig.parameters.items():
            # Require explicit type hints
            if param_name not in type_hints:
                raise ValueError(
                    f"Parameter '{param_name}' missing type hint. "
                    "All parameters must have explicit type annotations."
                )

            param_type = type_hints[param_name]

            # Handle default values
            if param.default == inspect.Parameter.empty:
                # Required parameter
                fields[param_name] = (param_type, ...)
                required_fields.append(param_name)
            else:
                # Optional parameter with default
                fields[param_name] = (param_type, param.default)

        # Create a temporary pydantic model
        temp_model = create_model(f"{self.name}_params", **fields)
        schema = temp_model.model_json_schema()

        # Convert to MCP format
        return {
            "type": "object",
            "properties": schema.get("properties", {}),
            "required": required_fields,
        }

    def validate_and_call(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments using pydantic and call the function"""
        try:
            # Create validation model from schema
            sig = inspect.signature(self.func)
            type_hints = get_type_hints(self.func)

            fields = {}
            for param_name, param in sig.parameters.items():
                param_type = type_hints.get(param_name, str)
                if param.default == inspect.Parameter.empty:
                    fields[param_name] = (param_type, ...)
                else:
                    fields[param_name] = (param_type, param.default)

            validator_model = create_model(f"{self.name}_validator", **fields)

            # Validate input
            validated_args = validator_model(**args)

            # Call function with validated arguments
            result = self.func(**validated_args.model_dump())

            # Format result for MCP
            return {"content": [{"type": "text", "text": str(result)}]}

        except ValidationError as e:
            return {"error": f"Invalid arguments: {str(e)}"}
        except Exception as e:
            return {"error": f"Error executing {self.name}: {str(e)}"}

    def to_mcp_tool(self) -> dict[str, Any]:
        """Convert to MCP tool definition format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

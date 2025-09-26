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
        self.model = self._create_model()
        self.input_schema = self._generate_schema()

    def _get_description(self) -> str:
        """Extract description from function docstring"""
        if self.func.__doc__:
            # Get the first line of the docstring, cleaned up
            lines = self.func.__doc__.strip().split("\n")
            return lines[0].strip()
        return f"Execute {self.name} function"

    def _create_model(self):
        """
        Create pydantic model from function signature, including all parameters
        (visible and hidden)
        """
        sig = inspect.signature(self.func)
        type_hints = get_type_hints(self.func)

        fields = {}
        for param_name, param in sig.parameters.items():
            # For hidden parameters, ensure they have defaults
            if param.kind == inspect.Parameter.KEYWORD_ONLY:
                if param.default == inspect.Parameter.empty:
                    raise ValueError(
                        f"Hidden parameter '{param_name}' must have a default value. "
                        "Hidden parameters cannot be required."
                    )

            # Require explicit type hints
            if param_name not in type_hints:
                raise ValueError(
                    f"Parameter '{param_name}' missing type hint. "
                    "All parameters must have explicit type annotations."
                )

            param_type = type_hints[param_name]

            # Handle default values
            if param.default == inspect.Parameter.empty:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (param_type, param.default)

        return create_model(f"{self.name}_model", **fields)

    def _generate_schema(self) -> dict[str, Any]:
        """
        Generate JSON schema from the pydantic model, excluding hidden parameters
        """
        sig = inspect.signature(self.func)
        schema = self.model.model_json_schema()

        # Build required fields list, excluding hidden parameters
        required_fields = []
        for param_name, param in sig.parameters.items():
            # Skip keyword-only parameters (hidden parameters after *)
            if param.kind == inspect.Parameter.KEYWORD_ONLY:
                continue
            if param.default == inspect.Parameter.empty:
                required_fields.append(param_name)

        # Filter properties to exclude hidden parameters
        filtered_properties = {}
        for param_name, param in sig.parameters.items():
            if param.kind != inspect.Parameter.KEYWORD_ONLY:
                if param_name in schema.get("properties", {}):
                    filtered_properties[param_name] = schema["properties"][param_name]

        # Convert to MCP format
        return {
            "type": "object",
            "properties": filtered_properties,
            "required": required_fields,
        }

    def validate_and_call(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments using the shared pydantic model and call the function"""
        try:
            # Validate input using the shared model
            validated_args = self.model(**args)

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

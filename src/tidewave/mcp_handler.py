"""
MCP (Model Context Protocol) Handler
Handles MCP-specific message processing and tool management
"""

import json
import logging
from typing import Any, Callable, Optional

from .tools.base import MCPTool


class MCPHandler:
    """Handles MCP protocol messages and tool management"""

    PROTOCOL_VERSION = "2025-03-26"
    VERSION = "1.0.0"

    def __init__(self, tool_functions: list[Callable]):
        """Initialize MCP handler

        Args:
            tool_functions: List of tool functions to make available
        """
        self.tools = {}
        self.logger = logging.getLogger(__name__)
        self._init_tools(tool_functions)

    def _init_tools(self, tool_functions: list[Callable]):
        """Initialize available MCP tools from provided functions"""
        self.tools = {}
        for func in tool_functions:
            tool = MCPTool(func)
            self.tools[tool.name] = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "tool_instance": tool,
            }

    def handle_request(self, environ: dict[str, Any], start_response: Callable):
        """Handle MCP POST request"""
        try:
            # Read request body
            content_length = int(environ.get("CONTENT_LENGTH", 0))
            if content_length == 0:
                return self._send_jsonrpc_error(
                    start_response, None, -32600, "Empty request body"
                )

            body = environ["wsgi.input"].read(content_length)

            # Parse JSON
            try:
                message = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self._send_jsonrpc_error(
                    start_response, None, -32700, "Parse error"
                )

            # Validate JSON-RPC format
            validation_error = self._validate_jsonrpc_message(message)
            if validation_error:
                return self._send_jsonrpc_error(
                    start_response, None, -32600, validation_error
                )

            # Handle the message
            response = self._handle_message(message)

            if response is None:
                # Notification with no response
                return self._send_json_response(
                    start_response, {"status": "ok"}, status=202
                )
            else:
                return self._send_json_response(start_response, response)

        except Exception as e:
            self.logger.error(f"Error handling MCP request: {str(e)}")
            return self._send_jsonrpc_error(
                start_response, None, -32603, "Internal error"
            )

    def _validate_jsonrpc_message(self, message: dict[str, Any]) -> Optional[str]:
        """
        Validate JSON-RPC 2.0 message format.

        Returns error message if invalid, None if valid.
        """
        if not isinstance(message, dict):
            return "Message must be a JSON object"

        if message.get("jsonrpc") != "2.0":
            return "Invalid JSON-RPC version"

        has_id = "id" in message
        has_method = "method" in message
        has_result = "result" in message

        if has_method and has_id:
            # Request
            return None
        elif has_method and not has_id:
            # Notification
            return None
        elif has_id and has_result:
            # Response (e.g., to ping)
            return None
        else:
            return "Invalid JSON-RPC message structure"

    def _handle_message(self, message: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Handle MCP message routing"""
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params", {})

        self.logger.info(f"Handling MCP method: {method}, ID: {request_id}")
        self.logger.debug(f"Full message: {message}")

        # Handle notifications (no response expected)
        if method == "notifications/initialized":
            self.logger.info("Received initialized notification")
            return None
        elif method == "notifications/cancelled":
            self.logger.info(f"Request cancelled: {params}")
            return None

        # Handle requests (response expected)
        if method == "ping":
            return self._handle_ping(request_id)
        elif method == "initialize":
            return self._handle_initialize(request_id, params)
        elif method == "tools/list":
            return self._handle_list_tools(request_id, params)
        elif method == "tools/call":
            return self._handle_call_tool(request_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"name": method},
                },
            }

    def _handle_ping(self, request_id: Any) -> dict[str, Any]:
        """Handle ping request"""
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    def _handle_initialize(
        self, request_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle initialize request"""
        client_version = params.get("protocolVersion")

        # Validate protocol version
        if not client_version:
            return self._create_error_response(
                request_id, -32602, "Protocol version is required"
            )

        if client_version < self.PROTOCOL_VERSION:
            return self._create_error_response(
                request_id,
                -32602,
                (
                    "Unsupported protocol version. "
                    f"Server supports {self.PROTOCOL_VERSION} or later"
                ),
            )

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "Python MCP Server", "version": self.VERSION},
                "tools": self._get_tool_list(),
            },
        }

    def _handle_list_tools(
        self, request_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle tools/list request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": self._get_tool_list()},
        }

    def _handle_call_tool(
        self, request_id: Any, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._create_error_response(
                request_id, -32602, "Tool name is required"
            )

        if tool_name not in self.tools:
            return self._create_error_response(
                request_id, -32601, f"Tool '{tool_name}' not found"
            )

        try:
            tool = self.tools[tool_name]
            result = tool["tool_instance"].validate_and_call(arguments)

            if "error" in result:
                # Error should be returned as successful response with isError: true
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": result["error"]}],
                        "isError": True,
                    },
                }
            else:
                return {"jsonrpc": "2.0", "id": request_id, "result": result}

        except Exception as e:
            self.logger.error(f"Tool execution error: {str(e)}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"Tool execution failed: {str(e)}"}
                    ],
                    "isError": True,
                },
            }

    def _get_tool_list(self) -> list[dict[str, Any]]:
        """Get list of available tools"""
        return [
            {
                "name": tool["name"],
                "description": tool["description"].strip(),
                "inputSchema": tool["inputSchema"],
            }
            for tool in self.tools.values()
        ]

    def _create_error_response(
        self, request_id: Any, code: int, message: str
    ) -> dict[str, Any]:
        """Create JSON-RPC error response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def _send_json_response(
        self, start_response: Callable, data: dict[str, Any], status: int = 200
    ):
        """Send JSON response"""
        json_data = json.dumps(data)
        response_headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(json_data))),
        ]

        status_map = {200: "OK", 202: "Accepted"}
        status_text = f"{status} {status_map.get(status, 'Error')}"
        start_response(status_text, response_headers)
        return [json_data.encode("utf-8")]

    def _send_jsonrpc_error(
        self, start_response: Callable, request_id: Any, code: int, message: str
    ):
        """Send JSON-RPC error response"""
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
        return self._send_json_response(start_response, error_response, status=200)

"""
MCP Integration Tests
"""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock
from tidewave.middleware import Middleware
from tidewave.mcp_handler import MCPHandler
from tidewave.tools import add, multiply


class TestMCPIntegration(unittest.TestCase):
    """Integration tests with real tools"""

    def setUp(self):
        tool_functions = [add, multiply]
        mcp_handler = MCPHandler(tool_functions)
        self.middleware = Middleware(Mock(), mcp_handler, {})
        self.start_response = Mock()

    def _create_environ(self, body):
        return {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/tidewave/mcp",
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": BytesIO(body.encode("utf-8")),
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": "application/json",
        }

    def test_ping_request(self):
        """Test MCP ping request"""
        message = {"jsonrpc": "2.0", "method": "ping", "id": 1}
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertEqual(response_data["result"], {})

    def test_tools_list_request(self):
        """Test MCP tools/list request"""
        message = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("tools", response_data["result"])

        # Should have both tools
        tools = response_data["result"]["tools"]
        self.assertEqual(len(tools), 2)
        tool_names = [tool["name"] for tool in tools]
        self.assertIn("add", tool_names)
        self.assertIn("multiply", tool_names)

    def test_tool_call_success(self):
        """Test successful tool call"""
        message = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": "add", "arguments": {"a": 5, "b": 3}},
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("result", response_data)
        self.assertIn("content", response_data["result"])

        # Check that the result contains the sum
        content = response_data["result"]["content"][0]["text"]
        self.assertIn("8", content)  # 5 + 3 = 8

    def test_nonexistent_tool_call(self):
        """Test calling non-existent tool"""
        message = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": "nonexistent", "arguments": {}},
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["code"], -32601)

    def test_initialize_method(self):
        """Test MCP initialize method with protocol version"""
        message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": "2025-03-26"}
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("result", response_data)

        result_data = response_data["result"]
        self.assertEqual(result_data["protocolVersion"], "2025-03-26")
        self.assertIn("capabilities", result_data)
        self.assertIn("serverInfo", result_data)
        self.assertIn("tools", result_data)

    def test_initialize_unsupported_protocol_version(self):
        """Test initialize request with unsupported protocol version"""
        message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": "2020-01-01"}  # Old version
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["code"], -32602)
        self.assertIn("Unsupported protocol version", response_data["error"]["message"])

    def test_protocol_version_compatibility(self):
        """Test protocol version compatibility with newer client versions"""
        message = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {"protocolVersion": "2025-12-31"}  # Future version
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("result", response_data)

        # Should accept future versions and return server's supported version
        result_data = response_data["result"]
        self.assertEqual(result_data["protocolVersion"], "2025-03-26")

    def test_tool_call_invalid_arguments(self):
        """Test tool call with invalid argument types"""
        message = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": "add", "arguments": {"a": "not_a_number", "b": 3}},
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("result", response_data)

        # Should return isError: true for validation errors
        self.assertTrue(response_data["result"].get("isError", False))
        self.assertIn("content", response_data["result"])

    def test_tool_call_missing_arguments(self):
        """Test tool call with missing required arguments"""
        message = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": "add", "arguments": {"a": 5}},  # Missing 'b'
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)
        self.assertIn("result", response_data)

        # Should return isError: true for validation errors
        self.assertTrue(response_data["result"].get("isError", False))

    def test_cancelled_notification_handling(self):
        """Test handling of cancelled notifications"""
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": "abc123", "reason": "user_cancelled"}
            # No 'id' field - this is a notification
        }
        body = json.dumps(message)
        environ = self._create_environ(body)

        result = self.middleware(environ, self.start_response)

        # Should return 202 Accepted with status response
        call_args = self.start_response.call_args[0]
        self.assertIn("202", call_args[0])

        response_data = json.loads(b"".join(result).decode("utf-8"))
        self.assertEqual(response_data["status"], "ok")


if __name__ == "__main__":
    unittest.main()
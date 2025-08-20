"""
Tests for MCP WSGI Middleware - focusing on middleware concerns only
"""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock
from tidewave import Middleware


class TestMiddleware(unittest.TestCase):
    """Test MCP middleware functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.demo_app = Mock()
        self.demo_app.return_value = [b"demo response"]

        self.config = {
            "debug": True,
            "allow_remote_access": True,  # Allow for testing
            "allowed_origins": ["http://localhost:3000"],
        }

        self.middleware = Middleware(self.demo_app, self.config)
        self.start_response = Mock()

    def _create_environ(
        self, path="/", method="GET", body=None, remote_addr="127.0.0.1", origin=None
    ):
        """Create WSGI environ dict for testing"""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "REMOTE_ADDR": remote_addr,
            "wsgi.input": BytesIO(body.encode("utf-8") if body else b""),
            "CONTENT_LENGTH": str(len(body.encode("utf-8"))) if body else "0",
        }

        if origin:
            environ["HTTP_ORIGIN"] = origin

        return environ

    def test_non_mcp_route_passes_through(self):
        """Test that non-MCP routes pass through to the wrapped app"""
        environ = self._create_environ("/")

        result = self.middleware(environ, self.start_response)

        # Should call the wrapped app
        self.demo_app.assert_called_once_with(environ, self.start_response)
        self.assertEqual(result, [b"demo response"])

    def test_empty_route_returns_empty_html(self):
        """Test that /tidewave/empty route returns empty HTML response"""
        environ = self._create_environ("/tidewave/empty", "GET")

        result = self.middleware(environ, self.start_response)

        # Should return 200 OK with empty content
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

        # Check headers
        headers = call_args[1]
        content_type = next(
            (value for name, value in headers if name == "Content-Type"), None
        )
        self.assertEqual(content_type, "text/html")

        # Check empty body
        self.assertEqual(result, [b""])

    def test_mcp_get_returns_405(self):
        """Test that GET requests to /tidewave/mcp return 405"""
        environ = self._create_environ("/tidewave/mcp", "GET")

        self.middleware(environ, self.start_response)

        # Should return 405 Method Not Allowed
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("405", call_args[0])

    def test_security_remote_ip_blocked(self):
        """Test that remote IPs are blocked by default"""
        middleware = Middleware(self.demo_app, {"allow_remote_access": False})
        environ = self._create_environ(
            "/tidewave/mcp", "POST", remote_addr="192.168.1.100"
        )

        middleware(environ, self.start_response)

        # Should return 403 Forbidden
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])

    def test_invalid_json_request(self):
        """Test handling of invalid JSON"""
        body = "invalid json"
        environ = self._create_environ("/tidewave/mcp", "POST", body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["code"], -32700)

    def test_invalid_jsonrpc_format(self):
        """Test handling of invalid JSON-RPC format"""
        message = {
            "jsonrpc": "1.0",  # Invalid version
            "method": "ping",
        }
        body = json.dumps(message)
        environ = self._create_environ("/tidewave/mcp", "POST", body)

        result = self.middleware(environ, self.start_response)

        response_data = json.loads(b"".join(result).decode("utf-8"))

        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertIn("error", response_data)
        self.assertEqual(response_data["error"]["code"], -32600)

    def test_notification_no_response(self):
        """Test that notifications don't return a response"""
        message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            # No 'id' field - this is a notification
        }
        body = json.dumps(message)
        environ = self._create_environ("/tidewave/mcp", "POST", body)

        result = self.middleware(environ, self.start_response)

        # Should return 202 Accepted with status response
        call_args = self.start_response.call_args[0]
        self.assertIn("202", call_args[0])

        response_data = json.loads(b"".join(result).decode("utf-8"))
        self.assertEqual(response_data["status"], "ok")

    def test_tool_loading(self):
        """Test that tools are loaded correctly"""
        # Test that middleware loads tools from the tools module via mcp_handler
        self.assertIn("add", self.middleware.mcp_handler.tools)
        self.assertIn("multiply", self.middleware.mcp_handler.tools)
        self.assertEqual(len(self.middleware.mcp_handler.tools), 2)

        # Test tool structure
        add_tool = self.middleware.mcp_handler.tools["add"]
        self.assertIn("name", add_tool)
        self.assertIn("description", add_tool)
        self.assertIn("inputSchema", add_tool)
        self.assertIn("tool_instance", add_tool)

    def test_empty_route_with_script_name(self):
        """Test that /tidewave/empty works when mounted with SCRIPT_NAME"""
        # Create middleware with use_script_name enabled
        config = {"use_script_name": True}
        middleware = Middleware(self.demo_app, config)

        environ = self._create_environ("/empty", "GET")
        environ["SCRIPT_NAME"] = "/tidewave"

        middleware(environ, self.start_response)

        # Should return 200 OK with empty content
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

    def test_mcp_route_with_script_name(self):
        """Test that /tidewave/mcp works when mounted with SCRIPT_NAME"""
        # Create middleware with use_script_name enabled
        config = {"use_script_name": True}
        middleware = Middleware(self.demo_app, config)

        body = '{"jsonrpc": "2.0", "method": "ping", "id": 1}'
        environ = self._create_environ("/mcp", "POST", body)
        environ["SCRIPT_NAME"] = "/tidewave"

        middleware(environ, self.start_response)

        # Should handle the MCP request (not pass through to app)
        self.demo_app.assert_not_called()

    def test_non_tidewave_route_with_script_name(self):
        """Test that non-tidewave routes pass through when mounted"""
        # Create middleware with use_script_name enabled
        config = {"use_script_name": True}
        middleware = Middleware(self.demo_app, config)

        environ = self._create_environ("/other", "GET")
        environ["SCRIPT_NAME"] = "/tidewave"

        middleware(environ, self.start_response)

        # Should pass through to wrapped app
        self.demo_app.assert_called_once_with(environ, self.start_response)

    def test_security_check_on_empty_route(self):
        """Test that security checks run on /tidewave/empty route"""
        middleware = Middleware(self.demo_app, {"allow_remote_access": False})
        environ = self._create_environ(
            "/tidewave/empty", "GET", remote_addr="192.168.1.100"
        )

        middleware(environ, self.start_response)

        # Should return 403 Forbidden
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])


class TestMCPIntegration(unittest.TestCase):
    """Integration tests with real tools"""

    def setUp(self):
        self.middleware = Middleware(Mock())
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


if __name__ == "__main__":
    unittest.main()

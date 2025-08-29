"""
Tests for MCP WSGI Middleware - focusing on middleware concerns only
"""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock
from tidewave.middleware import Middleware
from tidewave.mcp_handler import MCPHandler
from tidewave.tools import add, multiply


class TestMiddleware(unittest.TestCase):
    """Test MCP middleware functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.demo_app = Mock()
        self.demo_app.return_value = [b"demo response"]

        self.config = {
            "debug": True,
            "internal_ips": ["127.0.0.1"],  # Allow for testing
            "allowed_origins": ["localhost"],
        }

        tool_functions = [add, multiply]
        self.mcp_handler = MCPHandler(tool_functions)
        self.middleware = Middleware(self.demo_app, self.mcp_handler, self.config)
        self.start_response = Mock()

    def _create_middleware(self, config):
        """Helper method to create middleware with tools"""
        tool_functions = [add, multiply]
        mcp_handler = MCPHandler(tool_functions)
        return Middleware(self.demo_app, mcp_handler, config)

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
        config = {"internal_ips": ["127.0.0.1"]}
        middleware = self._create_middleware(config)
        environ = self._create_environ(
            "/tidewave/mcp", "POST", remote_addr="192.168.1.100"
        )

        middleware(environ, self.start_response)

        # Should return 403 Forbidden
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])

    def test_security_internal_ip_allowed(self):
        """Test that internal IPs are allowed"""
        config = {"internal_ips": ["127.0.0.1", "192.168.1.100"]}
        middleware = self._create_middleware(config)
        environ = self._create_environ(
            "/tidewave/mcp", "POST",
            body='{"jsonrpc": "2.0", "method": "ping", "id": 1}',
            remote_addr="192.168.1.100"
        )

        result = middleware(environ, self.start_response)

        # Should return 200 OK (ping response)
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

        # Should get proper JSON response
        response_data = json.loads(b"".join(result).decode("utf-8"))
        self.assertEqual(response_data["jsonrpc"], "2.0")
        self.assertEqual(response_data["id"], 1)

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
        middleware = self._create_middleware(config)

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
        middleware = self._create_middleware(config)

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
        middleware = self._create_middleware(config)

        environ = self._create_environ("/other", "GET")
        environ["SCRIPT_NAME"] = "/tidewave"

        middleware(environ, self.start_response)

        # Should pass through to wrapped app
        self.demo_app.assert_called_once_with(environ, self.start_response)

    def test_security_check_on_empty_route(self):
        """Test that security checks run on /tidewave/empty route"""
        config = {"internal_ips": ["127.0.0.1"]}
        middleware = self._create_middleware(config)
        environ = self._create_environ(
            "/tidewave/empty", "GET", remote_addr="192.168.1.100"
        )

        middleware(environ, self.start_response)

        # Should return 403 Forbidden
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])


class TestOriginValidation(unittest.TestCase):
    """Test origin validation with Django ALLOWED_HOSTS pattern"""

    def setUp(self):
        """Set up test fixtures"""
        self.demo_app = Mock()
        self.demo_app.return_value = [b"demo response"]
        self.start_response = Mock()

    def _create_middleware(self, config):
        """Helper method to create middleware with tools"""
        tool_functions = [add, multiply]
        mcp_handler = MCPHandler(tool_functions)
        return Middleware(self.demo_app, mcp_handler, config)

    def _create_environ(self, path="/tidewave/mcp", origin=None):
        """Create WSGI environ dict for testing"""
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "REMOTE_ADDR": "127.0.0.1",
            "wsgi.input": BytesIO(b""),
            "CONTENT_LENGTH": "0",
        }
        if origin:
            environ["HTTP_ORIGIN"] = origin
        return environ

    def test_no_origin_header_allowed(self):
        """Test that missing Origin header is allowed"""
        config = {"allowed_origins": ["example.com"]}
        middleware = self._create_middleware(config)
        environ = self._create_environ()  # No origin header

        middleware(environ, self.start_response)

        # Should not return 403 due to missing origin
        call_args = (
            self.start_response.call_args[0] if self.start_response.called else None
        )
        if call_args:
            self.assertNotIn("403", call_args[0])

    def test_empty_allowed_origins_blocks_all(self):
        """Test that empty allowed_origins blocks all requests"""
        config = {"allowed_origins": []}
        middleware = self._create_middleware(config)

        # Test localhost variants - all should be blocked
        test_origins = [
            "http://localhost:3000",
            "https://localhost",
            "http://test.localhost",
            "http://127.0.0.1:8000",
            "http://[::1]:3000",
        ]

        for origin in test_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertIn(
                        "403", call_args[0], f"Should have blocked origin: {origin}"
                    )
                self.start_response.reset_mock()

    def test_missing_allowed_origins_uses_defaults(self):
        """Test that missing allowed_origins key uses default local hosts"""
        config = {}  # No allowed_origins key at all
        middleware = self._create_middleware(config)

        # Test localhost variants - should be allowed with defaults
        test_origins = [
            "http://localhost:3000",
            "https://localhost",
            "http://test.localhost",
            "http://127.0.0.1:8000",
            "http://[::1]:3000",
        ]

        for origin in test_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn(
                        "403", call_args[0], f"Should have allowed origin: {origin}"
                    )
                self.start_response.reset_mock()

    def test_exact_host_match(self):
        """Test exact host matching (case-insensitive)"""
        config = {"allowed_origins": ["example.com", "API.service.com"]}
        middleware = self._create_middleware(config)

        # Should match
        allowed_origins = [
            "http://example.com",
            "https://example.com:443",
            "http://example.com:8000",
            "https://API.service.com",  # Case insensitive
            "http://api.service.com:3000",
        ]

        for origin in allowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn(
                        "403", call_args[0], f"Should allow origin: {origin}"
                    )
                self.start_response.reset_mock()

        # Should not match
        disallowed_origins = [
            "http://other.com",
            "https://sub.example.com",  # No wildcard
            "http://example.org",
        ]

        for origin in disallowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should return 403
                call_args = self.start_response.call_args[0]
                self.assertIn("403", call_args[0], f"Should block origin: {origin}")
                self.start_response.reset_mock()

    def test_subdomain_wildcard_match(self):
        """Test subdomain wildcard matching"""
        config = {"allowed_origins": [".example.com", ".api.service.net"]}
        middleware = self._create_middleware(config)

        # Should match
        allowed_origins = [
            "http://example.com",  # Exact domain
            "https://www.example.com",
            "http://api.example.com:8000",
            "https://deep.sub.example.com",
            "http://api.service.net",
            "https://v1.api.service.net:443",
        ]

        for origin in allowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn(
                        "403", call_args[0], f"Should allow origin: {origin}"
                    )
                self.start_response.reset_mock()

        # Should not match
        disallowed_origins = [
            "http://example.org",
            "https://notexample.com",
            "http://service.net",  # Missing 'api.' part
        ]

        for origin in disallowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should return 403
                call_args = self.start_response.call_args[0]
                self.assertIn("403", call_args[0], f"Should block origin: {origin}")
                self.start_response.reset_mock()

    def test_wildcard_match(self):
        """Test wildcard matching"""
        config = {"allowed_origins": ["*"]}
        middleware = self._create_middleware(config)

        # Should match everything
        test_origins = [
            "http://example.com",
            "https://any.domain.net:8000",
            "http://192.168.1.1:3000",
            "https://[::1]:8080",
        ]

        for origin in test_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn(
                        "403", call_args[0], f"Wildcard should allow: {origin}"
                    )
                self.start_response.reset_mock()

    def test_ipv6_origin_handling(self):
        """Test IPv6 origin handling"""
        config = {"allowed_origins": ["::1", "2001:db8::1"]}
        middleware = self._create_middleware(config)

        # Should match
        allowed_origins = [
            "http://[::1]",
            "https://[::1]:8000",
            "http://[2001:db8::1]:3000",
        ]

        for origin in allowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn(
                        "403", call_args[0], f"Should allow IPv6: {origin}"
                    )
                self.start_response.reset_mock()

    def test_host_extraction_edge_cases(self):
        """Test edge cases in host extraction"""
        config = {"allowed_origins": ["localhost", "example.com"]}
        middleware = self._create_middleware(config)

        # Test malformed origins that should still work
        test_cases = [
            ("http://localhost:3000", True),  # With scheme
            ("https://example.com", True),
        ]

        for origin, should_allow in test_cases:
            with self.subTest(origin=origin):
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    if should_allow:
                        self.assertNotIn("403", call_args[0], f"Should allow: {origin}")
                    # Note: We don't test blocking case as malformed origins might be handled gracefully
                self.start_response.reset_mock()

    def test_url_parsing_with_stdlib(self):
        """Test that URL parsing using urllib.parse works correctly"""
        config = {"allowed_origins": ["localhost", "example.com", "::1"]}
        middleware = self._create_middleware(config)

        # Test various URL formats that should be parsed correctly
        test_cases = [
            # (origin, expected_host, should_allow)
            ("http://localhost:3000", "localhost", True),
            ("https://example.com", "example.com", True),
            ("http://[::1]:8080", "::1", True),
            ("http://other.com", "other.com", False),
            ("https://[2001:db8::1]:3000", "2001:db8::1", False),
        ]

        for origin, expected_host, should_allow in test_cases:
            with self.subTest(origin=origin):
                # Test host extraction using urlparse directly
                from urllib.parse import urlparse

                extracted_host = urlparse(origin).hostname
                self.assertEqual(
                    extracted_host,
                    expected_host.lower(),
                    f"Host extraction failed for {origin}",
                )

                # Test validation
                environ = self._create_environ(origin=origin)
                middleware(environ, self.start_response)

                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    if should_allow:
                        self.assertNotIn(
                            "403",
                            call_args[0],
                            f"Should allow {origin} -> {extracted_host}",
                        )
                    else:
                        self.assertIn(
                            "403",
                            call_args[0],
                            f"Should block {origin} -> {extracted_host}",
                        )
                elif not should_allow:
                    self.fail(f"Expected 403 for {origin} but no response was sent")

                self.start_response.reset_mock()


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


if __name__ == "__main__":
    unittest.main()

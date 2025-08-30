"""
Tests for MCP WSGI Middleware
"""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock

from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware
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
            "/tidewave/mcp",
            "POST",
            body='{"jsonrpc": "2.0", "method": "ping", "id": 1}',
            remote_addr="192.168.1.100",
        )

        middleware(environ, self.start_response)

        # Should return 200 OK (ping response)
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

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

    def test_tidewave_route_with_script_name(self):
        """Test that /tidewave routes work when mounted with SCRIPT_NAME"""
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


if __name__ == "__main__":
    unittest.main()

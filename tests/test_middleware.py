"""
Tests for MCP WSGI Middleware
"""

import json
import unittest
from io import BytesIO
from unittest.mock import Mock

from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware, modify_csp
from tidewave.tools import project_eval


class TestMiddlewareBase(unittest.TestCase):
    """Base class for testing MCP middleware functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.demo_app = Mock()
        self.demo_app.return_value = [b"demo response"]

        self.config = {
            "debug": True,
            "allow_remote_access": True,  # Allow for testing
        }

        self.mcp_handler = MCPHandler([project_eval])
        self.middleware = self._create_middleware(self.config)
        self.start_response = Mock()

    def _create_middleware(self, config):
        """Helper method to create middleware with tools"""
        return Middleware(self.demo_app, self.mcp_handler, config)

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


class TestMiddleware(TestMiddlewareBase):
    """Test MCP middleware functionality"""

    def test_non_mcp_route_passes_through(self):
        """Test that non-MCP routes pass through to the wrapped app"""
        environ = self._create_environ("/")

        result = self.middleware(environ, self.start_response)

        # The app should be called with the environ and a wrapped start_response
        self.demo_app.assert_called_once()
        call_args = self.demo_app.call_args[0]
        self.assertEqual(call_args[0], environ)  # environ should be the same
        # start_response should be wrapped, so it won't be exactly the same
        self.assertEqual(result, [b"demo response"])

    def test_home_route_returns_html(self):
        """Test that /tidewave/ returns a valid HTML response"""
        environ = self._create_environ("/tidewave")
        result = self.middleware(environ, self.start_response)

        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])
        headers = call_args[1]
        content_type = next((value for name, value in headers if name == "Content-Type"), None)
        self.assertEqual(content_type, "text/html")
        self.assertTrue(result)
        self.assertIsInstance(result[0], bytes)
        self.assertNotIn(b"tidewave:config", result[0].lower())

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
        config = {"allow_remote_access": False}
        middleware = self._create_middleware(config)

        ips = ["192.168.1.100", "1.1.1.1", "invalid", "2001:4860:4860::8888"]

        for ip in ips:
            environ = self._create_environ("/tidewave/mcp", "POST", remote_addr=ip)

            middleware(environ, self.start_response)

            # Should return 403 Forbidden
            call_args = self.start_response.call_args[0]
            self.assertIn("403", call_args[0])

    def test_security_remote_ip_allowed_when_enabled(self):
        """Test that remote IPs are allowed when allow_remote_access is True"""
        config = {"allow_remote_access": True}
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

    def test_local_ip_detection(self):
        """Test that IPv4 localhost addresses are detected as local"""
        config = {"allow_remote_access": False}
        middleware = self._create_middleware(config)

        ips = ["127.0.0.1", "127.0.0.2", "127.0.0.255", "::1", "::ffff:127.0.0.1"]

        for ip in ips:
            environ = self._create_environ(
                "/tidewave/mcp",
                "POST",
                body='{"jsonrpc": "2.0", "method": "ping", "id": 1}',
                remote_addr=ip,
            )

            middleware(environ, self.start_response)

            # Should return 200 OK (ping response)
            call_args = self.start_response.call_args[0]
            self.assertIn("200", call_args[0], f"IP {ip} should be allowed as local")
            self.start_response.reset_mock()

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

        environ = self._create_environ("", "GET")
        environ["SCRIPT_NAME"] = "/tidewave"

        middleware(environ, self.start_response)

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
        self.demo_app.assert_called_once()
        call_args = self.demo_app.call_args[0]
        self.assertEqual(call_args[0], environ)  # environ should be the same

    def test_config_endpoint_returns_json(self):
        """Test that /tidewave/config returns JSON configuration"""
        # Set up config with team data
        self.config["team"] = {"id": "dashbit"}
        middleware = self._create_middleware(self.config)

        environ = self._create_environ("/tidewave/config", "GET")
        result = middleware(environ, self.start_response)

        # Check response
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

        headers = call_args[1]
        content_type = next((value for name, value in headers if name == "Content-Type"), None)
        self.assertEqual(content_type, "application/json")

        # Parse JSON response
        response_data = json.loads(b"".join(result).decode("utf-8"))
        self.assertEqual(response_data["framework_type"], "unknown")
        self.assertIn("tidewave_version", response_data)
        self.assertEqual(response_data["team"], {"id": "dashbit"})
        self.assertIn("project_name", response_data)

    def test_config_endpoint_post_method_not_allowed(self):
        """Test that POST to /tidewave/config returns 405"""
        environ = self._create_environ("/tidewave/config", "POST")

        self.middleware(environ, self.start_response)

        # Should return 405 Method Not Allowed
        self.start_response.assert_called_once()
        call_args = self.start_response.call_args[0]
        self.assertIn("405", call_args[0])


class TestOriginValidation(TestMiddlewareBase):
    """Test origin validation"""

    def test_mcp_and_config_refuse_requests_with_origin_header(self):
        """Test that /mcp and /config refuse any request with origin header"""
        # /mcp should refuse any request with origin header
        environ = self._create_environ(
            "/tidewave/mcp", method="POST", origin="http://localhost:4001"
        )
        self.middleware(environ, self.start_response)
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])
        self.start_response.reset_mock()

        # /config should refuse any request with origin header
        environ = self._create_environ(
            "/tidewave/config", method="GET", origin="http://localhost:4000"
        )
        self.middleware(environ, self.start_response)
        call_args = self.start_response.call_args[0]
        self.assertIn("403", call_args[0])

    def test_root_allows_any_origin(self):
        """Test that / (root) allows any origin"""
        environ = self._create_environ("/tidewave", method="GET", origin="http://example.com")
        result = self.middleware(environ, self.start_response)
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])
        self.start_response.reset_mock()

        environ = self._create_environ("/tidewave", method="GET", origin="http://localhost:4000")
        result = self.middleware(environ, self.start_response)
        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0])

    def test_no_origin_header_allowed(self):
        """Test that missing Origin header is allowed"""
        environ = self._create_environ("/tidewave/mcp", method="POST")
        self.middleware(environ, self.start_response)

        # Should not return 403 due to missing origin
        call_args = self.start_response.call_args[0] if self.start_response.called else None
        if call_args:
            self.assertNotIn("403", call_args[0])


class TestModifyCSP(unittest.TestCase):
    def setUp(self):
        self.client_url = "https://tidewave.ai/client.js"

    def test_empty_csp(self):
        """Test with empty CSP value"""
        result = modify_csp("")
        self.assertIn("script-src 'unsafe-eval'", result)
        self.assertNotIn("frame-ancestors", result)

    def test_whitespace_only_csp(self):
        """Test with whitespace-only CSP value"""
        result = modify_csp("   ")
        self.assertIn("script-src 'unsafe-eval'", result)
        self.assertNotIn("frame-ancestors", result)

    def test_adds_unsafe_eval_to_existing_script_src(self):
        """Test adding unsafe-eval to existing script-src"""
        csp = "script-src 'self' https://cdn.example.com; style-src 'self'"
        result = modify_csp(csp)

        self.assertIn("script-src 'self' https://cdn.example.com 'unsafe-eval'", result)
        self.assertIn("style-src 'self'", result)

    def test_preserves_existing_unsafe_eval(self):
        """Test that unsafe-eval is not duplicated if already present"""
        csp = "script-src 'self' 'unsafe-eval'; style-src 'self'"
        result = modify_csp(csp)

        # Should not add another unsafe-eval
        self.assertEqual(result.count("'unsafe-eval'"), 1)
        self.assertIn("script-src 'self' 'unsafe-eval'", result)

    def test_removes_frame_ancestors_from_existing_policy(self):
        """Test removing frame-ancestors when present"""
        csp = "script-src 'self'; style-src 'self'; frame-ancestors 'self'"
        result = modify_csp(csp)

        self.assertIn("script-src 'self' 'unsafe-eval'", result)
        self.assertIn("style-src 'self'", result)
        self.assertNotIn("frame-ancestors", result)

    def test_handles_directives_without_sources(self):
        """Test handling of directives without sources like upgrade-insecure-requests"""
        csp = "upgrade-insecure-requests; script-src 'self'; block-all-mixed-content"
        result = modify_csp(csp)

        self.assertIn("upgrade-insecure-requests", result)
        self.assertIn("block-all-mixed-content", result)
        self.assertIn("script-src 'self' 'unsafe-eval'", result)

    def test_case_insensitive_directive_handling(self):
        """Test that directive names are handled case-insensitively"""
        csp = "SCRIPT-SRC 'self'; Frame-Ancestors 'none'"
        result = modify_csp(csp)

        # Should modify both directives despite case differences
        self.assertIn("'unsafe-eval'", result)
        self.assertNotIn("frame-ancestors", result)

    def test_handles_extra_whitespace(self):
        """Test handling of extra whitespace in CSP"""
        csp = (
            "  script-src   'self'  https://cdn.example.com  ;"
            "  style-src  'self'  ; "
            "  frame-ancestors  'self'  ;"
        )
        result = modify_csp(csp)

        self.assertIn("script-src 'self' https://cdn.example.com 'unsafe-eval'", result)
        self.assertIn("style-src 'self'", result)
        self.assertNotIn("frame-ancestors", result)

    def test_handles_empty_semicolons(self):
        """Test handling of empty sections between semicolons"""
        csp = "script-src 'self';;; style-src 'self';;"
        result = modify_csp(csp)

        self.assertIn("script-src 'self' 'unsafe-eval'", result)
        self.assertIn("style-src 'self'", result)

    def test_real_world_csp(self):
        """Test with a complex, real-world-like CSP"""
        csp = (
            "default-src 'none'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.example.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        result = modify_csp(csp)

        # Check that unsafe-eval was added to script-src
        self.assertIn(
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net 'unsafe-eval'",
            result,
        )

        # Check frame ancestors
        self.assertNotIn("frame-ancestors", result)

        # Check that all other directives are preserved
        self.assertIn("default-src 'none'", result)
        self.assertIn("style-src 'self' 'unsafe-inline' https://fonts.googleapis.com", result)
        self.assertIn("font-src 'self' https://fonts.gstatic.com", result)
        self.assertIn("img-src 'self' data: https:", result)
        self.assertIn("connect-src 'self' https://api.example.com", result)
        self.assertIn("base-uri 'self'", result)
        self.assertIn("form-action 'self'", result)

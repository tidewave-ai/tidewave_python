"""
Tests for MCP WSGI Middleware
"""

import json
import struct
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

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
            "allowed_origins": ["localhost"],
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
        self.assertIn(b"tidewave:config", result[0].lower())
        self.assertIn(b"&quot;team&quot;: {}", result[0].lower())

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
    """Test origin validation with Django ALLOWED_HOSTS pattern"""

    def test_no_origin_header_allowed(self):
        """Test that missing Origin header is allowed"""
        config = {"allowed_origins": ["example.com"]}
        middleware = self._create_middleware(config)
        environ = self._create_environ("/tidewave/mcp", method="POST")

        middleware(environ, self.start_response)

        # Should not return 403 due to missing origin
        call_args = self.start_response.call_args[0] if self.start_response.called else None
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertIn("403", call_args[0], f"Should have blocked origin: {origin}")
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn("403", call_args[0], f"Should have allowed origin: {origin}")
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn("403", call_args[0], f"Should allow origin: {origin}")
                self.start_response.reset_mock()

        # Should not match
        disallowed_origins = [
            "http://other.com",
            "https://sub.example.com",  # No wildcard
            "http://example.org",
        ]

        for origin in disallowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn("403", call_args[0], f"Should allow origin: {origin}")
                self.start_response.reset_mock()

        # Should not match
        disallowed_origins = [
            "http://example.org",
            "https://notexample.com",
            "http://service.net",  # Missing 'api.' part
        ]

        for origin in disallowed_origins:
            with self.subTest(origin=origin):
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn("403", call_args[0], f"Wildcard should allow: {origin}")
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
                environ = self._create_environ("/tidewave/mcp", method="POST", origin=origin)
                middleware(environ, self.start_response)

                # Should not return 403
                if self.start_response.called:
                    call_args = self.start_response.call_args[0]
                    self.assertNotIn("403", call_args[0], f"Should allow IPv6: {origin}")
                self.start_response.reset_mock()


class TestShellHandler(TestMiddlewareBase):
    def test_non_post_method(self):
        """Test that non-POST methods are rejected"""
        environ = self._create_environ("/tidewave/shell", method="GET")
        result = self.middleware(environ, self.start_response)

        # Should return 405
        call_args = self.start_response.call_args[0]
        self.assertIn("405", call_args[0], "Should block non-POST methods")
        self.assertEqual(result, [b"Method Not Allowed"])
        self.start_response.reset_mock()

    def test_empty_body(self):
        """Test that empty request bodies return 400"""
        environ = self._create_environ("/tidewave/shell", method="POST", body="")
        result = self.middleware(environ, self.start_response)

        call_args = self.start_response.call_args[0]
        self.assertIn("400", call_args[0], "Should block empty request bodies")
        self.assertEqual(result, [b"Command body is required"])
        self.start_response.reset_mock()

    def test_invalid_json(self):
        """Test that invalid JSON bodies return 400"""
        environ = self._create_environ("/tidewave/shell", method="POST", body="invalid_json")
        result = self.middleware(environ, self.start_response)

        call_args = self.start_response.call_args[0]
        self.assertIn("400", call_args[0], "Should block invalid JSON bodies")
        self.assertEqual(result, [b"Invalid JSON in request body"])
        self.start_response.reset_mock()

    def test_missing_command_field(self):
        """Test that missing command field returns 400"""
        body = json.dumps({"other_field": "value"})
        environ = self._create_environ("/tidewave/shell", method="POST", body=body)

        result = self.middleware(environ, self.start_response)

        call_args = self.start_response.call_args[0]
        self.assertIn("400", call_args[0], "Should block invalid JSON bodies")
        self.assertEqual(result, [b"Command field is required"])
        self.start_response.reset_mock()

    def test_empty_command_field(self):
        """Test that empty command field returns 400"""
        body = json.dumps({"command": ""})
        environ = self._create_environ("/tidewave/shell", method="POST", body=body)

        result = self.middleware(environ, self.start_response)

        call_args = self.start_response.call_args[0]
        self.assertIn("400", call_args[0], "Should block invalid JSON bodies")
        self.assertEqual(result, [b"Command field is required"])
        self.start_response.reset_mock()

    @patch("tidewave.middleware.Middleware._execute_command")
    def test_valid_command(self, mock_execute):
        """Test that valid command starts execution"""
        mock_execute.return_value = [b"test output"]

        body = json.dumps({"command": "echo hello"})
        environ = self._create_environ("/tidewave/shell", method="POST", body=body)

        result = self.middleware(environ, self.start_response)

        call_args = self.start_response.call_args[0]
        self.assertIn("200", call_args[0], "Should allow valid commands")
        mock_execute.assert_called_once_with("echo hello")
        self.assertEqual(result, [b"test output"])
        self.start_response.reset_mock()


class TestExecuteCommand(TestMiddlewareBase):
    """Test suite for _execute_command function"""

    def _parse_binary_chunks(self, data):
        """Helper to parse binary chunks into (type, payload) tuples"""
        chunks = []
        offset = 0

        while offset < len(data):
            if offset + 5 > len(data):
                break

            # Unpack type (1 byte) and length (4 bytes)
            chunk_type, length = struct.unpack("!BL", data[offset : offset + 5])
            offset += 5

            if offset + length > len(data):
                break

            payload = data[offset : offset + length]
            offset += length

            chunks.append((chunk_type, payload))

        return chunks

    @patch("subprocess.Popen")
    def test_successful_command_execution(self, mock_popen):
        """Test successful command execution with output"""
        # Mock process
        mock_process = Mock()
        mock_process.stdout.read.side_effect = [b"hello world\n", b""]
        mock_process.poll.return_value = 0
        mock_process.wait.return_value = 0  # Exit code 0
        mock_process.stdin = Mock()
        mock_popen.return_value = mock_process

        # Mock select to indicate data is ready
        with patch("select.select") as mock_select:
            mock_select.side_effect = [
                ([mock_process.stdout], [], []),  # Data ready, read data.
                ([], [], []),  # No more data, process.poll() will indicate completion.
            ]

            # Execute command
            result = b"".join(self.middleware._execute_command("echo hello"))

        # Parse binary chunks
        chunks = self._parse_binary_chunks(result)

        # Should have 2 chunks: output + status
        self.assertEqual(len(chunks), 2)

        # First chunk: output (type 0)
        output_type, output_data = chunks[0]
        self.assertEqual(output_type, 0)
        self.assertEqual(output_data, b"hello world\n")

        # Second chunk: status (type 1)
        status_type, status_data = chunks[1]
        self.assertEqual(status_type, 1)
        status_json = json.loads(status_data.decode("utf-8"))
        self.assertEqual(status_json["status"], 0)

        # Verify subprocess was called correctly
        mock_popen.assert_called_once_with(
            "echo hello",
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            stdin=unittest.mock.ANY,
            shell=True,
        )
        mock_process.stdin.close.assert_called_once()

    @patch("subprocess.Popen")
    def test_command_with_error_exit_code(self, mock_popen):
        """Test command that exits with error code"""
        mock_process = Mock()
        mock_process.stdout.read.side_effect = [b"error message\n", b""]
        mock_process.poll.return_value = 0
        mock_process.wait.return_value = 1  # Exit code 1
        mock_process.stdin = Mock()
        mock_popen.return_value = mock_process

        with patch("select.select") as mock_select:
            mock_select.side_effect = [
                ([mock_process.stdout], [], []),  # Data ready, read data.
                ([], [], []),  # No more data, process.poll() will indicate completion.
            ]

            result = b"".join(self.middleware._execute_command("false"))

        chunks = self._parse_binary_chunks(result)

        # Check status chunk has exit code 1
        status_type, status_data = chunks[1]
        self.assertEqual(status_type, 1)
        status_json = json.loads(status_data.decode("utf-8"))
        self.assertEqual(status_json["status"], 1)

    @patch("subprocess.Popen")
    def test_command_execution_exception(self, mock_popen):
        """Test handling of subprocess exceptions"""
        mock_popen.side_effect = Exception("Command failed")

        result = b"".join(self.middleware._execute_command("invalid_command"))
        chunks = self._parse_binary_chunks(result)

        # Should only have error status chunk
        self.assertEqual(len(chunks), 1)

        status_type, status_data = chunks[0]
        self.assertEqual(status_type, 1)
        status_json = json.loads(status_data.decode("utf-8"))
        self.assertEqual(status_json["status"], 213)

    @patch("subprocess.Popen")
    def test_list_command(self, mock_popen):
        """Test command passed as list instead of string"""
        mock_process = Mock()
        mock_process.stdout.read.side_effect = [b"output", b""]
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0
        mock_process.stdin = Mock()
        mock_popen.return_value = mock_process

        with patch("select.select") as mock_select:
            mock_select.side_effect = [([mock_process.stdout], [], []), ([], [], [])]

            list(self.middleware._execute_command(["echo", "hello"]))

        # Verify shell=False for list commands
        mock_popen.assert_called_once_with(
            ["echo", "hello"],
            stdout=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            stdin=unittest.mock.ANY,
            shell=False,
        )

    @patch("select.select", side_effect=AttributeError)
    @patch("subprocess.Popen")
    def test_windows_fallback(self, mock_popen, mock_select):
        """Test Windows fallback when select is not available"""
        mock_process = Mock()
        mock_process.stdout.read.side_effect = [b"windows output", b""]
        mock_process.wait.return_value = 0
        mock_process.stdin = Mock()
        mock_popen.return_value = mock_process

        result = b"".join(self.middleware._execute_command("dir"))
        chunks = self._parse_binary_chunks(result)

        self.assertEqual(len(chunks), 2)
        output_type, output_data = chunks[0]
        self.assertEqual(output_type, 0)
        self.assertEqual(output_data, b"windows output")


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
        """Test adding frame-src when it doesn't exist"""
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

    def test_url_as_substring_handling(self):
        """Test handling when client URL appears as substring of another URL"""
        longer_url = f"{self.client_url}/some/path"
        csp = f"frame-src 'self' {longer_url}"
        result = modify_csp(csp)

        # Should not add client URL if it would be redundant with longer URL.
        self.assertIn(longer_url, result)

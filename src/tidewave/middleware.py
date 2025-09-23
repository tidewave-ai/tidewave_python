"""
WSGI Middleware for basic routing and security
"""

import html
import json
import logging
import re
import select
import struct
import subprocess
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any, Callable, Optional
from urllib.parse import urlparse

from . import __version__
from .mcp_handler import MCPHandler


class Middleware:
    """WSGI middleware that handles routing and security for Tidewave endpoints"""

    def __init__(
        self,
        app: Callable,
        mcp_handler: MCPHandler,
        config: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize middleware

        Args:
            app: WSGI application to wrap
            mcp_handler: MCPHandler instance to handle MCP requests
            config: Configuration dict with options:
                - allow_remote_access: bool (default False) - whether to allow
                  remote connections. If False, only local IPs are allowed.
                - allowed_origins: list of allowed origin hosts (default []) following
                  Django's ALLOWED_HOSTS pattern:
                  * Exact matches (case-insensitive): 'example.com', 'www.example.com'
                  * Subdomain wildcards: '.example.com' matches example.com and all
                    subdomains
                  * Wildcard: '*' matches any host (use with caution)
                  * Empty list defaults to local development hosts:
                    ['.localhost', '127.0.0.1', '::1']
                - use_script_name: bool (default False) - whether to read path
                  from SCRIPT_NAME
        """
        self.app = app
        self.config = config or {}
        self.mcp_handler = mcp_handler
        self.logger = logging.getLogger(__name__)

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        """WSGI application entry point"""
        path_info = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "").upper()

        if self.config.get("use_script_name", False):
            full_path = environ.get("SCRIPT_NAME", "") + path_info
        else:
            full_path = path_info

        # Check if this is a tidewave route
        if full_path.startswith("/tidewave"):
            security_error = self._check_security(environ)
            if security_error:
                self.logger.warning(security_error)
                return self._send_error_response(
                    start_response, HTTPStatus.FORBIDDEN, security_error
                )

        if full_path == "/tidewave":
            return self._handle_home_route(start_response)

        if full_path == "/tidewave/config":
            if method == "GET":
                return self._handle_config_route(start_response)
            else:
                return self._send_error_response(start_response, HTTPStatus.METHOD_NOT_ALLOWED)

        if full_path == "/tidewave/mcp":
            if method == "POST":
                return self.mcp_handler.handle_request(environ, start_response)
            else:
                return self._send_error_response(start_response, HTTPStatus.METHOD_NOT_ALLOWED)

        if full_path == "/tidewave/shell":
            if method == "POST":
                return self._handle_shell_command(environ, start_response)
            else:
                return self._send_error_response(start_response, HTTPStatus.METHOD_NOT_ALLOWED)

        return self.app(environ, start_response)

    def _handle_home_route(self, start_response: Callable) -> Iterator[bytes]:
        client_config = self._get_config_data()
        config_json = html.escape(json.dumps(client_config))

        template = f"""
            <!DOCTYPE html>
            <html>
                <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <meta name="tidewave:config" content="{config_json}" />
                <script type="module" src="{self.config.get("client_url")}/tc/tc.js"></script>
                </head>
                <body></body>
            </html>
        """

        response_headers = [
            ("Content-Type", "text/html"),
            ("Content-Length", str(len(template))),
        ]
        start_response(f"{HTTPStatus.OK.value} {HTTPStatus.OK.phrase}", response_headers)
        return [template.encode("utf-8")]

    def _handle_config_route(self, start_response: Callable) -> Iterator[bytes]:
        """Handle GET /tidewave/config route to return JSON configuration"""
        config_data = self._get_config_data()
        config_json = json.dumps(config_data)

        response_headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(config_json))),
        ]
        start_response(f"{HTTPStatus.OK.value} {HTTPStatus.OK.phrase}", response_headers)
        return [config_json.encode("utf-8")]

    def _get_config_data(self) -> dict[str, Any]:
        """Get configuration data for client"""
        return {
            "project_name": self.config.get("project_name", "unknown"),
            "framework_type": self.config.get("framework_type", "unknown"),
            "team": self.config.get("team", {}),
            "tidewave_version": __version__,
        }

    def _handle_shell_command(
        self, environ: dict[str, Any], start_response: Callable
    ) -> Iterator[bytes]:
        """
        Handle shell command execution for MCP server

        Args:
            environ: WSGI environ dict
            start_response: WSGI start_response callable

        Returns:
            Iterator of binary chunks
        """

        # Read request body
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length == 0:
            return self._send_error_response(
                start_response, HTTPStatus.BAD_REQUEST, "Command body is required"
            )

        # Read and parse body
        try:
            body = environ["wsgi.input"].read(content_length)
            parsed_body = json.loads(body)
            cmd = parsed_body.get("command")

            if not cmd:
                return self._send_error_response(
                    start_response, HTTPStatus.BAD_REQUEST, "Command field is required"
                )

        except json.JSONDecodeError:
            return self._send_error_response(
                start_response, HTTPStatus.BAD_REQUEST, "Invalid JSON in request body"
            )
        except Exception:
            return self._send_error_response(
                start_response, HTTPStatus.BAD_REQUEST, "Error reading request body"
            )

        # Start streaming response
        start_response("200 OK", [("Content-Type", "application/octet-stream")])

        # Execute command and yield binary chunks
        return self._execute_command(cmd)

    def _check_security(self, environ: dict[str, Any]) -> Optional[str]:
        """Check security constraints (IP and origin)"""

        # Check remote IP
        remote_addr = environ.get("REMOTE_ADDR", "")
        if not self._validate_ip(remote_addr):
            self.logger.warning(f"Access denied for IP: {remote_addr}")
            return (
                "For security reasons, Tidewave does not accept remote connections by default.\n\n"
                "If you really want to allow remote connections, "
                "configure Tidewave with the `allow_remote_access: true` option"
            )

        # Check origin header (if present)
        origin = environ.get("HTTP_ORIGIN")
        if origin:
            hostname = urlparse(origin).hostname
            if hostname is None:
                return (
                    "For security reasons, Tidewave only accepts requests from allowed hosts.\n\n"
                    f"The origin header appears to be malformed: {origin}"
                )

            host = hostname.lower()
            if not self._validate_allowed_origin(host):
                return (
                    "For security reasons, Tidewave only accepts requests from allowed hosts.\n\n"
                    f"If you want to allow requests from '{host}', "
                    "you must configure your framework/Tidewave accordingly"
                )

        return None

    def _validate_allowed_origin(self, host: str) -> bool:
        """Validate if origin host is allowed using Django ALLOWED_HOSTS pattern"""
        allowed_origins = self.config.get("allowed_origins", [".localhost", "127.0.0.1", "::1"])

        # Default to local development hosts if empty (like Django's DEBUG mode)
        if not allowed_origins:
            return False

        for allowed in allowed_origins:
            allowed = allowed.lower()  # Case-insensitive matching

            # Wildcard match
            if allowed == "*":
                return True

            # Exact match
            if host == allowed:
                return True

            if allowed.startswith("."):
                domain = allowed[1:]

                if host == domain or host.endswith("." + domain):
                    return True

        return False

    def _validate_ip(self, ip_str: str) -> bool:
        """Check if IP address is allowed based on allow_remote_access setting"""
        allow_remote_access = self.config.get("allow_remote_access", False)

        if allow_remote_access:
            return True

        if re.match(r"^127\.0\.0\.\d{1,3}$", ip_str):
            return True

        if ip_str == "::1":
            return True

        if ip_str == "::ffff:127.0.0.1":
            return True

        return False

    def _send_error_response(
        self,
        start_response: Callable,
        status: HTTPStatus,
        message: Optional[str] = None,
    ):
        """Send HTTP error response using standard status codes"""
        error_message = message or status.phrase
        message_bytes = error_message.encode("utf-8")

        response_headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(message_bytes))),
        ]

        status_line = f"{status.value} {status.phrase}"
        start_response(status_line, response_headers)
        return [message_bytes]

    def _execute_command(self, cmd) -> Iterator[bytes]:
        """
        Execute command and yield binary chunks

        Args:
            cmd: Command to execute (string or list)

        Yields:
            Binary chunks in format: [type:1byte][length:4bytes][data:variable]
            - Type 0: Command output data
            - Type 1: Status/completion data
        """
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                stdin=subprocess.PIPE,
                shell=isinstance(cmd, str),
            )

            # Close stdin
            process.stdin.close()

            # Stream output
            while True:
                try:
                    # Non-blocking I/O for Unix-like systems
                    ready, _, _ = select.select([process.stdout], [], [], 0.1)
                    if ready:
                        data = process.stdout.read(4096)
                        if data:
                            # Binary chunk: type (0) + 4-byte length + data
                            chunk = struct.pack("!BL", 0, len(data)) + data
                            yield chunk
                        else:
                            break  # EOF
                    elif process.poll() is not None:
                        # Process finished and no more data
                        break
                except (AttributeError, OSError):
                    # Windows fallback, or when select is not available
                    data = process.stdout.read(4096)
                    if data:
                        chunk = struct.pack("!BL", 0, len(data)) + data
                        yield chunk
                    else:
                        break

            # Send exit status
            exit_status = process.wait()
            status_json = json.dumps({"status": exit_status}).encode("utf-8")
            chunk = struct.pack("!BL", 1, len(status_json)) + status_json
            yield chunk

        except Exception:
            # Send error status
            error_json = json.dumps({"status": 213}).encode("utf-8")
            chunk = struct.pack("!BL", 1, len(error_json)) + error_json
            yield chunk


def modify_csp(csp_value: str) -> str:
    """
    Modify CSP header to support Tidewave embedding:
    - Add 'unsafe-eval' to script-src if not present
    - Remove frame-ancestors from CSP if present

    Args:
        csp_value: Original CSP header value

    Returns:
        Modified CSP header value
    """
    directives = {}
    parts = [part.strip() for part in csp_value.split(";") if part.strip()]

    for part in parts:
        if " " in part:
            directive, sources = part.split(" ", 1)
            directives[directive.lower()] = sources.strip()
        else:
            # Directive with no sources (like 'upgrade-insecure-requests')
            directives[part.lower()] = ""

    # Modify script-src to include unsafe-eval.
    script_src = directives.get("script-src", "")
    if script_src:
        script_sources = script_src.split()
        if "'unsafe-eval'" not in script_sources:
            directives["script-src"] = f"{' '.join(script_sources)} 'unsafe-eval'"
    elif not script_src:
        # No script-src directive, add one with unsafe-eval.
        directives["script-src"] = "'unsafe-eval'"

    # Rebuild CSP header
    csp_parts = []
    for directive, sources in directives.items():
        if directive != "frame-ancestors":
            if sources:
                csp_parts.append(f"{directive} {sources}")
            else:
                csp_parts.append(directive)

    return "; ".join(csp_parts)

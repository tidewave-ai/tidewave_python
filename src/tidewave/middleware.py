"""
WSGI Middleware for basic routing and security
"""

from http import HTTPStatus
from typing import Dict, Any, Optional, Callable
import ipaddress
import logging
from urllib.parse import urlparse

from .mcp_handler import MCPHandler


class Middleware:
    """WSGI middleware that handles routing and security for Tidewave endpoints"""

    def __init__(
        self,
        app: Callable,
        mcp_handler: MCPHandler,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize middleware

        Args:
            app: WSGI application to wrap
            mcp_handler: MCPHandler instance to handle MCP requests
            config: Configuration dict with options:
                - allow_remote_access: bool (default False)
                - allowed_origins: list of allowed origin hosts (default []) following Django's ALLOWED_HOSTS pattern:
                  * Exact matches (case-insensitive): 'example.com', 'www.example.com'
                  * Subdomain wildcards: '.example.com' matches example.com and all subdomains
                  * Wildcard: '*' matches any host (use with caution)
                  * Empty list defaults to local development hosts: ['.localhost', '127.0.0.1', '::1']
                - use_script_name: bool (default False) - whether to read path from SCRIPT_NAME
        """
        self.app = app
        self.config = config or {}
        self.mcp_handler = mcp_handler
        self.logger = logging.getLogger(__name__)

    def __call__(self, environ: Dict[str, Any], start_response: Callable):
        """WSGI application entry point"""
        path_info = environ.get("PATH_INFO", "")

        if self.config.get("use_script_name", False):
            full_path = environ.get("SCRIPT_NAME", "") + path_info
        else:
            full_path = path_info

        # Check if this is a tidewave route
        if full_path.startswith("/tidewave"):
            # Security checks for all tidewave routes
            security_error = self._check_security(environ)
            if security_error:
                return self._send_error_response(
                    start_response, HTTPStatus.FORBIDDEN, security_error
                )

        if full_path == "/tidewave/empty":
            return self._handle_empty_route(start_response)

        if full_path == "/tidewave/mcp":
            method = environ.get("REQUEST_METHOD", "").upper()

            if method == "POST":
                return self.mcp_handler.handle_request(environ, start_response)
            else:
                return self._send_error_response(
                    start_response, HTTPStatus.METHOD_NOT_ALLOWED
                )

        return self.app(environ, start_response)

    def _handle_empty_route(self, start_response: Callable):
        """Handle /empty route (returns empty HTML response)"""
        response_headers = [
            ("Content-Type", "text/html"),
            ("Content-Length", "0"),
        ]
        start_response(
            f"{HTTPStatus.OK.value} {HTTPStatus.OK.phrase}", response_headers
        )
        return [b""]

    def _check_security(self, environ: Dict[str, Any]) -> Optional[str]:
        """Check security constraints (IP and origin)"""

        # Check remote IP
        remote_addr = environ.get("REMOTE_ADDR", "")
        if not self._is_local_ip(remote_addr) and not self.config.get(
            "allow_remote_access", False
        ):
            self.logger.warning(f"Remote access denied for IP: {remote_addr}")
            return (
                "For security reasons, Tidewave does not accept remote connections by default.\n\n"
                "If you really want to allow remote connections, configure the Tidewave with the `allow_remote_access: True` option."
            )

        # Check origin header (if present)
        origin = environ.get("HTTP_ORIGIN")
        if origin:
            hostname = urlparse(origin).hostname
            if hostname is None:
                self.logger.warning(f"Malformed origin header: {origin}")
                return (
                    f"For security reasons, Tidewave only accepts requests from allowed hosts.\n\n"
                    f"The origin header appears to be malformed: {origin}"
                )

            host = hostname.lower()
            if not self._validate_allowed_origin(host):
                self.logger.warning(f"Origin validation failed for host: {host}")
                return (
                    f"For security reasons, Tidewave only accepts requests from allowed hosts.\n\n"
                    f"If you want to allow requests from '{host}', configure Tidewave with the `allowed_origins: ['{host}']` option."
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

    def _is_local_ip(self, ip_str: str) -> bool:
        """Check if IP address is local/loopback"""
        try:
            ip = ipaddress.ip_address(ip_str)
            # Check for IPv4 loopback (127.x.x.x)
            if ip.version == 4 and str(ip).startswith("127."):
                return True
            # Check for IPv6 loopback (::1)
            if ip.version == 6 and ip.is_loopback:
                return True
            # Check for IPv4-mapped IPv6 localhost (::ffff:127.0.0.1)
            if (
                ip.version == 6
                and ip.ipv4_mapped
                and str(ip.ipv4_mapped).startswith("127.")
            ):
                return True
            return False
        except ValueError:
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

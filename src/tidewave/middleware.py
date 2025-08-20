"""
WSGI Middleware for basic routing and security
Based on the Phoenix Tidewave Router implementation
"""

import logging
from http import HTTPStatus
from typing import Dict, Any, Optional, Callable
import ipaddress

from .mcp_handler import MCPHandler


class Middleware:
    """WSGI middleware that handles routing and security for Tidewave endpoints"""

    def __init__(self, app: Callable, config: Optional[Dict[str, Any]] = None):
        """Initialize middleware

        Args:
            app: WSGI application to wrap
            config: Configuration dict with options:
                - allow_remote_access: bool (default False)
                - allowed_origins: list of allowed origins (default None)
                - debug: bool (default False)
                - use_script_name: bool (default False) - whether to read path from SCRIPT_NAME
        """
        self.app = app
        self.config = config or {}
        self._init_logging()
        self.mcp_handler = MCPHandler(self.config)

    def _init_logging(self):
        """Initialize logging configuration"""
        level = logging.DEBUG if self.config.get("debug", False) else logging.INFO
        logging.basicConfig(
            level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
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
                return self._send_error_response(start_response, HTTPStatus.METHOD_NOT_ALLOWED)

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
            return (
                "For security reasons, Tidewave does not accept remote connections by default.\n\n"
                "If you really want to allow remote connections, configure the Tidewave with the `allow_remote_access: True` option."
            )

        # Check origin header
        origin = environ.get("HTTP_ORIGIN")
        if origin:
            if not self._validate_allowed_origin(origin):
                return (
                    f"For security reasons, Tidewave only accepts requests from the same origin your web app is running on.\n\n"
                    f"If you really want to allow remote connections, configure the Tidewave with the `allowed_origins: ['{origin}']` option."
                )

        return None

    def _validate_allowed_origin(self, origin: str) -> bool:
        """Validate if origin is allowed"""
        allowed_origins = self.config.get("allowed_origins")
        if allowed_origins is None:
            # Default behavior - for demo purposes, we'll be permissive
            # In production, you'd want stricter origin validation
            return True
        else:
            return origin in allowed_origins

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
        self, start_response: Callable, status: HTTPStatus, message: str = None
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

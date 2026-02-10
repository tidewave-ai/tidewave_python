"""
WSGI Middleware for basic routing and security
"""

import json
import logging
import re
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any, Callable, Optional

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

        full_path = full_path.rstrip("/")

        if full_path.startswith("/tidewave"):
            security_error = self._check_security(environ, full_path)
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

        return self.app(environ, start_response)

    def _handle_home_route(self, start_response: Callable) -> Iterator[bytes]:
        client_url = self.config.get("client_url", "https://tidewave.ai")

        template = f"""
        <!DOCTYPE html>
        <html>
            <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <script type="module" src="{client_url}/tc/tc.js"></script>
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

    def _check_security(self, environ: dict[str, Any], full_path: str) -> Optional[str]:
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

        # Check origin header
        origin = environ.get("HTTP_ORIGIN")

        # GET /tidewave (root) allows any origin
        if full_path == "/tidewave":
            return None

        # No origin header is always allowed (not from a browser)
        if not origin:
            return None

        # /config and /mcp refuse if origin header is set
        return (
            "For security reasons, Tidewave does not accept requests "
            "with an origin header for this endpoint."
        )

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

"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Any, Callable

from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import modify_csp


class Middleware:
    def __init__(self, wsgi_app: Callable, mcp_handler: MCPHandler, config: dict[str, Any]):
        self.wsgi_app = wsgi_app
        self.mcp_handler = mcp_handler
        self.config = config

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        """WSGI application entry point - handle response headers modification"""

        if environ.get("PATH_INFO").startswith("/tidewave"):
            # For Tidewave routes, delegate directly to base middleware
            return self.wsgi_app(environ, start_response)

        return self._handle_normal_request(environ, start_response)

    def get_mcp_handler(self) -> MCPHandler:
        """Get the MCP handler instance for advanced usage"""
        return self.mcp_handler

    def _handle_normal_request(self, environ, start_response):
        """Handle normal requests - modify response headers"""

        def handle_response(status, headers):
            modified_headers = self._process_response(headers)
            return start_response(status, modified_headers)

        return self.wsgi_app(environ, handle_response)

    def _process_response(self, headers):
        """
        Modify headers to allow embedding in Tidewave:
        - Remove X-Frame-Options
        - Add unsafe-eval to script-src in CSP if present
        - Remove frame-ancestors from CSP if present
        """
        headers_dict = dict(headers)
        if "X-Frame-Options" in headers_dict:
            del headers_dict["X-Frame-Options"]
        if "Content-Security-Policy" in headers_dict:
            headers_dict["Content-Security-Policy"] = modify_csp(
                headers_dict["Content-Security-Policy"]
            )

        return list(headers_dict.items())

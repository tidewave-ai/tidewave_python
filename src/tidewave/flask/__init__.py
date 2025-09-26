"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Any, Callable, Optional

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware, modify_csp


class Middleware:
    """Flask-specific middleware that handles MCP handler initialization and routing"""

    def __init__(self, app: Callable, config: Optional[dict[str, Any]] = None):
        """Initialize Flask middleware with MCP handler

        Args:
            app: Flask WSGI application to wrap
            config: Configuration dict with options:
                - allow_remote_access: bool (default False) - whether to allow remote connections
                - allowed_origins: list of allowed origin hosts (default [])
        """
        self.config = config or {}

        self.mcp_handler = MCPHandler(
            [
                tools.get_docs,
                tools.get_logs,
                tools.get_source_location,
                tools.project_eval,
            ]
        )
        self.app = app
        self.middleware = BaseMiddleware(app, self.mcp_handler, self.config)

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        """WSGI application entry point - handle response headers modification"""
        # Check if this is a Tidewave route
        if environ.get("PATH_INFO").startswith("/tidewave"):
            # For Tidewave routes, delegate directly to base middleware
            return self.middleware(environ, start_response)

        return self._handle_normal_request(environ, start_response)

    def get_mcp_handler(self) -> MCPHandler:
        """Get the MCP handler instance for advanced usage"""
        return self.mcp_handler

    def _handle_normal_request(self, environ, start_response):
        """Handle normal requests - modify response headers"""
        def handle_response(status, headers):
            modified_headers = self._process_response(headers)
            return start_response(status, modified_headers)
        return self.app(environ, handle_response)

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

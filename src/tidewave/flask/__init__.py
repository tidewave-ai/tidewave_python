"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Any, Callable

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware


class Middleware:
    """Flask-specific middleware that handles MCP handler initialization and routing"""

    def __init__(self, app: Callable, config: dict[str, Any] = None):
        """Initialize Flask middleware with MCP handler

        Args:
            app: Flask WSGI application to wrap
            config: Configuration dict with options:
                - internal_ips: list of allowed IP addresses (default ["127.0.0.1"])
                - allowed_origins: list of allowed origin hosts (default [])
        """
        self.config = config or {}

        tool_functions = [tools.project_eval]
        self.mcp_handler = MCPHandler(tool_functions)

        self.middleware = BaseMiddleware(app, self.mcp_handler, self.config)

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        """WSGI application entry point - delegate to base middleware"""
        return self.middleware(environ, start_response)

    def get_mcp_handler(self) -> MCPHandler:
        """Get the MCP handler instance for advanced usage"""
        return self.mcp_handler

"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Any, Callable, Optional

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware


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

        self.middleware = BaseMiddleware(app, self.mcp_handler, self.config)

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        """WSGI application entry point - delegate to base middleware"""
        return self.middleware(environ, start_response)

    def get_mcp_handler(self) -> MCPHandler:
        """Get the MCP handler instance for advanced usage"""
        return self.mcp_handler

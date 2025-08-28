"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Dict, Any, Optional, Callable

from ..middleware import Middleware as BaseMiddleware
from ..mcp_handler import MCPHandler
from ..tools import add, multiply


class Middleware:
    """Flask-specific middleware that handles MCP handler initialization and routing"""

    def __init__(self, app: Callable, config: Optional[Dict[str, Any]] = None):
        """Initialize Flask middleware with MCP handler

        Args:
            app: Flask WSGI application to wrap
            config: Configuration dict with options:
                - debug: bool (default False)
                - allow_remote_access: bool (default False)
                - allowed_origins: list of allowed origin hosts (default [])
                - use_script_name: bool (default False)
        """
        self.config = config or {}

        # Create MCP handler with tools
        tool_functions = [add, multiply]
        self.mcp_handler = MCPHandler(tool_functions)

        # Create the base middleware with the MCP handler
        self.middleware = BaseMiddleware(app, self.mcp_handler, self.config)

    def __call__(self, environ: Dict[str, Any], start_response: Callable):
        """WSGI application entry point - delegate to base middleware"""
        return self.middleware(environ, start_response)

    def get_mcp_handler(self) -> MCPHandler:
        """Get the MCP handler instance for advanced usage"""
        return self.mcp_handler
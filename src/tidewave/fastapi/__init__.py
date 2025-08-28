"""
FastAPI-specific integration for Tidewave MCP
"""

from typing import Dict, Any, Optional
from fastapi import FastAPI
from starlette.middleware.wsgi import WSGIMiddleware

from ..middleware import Middleware
from ..mcp_handler import MCPHandler
from ..tools import add, multiply


def mount(app: FastAPI, config: Optional[Dict[str, Any]] = None):
    """Mount Tidewave middleware to a FastAPI application

    Args:
        app: FastAPI application instance
        config: Configuration dict with options:
            - allow_remote_access: bool (default False)
            - allowed_origins: list of allowed origin hosts (default [])
    """
    # Create WSGI app for MCP handling
    def wsgi_app(environ, start_response):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    # Set use_script_name to True for mounted applications
    app_config = config.copy() if config else {}
    app_config["use_script_name"] = True

    # Create MCP handler and middleware
    tool_functions = [add, multiply]
    mcp_handler = MCPHandler(tool_functions)
    middleware = Middleware(wsgi_app, mcp_handler, app_config)

    # Mount WSGI app in FastAPI
    app.mount("/tidewave", WSGIMiddleware(middleware))
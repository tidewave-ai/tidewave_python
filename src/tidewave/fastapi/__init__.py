"""
FastAPI-specific integration for Tidewave MCP
"""

from typing import Any

from fastapi import FastAPI

from starlette.middleware.wsgi import WSGIMiddleware

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware


def mount(app: FastAPI, config: dict[str, Any] = None):
    """Mount Tidewave middleware to a FastAPI application

    Args:
        app: FastAPI application instance
        config: Configuration dict with options:
            - allow_remote_access: bool (default False) - whether to allow remote connections
            - allowed_origins: list of allowed origin hosts (default [])
    """

    config = config or {}

    # Create WSGI app for MCP handling
    def wsgi_app(environ, start_response):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    # Set use_script_name to True for mounted applications
    app_config = config.copy()
    app_config["use_script_name"] = True

    tool_functions = [tools.project_eval]
    mcp_handler = MCPHandler(tool_functions)
    middleware = Middleware(wsgi_app, mcp_handler, app_config)

    app.mount("/tidewave", WSGIMiddleware(middleware))

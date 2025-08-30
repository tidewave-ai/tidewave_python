"""
FastAPI-specific integration for Tidewave MCP
"""

from typing import Any

from fastapi import FastAPI

from starlette.middleware.wsgi import WSGIMiddleware

from ..mcp_handler import MCPHandler
from ..middleware import Middleware
from ..tools import add, multiply


def mount(app: FastAPI, config: dict[str, Any] = None):
    """Mount Tidewave middleware to a FastAPI application

    Args:
        app: FastAPI application instance
        config: Configuration dict with options:
            - internal_ips: list of allowed IP addresses (default ["127.0.0.1"])
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

    # Create MCP handler and middleware
    tool_functions = [add, multiply]
    mcp_handler = MCPHandler(tool_functions)
    middleware = Middleware(wsgi_app, mcp_handler, app_config)

    # Mount WSGI app in FastAPI
    app.mount("/tidewave", WSGIMiddleware(middleware))

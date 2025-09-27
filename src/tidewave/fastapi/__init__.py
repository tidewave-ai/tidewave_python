"""
FastAPI-specific integration for Tidewave MCP
"""

import os
from typing import Any, Optional

from fastapi import FastAPI

from starlette.middleware.wsgi import WSGIMiddleware

import __main__
from tidewave import tools
from tidewave.fastapi.middleware import Middleware
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as MCPMiddleware


def mount(app: FastAPI, config: Optional[dict[str, Any]] = None):
    """Mount Tidewave routes and middleware to a FastAPI application

    Args:
        app: FastAPI application instance
        config: Configuration dict with options:
            - allow_remote_access: bool (default False) - whether to allow remote connections
            - allowed_origins: list of allowed origin hosts (default [])
            - team: Enable Tidewave for teams
    """

    # Create WSGI app for MCP handling
    def wsgi_app(environ, start_response):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    mcp_handler = MCPHandler(
        [
            tools.get_docs,
            tools.get_logs,
            tools.get_source_location,
            tools.project_eval,
        ]
    )

    project_name = "fastapi_app"
    try:
        main_module = __main__.__file__
        project_name = os.path.splitext(os.path.basename(main_module))[0]
    except AttributeError:
        pass

    config = {
        **(config or {}),
        "framework_type": "fastapi",
        "project_name": project_name,
        "use_script_name": True,
    }

    mcp_middleware = MCPMiddleware(wsgi_app, mcp_handler, config)
    app.mount("/tidewave", WSGIMiddleware(mcp_middleware))
    app.add_middleware(Middleware)

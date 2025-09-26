"""
Flask-specific middleware for Tidewave MCP integration
"""

from typing import Any, Callable, Optional

from flask import current_app

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware, modify_csp
from tidewave.sqlalchemy import get_models, execute_sql_query


class Middleware:
    """Flask-specific middleware that handles MCP handler initialization and routing"""

    def __init__(self, app: Callable, config: Optional[dict[str, Any]] = None):
        """Build a Flask middleware with MCP handler

        Args:
            app: Flask application instance
            config: Configuration dict with options:
                - allow_remote_access: bool (default False) - whether to allow remote connections
                - allowed_origins: list of allowed origin hosts (default [])
                - team: Enable Tidewave for teams
        """
        self.wsgi_app = app.wsgi_app

        mcp_tools = [
            tools.get_docs,
            tools.get_logs,
            tools.get_source_location,
            tools.project_eval,
        ]

        if "sqlalchemy" in app.extensions:
            with app.app_context():
                db = app.extensions["sqlalchemy"]
                mcp_tools.extend(
                    [
                        get_models(db.Model),
                        execute_sql_query(db.engine),
                    ]
                )

        self.mcp_handler = MCPHandler(mcp_tools)

        project_name = "flask_app"
        try:
            project_name = current_app.name
        except RuntimeError:
            pass

        config = {
            **(config or {}),
            "framework_type": "flask",
            "project_name": project_name,
        }

        self.middleware = BaseMiddleware(self.wsgi_app, self.mcp_handler, config)

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

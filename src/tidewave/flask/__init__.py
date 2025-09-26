from typing import Any, Optional

from flask import current_app

from tidewave import tools
from tidewave.flask.middleware import Middleware
from tidewave.jinja2 import Extension
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware
from tidewave.sqlalchemy import execute_sql_query, get_models


class Tidewave:
    """Initialize Tidewave with a Flask application.

    Configuration accepted on initialization:
      - allow_remote_access: bool (default False) - whether to allow remote connections
      - allowed_origins: list of allowed origin hosts (default [])
      - team: Enable Tidewave for teams
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}

    def init_app(self, app):
        if app.debug:
            # Create MCP tools
            mcp_tools = [
                tools.get_docs,
                tools.get_logs,
                tools.get_source_location,
                tools.project_eval,
            ]

            # Add SQLAlchemy tools if available
            if "sqlalchemy" in app.extensions:
                with app.app_context():
                    db = app.extensions["sqlalchemy"]
                    mcp_tools.extend(
                        [
                            get_models(db.Model),
                            execute_sql_query(db.engine),
                        ]
                    )

            # Create MCP handler
            mcp_handler = MCPHandler(mcp_tools)

            # Get project name
            project_name = "flask_app"
            try:
                project_name = current_app.name
            except RuntimeError:
                pass

            # Create config for middleware
            middleware_config = {
                **self.config,
                "framework_type": "flask",
                "project_name": project_name,
            }

            # Create base middleware
            base_middleware = BaseMiddleware(app.wsgi_app, mcp_handler, middleware_config)

            # Wrap with Flask-specific middleware
            app.wsgi_app = Middleware(base_middleware, mcp_handler, middleware_config)
            app.jinja_env.add_extension(Extension)

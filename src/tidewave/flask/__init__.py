"""
Flask-specific integration for Tidewave
"""

import logging
from typing import Any, Optional

from flask import current_app, got_request_exception, request

from tidewave import tools
from tidewave.flask.middleware import Middleware
from tidewave.jinja2 import Extension
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as MCPMiddleware


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
        if not app.debug:
            return

        # Create MCP tools
        mcp_tools = [
            tools.get_docs,
            tools.get_logs,
            tools.get_source_location,
            tools.project_eval,
        ]

        # Add SQLAlchemy tools if available
        if "sqlalchemy" in app.extensions:
            from tidewave.sqlalchemy import execute_sql_query, get_models

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

        app.wsgi_app = MCPMiddleware(Middleware(app.wsgi_app), mcp_handler, middleware_config)
        app.jinja_env.add_extension(Extension)

        # In debug mode, exceptions are not logged [1], they propagate,
        # the debugger shows an error page and only writes to stderr [2].
        # We want the exceptions to appear in get_logs, so we log them
        # explicitly.
        #
        # [1]: https://flask.palletsprojects.com/en/stable/api/#flask.Flask.handle_exception
        # [2]: https://github.com/pallets/werkzeug/blob/3.1.3/src/werkzeug/debug/__init__.py#L378
        got_request_exception.connect(app_exception_handler, app)


def app_exception_handler(sender, exception, **extra):
    # We log to the default logger. This does not log to the terminal,
    # because terminal output comes from terminal handlers in more
    # specific flask/werkzeug loggers.
    logging.getLogger().exception(
        f"Exception on {request.path} [{request.method}]",
        exc_info=exception,
    )

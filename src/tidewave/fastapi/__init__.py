"""
FastAPI-specific integration for Tidewave
"""

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI

from a2wsgi import WSGIMiddleware

import __main__
from tidewave import tools
from tidewave.fastapi.middleware import Middleware
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as MCPMiddleware
from tidewave.tools.get_logs import file_handler


class Tidewave:
    """Initialize Tidewave with a FastAPI application.

    Configuration accepted on initialization:
      - allow_remote_access: bool (default False) - whether to allow remote connections
      - allowed_origins: list of allowed origin hosts (default [])
      - team: Enable Tidewave for teams
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}

    def install(self, app: FastAPI, sqlalchemy_base=None, sqlalchemy_engine=None):
        # Create WSGI app for MCP handling
        def wsgi_app(environ, start_response):
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found"]

        # Create MCP tools
        mcp_tools = [
            tools.get_docs,
            tools.get_logs,
            tools.get_source_location,
            tools.project_eval,
        ]

        if sqlalchemy_base is not None:
            from tidewave.sqlalchemy import get_models

            mcp_tools.extend([get_models(sqlalchemy_base)])

        if sqlalchemy_engine is not None:
            from tidewave.sqlalchemy import execute_sql_query

            mcp_tools.extend([execute_sql_query(sqlalchemy_engine)])

        mcp_handler = MCPHandler(mcp_tools)

        project_name = "fastapi_app"
        try:
            main_module = __main__.__file__
            project_name = os.path.splitext(os.path.basename(main_module))[0]
        except AttributeError:
            pass

        config = {
            **self.config,
            "framework_type": "fastapi",
            "project_name": project_name,
            "use_script_name": True,
        }

        mcp_middleware = MCPMiddleware(wsgi_app, mcp_handler, config)
        app.mount("/tidewave", WSGIMiddleware(mcp_middleware))
        app.add_middleware(Middleware)

        self._setup_logging()

    def _setup_logging(self):
        file_handler.addFilter(
            lambda record: not (
                (record.name == "uvicorn.access") and " /tidewave" in record.getMessage()
            )
        )

        # We set a global logger handler. The "uvicorn.error" logger
        # propagates [1], so it will also invoke that handler, on the
        # other hand, "uvicorn.access" logger does not propagate, so
        # we need to add the handler separately.
        #
        # [1]: https://github.com/Kludex/uvicorn/blob/0.37.0/uvicorn/config.py#L94-L98
        logging.getLogger().addHandler(file_handler)
        logging.getLogger("uvicorn.access").addHandler(file_handler)

"""
Basic tests for Flask middleware
"""

import unittest

from flask import Flask, Response

from flask_sqlalchemy import SQLAlchemy

from tidewave.flask.middleware import Middleware


class TestFlaskMiddleware(unittest.TestCase):
    """Test Flask middleware initialization and basic functionality"""

    def test_middleware_initialization_and_tools(self):
        """Test that Flask middleware initializes properly and has expected tools"""
        app = Flask(__name__)
        config = {"debug": True}

        middleware = Middleware(app, config)
        mcp_handler = middleware.get_mcp_handler()

        # Check that middleware and handler were created
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(mcp_handler)

        # Check that specific tools are available
        self.assertIn("project_eval", mcp_handler.tools)

    def test_flask_response_headers_modified(self):
        """Test that Flask response headers are modified by middleware"""
        app = Flask(__name__)

        @app.route("/flask/path")
        def flask_path():
            resp = Response("Flask response")
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; frame-ancestors 'none'"
            )
            return resp

        app.wsgi_app = Middleware(app, {})

        with app.test_client() as client:
            response = client.get("/flask/path")

            csp_value = response.headers.get("Content-Security-Policy", "")
            self.assertNotIn("X-Frame-Options", response.headers)
            self.assertIn("script-src 'self' 'unsafe-eval'", csp_value)
            self.assertNotIn("frame-ancestors", csp_value)
            self.assertIn("default-src 'none'", csp_value)

    def test_middleware_with_sqlalchemy(self):
        """Test that SQLAlchemy tools are added when SQLAlchemy is detected in Flask app"""

        app = Flask(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        db = SQLAlchemy()
        db.init_app(app)

        middleware = Middleware(app, {})
        mcp_handler = middleware.get_mcp_handler()

        # Check that middleware and handler were created
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(mcp_handler)

        # Check that basic tools are still available
        self.assertIn("project_eval", mcp_handler.tools)

        # Check that SQLAlchemy tools are available
        self.assertIn("get_models", mcp_handler.tools)
        self.assertIn("execute_sql_query", mcp_handler.tools)

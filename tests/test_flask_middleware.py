"""
Basic tests for Flask middleware
"""

import unittest
from unittest.mock import Mock

from flask import Flask, Response

from tidewave.flask import Middleware


class TestFlaskMiddleware(unittest.TestCase):
    """Test Flask middleware initialization and basic functionality"""

    def setUp(self):
        self.app = Flask(__name__)

    def test_middleware_initialization_and_tools(self):
        """Test that Flask middleware initializes properly and has expected tools"""
        mock_app = Mock()
        config = {"debug": True}

        middleware = Middleware(mock_app, config)
        mcp_handler = middleware.get_mcp_handler()

        # Check that middleware and handler were created
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(mcp_handler)

        # Check that specific tools are available
        self.assertIn("project_eval", mcp_handler.tools)

    def test_flask_response_headers_modified(self):
        """Test that Flask response headers are modified by middleware"""

        @self.app.route("/flask/path")
        def flask_path():
            resp = Response("Flask response")
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Content-Security-Policy"] = (
                "default-src 'none'; script-src 'self'; frame-ancestors 'none'"
            )
            return resp

        self.app.wsgi_app = Middleware(self.app.wsgi_app)

        with self.app.test_client() as client:
            response = client.get("/flask/path")

            csp_value = response.headers.get("Content-Security-Policy", "")
            self.assertNotIn("X-Frame-Options", response.headers)
            self.assertIn("script-src 'self' 'unsafe-eval'", csp_value)
            self.assertNotIn("frame-ancestors", csp_value)
            self.assertIn("default-src 'none'", csp_value)

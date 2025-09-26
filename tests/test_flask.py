"""
Tests for Flask Tidewave integration class
"""

import unittest

from flask import Flask, render_template_string

from flask_sqlalchemy import SQLAlchemy

from tidewave.flask import Tidewave


class TestFlaskTidewave(unittest.TestCase):
    """Test Flask Tidewave integration class"""

    def test_with_debug_mode(self):
        """Test that Tidewave initializes properly with Flask app in debug mode"""
        app = Flask(__name__)
        app.debug = True

        @app.route("/test")
        def test_route():
            return "Test response"

        tidewave = Tidewave({"allow_remote_access": True, "team": {"id": "dashbit"}})
        tidewave.init_app(app)

        # Verify middleware was applied (wsgi_app should be wrapped with Middleware)
        self.assertEqual(type(app.wsgi_app).__name__, "Middleware")

        # Verify tools
        mcp_handler = app.wsgi_app.mcp_handler
        self.assertIn("project_eval", mcp_handler.tools)

        # Verify config
        self.assertEqual("dashbit", app.wsgi_app.config["team"]["id"])
        self.assertEqual(True, app.wsgi_app.config["allow_remote_access"])

        # Verify Jinja extension was added
        extension_names = [ext.__class__.__name__ for ext in app.jinja_env.extensions.values()]
        self.assertIn("TemplateAnnotationExtension", extension_names)

        # Test that the app still works
        with app.test_client() as client:
            response = client.get("/test")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode(), "Test response")

    def test_with_production_mode(self):
        """Test that Tidewave does not initialize middleware in production mode"""
        app = Flask(__name__)
        app.debug = False  # Production mode

        # Store original wsgi_app type for comparison
        original_wsgi_app_type = type(app.wsgi_app).__name__

        @app.route("/test")
        def test_route():
            template = "<p>{{ 'Hello World' | upper }}</p>"
            return render_template_string(template)

        tidewave = Tidewave()
        tidewave.init_app(app)

        # Verify middleware was NOT applied (wsgi_app should still be original type)
        self.assertEqual(type(app.wsgi_app).__name__, original_wsgi_app_type)
        self.assertNotEqual(type(app.wsgi_app).__name__, "Middleware")

        # Verify Jinja extension was NOT added
        extension_names = [ext.__class__.__name__ for ext in app.jinja_env.extensions.values()]
        self.assertNotIn("TemplateAnnotationExtension", extension_names)

        # Test that the app still works normally
        with app.test_client() as client:
            response = client.get("/test")
            self.assertEqual(response.status_code, 200)
            self.assertIn("HELLO WORLD", response.data.decode())

    def test_with_sqlalchemy(self):
        """Test that SQLAlchemy tools are added when SQLAlchemy is detected in Flask app"""

        app = Flask(__name__)
        app.debug = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        db = SQLAlchemy()
        db.init_app(app)

        tidewave = Tidewave()
        tidewave.init_app(app)

        mcp_handler = app.wsgi_app.mcp_handler
        self.assertIn("project_eval", mcp_handler.tools)
        self.assertIn("get_models", mcp_handler.tools)
        self.assertIn("execute_sql_query", mcp_handler.tools)

    def test_x_frame_options_header_removal(self):
        """Test that X-Frame-Options header is removed by Tidewave middleware"""
        app = Flask(__name__)
        app.debug = True

        @app.route("/test")
        def test_route():
            from flask import make_response

            response = make_response("Test response")
            response.headers["X-Frame-Options"] = "DENY"
            return response

        tidewave = Tidewave()
        tidewave.init_app(app)

        # Test that X-Frame-Options header is removed
        with app.test_client() as client:
            response = client.get("/test")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode(), "Test response")
            # Verify X-Frame-Options header was removed
            self.assertNotIn("X-Frame-Options", response.headers)

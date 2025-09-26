"""
Tests for Flask Tidewave integration class
"""

import unittest

from flask import Flask, render_template_string

from tidewave.flask import Tidewave


class TestFlaskTidewave(unittest.TestCase):
    """Test Flask Tidewave integration class"""

    def test_tidewave_init_app_with_debug_mode(self):
        """Test that Tidewave initializes properly with Flask app in debug mode"""
        app = Flask(__name__)
        app.debug = True

        @app.route("/test")
        def test_route():
            return "Test response"

        tidewave = Tidewave()
        config = {"allow_remote_access": True, "team": True}
        tidewave.init_app(app, config)

        # Verify middleware was applied (wsgi_app should be wrapped with Middleware)
        self.assertEqual(type(app.wsgi_app).__name__, "Middleware")

        # Verify Jinja extension was added
        extension_names = [ext.__class__.__name__ for ext in app.jinja_env.extensions.values()]
        self.assertIn("TemplateAnnotationExtension", extension_names)

        # Test that the app still works
        with app.test_client() as client:
            response = client.get("/test")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data.decode(), "Test response")

    def test_tidewave_init_app_with_production_mode(self):
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
        config = {"allow_remote_access": False}
        tidewave.init_app(app, config)

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

"""
Basic tests for Django middleware
"""

import unittest
from unittest.mock import Mock

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from tidewave.django import Middleware


class TestDjangoMiddleware(unittest.TestCase):
    """Test Django middleware initialization and basic functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock()

    def test_middleware_initialization_and_tools(self):
        """Test that Django middleware initializes properly and has expected tools"""
        middleware = Middleware(self.get_response)

        # Check that middleware was created
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(middleware.mcp_handler)
        self.assertIsNotNone(middleware.base_middleware)

        # Check that specific tools are available
        self.assertIn("project_eval", middleware.mcp_handler.tools)

    def test_config_with_allow_remote_access(self):
        """Test that middleware uses Django's TIDEWAVE allow_remote_access setting"""
        with override_settings(TIDEWAVE={"allow_remote_access": True}):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allow_remote_access"], True)

        with override_settings(TIDEWAVE={"allow_remote_access": False}):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allow_remote_access"], False)

    def test_config_without_tidewave_settings(self):
        """Test that middleware defaults to allow_remote_access=False when no TIDEWAVE settings"""
        with override_settings(TIDEWAVE={}):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allow_remote_access"], False)

    def test_config_with_allowed_hosts_debug_false(self):
        """Test that middleware uses ALLOWED_HOSTS when DEBUG is False"""
        with override_settings(ALLOWED_HOSTS=["example.com", "api.example.com"], DEBUG=False):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allowed_origins"], ["example.com", "api.example.com"])

    def test_config_with_empty_allowed_hosts_debug_true(self):
        """
        Test that middleware defaults to local origins when ALLOWED_HOSTS is empty
        and DEBUG is True
        """
        with override_settings(ALLOWED_HOSTS=[], DEBUG=True):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allowed_origins"], [".localhost", "127.0.0.1", "::1"])

    def test_config_with_client_url(self):
        """Test that middleware uses CLIENT_URL setting"""
        with override_settings(TIDEWAVE={"client_url": "http://localhost:9000"}):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["client_url"], "http://localhost:9000")

    def test_config_with_project_name(self):
        """Test that middleware uses detects project name"""
        with override_settings(SETTINGS_MODULE="tidewave_django.settings"):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["project_name"], "tidewave_django")

        # Test fallback.
        with override_settings(SETTINGS_MODULE=None):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["project_name"], "django_app")

    def test_django_request_passes_through(self):
        """Test that non-tidewave requests pass through unchanged"""
        response = HttpResponse("Django response")
        self.get_response.return_value = response

        middleware = Middleware(self.get_response)
        request = self.factory.get("/django/path")

        response = middleware(request)

        self.assertIn("Django response", str(response.content))

    def test_django_response_headers_modified(self):
        """Test that Django response headers are modified by middleware"""

        response = HttpResponse("Django response")
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; frame-ancestors 'none'"
        )

        self.get_response.return_value = response

        middleware = Middleware(self.get_response)
        request = self.factory.get("/django/path")

        response = middleware(request)

        csp_value = response.headers.get("Content-Security-Policy", "")

        # Test that X-Frame-Options is removed
        self.assertNotIn("X-Frame-Options", response.headers)
        # Test that CSP is modified to allow Tidewave client
        self.assertIn("script-src 'self' 'unsafe-eval'", csp_value)
        self.assertNotIn("frame-ancestors", csp_value)
        # Test that original directives are preserved
        self.assertIn("default-src 'none'", csp_value)

    def test_django_request_to_wsgi_environ_conversion(self):
        """Test conversion from Django request to WSGI environ"""
        middleware = Middleware(self.get_response)
        request = self.factory.post(
            "/tidewave/mcp", data='{"test": "data"}', content_type="application/json"
        )

        environ = middleware._django_request_to_wsgi_environ(request)

        # Check basic WSGI environ keys
        self.assertEqual(environ["REQUEST_METHOD"], "POST")
        self.assertEqual(environ["PATH_INFO"], "/tidewave/mcp")
        self.assertEqual(environ["CONTENT_TYPE"], "application/json")
        self.assertIn("wsgi.input", environ)
        self.assertIn("REMOTE_ADDR", environ)

"""
Tests for Flask middleware header modification functionality
"""

import unittest

from tidewave.flask.middleware import Middleware


class TestFlaskMiddleware(unittest.TestCase):
    """Test Flask middleware header modification functionality"""

    def simple_wsgi_app(self, environ, start_response):
        """Simple WSGI app that returns headers we want to test"""
        headers = [
            ("Content-Type", "text/html"),
            ("X-Frame-Options", "DENY"),
            (
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; frame-ancestors 'none'",
            ),
        ]
        start_response("200 OK", headers)
        return [b"Hello World"]

    def simple_wsgi_app_no_headers(self, environ, start_response):
        """Simple WSGI app without security headers"""
        headers = [("Content-Type", "text/html")]
        start_response("200 OK", headers)
        return [b"Hello World"]

    def create_middleware(self, wsgi_app):
        """Helper to create middleware with minimal config"""
        return Middleware(wsgi_app)

    def test_headers_modified_for_normal_requests(self):
        """Test that response headers are modified for normal (non-tidewave) requests"""
        middleware = self.create_middleware(self.simple_wsgi_app)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
        }

        response_data = []
        response_headers = []

        def start_response(status, headers):
            response_headers.extend(headers)
            return lambda data: response_data.append(data)

        result = middleware(environ, start_response)
        list(result)  # Consume the iterator

        headers_dict = dict(response_headers)

        # X-Frame-Options should be removed
        self.assertNotIn("X-Frame-Options", headers_dict)

        # CSP should be modified to include unsafe-eval and remove frame-ancestors
        csp = headers_dict.get("Content-Security-Policy", "")
        self.assertIn("script-src 'self' 'unsafe-eval'", csp)
        self.assertNotIn("frame-ancestors", csp)
        self.assertIn("default-src 'none'", csp)

    def test_headers_not_modified_when_not_present(self):
        """Test that headers are not added if they weren't present originally"""
        middleware = self.create_middleware(self.simple_wsgi_app_no_headers)

        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
        }

        response_headers = []

        def start_response(status, headers):
            response_headers.extend(headers)
            return lambda data: None

        result = middleware(environ, start_response)
        list(result)  # Consume the iterator

        headers_dict = dict(response_headers)

        # Should only have Content-Type, no security headers added
        self.assertEqual(headers_dict.get("Content-Type"), "text/html")
        self.assertNotIn("X-Frame-Options", headers_dict)
        self.assertNotIn("Content-Security-Policy", headers_dict)

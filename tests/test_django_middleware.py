"""
Basic tests for Django middleware
"""

import unittest
from unittest.mock import Mock
import django
from django.conf import settings
from django.test import RequestFactory

# Configure Django settings for testing
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY='test-secret-key',
        INTERNAL_IPS=['127.0.0.1', '::1'],
        ALLOWED_HOSTS=[],
        USE_TZ=True,
    )
    django.setup()

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
        self.assertIn("add", middleware.mcp_handler.tools)
        self.assertIn("multiply", middleware.mcp_handler.tools)

    def test_config_with_internal_ips(self):
        """Test that middleware uses Django's INTERNAL_IPS setting"""
        with self.settings(INTERNAL_IPS=['192.168.1.1', '10.0.0.1']):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["internal_ips"], ['192.168.1.1', '10.0.0.1'])

    def test_config_with_allowed_hosts_debug_false(self):
        """Test that middleware uses ALLOWED_HOSTS when DEBUG is False"""
        with self.settings(ALLOWED_HOSTS=['example.com', 'api.example.com'], DEBUG=False):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allowed_origins"], ['example.com', 'api.example.com'])

    def test_config_with_empty_allowed_hosts_debug_true(self):
        """Test that middleware defaults to local origins when ALLOWED_HOSTS is empty and DEBUG is True"""
        with self.settings(ALLOWED_HOSTS=[], DEBUG=True):
            middleware = Middleware(self.get_response)
            config = middleware._build_config()

            self.assertEqual(config["allowed_origins"], [".localhost", "127.0.0.1", "::1"])

    def test_non_tidewave_request_passes_through(self):
        """Test that non-tidewave requests pass through unchanged"""
        middleware = Middleware(self.get_response)
        request = self.factory.get('/some/other/path')

        result = middleware.process_request(request)

        # Should return None to pass through to next middleware
        self.assertIsNone(result)

    def test_django_request_to_wsgi_environ_conversion(self):
        """Test conversion from Django request to WSGI environ"""
        middleware = Middleware(self.get_response)
        request = self.factory.post('/tidewave/mcp',
                                   data='{"test": "data"}',
                                   content_type='application/json')

        environ = middleware._django_request_to_wsgi_environ(request)

        # Check basic WSGI environ keys
        self.assertEqual(environ['REQUEST_METHOD'], 'POST')
        self.assertEqual(environ['PATH_INFO'], '/tidewave/mcp')
        self.assertEqual(environ['CONTENT_TYPE'], 'application/json')
        self.assertIn('wsgi.input', environ)
        self.assertIn('REMOTE_ADDR', environ)

    def settings(self, **kwargs):
        """Helper method to override Django settings"""
        from django.test import override_settings
        return override_settings(**kwargs)


if __name__ == "__main__":
    unittest.main()
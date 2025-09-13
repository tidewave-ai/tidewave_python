"""
Django-specific middleware for Tidewave MCP integration
"""

import io
from typing import Any, Callable

from django.conf import settings
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from tidewave import tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware


class Middleware(MiddlewareMixin):
    """Django middleware for Tidewave MCP integration

    This middleware integrates Tidewave MCP functionality into Django applications.
    It automatically configures security settings based on Django's INTERNAL_IPS,
    ALLOWED_HOSTS, and DEBUG settings.

    Usage:
        Add to Django's MIDDLEWARE setting:
        MIDDLEWARE = [
            ...
            'tidewave.django.Middleware',
            ...
        ]

    Configuration:
        The middleware automatically uses Django settings:
        - INTERNAL_IPS: Used for IP-based access control
        - ALLOWED_HOSTS: Used as allowed origins (when not empty or when DEBUG=False)
        - DEBUG: When True and ALLOWED_HOSTS is empty, allows local development
    """

    def __init__(self, get_response: Callable):
        """Initialize Django middleware"""
        super().__init__(get_response)
        self.get_response = get_response

        # Create MCP handler with tools
        self.mcp_handler = MCPHandler(
            [
                tools.project_eval,
            ]
        )

        # Create dummy WSGI app for base middleware
        def dummy_wsgi_app(environ, start_response):
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found"]

        # Configure middleware based on Django settings
        config = self._build_config()
        self.base_middleware = BaseMiddleware(dummy_wsgi_app, self.mcp_handler, config)

    def _build_config(self) -> dict[str, Any]:
        """Build configuration based on Django settings"""
        # Use Django's INTERNAL_IPS for IP-based access control
        internal_ips = getattr(settings, "INTERNAL_IPS", [])

        # Determine allowed origins from ALLOWED_HOSTS
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        debug = getattr(settings, "DEBUG", False)

        # In debug mode with empty ALLOWED_HOSTS, allow local development
        if not allowed_hosts and debug:
            allowed_hosts = [".localhost", "127.0.0.1", "::1"]

        # Grab Tidewave client URL
        client_url = getattr(settings, "TIDEWAVE", {}).get(
            "client_url", "https://tidewave.ai"
        )

        # Determine Django project name
        project_name = "django_app"
        try:
            project_name = settings.SETTINGS_MODULE.split(".")[0]
        except AttributeError:
            pass

        config = {
            "framework_type": "django",
            "project_name": project_name,
            "client_url": client_url,
            "internal_ips": internal_ips,
            "allowed_origins": allowed_hosts,
        }

        return config

    def process_request(self, request):
        """Process incoming request - let BaseMiddleware handle Tidewave routes"""
        # Only handle requests that start with /tidewave
        if not request.path.startswith("/tidewave"):
            return None

        # Convert Django request to WSGI environ
        environ = self._django_request_to_wsgi_environ(request)

        # Capture response from base middleware
        response_data = {"status": None, "headers": [], "body": []}

        def start_response(status, headers, exc_info=None):
            response_data["status"] = status
            response_data["headers"] = headers
            return lambda data: response_data["body"].append(data)

        # Let base middleware handle the request
        result = self.base_middleware(environ, start_response)

        # Convert WSGI response back to Django HttpResponse
        status_code = int(response_data["status"].split()[0])
        headers = dict(response_data["headers"])

        # Collect response body
        body = b"".join(result)

        response = HttpResponse(
            body,
            status=status_code,
            content_type=headers.get("Content-Type", "text/plain"),
        )

        # Add other headers
        for key, value in headers.items():
            if key.lower() != "content-type":
                response[key] = value

        return response

    def process_response(self, request, response):
        if "X-Frame-Options" in response:
            del response["X-Frame-Options"]

        return response

    def _django_request_to_wsgi_environ(self, request) -> dict[str, Any]:
        """Convert Django request to WSGI environ dict"""
        # Copy Django's META dict (which is the WSGI environ)
        environ = request.META.copy()

        # Inject the input stream
        environ["wsgi.input"] = io.BytesIO(request.body)

        return environ

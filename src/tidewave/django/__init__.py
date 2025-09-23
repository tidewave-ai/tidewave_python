"""
Django-specific middleware for Tidewave MCP integration
"""

import io
import logging
from typing import Any, Callable

from django.conf import settings
from django.http import HttpResponse
from django.utils.log import CallbackFilter

import tidewave.django.tools as django_tools
import tidewave.tools as tidewave_tools
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware, modify_csp
from tidewave.tools.get_logs import file_handler


class Middleware:
    """Django middleware for Tidewave MCP integration

    This middleware integrates Tidewave MCP functionality into Django applications.
    It automatically configures security settings based on Django's ALLOWED_HOSTS and
    DEBUG settings.

    Usage:
        # After MIDDLEWARE= and INSTALLED_APPS= definition
        if DEBUG:
            INSTALLED_APPS.insert(0, "tidewave.django.apps.TidewaveConfig")
            MIDDLEWARE.insert(0, 'tidewave.django.Middleware')

    Configuration:
        - ALLOWED_HOSTS: Used as allowed origins
        - TIDEWAVE['allow_remote_access']: Whether to allow remote connections (default False)
        - TIDEWAVE['team']: Enable Tidewave for teams

    Optional configuration:
        If you are using Jinja2 with Django, you need to explicitly add

        JINJA2_ENVIRONMENT_OPTIONS = {
            "extensions": [
                "tidewave.jinja2.Extension"
            ],
        }

    """

    def __init__(self, get_response: Callable):
        """Initialize Django middleware"""
        super().__init__()

        self.get_response = get_response

        self._setup_logging()

        # Create MCP handler with tools
        self.mcp_handler = MCPHandler(
            [
                django_tools.get_models,
                tidewave_tools.get_docs,
                tidewave_tools.get_logs,
                tidewave_tools.get_source_location,
                tidewave_tools.project_eval,
            ]
        )

        # Configure middleware based on Django settings
        self.config = self._build_config()

        self.base_middleware = BaseMiddleware(self._dummy_wsgi_app, self.mcp_handler, self.config)

    def _setup_logging(self):
        django_logger = logging.getLogger("django")
        if file_handler not in django_logger.handlers:
            file_handler.addFilter(
                CallbackFilter(lambda record: record.name != "django.utils.autoreload")
            )
            file_handler.addFilter(
                CallbackFilter(
                    lambda record: not (
                        record.name == "django.server" and "/tidewave" in record.getMessage()
                    )
                )
            )
            django_logger.addHandler(file_handler)
            django_logger.setLevel(logging.DEBUG)
            django_logger.propagate = False

    def _build_config(self) -> dict[str, Any]:
        """Build configuration based on Django settings"""
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        debug = getattr(settings, "DEBUG", False)

        # In debug mode with empty ALLOWED_HOSTS, allow local development
        if not allowed_hosts and debug:
            allowed_hosts = [".localhost", "127.0.0.1", "::1"]

        tidewave_settings = getattr(settings, "TIDEWAVE", {})
        allow_remote_access = tidewave_settings.get("allow_remote_access", False)
        client_url = tidewave_settings.get("client_url", "https://tidewave.ai")
        team = tidewave_settings.get("team", {})

        project_name = "django_app"
        try:
            project_name = settings.SETTINGS_MODULE.split(".")[0]
        except AttributeError:
            pass

        config = {
            "framework_type": "django",
            "project_name": project_name,
            "client_url": client_url,
            "allow_remote_access": allow_remote_access,
            "allowed_origins": allowed_hosts,
            "team": team,
        }

        return config

    def _dummy_wsgi_app(self, environ, start_response):
        """Dummy WSGI app for base middleware (should never be called for Tidewave routes)"""
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    def __call__(self, request):
        """
        Modern Django middleware interface.

        This method is called for each request and should return either:
        - None: Continue to the next middleware/view
        - HttpResponse: Short-circuit and return this response
        """
        # Check if this is a Tidewave route
        if request.path.startswith("/tidewave"):
            response = self._handle_tidewave_request(request)
            if response:
                return response

        # Handle Django request normally
        response = self.get_response(request)
        return self._process_response(request, response)

    def _handle_tidewave_request(self, request):
        """Handle Tidewave routes through base middleware"""

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

    def _django_request_to_wsgi_environ(self, request) -> dict[str, Any]:
        """Convert Django request to WSGI environ dict"""
        environ = request.META.copy()
        environ["wsgi.input"] = io.BytesIO(request.body)

        return environ

    def _process_response(self, request, response):
        """
        Modify headers to allow embedding in Tidewave:
        - Remove X-Frame-Options
        - Add unsafe-eval to script-src in CSP if present
        - Remove frame-ancestors from CSP if present

        """

        if "X-Frame-Options" in response:
            del response["X-Frame-Options"]

        csp_header = response.get("Content-Security-Policy")
        if csp_header:
            response["Content-Security-Policy"] = modify_csp(csp_header)

        return response

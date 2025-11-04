"""
Django-specific integration for Tidewave
"""

import io
import logging
import subprocess
import sys
import threading
import time
import traceback
from typing import Any, Callable

import django.utils.autoreload
from django.conf import settings
from django.http import HttpResponse

import tidewave.tools as tidewave_tools
from tidewave.django.models import get_models
from tidewave.django.sql import execute_sql_query
from tidewave.mcp_handler import MCPHandler
from tidewave.middleware import Middleware as BaseMiddleware, modify_csp
from tidewave.tools.get_logs import file_handler


def add_threading_except_hook():
    # Some errors prevent the server from starting, for example
    # a missing import in urls.py. The process keeps running, just
    # without the server. The LLM can fix the issue, then the watcher
    # restarts the server and it works as expected. To enable the LLM
    # to fix the issue, we need to surface the startup error in the
    # logs. The crash results from an uncaught exception in the Django
    # thread, so we patch the global excepthook, so that we write the
    # exception to the log file.

    original_threading_excepthook = threading.excepthook

    def tidewave_excepthook(args):
        if args.thread is not None and args.thread.name == "django-main-thread":
            formatted = "".join(
                traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
            )
            emit_error_log("Django terminated with exception:\n" + formatted)

        if original_threading_excepthook is not None:
            original_threading_excepthook(args)

    threading.excepthook = tidewave_excepthook


def patch_django_autoreload():
    original_restart_with_reloader = django.utils.autoreload.restart_with_reloader

    def new_restart_with_reloader():
        while True:
            # With autoreload enabled, Django has a top-level process,
            # which then starts a child server process. The child
            # process also runs a watcher and calls sys.exit(3) whenever
            # files change. The top-level process then tries to start
            # a new child. This loop is defined in restart_with_reloader [1].
            # If booting the child fails (for example, exception in
            # settings.py), the loop stops and all processes terminate.
            # We want to keep the process running, so we patch the
            # loop, such that on boot failure, we wait 1 second and
            # try booting again. We want to enable the LLM to see the
            # exception, so we run "python manage.py shell", which
            # should fail with the exception in stderr, and then we
            # write that exception to our log file.
            #
            # [1]: https://github.com/django/django/blob/5.2.6/django/utils/autoreload.py#L269-L275
            original_restart_with_reloader()

            manage_py_path = sys.argv[0]
            process = subprocess.run(
                [sys.executable, manage_py_path, "shell"], capture_output=True, text=True, input=""
            )

            if process.returncode != 0:
                print("[Tidewave] Django failed to boot, retrying in 2 seconds")
                emit_error_log(
                    "Django failed to boot, retrying in 2 seconds. Error:" + process.stderr
                )
                time.sleep(2)

    django.utils.autoreload.restart_with_reloader = new_restart_with_reloader


def emit_error_log(message: str):
    record = logging.LogRecord(
        name="tidewave",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )

    file_handler.emit(record)
    file_handler.flush()


add_threading_except_hook()
patch_django_autoreload()


class Middleware:
    """Django middleware for Tidewave MCP integration

    Usage:
        # After MIDDLEWARE= and INSTALLED_APPS= definition
        if DEBUG:
            INSTALLED_APPS.insert(0, "tidewave.django.apps.TidewaveConfig")
            MIDDLEWARE.insert(0, 'tidewave.django.Middleware')

    Configuration:
        - ALLOWED_HOSTS: Used as allowed origins
        - TIDEWAVE["allow_remote_access"]: Whether to allow remote connections (default False)
        - TIDEWAVE["team"]: Enable Tidewave for teams

    Optional configuration:
        If you are using Jinja2 with Django, you need to add our extension:

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
                execute_sql_query,
                get_models,
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
        file_handler.addFilter(lambda record: record.name != "django.utils.autoreload")
        file_handler.addFilter(
            lambda record: not (
                (record.name == "django.server" or record.name == "django.request")
                and " /tidewave" in record.getMessage()
            )
        )

        # Set global handler. The "django" logger propagates, so it
        # will also invoke that handler.
        logging.getLogger().addHandler(file_handler)
        # The "django.server" logger does not propagate, so we need
        # to add the handler separately.
        logging.getLogger("django.server").addHandler(file_handler)

    def _build_config(self) -> dict[str, Any]:
        """Build configuration based on Django settings"""
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
        debug = getattr(settings, "DEBUG", False)

        # In debug mode with empty ALLOWED_HOSTS, allow local development
        if not allowed_hosts and debug:
            allowed_hosts = [".localhost", "127.0.0.1", "::1"]

        project_name = "django_app"
        try:
            project_name = settings.SETTINGS_MODULE.split(".")[0]
        except AttributeError:
            pass

        config = {
            **getattr(settings, "TIDEWAVE", {}),
            "allowed_origins": allowed_hosts,
            "framework_type": "django",
            "project_name": project_name,
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

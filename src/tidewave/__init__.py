"""
Python WSGI Middleware for Model Context Protocol (MCP)
"""

from .middleware import Middleware

__version__ = "0.1.0"
__all__ = ["Middleware", "as_wsgi_app"]


def as_wsgi_app(config=None):
    """Create a WSGI app with Tidewave middleware that returns 404 for all routes except MCP endpoints"""

    def app(environ, start_response):
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]

    # Set use_script_name to True for mounted applications
    app_config = config.copy() if config else {}
    app_config["use_script_name"] = True

    return Middleware(app, app_config)

"""
Flask-specific middleware for dealing with CSP/frame headers.
"""

from typing import Any, Callable
from tidewave.middleware import modify_csp


class Middleware:
    def __init__(self, app: Callable):
        self.app = app

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        def handle_response(status, headers):
            modified_headers = self._process_response(headers)
            return start_response(status, modified_headers)

        return self.app(environ, handle_response)

    def _process_response(self, headers):
        """
        Modify headers to allow embedding in Tidewave:
        - Remove X-Frame-Options
        - Add unsafe-eval to script-src in CSP if present
        - Remove frame-ancestors from CSP if present
        """
        headers_dict = dict(headers)
        if "X-Frame-Options" in headers_dict:
            del headers_dict["X-Frame-Options"]
        if "Content-Security-Policy" in headers_dict:
            headers_dict["Content-Security-Policy"] = modify_csp(
                headers_dict["Content-Security-Policy"]
            )

        return list(headers_dict.items())

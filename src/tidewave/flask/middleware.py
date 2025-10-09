"""
Flask-specific middleware for dealing with CSP/frame headers.
"""

import logging
from typing import Any, Callable

from tidewave.middleware import modify_csp
from tidewave.tools.get_logs import file_handler


class Middleware:
    def __init__(self, app: Callable):
        self.app = app
        self.logging_initialized = False

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        self._maybe_initialize_logging()

        def handle_response(status, headers):
            modified_headers = self._process_response(headers)
            return start_response(status, modified_headers)

        return self.app(environ, handle_response)

    def _maybe_initialize_logging(self):
        # Ideally we would add the logger handler as part of
        # tidewave.flask.Tidewave, however that is too soon. Both
        # werkzeug [1] and flask [2] have conditional logic that adds
        # a default terminal handler, only if no other handler is
        # present, so if we add our handler too soon, no logs would
        # show up in the terminal. Instead, we add our handler on the
        # first request, by which point the default handler is already
        # added.
        #
        # [1]: https://github.com/pallets/werkzeug/blob/3.1.3/src/werkzeug/_internal.py#L94-L95
        # [2]: https://github.com/pallets/flask/blob/3.1.2/src/flask/logging.py#L76-L77

        if not self.logging_initialized:
            file_handler.addFilter(
                lambda record: not (
                    record.name == "werkzeug" and " /tidewave" in record.getMessage()
                )
            )
            logging.getLogger().addHandler(file_handler)
            self.logging_initialized = True

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

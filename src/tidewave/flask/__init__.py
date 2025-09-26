from typing import Any, Optional
from tidewave.flask.middleware import Middleware
from tidewave.jinja2 import Extension


class Tidewave:
    """Tidewave-Flask integration class."""

    def __init__(self):
        pass

    def init_app(self, app, config: Optional[dict[str, Any]] = None):
        """Initialize Tidewave with a Flask application.

        Args:
            app: Flask application instance
            config: Configuration dict with options:
                - allow_remote_access: bool (default False) - whether to allow remote connections
                - allowed_origins: list of allowed origin hosts (default [])
                - team: Enable Tidewave for teams
        """
        if app.debug:
            app.wsgi_app = Middleware(app, config or {})
            app.jinja_env.add_extension(Extension)

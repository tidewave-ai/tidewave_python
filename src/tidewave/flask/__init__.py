from typing import Any, Optional

from tidewave.flask.middleware import Middleware
from tidewave.jinja2 import Extension


class Tidewave:
    """Initialize Tidewave with a Flask application.

    Configuration accepted on initialization:
      - allow_remote_access: bool (default False) - whether to allow remote connections
      - allowed_origins: list of allowed origin hosts (default [])
      - team: Enable Tidewave for teams
    """

    def __init__(self, config: Optional[dict[str, Any]] = None):
        self.config = config or {}

    def init_app(self, app):
        if app.debug:
            app.wsgi_app = Middleware(app, self.config)
            app.jinja_env.add_extension(Extension)

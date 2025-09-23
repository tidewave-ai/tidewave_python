"""
uv run python examples/flask_app.py
"""
# ruff: noqa: T201 -- allow print statements

from flask import Flask, render_template

from tidewave.flask import Middleware
from tidewave.jinja2 import Extension as TidewaveJinjaExtension


def create_app():
    """Create a Flask app with MCP middleware"""
    app = Flask(__name__)

    # Configure Jinja2 with Tidewave extension
    app.jinja_env.add_extension(TidewaveJinjaExtension)

    @app.route("/")
    def home():
        return render_template("home.html", title="Flask + Tidewave MCP", message="Welcome to Flask with Jinja2 template debugging!")

    return app


def main():
    """Run the Flask app with MCP middleware"""
    flask_app = create_app()
    app_with_mcp = Middleware(flask_app)

    print("Starting Flask server on http://localhost:8000")
    print("Try sending MCP requests to http://localhost:8000/tidewave/mcp")
    print("Press Ctrl+C to stop")

    from wsgiref.simple_server import make_server

    server = make_server("localhost", 8000, app_with_mcp)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()

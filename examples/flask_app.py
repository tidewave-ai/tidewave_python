"""
uv run python examples/flask_app.py
"""
# ruff: noqa: T201 -- allow print statements

from flask import Flask

from tidewave.flask import Middleware


def create_app():
    """Create a Flask app with MCP middleware"""
    app = Flask(__name__)

    @app.route("/")
    def home():
        return """
        <html>
            <head><title>Flask + Tidewave MCP</title></head>
            <body><h1>Flask app with MCP middleware</h1></body>
        </html>
        """

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

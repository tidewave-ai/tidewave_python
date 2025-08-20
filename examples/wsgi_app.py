"""
uv run python examples/wsgi_app.py
"""

from wsgiref.simple_server import make_server
from tidewave import Middleware


def demo_app(environ, start_response):
    """Simple demo WSGI application"""
    status = "200 OK"
    headers = [("Content-type", "text/plain")]
    start_response(status, headers)
    return [b"Hello from demo WSGI app! Try POST to /tidewave/mcp"]


def main():
    """Run the demo server"""
    config = {
        "debug": True,
        "allow_remote_access": False,
        "allowed_origins": None,
    }

    wrapped_app = Middleware(demo_app, config)

    print("Starting WSGI server on http://localhost:8000")
    print("Try sending MCP requests to http://localhost:8000/tidewave/mcp")
    print("Press Ctrl+C to stop")

    server = make_server("localhost", 8000, wrapped_app)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()

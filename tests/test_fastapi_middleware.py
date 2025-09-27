"""
Basic tests for FastAPI integration
"""

import unittest

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from tidewave.fastapi import mount


class TestFastAPIIntegration(unittest.TestCase):
    """Test FastAPI integration initialization and basic functionality"""

    def test_mount_and_tools(self):
        """Test that FastAPI mount works properly and has expected tools"""
        app = FastAPI()
        config = {"debug": True}

        mount(app, config)

        # Check that tidewave route was mounted
        tidewave_routes = [
            route for route in app.routes if hasattr(route, "path") and "tidewave" in route.path
        ]
        self.assertEqual(len(tidewave_routes), 1)
        self.assertEqual(tidewave_routes[0].path, "/tidewave")

        # Get the mounted WSGI middleware and access the MCP handler
        wsgi_middleware = tidewave_routes[0].app
        base_middleware = wsgi_middleware.app
        mcp_handler = base_middleware.mcp_handler

        # Check that specific tools are available
        self.assertIn("project_eval", mcp_handler.tools)

    def test_fastapi_response_headers_modified(self):
        app = FastAPI()

        @app.get("/test")
        def test_router():
            content = "FastAPI response"
            headers = {"X-Frame-Options": "DENY"}
            return Response(content=content, headers=headers)

        mount(app)
        client = TestClient(app)
        response = client.get("/test")

        self.assertEqual(200, response.status_code)
        self.assertEqual("FastAPI response", response.content.decode())
        self.assertNotIn("X-Frame-Options", response.headers)

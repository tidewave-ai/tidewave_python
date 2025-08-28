"""
Basic tests for FastAPI integration
"""

import unittest
from fastapi import FastAPI
from tidewave.fastapi import mount


class TestFastAPIIntegration(unittest.TestCase):
    """Test FastAPI integration initialization and basic functionality"""

    def test_mount_and_tools(self):
        """Test that FastAPI mount works properly and has expected tools"""
        app = FastAPI()
        config = {"debug": True}

        mount(app, config)

        # Check that tidewave route was mounted
        tidewave_routes = [route for route in app.routes if hasattr(route, 'path') and 'tidewave' in route.path]
        self.assertEqual(len(tidewave_routes), 1)
        self.assertEqual(tidewave_routes[0].path, "/tidewave")

        # Get the mounted WSGI middleware and access the MCP handler
        wsgi_middleware = tidewave_routes[0].app
        base_middleware = wsgi_middleware.app
        mcp_handler = base_middleware.mcp_handler

        # Check that specific tools are available
        self.assertIn("add", mcp_handler.tools)
        self.assertIn("multiply", mcp_handler.tools)


if __name__ == "__main__":
    unittest.main()
"""
Basic tests for Flask middleware
"""

import unittest
from unittest.mock import Mock

from tidewave.flask import Middleware


class TestFlaskMiddleware(unittest.TestCase):
    """Test Flask middleware initialization and basic functionality"""

    def test_middleware_initialization_and_tools(self):
        """Test that Flask middleware initializes properly and has expected tools"""
        mock_app = Mock()
        config = {"debug": True}

        middleware = Middleware(mock_app, config)
        mcp_handler = middleware.get_mcp_handler()

        # Check that middleware and handler were created
        self.assertIsNotNone(middleware)
        self.assertIsNotNone(mcp_handler)

        # Check that specific tools are available
        self.assertIn("add", mcp_handler.tools)
        self.assertIn("multiply", mcp_handler.tools)


if __name__ == "__main__":
    unittest.main()

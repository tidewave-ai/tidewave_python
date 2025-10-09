"""
Tests for FastAPI Tidewave integration class
"""

import unittest

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base

from tidewave.fastapi import Tidewave


class TestFastAPITidewave(unittest.TestCase):
    """Test FastAPI Tidewave integration class"""

    def test_with_debug_mode(self):
        """Test that Tidewave initializes properly with FastAPI app in debug mode"""
        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"message": "Test response"}

        tidewave = Tidewave({"allow_remote_access": True, "team": {"id": "dashbit"}})
        tidewave.install(app)

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

        # Verify tools
        self.assertIn("project_eval", mcp_handler.tools)

        # Verify config
        self.assertEqual("dashbit", base_middleware.config["team"]["id"])
        self.assertEqual(True, base_middleware.config["allow_remote_access"])

        # Test that the app still works
        client = TestClient(app)
        response = client.get("/test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Test response"})

    def test_x_frame_options_and_csp_headers(self):
        """Test that X-Frame-Options and CSP headers"""
        app = FastAPI()

        @app.get("/test")
        def test_route():
            content = "Test response"
            headers = {
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; "
                "frame-ancestors 'none'",
            }
            return Response(content=content, headers=headers)

        tidewave = Tidewave()
        tidewave.install(app)

        # Test that X-Frame-Options header is removed
        client = TestClient(app)
        response = client.get("/test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Test response")
        # Verify X-Frame-Options header was removed
        self.assertNotIn("X-Frame-Options", response.headers)
        # Verify CSP updated
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self' 'unsafe-eval'", csp)
        self.assertNotIn("frame-ancestors", csp)
        self.assertIn("default-src 'none'", csp)

    def test_with_sqlalchemy(self):
        """Test that SQLAlchemy tools are added when SQLAlchemy parameters are provided"""
        app = FastAPI()

        # Create SQLAlchemy setup
        engine = create_engine("sqlite:///:memory:")
        Base = declarative_base()

        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        Base.metadata.create_all(engine)

        @app.get("/test")
        def test_route():
            return {"message": "Test response"}

        tidewave = Tidewave()
        tidewave.install(app, sqlalchemy_base=Base, sqlalchemy_engine=engine)

        # Get the mounted WSGI middleware and access the MCP handler
        tidewave_routes = [
            route for route in app.routes if hasattr(route, "path") and "tidewave" in route.path
        ]
        wsgi_middleware = tidewave_routes[0].app
        base_middleware = wsgi_middleware.app
        mcp_handler = base_middleware.mcp_handler

        # Verify SQLAlchemy tools were added
        self.assertIn("project_eval", mcp_handler.tools)
        self.assertIn("get_models", mcp_handler.tools)
        self.assertIn("execute_sql_query", mcp_handler.tools)

"""
uv run python examples/fastapi_app.py
"""
# ruff: noqa: T201 -- allow print statements

import asyncio

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from tidewave.fastapi import mount


def create_app():
    """Create a FastAPI app with mounted WSGI middleware"""
    app = FastAPI(title="FastAPI + Tidewave MCP")

    @app.get("/", response_class=HTMLResponse)
    async def fastapi_endpoint():
        return """
        <html>
            <head><title>FastAPI + Tidewave MCP</title></head>
            <body>
                <h1>FastAPI app with MCP middleware</h1>
            </body>
        </html>
        """

    mount(app)
    return app


async def main():
    """Run the FastAPI app with mounted WSGI middleware"""
    import uvicorn

    app = create_app()

    print("Starting FastAPI server on http://localhost:8000")
    print("Try sending MCP requests to http://localhost:8000/tidewave/mcp")
    print("Press Ctrl+C to stop")

    uvicorn_config = uvicorn.Config(app=app, host="localhost", port=8000, log_level="info")
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

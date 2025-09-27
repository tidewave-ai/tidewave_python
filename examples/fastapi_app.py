"""
uv run python examples/fastapi_app.py
"""
# ruff: noqa: T201 -- allow print statements

import asyncio
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from tidewave.fastapi import Tidewave
from tidewave.jinja2 import Extension as TidewaveJinjaExtension


def create_app():
    """Create a FastAPI app with mounted WSGI middleware"""
    app = FastAPI(title="FastAPI + Tidewave MCP")

    @app.get("/", response_class=HTMLResponse)
    async def fastapi_endpoint(request: Request):
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "title": "FastAPI + Tidewave MCP",
                "message": "Welcome to FastAPI with Jinja2 template debugging!",
            },
        )

    tidewave = Tidewave()
    tidewave.install(app)

    # Configure Jinja2 templates with Tidewave extension
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    templates.env.add_extension(TidewaveJinjaExtension)

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

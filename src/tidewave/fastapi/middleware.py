from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from tidewave.middleware import modify_csp


class Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/tidewave"):
            return await call_next(request)

        response = await call_next(request)
        return self._process_response(response)

    def _process_response(self, response):
        """
         Modify headers to allow embedding in Tidewave:
        - Remove X-Frame-Options
        - Add unsafe-eval to script-src in CSP if present
        - Remove frame-ancestors from CSP if present

        """
        if "X-Frame-Options" in response.headers:
            del response.headers["X-Frame-Options"]

        if "Content-Security-Policy" in response.headers:
            csp_value = response.headers["Content-Security-Policy"]
            response.headers["Content-Security-Policy"] = modify_csp(csp_value)

        return response

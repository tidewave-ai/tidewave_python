from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from tidewave.middleware import modify_csp


class Middleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request = self._process_requset(request)
        response = await call_next(request)
        return self._process_response(response)

    def _process_requset(self, request):
        # By default starlette redirects paths to their trailing slash
        # counterparts. To avoid such redirects for tidewave, we rewrite
        # the request path. See [1].
        #
        # Redirects are problematic, if there is a proxy in front of
        # the app, such as Vite dev server. The proxy may not rewrite
        # the redirect origin, so when the browser follows the redirect
        # it skips the proxy.
        #
        # [1]: https://github.com/Kludex/starlette/issues/869#issuecomment-908634218
        if request.scope["path"] == "/tidewave":
            request.scope["path"] = "/tidewave/"
            request.scope["raw_path"] = b"/tidewave/"

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

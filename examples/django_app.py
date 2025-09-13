"""
uv run python examples/django_app.py
"""
# ruff: noqa: T201 -- allow print statements

import django
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.http import HttpResponse
from django.urls import path


def create_app():
    """Create a Django app configuration"""
    settings.configure(
        DEBUG=True,
        SECRET_KEY="django-insecure-example-key-not-for-production",
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.common.CommonMiddleware",
            "tidewave.django.Middleware",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
    )
    django.setup()
    return get_wsgi_application()


def home_view(request):
    """Simple home view"""
    return HttpResponse("""
    <html>
        <head><title>Django + Tidewave MCP</title></head>
        <body>
            <h1>Django app with MCP middleware</h1>
        </body>
    </html>
    """)


urlpatterns = [
    path("", home_view, name="home"),
]


def main():
    """Run the Django app"""
    django_app = create_app()

    print("Starting Django server on http://localhost:8000")
    print("Try sending MCP requests to http://localhost:8000/tidewave/mcp")
    print("Press Ctrl+C to stop")

    from wsgiref.simple_server import make_server

    server = make_server("localhost", 8000, django_app)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()

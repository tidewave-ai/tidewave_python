import os

import django
from django.conf import settings


def configure_django_for_tests():
    """Configure Django with unified test settings."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            SECRET_KEY="test-secret-key-for-tidewave-tests",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
            ],
            MIDDLEWARE=[],
            TEMPLATES=[
                {
                    "BACKEND": "django.template.backends.django.DjangoTemplates",
                    "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
                    "APP_DIRS": True,
                    "OPTIONS": {
                        "context_processors": [
                            "django.template.context_processors.debug",
                        ],
                    },
                },
            ],
            USE_TZ=True,
            ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost"],
            TIDEWAVE={
                "allow_remote_access": False,
                "client_url": "http://localhost:3000",
            },
        )
        django.setup()


# Configure Django when this module is imported
configure_django_for_tests()

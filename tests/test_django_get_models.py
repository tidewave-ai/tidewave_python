"""
Tests for Django get_models tool
"""

import re
from pathlib import Path
from unittest.mock import Mock, patch

import django
from django.conf import settings
from django.test import TestCase

from tidewave.django.tools import get_models
from tidewave.django.tools.models import _get_relative_source_location

if not settings.configured:
    settings.configure(
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
        SECRET_KEY="test-secret-key",
        USE_TZ=True,
    )
    django.setup()


class TestDjangoGetModels(TestCase):
    def test_get_models(self):
        """Test get_models with Django models."""
        result = get_models()

        # Should contain Django's built-in models
        self.assertIn("User", result)
        self.assertIn("Group", result)
        self.assertIn("Permission", result)
        self.assertIn("ContentType", result)

        # Should have bullet point format
        lines = result.strip().split("\n")
        for line in lines:
            self.assertTrue(line.startswith("* "))

        # Should include source locations if available
        self.assertTrue(re.search(r"\* \w+ at .+\.py:\d+", result))

    def test_get_models_excludes_abstract_models(self):
        """Test that abstract models are excluded from results."""
        # Create a mock abstract model
        mock_abstract_model = Mock()
        mock_abstract_model.__name__ = "AbstractTestModel"
        mock_abstract_model._meta.abstract = True

        # Create a mock concrete model
        mock_concrete_model = Mock()
        mock_concrete_model.__name__ = "ConcreteTestModel"
        mock_concrete_model._meta.abstract = False

        with patch("django.apps.apps.get_models") as mock_get_models:
            mock_get_models.return_value = [mock_abstract_model, mock_concrete_model]

            result = get_models()

            self.assertIn("ConcreteTestModel", result)
            self.assertNotIn("AbstractTestModel", result)

    def test_get_models_no_models_found(self):
        """Test behavior when no models are found."""
        with patch("django.apps.apps.get_models") as mock_get_models:
            mock_get_models.return_value = []

            result = get_models()

            self.assertEqual(result, "No models found in the Django application")

    def test_get_models_sorts_by_model_name(self):
        """Test that models are sorted by name."""
        # Create mock models with names that would be unsorted
        mock_models = []
        for name in ["ZebraModel", "AlphaModel", "BetaModel"]:
            mock_model = Mock()
            mock_model.__name__ = name
            mock_model._meta.abstract = False
            mock_models.append(mock_model)

        with patch("django.apps.apps.get_models") as mock_get_models:
            with patch(
                "tidewave.django.tools.models._get_relative_source_location"
            ) as mock_location:
                mock_get_models.return_value = mock_models
                mock_location.return_value = "test.py:1"

                result = get_models()

                lines = result.strip().split("\n")
                self.assertIn("AlphaModel", lines[0])
                self.assertIn("BetaModel", lines[1])
                self.assertIn("ZebraModel", lines[2])

    def test_get_relative_source_location_with_relative_path(self):
        """Test _get_relative_source_location with a path that can be made relative."""

        mock_model = Mock()

        cwd = Path.cwd()
        test_file = cwd / "myapp" / "models.py"

        with patch("inspect.getsourcefile") as mock_getsourcefile:
            with patch("inspect.getsourcelines") as mock_getsourcelines:
                mock_getsourcefile.return_value = str(test_file)
                mock_getsourcelines.return_value = ([], 42)

                result = _get_relative_source_location(mock_model)

                self.assertEqual(result, "myapp/models.py:42")

    def test_get_relative_source_location_with_absolute_path(self):
        """Test _get_relative_source_location with a path that cannot be made relative."""

        mock_model = Mock()

        absolute_path = "/usr/lib/python3.x/site-packages/django/contrib/auth/models.py"

        with patch("inspect.getsourcefile") as mock_getsourcefile:
            with patch("inspect.getsourcelines") as mock_getsourcelines:
                mock_getsourcefile.return_value = absolute_path
                mock_getsourcelines.return_value = ([], 123)

                result = _get_relative_source_location(mock_model)

                self.assertEqual(result, f"{absolute_path}:123")

    def test_get_relative_source_location_with_no_source(self):
        """Test _get_relative_source_location when source cannot be found."""

        mock_model = Mock()

        with patch("inspect.getsourcefile") as mock_getsourcefile:
            mock_getsourcefile.return_value = None

            result = _get_relative_source_location(mock_model)

            self.assertIsNone(result)

    def test_get_relative_source_location_with_inspect_error(self):
        """Test _get_relative_source_location when inspect raises an error."""

        mock_model = Mock()

        with patch("inspect.getsourcefile") as mock_getsourcefile:
            mock_getsourcefile.side_effect = OSError("Cannot get source file")

            result = _get_relative_source_location(mock_model)

            self.assertIsNone(result)

    def test_model_without_source_location(self):
        """Test handling of models that don't have source locations."""
        mock_model = Mock()
        mock_model.__name__ = "TestModel"
        mock_model._meta.abstract = False

        with patch("django.apps.apps.get_models") as mock_get_models:
            with patch(
                "tidewave.django.tools.models._get_relative_source_location"
            ) as mock_location:
                mock_get_models.return_value = [mock_model]
                mock_location.return_value = None

                result = get_models()

                self.assertEqual(result.strip(), "* TestModel")

import re
import unittest
from unittest.mock import patch

from tidewave.tools.source import get_source_location


class TestGetSourceLocation(unittest.TestCase):
    """Test suite for get_source_location function."""

    def test_get_source_location_with_valid_module(self):
        """Test calling the function with a valid module reference."""
        result = get_source_location("pathlib.Path")
        self.assertTrue("pathlib" in result)
        self.assertTrue(re.search(r"\.py:\d+$", result))

    def test_get_source_location_with_class_method(self):
        """Test calling the function with a class method reference."""
        result = get_source_location("pathlib.Path.cwd")
        self.assertTrue("pathlib" in result)
        self.assertTrue(re.search(r"\.py:\d+$", result))

    def test_get_source_location_with_pure_python_function(self):
        """Test calling the function with a pure Python function."""
        result = get_source_location("json.loads")
        self.assertTrue("json" in result)
        self.assertTrue(re.search(r"\.py:\d+$", result))

    def test_get_source_location_with_nonexistent_module(self):
        """Test calling the function with a non-existent module."""
        with self.assertRaises(NameError) as cm:
            get_source_location("NonExistentModule")
        self.assertIn("could not find source location for NonExistentModule", str(cm.exception))

    def test_get_source_location_with_invalid_reference(self):
        """Test calling the function with an invalid reference format."""
        with self.assertRaises((NameError, ValueError)):
            get_source_location("1+2")

    def test_get_source_location_with_nonexistent_method(self):
        """Test calling the function with a non-existent method."""
        with self.assertRaises(NameError):
            get_source_location("pathlib.Path.unknown_method")

    def test_get_source_location_with_builtin_function_fails_gracefully(self):
        """Test that built-in functions that have no source fail gracefully."""
        with self.assertRaises(NameError) as cm:
            get_source_location("len")
        self.assertIn("could not find source location for len", str(cm.exception))

    def test_get_source_location_with_c_extension_fails_gracefully(self):
        """Test that C extension functions fail gracefully."""
        with self.assertRaises(NameError) as cm:
            get_source_location("dict.get")  # Built-in method, always C extension
        self.assertIn("could not find source location for dict.get", str(cm.exception))

    def test_empty_or_none_reference(self):
        """Test that empty or None reference raises appropriate error."""
        for reference in ("", 123, None):
            with self.assertRaises(ValueError) as cm:
                get_source_location(reference)  # type: ignore
            self.assertIn("Reference must be a non-empty string", str(cm.exception))

    def test_various_python_references(self):
        """Test various types of Python references."""
        test_cases = [
            ("collections.Counter", True),  # Pure Python class
            ("datetime.datetime", True),  # Mixed implementation class
            ("json.loads", True),  # Pure Python function
            ("pathlib.Path.resolve", True),  # Pure Python method
            ("pathlib.Path.walk", True),  # Pure Python method, only in 3.12+
            ("", False),
            ("invalid_module", False),
            ("invalid_module.invalid_function", False),
        ]

        for reference, should_succeed in test_cases:
            if should_succeed:
                try:
                    result = get_source_location(reference)
                    self.assertTrue(re.search(r"\.py:\d+", result))
                except NameError:
                    # Some references might not be available in all Python versions
                    self.skipTest(f"Reference {reference} not available in this Python version")
            else:
                with self.assertRaises((NameError, ValueError)):
                    get_source_location(reference)

    def test_inspect_error_handling(self):
        """Test handling of inspect module errors."""

        class MockObject:
            def __getattr__(self, name):
                raise OSError("Mock inspect error")

        with patch("tidewave.tools.source._resolve_reference", return_value=MockObject()):
            with self.assertRaises(NameError):
                get_source_location("mock_obj")

    def test_exception_wrapping_in_get_source_location(self):
        """Test that get_source_location properly wraps and re-raises exceptions."""

        # Test ValueError is re-raised as-is
        with self.assertRaises(ValueError) as cm:
            get_source_location("")  # Empty string should raise ValueError
        self.assertIn("Reference must be a non-empty string", str(cm.exception))

        # Test NameError is re-raised as-is
        with self.assertRaises(NameError) as cm:
            get_source_location("nonexistent_module_xyz")
        self.assertIn("could not find source location", str(cm.exception))

    def test_various_inspect_scenarios(self):
        """Test different scenarios that might affect inspect module behavior."""

        test_lambda = lambda x: x  # noqa: E731

        with patch("tidewave.tools.source._resolve_reference", return_value=test_lambda):
            result = get_source_location("test_lambda")
            self.assertIsInstance(result, str)
            self.assertTrue(re.search(r"\.py:\d+$", result))

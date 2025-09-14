import re
import sys
import unittest
from unittest.mock import patch

from tidewave.tools.get_src_location import (
    _resolve_reference,
    _traverse_attrs,
    get_source_location,
)


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

    def test_resolve_reference_strategies(self):
        """Test that different resolution strategies work."""
        # Test direct module import
        obj = _resolve_reference("json")
        self.assertIsNotNone(obj)

        # Test attribute access
        obj = _resolve_reference("json.loads")
        self.assertIsNotNone(obj)
        self.assertTrue(callable(obj))

        # Test built-ins (should work for resolution but fail for source location)
        obj = _resolve_reference("len")
        self.assertIsNotNone(obj)
        self.assertTrue(callable(obj))

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

        with patch("tidewave.tools.get_src_location._resolve_reference", return_value=MockObject()):
            with self.assertRaises(NameError):
                get_source_location("mock_obj")

    def test_sys_modules_fallback(self):
        """Test that _resolve_reference properly uses sys.modules fallback."""

        class MockModule:
            def test_attr(self):
                return "test"

        mock_module = MockModule()
        sys.modules["test_mock_module"] = mock_module

        try:
            result = _resolve_reference("test_mock_module.test_attr")
            self.assertIsNotNone(result)
            self.assertEqual(result(), "test")
        finally:
            if "test_mock_module" in sys.modules:
                del sys.modules["test_mock_module"]

    def test_builtins_fallback(self):
        """Test that _resolve_reference properly uses builtins fallback."""
        result = _resolve_reference("len")
        self.assertIsNotNone(result)
        self.assertTrue(callable(result))
        self.assertEqual(result([1, 2, 3]), 3)

    def test_progressive_import_strategy(self):
        """Test the progressive import strategy in _resolve_reference."""
        result = _resolve_reference("pathlib.Path.cwd")
        self.assertIsNotNone(result)
        self.assertTrue(callable(result))

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

        with patch("tidewave.tools.get_src_location._resolve_reference", return_value=test_lambda):
            result = get_source_location("test_lambda")
            self.assertIsInstance(result, str)
            self.assertTrue(re.search(r"\.py:\d+$", result))

    def test_traverse_attrs_helper(self):
        """Test the _traverse_attrs helper function."""

        # Test with a simple object
        class TestObj:
            class NestedObj:
                value = "test"

        obj = TestObj()
        result = _traverse_attrs(obj, ["NestedObj", "value"])
        self.assertEqual(result, "test")

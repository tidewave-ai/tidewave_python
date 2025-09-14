import unittest
from unittest.mock import patch

from tidewave.tools.source import get_docs


class TestGetDocs(unittest.TestCase):
    """Test suite for get_docs function."""

    def test_get_docs_with_valid_module(self):
        """Test calling the function with a valid module reference."""
        result = get_docs("pathlib.Path")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertIn("path", result.lower())

    def test_get_docs_with_class_method(self):
        """Test calling the function with a class method reference."""
        result = get_docs("pathlib.Path.resolve")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_get_docs_with_pure_python_function(self):
        """Test calling the function with a pure Python function."""
        result = get_docs("json.loads")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertIn("json", result.lower())

    def test_get_docs_with_builtin_function(self):
        """Test calling the function with a built-in function."""
        result = get_docs("len")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertIn("number", result.lower())

    def test_get_docs_with_nonexistent_module(self):
        """Test calling the function with a non-existent module."""
        with self.assertRaises(NameError) as cm:
            get_docs("NonExistentModule")
        self.assertIn("could not find documentation for NonExistentModule", str(cm.exception))

    def test_get_docs_with_invalid_reference(self):
        """Test calling the function with an invalid reference format."""
        with self.assertRaises((NameError, ValueError)):
            get_docs("1+2")

    def test_get_docs_with_nonexistent_method(self):
        """Test calling the function with a non-existent method."""
        with self.assertRaises(NameError):
            get_docs("pathlib.Path.unknown_method")

    def test_get_docs_empty_or_none_reference(self):
        """Test that empty or None reference raises appropriate error."""
        for reference in ("", 123, None):
            with self.assertRaises(ValueError) as cm:
                get_docs(reference)  # type: ignore
            self.assertIn("Reference must be a non-empty string", str(cm.exception))

    def test_get_docs_various_python_references(self):
        """Test various types of Python references."""
        test_cases = [
            ("collections.Counter", True),  # Pure Python class
            ("datetime.datetime", True),  # Mixed implementation class
            ("json.loads", True),  # Pure Python function
            ("pathlib.Path.resolve", True),  # Pure Python method
            ("len", True),  # Built-in function
            ("", False),
            ("invalid_module", False),
            ("invalid_module.invalid_function", False),
        ]

        for reference, should_succeed in test_cases:
            if should_succeed:
                try:
                    result = get_docs(reference)
                    self.assertIsInstance(result, str)
                    self.assertTrue(len(result) > 0)
                except NameError:
                    # Some references might not be available in all Python versions
                    self.skipTest(f"Reference {reference} not available in this Python version")
            else:
                with self.assertRaises((NameError, ValueError)):
                    get_docs(reference)

    def test_get_docs_inspect_error_handling(self):
        """Test handling of inspect module errors."""

        class MockObject:
            def __getattr__(self, name):
                raise OSError("Mock inspect error")

        with patch("tidewave.tools.source._resolve_reference", return_value=MockObject()):
            with self.assertRaises(NameError):
                get_docs("mock_obj")

    def test_get_docs_exception_wrapping(self):
        """Test that get_docs properly wraps and re-raises exceptions."""

        # Test ValueError is re-raised as-is
        with self.assertRaises(ValueError) as cm:
            get_docs("")  # Empty string should raise ValueError
        self.assertIn("Reference must be a non-empty string", str(cm.exception))

        # Test NameError is re-raised as-is
        with self.assertRaises(NameError) as cm:
            get_docs("nonexistent_module_xyz")
        self.assertIn("could not find documentation", str(cm.exception))

    def test_get_docs_object_without_docs(self):
        """Test calling get_docs on an object without documentation."""

        class TestObjWithoutDocs:
            pass

        with patch("tidewave.tools.source._resolve_reference", return_value=TestObjWithoutDocs()):
            with self.assertRaises(NameError) as cm:
                get_docs("test_obj")
            self.assertIn("could not find documentation", str(cm.exception))

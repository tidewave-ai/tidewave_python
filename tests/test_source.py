import sys
import unittest

from tidewave.tools.source import _resolve_reference


class TestSource(unittest.TestCase):
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

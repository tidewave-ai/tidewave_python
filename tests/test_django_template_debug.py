from pathlib import Path
from unittest.mock import Mock, patch

from django.template import Context, Template
from django.template.loader_tags import ExtendsNode
from django.test import TestCase, override_settings

from tidewave.django.apps import TidewaveConfig
from tidewave.django.templates import clean_template_path, debug_render, get_debug_name

TEST_SETTINGS = {
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    },
    "TEMPLATES": [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
            },
        },
    ],
    "TIDEWAVE": {
        "allow_remote_access": False,
    },
}


@override_settings(**TEST_SETTINGS)
class TestTemplateDebugRender(TestCase):
    """Test Django template debug rendering functionality"""

    def setUp(self):
        # Store original render method
        Template._original_render = Template.render
        # Reset patching state
        if hasattr(Template, "_debug_patched"):
            delattr(Template, "_debug_patched")

    def tearDown(self):
        """Clean up after tests"""
        # Restore original render method
        Template.render = Template._original_render
        # Clean up patching attributes
        for attr in ["_get_debug_name", "_clean_template_path", "_debug_patched"]:
            if hasattr(Template, attr):
                delattr(Template, attr)

    def _apply_debug_patch(self):
        """Helper to apply the debug patch manually"""
        # This mimics the patch_template_render method in `TidewaveConfig` without depending on
        # Django calling `ready()`.
        original_render = Template.render

        # Apply the patches
        Template.render = debug_render
        Template._get_debug_name = get_debug_name
        Template._clean_template_path = clean_template_path
        Template._debug_patched = True

    def test_html_template_gets_debug_comments(self):
        """Test that HTML templates get wrapped with debug comments"""
        self._apply_debug_patch()

        template_content = "<div>Hello World</div>"
        template = Template(template_content)

        template.origin = Mock()
        template.origin.template_name = "test.html"

        result = template.render(Context({}))

        expected_start = "<!-- Template: test.html  -->"
        expected_end = "<!-- End Template: test.html -->"

        self.assertIn(expected_start, result)
        self.assertIn(expected_end, result)
        self.assertIn(template_content, result)

    def test_non_html_template_unchanged(self):
        """Test that non-HTML content is not wrapped with debug comments"""
        self._apply_debug_patch()

        template_content = "Plain text content"
        template = Template(template_content)

        template.origin = Mock()
        template.origin.template_name = "test.txt"

        result = template.render(Context({}))

        self.assertNotIn("<!-- Template:", result)
        self.assertNotIn("<!-- End Template:", result)
        self.assertEqual(result, template_content)

    def test_json_template_unchanged(self):
        """Test that JSON content is not wrapped with debug comments"""
        self._apply_debug_patch()

        template_content = '{"key": "value"}'
        template = Template(template_content)

        template.origin = Mock()
        template.origin.template_name = "test.json"

        result = template.render(Context({}))

        self.assertNotIn("<!-- Template:", result)
        self.assertEqual(result, template_content)

    def test_template_with_extends_shows_parent(self):
        """Test that templates with extends show parent template info"""
        self._apply_debug_patch()

        template_content = "<div>Child content</div>"
        template = Template(template_content)
        template.origin = Mock()
        template.origin.template_name = "child.html"

        extends_node = Mock(spec=ExtendsNode)
        extends_node.parent_name = "'base.html'"
        extends_node.render_annotated.return_value = ""  # ExtendsNode doesn't render content
        template.nodelist.insert(0, extends_node)

        result = template.render(Context({}))

        expected_start = "<!-- Template: child.html (extends: base.html) -->"
        expected_end = "<!-- End Template: child.html -->"

        self.assertIn(expected_start, result)
        self.assertIn(expected_end, result)

    def test_template_origin_name_fallback(self):
        """Test fallback to origin.name when template_name not available"""
        self._apply_debug_patch()

        template_content = "<p>Test content</p>"
        template = Template(template_content)

        template.origin = Mock()
        template.origin.name = "fallback.html"
        # Remove template_name to test fallback
        if hasattr(template.origin, "template_name"):
            delattr(template.origin, "template_name")

        result = template.render(Context({}))

        expected_start = "<!-- Template: fallback.html  -->"
        self.assertIn(expected_start, result)

    def test_template_name_attribute_fallback(self):
        """Test fallback to template.name when origin not available"""
        self._apply_debug_patch()

        template_content = "<span>Another test</span>"
        template = Template(template_content)

        template.name = "direct_name.html"
        # Remove origin to test fallback
        template.origin = None

        result = template.render(Context({}))

        expected_start = "<!-- Template: direct_name.html  -->"
        self.assertIn(expected_start, result)

    def test_no_template_name_available(self):
        """Test behavior when no template name is available"""
        self._apply_debug_patch()

        template_content = "<div>No name template</div>"
        template = Template(template_content)

        result = template.render(Context({}))

        self.assertEqual(result, template_content)
        self.assertNotIn("<!-- Template:", result)

    def test_clean_template_path_absolute_path(self):
        """Test cleaning absolute template paths relative to BASE_DIR"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        with override_settings(BASE_DIR="/test/project"):
            result = template._clean_template_path("/test/project/templates/app/test.html")
            expected = Path("templates/app/test.html")
            self.assertEqual(result, expected)

    def test_clean_template_path_relative_path(self):
        """Test that relative paths are returned as Path objects"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        result = template._clean_template_path("templates/test.html")
        expected = Path("templates/test.html")
        self.assertEqual(result, expected)

    def test_clean_template_path_none_input(self):
        """Test clean_template_path with None input"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        result = template._clean_template_path(None)
        self.assertIsNone(result)

    def test_get_debug_name_with_extends(self):
        """Test get_debug_name method with extends node"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")
        template.origin = Mock()
        template.origin.template_name = "test.html"

        extends_node = Mock(spec=ExtendsNode)
        extends_node.parent_name = "'base.html'"
        extends_node.render_annotated.return_value = ""
        template.nodelist.insert(0, extends_node)

        name, extends = template._get_debug_name()

        self.assertEqual(name, "test.html")
        self.assertEqual(extends, "base.html")

    def test_get_debug_name(self):
        """Test get_debug_name method"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")
        template.origin = Mock()
        template.origin.template_name = "test.html"

        name, extends = template._get_debug_name()

        self.assertEqual(name, "test.html")
        self.assertIsNone(extends)

    @override_settings(DEBUG=False)
    def test_config_ready_not_applied_when_debug_false(self):
        """Test that template patching is not applied when DEBUG=False"""
        # Reset patching state
        if hasattr(Template, "_debug_patched"):
            delattr(Template, "_debug_patched")

        # Mock the app module properly
        with patch("tidewave.django.apps.TidewaveConfig") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.ready.return_value = None

            config = TidewaveConfig.__new__(TidewaveConfig)
            config.name = "tidewave.django"

            config.ready()

            self.assertFalse(getattr(Template, "_debug_patched", False))

    @override_settings(DEBUG=True)
    def test_config_ready_applied_when_debug_true(self):
        """Test that template patching is applied when DEBUG=True"""
        # Reset patching state
        if hasattr(Template, "_debug_patched"):
            delattr(Template, "_debug_patched")

        config = TidewaveConfig.__new__(TidewaveConfig)
        config.name = "tidewave.django"

        config.ready()

        self.assertTrue(getattr(Template, "_debug_patched", False))

    def test_complex_html_template_with_context(self):
        """Test debug rendering with complex HTML and template context"""
        self._apply_debug_patch()

        template_content = """
        <html>
        <head><title>{{ title }}</title></head>
        <body>
            <h1>{{ heading }}</h1>
            <p>{{ content }}</p>
        </body>
        </html>
        """

        template = Template(template_content)
        template.origin = Mock()
        template.origin.template_name = "complex.html"

        context = Context(
            {"title": "Hi Tidewave!", "heading": "Test", "content": "This is test content"}
        )

        result = template.render(context)

        self.assertIn("<!-- Template: complex.html  -->", result)
        self.assertIn("<!-- End Template: complex.html -->", result)

        self.assertIn("<title>Hi Tidewave!</title>", result)
        self.assertIn("<h1>Test</h1>", result)
        self.assertIn("<p>This is test content</p>", result)

    def test_whitespace_handling(self):
        """Test that whitespace in templates is handled correctly"""
        self._apply_debug_patch()

        template_content = "   \n  <div>Content</div>  \n  "
        template = Template(template_content)
        template.origin = Mock()
        template.origin.template_name = "whitespace.html"

        result = template.render(Context({}))

        self.assertIn("<!-- Template: whitespace.html  -->", result)
        self.assertIn("<!-- End Template: whitespace.html -->", result)
        self.assertIn("<div>Content</div>", result)

    def test_template_without_html_content_detection(self):
        """Test various non-HTML content types are not wrapped"""
        self._apply_debug_patch()

        test_cases = [
            "",
            "Just plain text",
            "123 numeric content",
            "\n\n  Some text with whitespace  \n",
            "Text with < bracket but not HTML",
            "email@example.com content",
            'attr1="value1", attr2="value2"',
        ]

        for content in test_cases:
            with self.subTest(content=content):
                template = Template(content)
                template.origin = Mock()
                template.origin.template_name = "test.txt"

                result = template.render(Context({}))

                self.assertNotIn("<!-- Template:", result)
                self.assertEqual(result.strip(), content.strip())

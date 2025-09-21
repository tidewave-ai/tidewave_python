from pathlib import Path
from unittest.mock import Mock, patch

from django.template import Context, Template
from django.template.loader import render_to_string
from django.template.loader_tags import BlockNode
from django.test import TestCase, override_settings

from tidewave.django.apps import TidewaveConfig
from tidewave.django.templates import (
    clean_template_path,
    debug_block_render,
    debug_render,
    recurse_inheritance_chain,
)

TEMPLATES_PATH = Path(__file__).parent / "templates"
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
            "DIRS": [str(TEMPLATES_PATH)],
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
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
        BlockNode._original_render = BlockNode.render

        # Reset patching state
        if hasattr(Template, "_tidewave_patched"):
            delattr(Template, "_tidewave_patched")

        self.block_node = Mock()
        self.block_node.name = "content"
        self.block_node._get_template_name = Mock()
        self.context = Context()

        self.cwd = Path.cwd()

    def tearDown(self):
        """Clean up after tests"""
        # Restore original render method
        Template.render = Template._original_render
        BlockNode.render = BlockNode._original_render

        # Clean up patching attributes
        for attr in ["_tidewave_debug_name", "_tidewave_template_path", "_tidewave_patched"]:
            if hasattr(Template, attr):
                delattr(Template, attr)
            if hasattr(BlockNode, attr):
                delattr(BlockNode, attr)

    def _apply_debug_patch(self):
        """Helper to apply the debug patch manually"""
        # This mimics the patch_template_render method in `TidewaveConfig` without depending on
        # Django calling `ready()`.

        # Patch Template.render
        Template.render = debug_render
        Template._tidewave_template_path = clean_template_path
        Template._tidewave_inheritance_chain = recurse_inheritance_chain
        Template._tidewave_patched = True

        # Patch BlockNode.render
        BlockNode.render = debug_block_render
        BlockNode._tidewave_template_path = clean_template_path

    def test_html_template_gets_debug_comments(self):
        """Test that HTML templates get wrapped with debug comments"""
        self._apply_debug_patch()

        template_content = "<div>Hello World</div>"
        template = Template(template_content)

        template.origin = Mock()
        template.origin.template_name = "test.html"

        result = template.render(Context({}))

        expected_start = "<!-- TEMPLATE: test.html -->"
        expected_end = "<!-- END TEMPLATE: test.html -->"

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

        self.assertNotIn("<!-- TEMPLATE:", result)
        self.assertNotIn("<!-- END TEMPLATE:", result)
        self.assertEqual(result, template_content)

    def test_json_template_unchanged(self):
        """Test that JSON content is not wrapped with debug comments"""
        self._apply_debug_patch()

        template_content = '{"key": "value"}'
        template = Template(template_content)

        template.origin = Mock()
        template.origin.template_name = "test.json"

        result = template.render(Context({}))

        self.assertNotIn("<!-- TEMPLATE:", result)
        self.assertEqual(result, template_content)

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

        expected_start = "<!-- TEMPLATE: fallback.html -->"
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

        expected_start = "<!-- TEMPLATE: direct_name.html -->"
        self.assertIn(expected_start, result)

    def test_no_template_name_available(self):
        """Test behavior when no template name is available"""
        self._apply_debug_patch()

        template_content = "<div>No name template</div>"
        template = Template(template_content)

        result = template.render(Context({}))

        self.assertEqual(result, template_content)
        self.assertNotIn("<!-- TEMPLATE:", result)

    def test_clean_template_path_absolute_path(self):
        """Test cleaning absolute template paths relative to BASE_DIR"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        with override_settings(BASE_DIR="/test/project"):
            result = template._tidewave_template_path("/test/project/templates/app/test.html")
            expected = "templates/app/test.html"
            self.assertEqual(result, expected)

    def test_clean_template_path_relative_path(self):
        """Test that relative paths are returned as Path objects"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        result = template._tidewave_template_path("templates/test.html")
        expected = "templates/test.html"
        self.assertEqual(result, expected)

    def test_clean_template_path_none_input(self):
        """Test clean_template_path with None input"""
        self._apply_debug_patch()

        template = Template("<div>Test</div>")

        result = template._tidewave_template_path(None)
        self.assertIsNone(result)

    @override_settings(DEBUG=False)
    def test_config_ready_not_applied_when_debug_false(self):
        """Test that template patching is not applied when DEBUG=False"""
        # Reset patching state
        if hasattr(Template, "_tidewave_patched"):
            delattr(Template, "_tidewave_patched")

        # Mock the app module properly
        with patch("tidewave.django.apps.TidewaveConfig") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.ready.return_value = None

            config = TidewaveConfig.__new__(TidewaveConfig)
            config.name = "tidewave.django"

            config.ready()

            self.assertFalse(getattr(Template, "_tidewave_patched", False))

    @override_settings(DEBUG=True)
    def test_config_ready_applied_when_debug_true(self):
        """Test that template patching is applied when DEBUG=True"""
        # Reset patching state
        if hasattr(Template, "_tidewave_patched"):
            delattr(Template, "_tidewave_patched")

        config = TidewaveConfig.__new__(TidewaveConfig)
        config.name = "tidewave.django"

        config.ready()

        self.assertTrue(getattr(Template, "_tidewave_patched", False))

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

        self.assertIn("<!-- TEMPLATE: complex.html -->", result)
        self.assertIn("<!-- END TEMPLATE: complex.html -->", result)

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

        self.assertIn("<!-- TEMPLATE: whitespace.html -->", result)
        self.assertIn("<!-- END TEMPLATE: whitespace.html -->", result)
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

                self.assertNotIn("<!-- TEMPLATE:", result)
                self.assertEqual(result.strip(), content.strip())

    def test_single_block_with_template_info(self):
        """Single block should show correct template info."""
        html_content = "<div>content</div>"
        with patch.object(BlockNode, "_original_render", return_value=html_content):
            mock_block = Mock()
            self.block_node._tidewave_template_path.return_value = "base.html"

            mock_block_context = Mock()
            mock_block_context.blocks = {"content": [mock_block]}
            self.context.render_context = {"block_context": mock_block_context}

            result = debug_block_render(self.block_node, self.context)

            self.assertIn("<!-- START BLOCK: content, TEMPLATE: base.html -->", result)
            self.assertIn("<!-- END BLOCK: content -->", result)

    def test_multiple_blocks_with_inheritance_chain(self):
        """Multiple blocks should show depth and chain information."""
        html_content = "<div>content</div>"
        with patch.object(BlockNode, "_original_render", return_value=html_content):
            mock_block1 = Mock()
            mock_block2 = Mock()

            # Mock the template name calls in order
            self.block_node._tidewave_template_path.side_effect = [
                "child.html",  # child extends parent
                "parent.html",
            ]

            mock_block_context = Mock()
            mock_block_context.blocks = {"content": [mock_block1, mock_block2]}
            self.context.render_context = {"block_context": mock_block_context}

            result = debug_block_render(self.block_node, self.context)

            self.assertIn("<!-- START BLOCK: content, TEMPLATE: child.html -->", result)
            self.assertIn("<!-- END BLOCK: content -->", result)

    def test_empty_blocks_list_returns_basic_comments(self):
        """Empty blocks list should return basic debug comments."""
        html_content = "<div>content</div>"
        with patch.object(BlockNode, "_original_render", return_value=html_content):
            mock_block_context = Mock()
            mock_block_context.blocks = {"content": []}
            self.context.render_context = {"block_context": mock_block_context}

            result = debug_block_render(self.block_node, self.context)

            self.assertIn("<!-- START BLOCK: content, TEMPLATE: <unknown> -->", result)
            self.assertIn("<!-- END BLOCK: content -->", result)

    def test_base_template_renders_correctly(self):
        """Test that the base template renders with debug comments"""
        self._apply_debug_patch()

        result = render_to_string("base.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                "<!-- TEMPLATE: base.html -->"
                f"<!-- START BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                "<p>Base content</p>"
                "<!-- END BLOCK: content -->"
                "<!-- END TEMPLATE: base.html -->"
            ),
        )

    def test_child_template_extends_base(self):
        """Test that child template properly wraps base template and super block"""
        self._apply_debug_patch()

        result = render_to_string("child.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                "<!-- TEMPLATE: child.html, EXTENDS: base.html -->"
                f"<!-- START BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'child.html'} -->"
                f"<!-- START BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                "<p>Base content</p>"
                "<!-- END BLOCK: content -->"
                "<p>Child content</p>"
                "<!-- END BLOCK: content -->"
                "<!-- END TEMPLATE: child.html -->"
            ),
        )

    def test_grandchild_template_inheritance(self):
        """Test that grandchild template properly shows full inheritance chain"""
        self._apply_debug_patch()

        result = render_to_string("grandchild.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                "<!-- TEMPLATE: grandchild.html, EXTENDS: child.html, EXTENDS: base.html -->"
                f"<!-- START BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'grandchild.html'} -->"
                "<p>Grandchild content</p>"
                "<!-- END BLOCK: content -->"
                "<!-- END TEMPLATE: grandchild.html -->"
            ),
        )

    def test_child_template_with_includes(self):
        """Test that child template properly wraps included templates"""
        self._apply_debug_patch()

        result = render_to_string("child-includes.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                "<!-- TEMPLATE: child-includes.html, EXTENDS: base.html -->"
                f"<!-- START BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'child-includes.html'} -->"
                "<p>Child content</p>"
                "<!-- TEMPLATE: include.html -->"
                "<p>Included content: foo</p>"
                "<!-- END TEMPLATE: include.html -->"
                "<!-- END BLOCK: content -->"
                "<!-- END TEMPLATE: child-includes.html -->"
            ),
        )

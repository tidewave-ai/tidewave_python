import os
from pathlib import Path
from unittest.mock import patch

from django.template import Context, Template
from django.template.loader import render_to_string
from django.template.loader_tags import BlockNode
from django.test import TestCase, override_settings

from tidewave.django.apps import TidewaveConfig
from tidewave.django.templates import (
    debug_block_render,
    debug_render,
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

    def tearDown(self):
        """Clean up after tests"""
        # Restore original render method, if applicable

        if hasattr(Template, "_tidewave_original_render"):
            Template.render = Template._tidewave_original_render
            del Template._tidewave_original_render

        if hasattr(BlockNode, "_tidewave_original_render"):
            BlockNode.render = BlockNode._tidewave_original_render
            del BlockNode._tidewave_original_render

    def _apply_debug_patch(self):
        """Helper to apply the debug patch manually"""
        # This mimics the patch_template_render method in `TidewaveConfig` without depending on
        # Django calling `ready()`.

        Template._tidewave_original_render = Template.render
        Template.render = debug_render
        BlockNode._tidewave_original_render = BlockNode.render
        BlockNode.render = debug_block_render

    @override_settings(DEBUG=False)
    def test_config_ready_not_applied_when_debug_false(self):
        """Test that template patching is not applied when DEBUG=False"""
        # Reset patching state
        if hasattr(Template, "_tidewave_original_render"):
            delattr(Template, "_tidewave_original_render")

        # Mock the app module properly
        with patch("tidewave.django.apps.TidewaveConfig") as mock_config_class:
            mock_config = mock_config_class.return_value
            mock_config.ready.return_value = None

            config = TidewaveConfig.__new__(TidewaveConfig)
            config.name = "tidewave.django"

            config.ready()

            self.assertFalse(hasattr(Template, "_tidewave_original_render"))

    @override_settings(DEBUG=True)
    def test_config_ready_applied_when_debug_true(self):
        """Test that template patching is applied when DEBUG=True"""
        # Reset patching state
        if hasattr(Template, "_tidewave_original_render"):
            delattr(Template, "_tidewave_original_render")

        config = TidewaveConfig.__new__(TidewaveConfig)
        config.name = "tidewave.django"

        config.ready()

        self.assertTrue(hasattr(Template, "_tidewave_original_render"))

    def test_template_without_html_content_detection(self):
        """Test various non-HTML content types are not wrapped"""
        self._apply_debug_patch()

        test_cases = os.listdir(TEMPLATES_PATH / "non_html")

        for name in test_cases:
            with self.subTest(name=name):
                result = render_to_string(f"non_html/{name}")

                with open(TEMPLATES_PATH / "non_html" / name, encoding="utf-8") as f:
                    content = f.read()

                self.assertNotIn("<!-- TEMPLATE:", result)
                self.assertEqual(result, content)

    def test_base_template_renders_correctly(self):
        """Test that the base template renders with debug comments"""
        self._apply_debug_patch()

        result = render_to_string("base.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                f"<!-- BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                "<p>Base content</p>"
                "<!-- END BLOCK: content -->"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
            ),
        )

    def test_whitespace_handling(self):
        """Test that whitespace in templates is handled correctly"""
        self._apply_debug_patch()

        result = render_to_string("whitespace.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'whitespace.html'} -->"
                "  <div>Content</div>"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'whitespace.html'} -->"
            ),
        )

    @override_settings(BASE_DIR=TEMPLATES_PATH)
    def test_paths_relative_to_base_dir(self):
        """Test that the paths are relative to BASE_DIR"""
        self._apply_debug_patch()

        result = render_to_string("base.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                "<!-- TEMPLATE: base.html -->"
                "<!-- BLOCK: content, TEMPLATE: base.html -->"
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
                f"<!-- SUBTEMPLATE: {TEMPLATES_PATH / 'child.html'} -->"
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                f"<!-- BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'child.html'} -->"
                f"<!-- BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                "<p>Base content</p>"
                "<!-- END BLOCK: content -->"
                "<p>Child content</p>"
                "<!-- END BLOCK: content -->"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
            ),
        )

    def test_grandchild_template_inheritance(self):
        """Test that grandchild template properly shows full inheritance chain"""
        self._apply_debug_patch()

        result = render_to_string("grandchild.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                f"<!-- SUBTEMPLATE: {TEMPLATES_PATH / 'grandchild.html'} -->"
                f"<!-- SUBTEMPLATE: {TEMPLATES_PATH / 'child.html'} -->"
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                f"<!-- BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'grandchild.html'} -->"
                "<p>Grandchild content</p>"
                "<!-- END BLOCK: content -->"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
            ),
        )

    def test_child_template_with_includes(self):
        """Test that child template properly wraps included templates"""
        self._apply_debug_patch()

        result = render_to_string("child-includes.html")

        self.assertEqual(
            result.replace("\n", "").strip(),
            (
                f"<!-- SUBTEMPLATE: {TEMPLATES_PATH / 'child-includes.html'} -->"
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
                f"<!-- BLOCK: content, TEMPLATE: {TEMPLATES_PATH / 'child-includes.html'} -->"
                "<p>Child content</p>"
                f"<!-- TEMPLATE: {TEMPLATES_PATH / 'include.html'} -->"
                "<p>Included content: foo</p>"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'include.html'} -->"
                "<!-- END BLOCK: content -->"
                f"<!-- END TEMPLATE: {TEMPLATES_PATH / 'base.html'} -->"
            ),
        )

    def test_django_api_change(self):
        """Test behavior when expected django fields are not present"""
        self._apply_debug_patch()

        template_content = "<div>No name template</div>"
        template = Template(template_content)

        # Remove origin to test
        del template.origin

        with self.assertLogs("django", level="WARNING") as log_context:
            result = template.render(Context({}))

        self.assertEqual(result, template_content)
        self.assertIn("Tidewave failed to annotate template, ", log_context.output[0])

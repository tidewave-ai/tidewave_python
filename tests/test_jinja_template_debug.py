from pathlib import Path
from unittest import TestCase

from jinja2 import Environment, FileSystemLoader

from tidewave.jinja2 import Extension as TemplateAnnotationExtension

TEMPLATES_PATH = Path(__file__).parent / "jinja2"


class TestJinjaTemplateDebug(TestCase):
    """Test Jinja template debug annotation functionality"""

    def setUp(self):
        """Set up test environment"""
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_PATH)), extensions=[TemplateAnnotationExtension]
        )

    def test_base_template_renders_with_annotations(self):
        """Test that base template renders with debug comments"""
        template = self.env.get_template("base.html")
        result = template.render()

        expected = (
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            "<!-- BLOCK: content, TEMPLATE: tests/jinja2/base.html -->\n"
            "\n"
            "<p>Base content</p>\n"
            "\n"
            "<!-- END BLOCK: content -->\n"
            "\n"
            "<!-- END TEMPLATE: tests/jinja2/base.html -->"
        )

        self.assertEqual(result, expected)

    def test_child_template_renders_with_annotations(self):
        """Test that child template renders with debug comments"""
        template = self.env.get_template("child.html")
        result = template.render()

        expected = (
            "<!-- TEMPLATE: tests/jinja2/child.html -->\n"
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            "<!-- BLOCK: content, TEMPLATE: tests/jinja2/child.html -->\n"
            " <!-- BLOCK: content, TEMPLATE: tests/jinja2/base.html -->\n"
            "\n"
            "<p>Base content</p>\n"
            "\n"
            "<!-- END BLOCK: content -->\n"
            "<p>Child content</p>\n"
            "\n"
            "<!-- END BLOCK: content -->\n"
            "\n"
            "<!-- END TEMPLATE: tests/jinja2/base.html -->"
        )

        self.assertEqual(result, expected)

    def test_inline_template_not_annotated(self):
        """Test that inline templates (without names) are not annotated"""
        template_string = "<p>Inline template content</p>"
        template = self.env.from_string(template_string)
        result = template.render()

        expected = "<p>Inline template content</p>"
        self.assertEqual(result, expected)

    def test_plain_text_template_not_annotated(self):
        """Test that plain text templates (without HTML tags) are not annotated"""
        template = self.env.get_template("plain.txt")
        result = template.render(message="Test message")

        expected = (
            "This is a plain text template.\n"
            "It has no HTML tags.\n"
            "Just some regular text content.\n"
            "Test message"
        )

        # Should not contain any annotation comments
        self.assertEqual(result, expected)
        self.assertNotIn("<!-- TEMPLATE:", result)
        self.assertNotIn("<!-- END TEMPLATE:", result)

    def test_grandchild_template_inheritance(self):
        """Test that grandchild template properly shows full inheritance chain"""
        template = self.env.get_template("grandchild.html")
        result = template.render()

        expected = (
            "<!-- TEMPLATE: tests/jinja2/grandchild.html -->\n"
            "<!-- TEMPLATE: tests/jinja2/child.html -->\n"
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            "<!-- BLOCK: content, TEMPLATE: tests/jinja2/grandchild.html -->\n"
            "\n"
            "<p>Grandchild content</p>\n"
            "\n"
            "<!-- END BLOCK: content -->\n"
            "\n"
            "<!-- END TEMPLATE: tests/jinja2/base.html -->"
        )

        self.assertEqual(result, expected)

    def test_child_template_with_includes(self):
        """Test that child template properly wraps included templates"""
        template = self.env.get_template("child-includes.html")
        result = template.render(value="foo")

        expected = (
            "<!-- TEMPLATE: tests/jinja2/child-includes.html -->\n"
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            "<!-- BLOCK: content, TEMPLATE: tests/jinja2/child-includes.html -->\n"
            "\n"
            "<p>Child content</p>\n"
            "<!-- TEMPLATE: tests/jinja2/include.html -->\n"
            "<p>Included content: foo</p>\n"
            "<!-- END TEMPLATE: tests/jinja2/include.html -->\n"
            "\n"
            "<!-- END BLOCK: content -->\n"
            "\n"
            "<!-- END TEMPLATE: tests/jinja2/base.html -->"
        )

        self.assertEqual(result, expected)

    def test_block_without_html_not_annotated(self):
        """Test that blocks without HTML content are not annotated"""
        # Create a template with a block that only contains text
        template_content = "{% block textonly %}Just plain text{% endblock %}"
        template = self.env.from_string(template_content)
        result = template.render()

        expected = "Just plain text"
        self.assertEqual(result, expected)
        self.assertNotIn("<!-- BLOCK:", result)
        self.assertNotIn("<!-- END BLOCK:", result)

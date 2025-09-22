from pathlib import Path
from unittest import TestCase

from jinja2 import Environment, FileSystemLoader
from jinja2.ext import Extension
from jinja2.lexer import Token


class TemplateAnnotationExtension(Extension):
    """Jinja2 extension that adds HTML comments around templates"""

    def filter_stream(self, stream):
        """Filter token stream to add template annotations"""
        # Get template name from the stream
        template_name = getattr(stream, 'name', None)

        # Only annotate named templates (not inline strings)
        if template_name:
            # Create start annotation token
            start_comment = f"<!-- TEMPLATE: {template_name} -->\n"
            yield Token(1, 'data', start_comment)

            # Yield all original tokens
            last_lineno = 1
            for token in stream:
                yield token
                last_lineno = token.lineno

            # Create end annotation token
            end_comment = f"\n\n<!-- END TEMPLATE: {template_name} -->"
            yield Token(last_lineno, 'data', end_comment)
        else:
            # For unnamed templates, just pass through all tokens
            for token in stream:
                yield token


TEMPLATES_PATH = Path(__file__).parent / "jinja2"


class TestJinjaTemplateDebug(TestCase):
    """Test Jinja template debug annotation functionality"""

    def setUp(self):
        """Set up test environment"""
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_PATH)),
            extensions=[TemplateAnnotationExtension]
        )

    def test_base_template_renders_with_annotations(self):
        """Test that base template renders with debug comments"""
        template = self.env.get_template('base.html')
        result = template.render()

        expected = (
            "<!-- TEMPLATE: base.html -->\n"
            "\n"
            "<p>Base content</p>\n"
            "\n"
            "\n"
            "<!-- END TEMPLATE: base.html -->"
        )


        self.assertEqual(result, expected)

    def test_child_template_renders_with_annotations(self):
        """Test that child template renders with debug comments"""
        template = self.env.get_template('child.html')
        result = template.render()

        expected = (
            "<!-- TEMPLATE: child.html -->\n"
            "<!-- TEMPLATE: base.html -->\n"
            " \n"
            "<p>Base content</p>\n"
            "\n"
            "<p>Child content</p>\n"
            "\n"
            "\n"
            "<!-- END TEMPLATE: base.html -->"
        )

        self.assertEqual(result, expected)

    def test_inline_template_not_annotated(self):
        """Test that inline templates (without names) are not annotated"""
        template_string = "<p>Inline template content</p>"
        template = self.env.from_string(template_string)
        result = template.render()

        expected = "<p>Inline template content</p>"
        self.assertEqual(result, expected)

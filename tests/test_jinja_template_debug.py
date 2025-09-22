import os
from pathlib import Path
from unittest import TestCase

from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension


class TemplateAnnotationExtension(Extension):
    """Jinja2 extension that adds HTML comments around templates using AST manipulation"""

    tags = {'template_debug'}

    def preprocess(self, source, name, filename=None):
        """Preprocess template source to inject filename"""

        if filename:
            relative_filename = os.path.relpath(filename)
            return f"{{% template_debug '{relative_filename}' %}}{source}{{% endtemplate_debug %}}"
        return source

    def _has_html_content_in_ast(self, body):
        """Check if AST body contains HTML tags by analyzing text nodes"""
        for node in body:
            for text_node in node.find_all(nodes.TemplateData):
                if '<' in text_node.data:
                    return True
        return False

    def parse(self, parser):
        """Parse the template_debug tag"""
        lineno = next(parser.stream).lineno
        template_filename = parser.parse_expression()
        body = parser.parse_statements(['name:endtemplate_debug'], drop_needle=True)

        if not self._has_html_content_in_ast(body):
            return body

        filename_value = template_filename.as_const()

        start_comment = nodes.Output([
            nodes.TemplateData(f"<!-- TEMPLATE: {filename_value} -->\n")
        ]).set_lineno(lineno)

        end_comment = nodes.Output([
            nodes.TemplateData(f"\n<!-- END TEMPLATE: {filename_value} -->")
        ]).set_lineno(lineno)

        return [start_comment] + body + [end_comment]


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
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            "\n"
            "<p>Base content</p>\n"
            "\n"
            "\n"
            "<!-- END TEMPLATE: tests/jinja2/base.html -->"
        )


        self.assertEqual(result, expected)

    def test_child_template_renders_with_annotations(self):
        """Test that child template renders with debug comments"""
        template = self.env.get_template('child.html')
        result = template.render()

        expected = (
            "<!-- TEMPLATE: tests/jinja2/child.html -->\n"
            "<!-- TEMPLATE: tests/jinja2/base.html -->\n"
            " \n"
            "<p>Base content</p>\n"
            "\n"
            "<p>Child content</p>\n"
            "\n"
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
        template = self.env.get_template('plain.txt')
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

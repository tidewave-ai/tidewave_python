from pathlib import Path
from unittest import TestCase

from jinja2 import Environment, FileSystemLoader, nodes
from jinja2.ext import Extension


class TemplateAnnotationExtension(Extension):
    """Jinja2 extension that adds HTML comments around templates using AST manipulation"""

    tags = {'template_debug'}

    def preprocess(self, source, name, filename=None):
        """Preprocess template source to inject template_debug tags"""
        # Only inject for named templates and if they contain HTML
        if name and self._source_has_html_content(source):
            # Wrap the source with our custom tags
            return f"{{% template_debug '{name}' %}}{source}{{% endtemplate_debug %}}"
        return source

    def _source_has_html_content(self, source):
        """Check if source contains HTML tags"""
        return '<' in source and '>' in source

    def parse(self, parser):
        """Parse the template_debug tag"""
        lineno = next(parser.stream).lineno

        # Parse the template name
        template_name = parser.parse_expression()

        # Parse the body until endtemplate_debug
        body = parser.parse_statements(['name:endtemplate_debug'], drop_needle=True)

        # Create start and end comment nodes
        start_comment = nodes.Output([
            nodes.TemplateData(f"<!-- TEMPLATE: {template_name.value.strip('\"')} -->\n")
        ]).set_lineno(lineno)

        end_comment = nodes.Output([
            nodes.TemplateData(f"\n<!-- END TEMPLATE: {template_name.value.strip('\"')} -->")
        ]).set_lineno(lineno)

        # Return the wrapped content
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

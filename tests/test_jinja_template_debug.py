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
        for node in body:
            for text_node in node.find_all(nodes.TemplateData):
                if '<' in text_node.data:
                    return True
        return False

    def _has_html_content_in_node(self, node):
        for text_node in node.find_all(nodes.TemplateData):
            if '<' in text_node.data:
                return True
        return False

    def _wrap_blocks_with_annotations(self, body, template_filename):
        wrapped_body = []

        for node in body:
            if isinstance(node, nodes.Block):
                if self._has_html_content_in_node(node):
                    block_start = nodes.Output([
                        nodes.TemplateData(f"<!-- BLOCK: {node.name}, TEMPLATE: {template_filename} -->\n")
                    ]).set_lineno(node.lineno)

                    block_end = nodes.Output([
                        nodes.TemplateData(f"\n<!-- END BLOCK: {node.name} -->")
                    ]).set_lineno(node.lineno)

                    processed_body = self._wrap_blocks_with_annotations(node.body, template_filename)
                    node.body = [block_start] + processed_body + [block_end]
                    wrapped_body.append(node)
                else:
                    node.body = self._wrap_blocks_with_annotations(node.body, template_filename)
                    wrapped_body.append(node)
            else:
                # For non-block nodes, recursively process any nested blocks
                if hasattr(node, 'body') and isinstance(node.body, list):
                    node.body = self._wrap_blocks_with_annotations(node.body, template_filename)
                elif hasattr(node, 'nodes') and isinstance(node.nodes, list):
                    node.nodes = self._wrap_blocks_with_annotations(node.nodes, template_filename)
                wrapped_body.append(node)

        return wrapped_body

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        template_filename = parser.parse_expression()
        body = parser.parse_statements(['name:endtemplate_debug'], drop_needle=True)

        if not self._has_html_content_in_ast(body):
            return body

        filename_value = template_filename.as_const()

        # Wrap blocks with annotations
        body = self._wrap_blocks_with_annotations(body, filename_value)

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
        template = self.env.get_template('child.html')
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

    def test_grandchild_template_inheritance(self):
        """Test that grandchild template properly shows full inheritance chain"""
        template = self.env.get_template('grandchild.html')
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
        template = self.env.get_template('child-includes.html')
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

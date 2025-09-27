"""
Jinja2-specific integration for Tidewave
"""

import os

from jinja2 import nodes
from jinja2.ext import Extension


class TemplateAnnotationExtension(Extension):
    """Jinja2 extension that adds HTML comments around templates using AST manipulation"""

    tags = {"template_debug"}

    def preprocess(self, source, name, filename=None):
        """Preprocess template source to inject filename"""

        if filename:
            relative_filename = os.path.relpath(filename)
            return f"{{% template_debug '{relative_filename}' %}}{source}{{% endtemplate_debug %}}"
        return source

    def _has_html_content_in_ast(self, body):
        for node in body:
            if self._has_html_content_in_node(node):
                return True
        return False

    def _has_html_content_in_node(self, node):
        for text_node in node.find_all(nodes.TemplateData):
            if "<" in text_node.data:
                return True
        return False

    def _wrap_blocks_with_annotations(self, body, template_filename):
        wrapped_body = []

        for node in body:
            if isinstance(node, nodes.Block):
                if self._has_html_content_in_node(node):
                    block_start = nodes.Output(
                        [
                            nodes.TemplateData(
                                f"<!-- BLOCK: {node.name}, TEMPLATE: {template_filename} -->\n"
                            )
                        ]
                    ).set_lineno(node.lineno)

                    block_end = nodes.Output(
                        [nodes.TemplateData(f"\n<!-- END BLOCK: {node.name} -->")]
                    ).set_lineno(node.lineno)

                    processed_body = self._wrap_blocks_with_annotations(
                        node.body, template_filename
                    )
                    node.body = [block_start] + processed_body + [block_end]
                    wrapped_body.append(node)
                else:
                    node.body = self._wrap_blocks_with_annotations(node.body, template_filename)
                    wrapped_body.append(node)
            else:
                # For non-block nodes, recursively process any nested blocks
                if hasattr(node, "body") and isinstance(node.body, list):
                    node.body = self._wrap_blocks_with_annotations(node.body, template_filename)
                elif hasattr(node, "nodes") and isinstance(node.nodes, list):
                    node.nodes = self._wrap_blocks_with_annotations(node.nodes, template_filename)
                wrapped_body.append(node)

        return wrapped_body

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        template_filename = parser.parse_expression()
        body = parser.parse_statements(["name:endtemplate_debug"], drop_needle=True)

        if not self._has_html_content_in_ast(body):
            return body

        filename_value = template_filename.as_const()
        body = self._wrap_blocks_with_annotations(body, filename_value)
        has_extends = self._has_extends_node(body)

        if has_extends:
            # For templates with extends, only emit SUBTEMPLATE comment (no closing)
            start_comment = nodes.Output(
                [nodes.TemplateData(f"<!-- SUBTEMPLATE: {filename_value} -->\n")]
            ).set_lineno(lineno)
            return [start_comment] + body
        else:
            # For base templates, emit full TEMPLATE comments
            start_comment = nodes.Output(
                [nodes.TemplateData(f"<!-- TEMPLATE: {filename_value} -->\n")]
            ).set_lineno(lineno)

            end_comment = nodes.Output(
                [nodes.TemplateData(f"\n<!-- END TEMPLATE: {filename_value} -->")]
            ).set_lineno(lineno)

            return [start_comment] + body + [end_comment]

    def _has_extends_node(self, body):
        """Check if the template body contains an extends node"""
        for node in body:
            if isinstance(node, nodes.Extends):
                return True
            # Also check nested nodes recursively
            for _child in node.find_all(nodes.Extends):
                return True
        return False


# Expose the extension as the main export
Extension = TemplateAnnotationExtension

from pathlib import Path

from django.conf import settings
from django.template import Template
from django.template.loader_tags import ExtendsNode


def debug_render(self, context=None):
    content = Template._original_render(self, context)

    # Only wrap HTML content in HTML comments.
    stripped_content = content.strip()
    if not stripped_content.startswith("<"):
        return content

    template_name, extends = self._get_debug_name()

    if not template_name:
        return content

    display_name = self._clean_template_path(template_name)
    extends_name = self._clean_template_path(extends)

    extends_info = f"(extends: {extends_name})" if extends else ""
    start_comment = f"<!-- Template: {display_name} {extends_info} -->"
    end_comment = f"<!-- End Template: {display_name} -->"

    return f"{start_comment}{content}{end_comment}"


def get_debug_name(self):
    extends = None
    for node in self.nodelist:
        if isinstance(node, ExtendsNode):
            extends = str(node.parent_name).strip("'\"")

    if hasattr(self, "origin") and self.origin:
        if hasattr(self.origin, "template_name"):
            return self.origin.template_name, extends
        elif hasattr(self.origin, "name"):
            return self.origin.name, extends

    if hasattr(self, "name") and self.name:
        return self.name, extends

    return None, extends


def clean_template_path(self, template_name):
    """Clean up template path for display."""
    if not template_name:
        return

    # If it's an absolute path, make it relative to BASE_DIR
    template_path = Path(template_name)
    if template_path.is_absolute() and hasattr(settings, "BASE_DIR"):
        try:
            base_dir = Path(settings.BASE_DIR)
            return template_path.relative_to(base_dir)
        except ValueError:
            pass

    return template_path

from pathlib import Path
from typing import Optional

from django.conf import settings
from django.template import Template
from django.template.base import mark_safe
from django.template.loader_tags import BlockNode, ExtendsNode


def debug_render(self, context) -> str:
    content = Template._original_render(self, context)

    # Only add debug comments for HTML content
    if not content.lstrip().startswith("<"):
        return content

    template_name, extends = self._tidewave_debug_name()

    if not template_name:
        return content

    display_name = self._tidewave_template_path(template_name)
    extends_name = self._tidewave_template_path(extends)

    extends_info = f" EXTENDS: {extends_name}" if extends else ""
    start_comment = f"<!-- TEMPLATE: {display_name}{extends_info} -->"
    end_comment = f"<!-- END TEMPLATE: {display_name} -->"

    return f"{start_comment}{content}{end_comment}"


def debug_block_render(self, context) -> str:
    content = BlockNode._original_render(self, context)

    # Only add debug comments for HTML content
    if not content.lstrip().startswith("<"):
        return content

    # Gather extra info about the block inheritance.
    block_context = context.render_context.get("block_context")

    template_name = None
    if block_context and hasattr(block_context, "blocks"):
        blocks = block_context.blocks.get(self.name, [])
        block = blocks[-1] if blocks else None
        if hasattr(block, "origin") and block.origin and hasattr(block.origin, "name"):
            template_name = self._tidewave_template_path(block.origin.name)

    # Fallback to context's template if available, this happens when there's no inheritance.
    if not template_name:
        template = getattr(context, "template", None)
        if template and hasattr(template, "origin") and template.origin:
            template_name = self._tidewave_template_path(template.origin.name)

    start_comment = f"<!-- START BLOCK: {self.name}, TEMPLATE: {template_name or '<unknown>'} -->"
    end_comment = f"<!-- END BLOCK: {self.name} -->"

    return mark_safe(f"{start_comment}{content}{end_comment}")


def get_debug_name(self) -> tuple[Optional[str], Optional[str]]:
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


def clean_template_path(self, template_name) -> Optional[str]:
    """Clean up template path for display."""
    if not template_name:
        return

    # If it's an absolute path, make it relative to BASE_DIR.
    # Force to string in case it's a SafeString.
    template_path = Path("".join(c for c in str(template_name)))
    if template_path.is_absolute() and hasattr(settings, "BASE_DIR"):
        try:
            base_dir = Path(settings.BASE_DIR)
            return str(template_path.relative_to(base_dir))
        except ValueError:
            pass

    return str(template_path)

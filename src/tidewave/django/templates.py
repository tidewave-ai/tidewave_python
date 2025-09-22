import logging
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.template import Template
from django.template.base import mark_safe
from django.template.loader_tags import BlockNode, ExtendsNode
from django.utils.safestring import SafeString


logger = logging.getLogger(__name__)


def debug_render(self, context) -> str:
    content = Template._tidewave_original_render(self, context)

    try:
        # Only add debug comments for HTML content
        if not content.lstrip().startswith("<"):
            return content

        template_path = get_template_path(self)

        if not template_path:
            return content

        extends_parents = get_extends_parents(self)

        extends_info = "".join(f", EXTENDS: {p}" for p in extends_parents)
        start_comment = f"<!-- TEMPLATE: {template_path}{extends_info} -->"
        end_comment = f"<!-- END TEMPLATE: {template_path} -->"

        return wrap_rendered(content, start_comment, end_comment)
    except Exception as e:
        logger.warning(
            f"Tidewave failed to annotate template, please open up an issue on https://github.com/tidewave-ai/tidewave_python.\nException: {e}"
        )
        return content


def debug_block_render(self, context) -> str:
    content = BlockNode._tidewave_original_render(self, context)

    try:
        # Only add debug comments for HTML content
        if not content.lstrip().startswith("<"):
            return content

        # Gather extra info about the block inheritance.
        block_context = context.render_context.get("block_context")

        template_path = None

        # Get template name from the block context if available.
        if block_context:
            blocks = block_context.blocks.get(self.name, [])
            block = blocks[-1] if blocks else None
            if block:
                template_path = get_template_path(block)

        # Fallback to context's template if available, this happens when there's no inheritance.
        if not template_path and context.template:
            template_path = get_template_path(context.template)

        if not template_path:
            return content

        start_comment = f"<!-- BLOCK: {self.name}, TEMPLATE: {template_path} -->"
        end_comment = f"<!-- END BLOCK: {self.name} -->"

        return wrap_rendered(content, start_comment, end_comment)
    except Exception as e:
        logger.warning(
            f"Tidewave failed to annotate block, please open up an issue on https://github.com/tidewave-ai/tidewave_python.\nException: {e}"
        )
        return content


def wrap_rendered(content, prefix, suffix):
    new_content = f"{prefix}{content}{suffix}"

    if isinstance(content, SafeString):
        return mark_safe(new_content)
    else:
        return new_content


def get_template_path(template_or_block) -> Optional[str]:
    """Clean up template path for display."""

    template_path = template_or_block.origin.name

    # If it's an absolute path, make it relative to BASE_DIR.
    template_path = Path(template_path)
    if template_path.is_absolute() and hasattr(settings, "BASE_DIR"):
        try:
            base_dir = Path(settings.BASE_DIR)
            return str(template_path.relative_to(base_dir))
        except ValueError:
            pass

    return str(template_path)


def get_extends_parents(template) -> list[str]:
    extends_node = None
    for node in template.nodelist:
        if isinstance(node, ExtendsNode):
            extends_node = node
            break

    if not extends_node:
        return []

    if hasattr(extends_node.parent_name, "var"):
        parent_name = extends_node.parent_name.var
    else:
        parent_name = str(extends_node.parent_name)
    parent_template = template.engine.get_template(parent_name)

    parent_template_path = get_template_path(parent_template)

    if not parent_template_path:
        return []

    # Recursively get the parent's chain
    return [parent_template_path] + get_extends_parents(parent_template)

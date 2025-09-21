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

    # Find template name
    template_name = None
    if hasattr(self, "origin") and self.origin:
        if hasattr(self.origin, "template_name"):
            template_name = self.origin.template_name
        elif hasattr(self.origin, "name"):
            template_name = self.origin.name
    elif hasattr(self, "name") and self.name:
        template_name = self.name

    if not template_name:
        return content

    display_name = clean_template_path(template_name)

    # Gather inheritance chain info
    inheritance_chain = recurse_inheritance_chain(self, context)

    extends_info = "".join(f", EXTENDS: {n}" for n in inheritance_chain[1:])
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

    # Get template name from the block context if available.
    if block_context and hasattr(block_context, "blocks"):
        blocks = block_context.blocks.get(self.name, [])
        block = blocks[-1] if blocks else None
        if hasattr(block, "origin") and block.origin and hasattr(block.origin, "name"):
            template_name = clean_template_path(block.origin.name)

    # Fallback to context's template if available, this happens when there's no inheritance.
    if not template_name:
        template = getattr(context, "template", None)
        if template and hasattr(template, "origin") and template.origin:
            template_name = clean_template_path(template.origin.name)

    start_comment = f"<!-- START BLOCK: {self.name}, TEMPLATE: {template_name or '<unknown>'} -->"
    end_comment = f"<!-- END BLOCK: {self.name} -->"

    return mark_safe(f"{start_comment}{content}{end_comment}")


def clean_template_path(template_name) -> Optional[str]:
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


def recurse_inheritance_chain(template, context) -> list[str]:
    chain = [template.name if template.name else "<unknown>"]

    extends_node = None
    for node in template.nodelist:
        if isinstance(node, ExtendsNode):
            extends_node = node
            break

    if not extends_node:
        return chain

    try:
        if hasattr(extends_node, "parent_template") and extends_node.parent_template:
            parent_template = extends_node.parent_template
        else:
            if hasattr(extends_node.parent_name, "var"):
                parent_name = extends_node.parent_name.var
            else:
                parent_name = str(extends_node.parent_name)
            parent_template = template.engine.get_template(parent_name)

        # Recursively get the parent's chain
        parent_chain = recurse_inheritance_chain(parent_template, context)
        chain.extend(parent_chain)

    except Exception as e:
        chain.append(f"<unknown: {e}>")

    return chain

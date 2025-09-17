from django.apps import AppConfig
from django.conf import settings
from django.template import Template
from django.template.loader_tags import BlockNode

from tidewave.django.templates import (
    clean_template_path,
    debug_block_render,
    debug_render,
    get_debug_name,
)


class TidewaveConfig(AppConfig):
    name = "tidewave.django"

    def ready(self):
        if not getattr(settings, "DEBUG", False):
            return

        # Only patch if not already patched
        if not getattr(Template, "_tidewave_patched", False):
            self.patch_template_render()

    def patch_template_render(self):
        """Monkey patch Template.render to add debug HTML comments."""
        Template._original_render = Template.render
        BlockNode._original_render = BlockNode.render

        # Patch Template.render
        Template.render = debug_render
        Template._tidewave_debug_name = get_debug_name
        Template._tidewave_template_path = clean_template_path
        Template._tidewave_patched = True

        # Patch BlockNode.render
        BlockNode.render = debug_block_render
        BlockNode._tidewave_template_path = clean_template_path

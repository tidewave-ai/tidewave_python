from django.apps import AppConfig
from django.conf import settings
from django.template import Template
from django.template.loader_tags import BlockNode

from tidewave.django.templates import (
    debug_block_render,
    debug_render,
)


class TidewaveConfig(AppConfig):
    name = "tidewave.django"

    def ready(self):
        if not getattr(settings, "DEBUG", False):
            return

        # Only patch if not already patched
        if not hasattr(Template, "_tidewave_original_render"):
            self.patch_template_render()

    def patch_template_render(self):
        """Monkey patch Template.render to add debug HTML comments."""
        Template._tidewave_original_render = Template.render
        BlockNode._tidewave_original_render = BlockNode.render

        # Patch Template.render
        Template.render = debug_render

        # Patch BlockNode.render
        BlockNode.render = debug_block_render

from django.apps import AppConfig
from django.conf import settings
from django.template import Template

from tidewave.django.templates import clean_template_path, debug_render, get_debug_name


class TidewaveConfig(AppConfig):
    name = "tidewave.django"

    def ready(self):
        if not getattr(settings, "DEBUG", False):
            return

        # Only patch if not already patched
        if not getattr(Template, "_debug_patched", False):
            self.patch_template_render()

    def patch_template_render(self):
        """Monkey patch Template.render to add debug HTML comments."""
        Template._original_render = Template.render

        # Apply the patches
        Template.render = debug_render
        Template._get_debug_name = get_debug_name
        Template._clean_template_path = clean_template_path
        Template._debug_patched = True

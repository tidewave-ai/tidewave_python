from django.apps import apps

from tidewave.tools.source import get_relative_source_location


def get_models() -> str:
    """
    Returns a list of all database-backed models and their file paths in the application.

    You should prefer this tool over grepping the file system when you need to find a specific
    Django models.
    """

    models = apps.get_models()
    models = list(filter(lambda m: not m._meta.abstract, models))

    if not models:
        return "No models found in the Django application"

    models.sort(key=lambda m: m.__name__)

    result = []
    for model in models:
        location = get_relative_source_location(model)
        result.append(f"* {model.__name__}" + (f" at {location}" if location else ""))

    return "\n".join(result)

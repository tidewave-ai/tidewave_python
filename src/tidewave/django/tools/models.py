import inspect
import os
from pathlib import Path
from typing import Optional

from django.apps import apps


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
        location = _get_relative_source_location(model)
        result.append(f"* {model.__name__}" + (f" at {location}" if location else ""))

    return "\n".join(result)


def _get_relative_source_location(model) -> Optional[str]:
    """Get relative source location for a Django model."""
    try:
        file_path = inspect.getsourcefile(model)
        line_number = inspect.getsourcelines(model)[1]

        if not file_path:
            return None

        try:
            cwd = Path(os.getcwd())
            file_path_obj = Path(file_path)
            relative_path = file_path_obj.relative_to(cwd)
            return f"{relative_path}:{line_number}"
        except ValueError:
            return f"{file_path}:{line_number}"

    except (OSError, TypeError):
        return None

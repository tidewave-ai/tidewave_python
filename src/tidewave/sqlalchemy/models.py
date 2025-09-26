from typing import Callable

from sqlalchemy import Column

from tidewave.tools.source import get_relative_source_location


def get_models(base_class) -> Callable[[], str]:
    def get_models() -> str:
        """
        Returns a list of all database-backed models and their file paths in the application.

        You should prefer this tool over grepping the file system when you need to find a
        specific SQLAlchemy model.
        """
        models = _get_all_subclasses(base_class)

        # Filter out abstract models and the base class itself
        concrete_models = []
        for model in models:
            if model is base_class:
                continue

            # Check if it's an abstract model (has __abstract__ = True)
            if getattr(model, "__abstract__", False):
                continue

            # Check if it has any columns (indicating it's a concrete model)
            if hasattr(model, "__table__") or _has_columns(model):
                concrete_models.append(model)

        if not concrete_models:
            return f"No concrete models found that inherit from {base_class.__name__}"

        # Sort models by name for consistent output
        concrete_models.sort(key=lambda m: m.__name__)

        result = []
        for model in concrete_models:
            location = get_relative_source_location(model)
            result.append(f"* {model.__name__}" + (f" at {location}" if location else ""))

        return "\n".join(result)

    return get_models


def _get_all_subclasses(cls):
    """
    Recursively get all subclasses of a given class.
    """
    subclasses = set()
    to_visit = [cls]

    while to_visit:
        current = to_visit.pop()
        current_subclasses = current.__subclasses__()
        subclasses.update(current_subclasses)
        to_visit.extend(current_subclasses)

    return list(subclasses)


def _has_columns(model_class) -> bool:
    """
    Check if a model class has any SQLAlchemy columns defined.
    """
    for attr_name in dir(model_class):
        if attr_name.startswith("_"):
            continue

        attr = getattr(model_class, attr_name, None)
        if isinstance(attr, Column):
            return True

    return False

import builtins
import importlib
import inspect
import sys
from typing import Any, Optional


def get_source_location(reference: str) -> str:
    """
    Get source location for a Python reference.

    The reference may be:
    - A module/class: `pathlib.Path`, `collections.Counter`
    - An instance method: `pathlib.Path.resolve`, `collections.Counter.update`
    - A class method or static method: `pathlib.Path.cwd`, `pathlib.Path.home`
    - A function: `json.loads`, `uuid.uuid4`

    This works for modules in the current project as well as dependencies.
    This tool only works if you know the specific module/function/method being targeted.

    Args:
        reference: The module/class/method to lookup

    Returns:
        String in format "/absolute/path/to/file.py:line_number"

    Raises:
        NameError: If the reference cannot be found
        ValueError: If the reference format is invalid

    """
    if not reference or not isinstance(reference, str):
        raise ValueError("Reference must be a non-empty string")

    reference = reference.strip()
    obj = _normalized_resolve_reference(reference)

    if obj is None:
        raise NameError(f"could not find source location for {reference}")

    try:
        file_path, line_number = (
            inspect.getsourcefile(obj),
            inspect.getsourcelines(obj)[1],
        )
        if file_path:
            return f"{file_path}:{line_number}"
        else:
            raise NameError(f"could not find source location for {reference}")
    except (OSError, TypeError) as e:
        # Some built-ins don't have source (like C extensions)
        raise NameError(f"could not find source location for {reference}") from e


def _normalized_resolve_reference(reference: str) -> Optional[Any]:
    try:
        return _resolve_reference(reference)
    except (ImportError, AttributeError) as e:
        raise NameError(f"could not resolve reference {reference}") from e
    except (TypeError, OSError) as e:
        raise ValueError(f"invalid reference format {reference}") from e


def _resolve_reference(reference: str) -> Optional[Any]:
    """
    Resolve a Python reference to an actual object.

    Attempts multiple strategies to find the object:
    1. Try as a complete import path
    2. Try importing progressively shorter module paths
    3. Try sys.modules for already imported modules
    4. Try built-ins

    Args:
        reference: Dot-separated reference like 'module.Class.method'

    Returns:
        The resolved Python object or None if not found

    """
    parts = [part for part in reference.split(".") if part]

    if not parts:
        return None

    # Strategy 1: Try as complete import path
    try:
        return importlib.import_module(reference)
    except ImportError:
        pass

    # Strategy 2: Progressive import with attribute access
    for i in range(len(parts) - 1, 0, -1):
        module_path, *attr_path = ".".join(parts[:i]), parts[i:]

        try:
            module = importlib.import_module(module_path)
            obj = _traverse_attrs(module, *attr_path)
            return obj
        except (ImportError, AttributeError):
            continue

    # Strategy 3: Try sys.modules for already imported modules
    if parts[0] in sys.modules:
        try:
            obj = sys.modules[parts[0]]
            obj = _traverse_attrs(obj, parts[1:])
            return obj
        except AttributeError:
            pass

    # Strategy 4: Try built-ins
    try:
        obj = _traverse_attrs(builtins, parts)
        return obj
    except AttributeError:
        pass

    return None


def _traverse_attrs(obj: Any, attrs: list[str]) -> Any:
    """Traverse a chain of attributes on an object."""
    for attr in attrs:
        obj = getattr(obj, attr)
    return obj

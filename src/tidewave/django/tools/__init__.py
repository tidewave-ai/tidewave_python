"""
Django-specific MCP tools
"""

from .models import get_models
from .sql import execute_sql_query

__all__ = [
    "get_models",
    "execute_sql_query",
]

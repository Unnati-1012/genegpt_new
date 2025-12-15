# backend/app/db_handlers/base.py
"""
Base utilities for database handlers.
"""

from typing import Optional
from ..schemas import DatabaseResult


def success_result(db_type: str, search_term: str, data: dict) -> DatabaseResult:
    """Create a successful DatabaseResult."""
    return DatabaseResult(
        db_type=db_type,
        search_term=search_term,
        success=True,
        data=data
    )


def error_result(db_type: str, search_term: str, error: str) -> DatabaseResult:
    """Create a failed DatabaseResult."""
    return DatabaseResult(
        db_type=db_type,
        search_term=search_term,
        success=False,
        error=error
    )

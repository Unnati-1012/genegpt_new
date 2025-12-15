# backend/app/db_handlers/string_handler.py
"""
STRING database handler for GeneGPT.
"""

from typing import Optional
from ..schemas import DatabaseResult
from ..string_tools import STRINGTools
from .base import success_result, error_result

# Initialize STRING tools
string_tools = STRINGTools()


def fetch_string(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch protein-protein interactions from STRING.
    
    Args:
        search_term: Gene/protein name
        sub_command: Not used for STRING
        
    Returns:
        DatabaseResult with interaction data
    """
    data = string_tools.fetch_interactions(search_term)
    
    if "error" in data:
        return error_result("string", search_term, data["error"])
    
    # Add network image URL
    data["network_image_url"] = string_tools.network_image(search_term)
    
    return success_result("string", search_term, data)

# backend/app/db_handlers/image_handler.py
"""
Google Image Search handler for GeneGPT.
Handles image searches for biological entities.
"""

from typing import Optional
from ..schemas import DatabaseResult
from ..google_image_tools import GoogleImageSearch
from .base import success_result, error_result


def fetch_images(google_image_search: GoogleImageSearch, search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch images from Google Image Search.
    
    Args:
        google_image_search: GoogleImageSearch tool instance
        search_term: Query to search for
        sub_command: Not used for image search
        
    Returns:
        DatabaseResult with image URLs
    """
    images = google_image_search.search(search_term)
    
    if not images:
        return error_result("google_image_search", search_term, "No images found")
    
    return success_result("google_image_search", search_term, {
        "query": search_term,
        "images": images[:10]  # Top 10 images
    })

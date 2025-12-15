# backend/app/utils.py
"""
Shared utility functions for GeneGPT.
"""

import re
import requests
from typing import Optional


def safe_get(
    url: str,
    method: str = "get",
    timeout: int = 8,
    allow_redirects: bool = True,
    params: dict = None,
):
    """
    Safe HTTP request wrapper with proper headers and error handling.
    
    Args:
        url: The URL to request
        method: HTTP method ('get' or 'head')
        timeout: Request timeout in seconds
        allow_redirects: Whether to follow redirects
        params: Query parameters
        
    Returns:
        Response object
    """
    headers = {"User-Agent": "Mozilla/5.0 (GeneGPT Bot)"}
    if method.lower() == "head":
        return requests.head(
            url, headers=headers, timeout=timeout, allow_redirects=allow_redirects
        )
    return requests.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=allow_redirects,
        params=params,
    )


def clean_message(text: str) -> str:
    """
    Clean user message by removing special characters.
    
    Args:
        text: Raw user message
        
    Returns:
        Cleaned message string
    """
    if not text:
        return ""
    cleaned = re.sub(r"[\"\'\%\{\}\|\^\~\[\]\<\>]", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def multimodal_response(text: str = None, html: str = None) -> dict:
    """
    Create a standardized response with text and optional HTML.
    
    Args:
        text: Text response
        html: Optional HTML content
        
    Returns:
        Response dictionary with 'reply' and 'html' keys
    """
    return {"reply": text, "html": html}

# backend/app/google_image_tools.py
"""
Google Custom Search API tools for GeneGPT.

Provides image search functionality using Google Custom Search Engine.
Requires GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables.
"""

import os
import requests
from typing import Dict, Any, List


class GoogleImageSearch:
    """
    Client for Google Custom Search API (image mode).
    
    Provides image search functionality for finding biological diagrams,
    protein structures, and scientific illustrations.
    
    Requires environment variables:
    - GOOGLE_API_KEY: Google API key with Custom Search enabled
    - GOOGLE_CSE_ID: Custom Search Engine ID configured for image search
    
    Attributes:
        api_key: Google API key
        cse_id: Custom Search Engine ID
        enabled: Whether the service is configured and available
    """
    
    def __init__(self):
        """Initialize the image search client from environment variables."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")

        if not self.api_key or not self.cse_id:
            print("⚠️ GOOGLE_API_KEY or GOOGLE_CSE_ID not set. Image search disabled.")
            self.enabled = False
        else:
            self.enabled = True

    def search_images(self, query: str, num: int = 3) -> Dict[str, Any]:
        """
        Search for images using Google Custom Search.
        
        Args:
            query: Search terms (e.g., "TP53 protein structure")
            num: Number of images to return (default: 3, max: 10)
            
        Returns:
            Dict containing:
            - results: List of images, each with:
                - title: Image title
                - link: Direct URL to image
                - thumbnail: URL to thumbnail version
            
            Or {"error": str} if search fails or not configured
        """
        if not self.enabled:
            return {"error": "Image search is not configured on the server."}

        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "q": query,
                    "searchType": "image",
                    "num": num,
                    "key": self.api_key,
                    "cx": self.cse_id,
                },
                timeout=10,
            )
            data = resp.json()

            items = data.get("items", []) or []
            results = []
            for item in items:
                results.append(
                    {
                        "title": item.get("title", "image"),
                        "link": item.get("link", ""),
                        "thumbnail": item.get("image", {}).get("thumbnailLink", ""),
                    }
                )

            if not results:
                return {"error": "No images found for that query."}

            return {"results": results}

        except Exception as e:
            print("❌ Google image search error:", e)
            return {"error": "Image search failed due to a server error."}

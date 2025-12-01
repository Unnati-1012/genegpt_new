# backend/app/google_image_tools.py
import os
import requests


class GoogleImageSearch:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")

        if not self.api_key or not self.cse_id:
            print("⚠️ GOOGLE_API_KEY or GOOGLE_CSE_ID not set. Image search disabled.")
            self.enabled = False
        else:
            self.enabled = True

    def search_images(self, query: str, num: int = 3):
        """
        Call Google Custom Search (image mode) and return a small list of results.
        Each result: {"title": ..., "link": ..., "thumbnail": ...}
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

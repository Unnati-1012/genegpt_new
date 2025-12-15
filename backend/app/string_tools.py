# backend/app/string_tools.py
"""
STRING Database API tools for GeneGPT.

Provides access to protein-protein interaction data from STRING-DB.
API Documentation: https://string-db.org/help/api/
"""

import requests
from typing import Dict, Any, List


class STRINGTools:
    """
    Client for STRING Database API.
    
    Provides methods for:
    - Fetching protein-protein interaction networks
    - Generating network visualization URLs
    
    Attributes:
        base: Base URL for STRING API
        format: Response format (json)
        species: NCBI taxonomy ID (9606 for human)
    """
    
    def __init__(self):
        """Initialize STRING API client with default settings for human proteins."""
        self.base = "https://string-db.org/api"
        self.format = "json"
        self.species = 9606  # Human

    def fetch_interactions(self, gene: str) -> Dict[str, Any]:
        """
        Fetch protein-protein interactions from STRING database.
        
        Args:
            gene: Gene symbol or protein name (e.g., "TP53", "BRCA1")
            
        Returns:
            Dict containing:
            - query: The queried gene
            - interactions: List of interaction partners, each with:
                - partner: Partner protein name
                - score: Interaction confidence score (0-1)
                - string_id: STRING database identifier
            
            Or {"error": str} if no interactions found
        """
        try:
            url = f"{self.base}/{self.format}/network"
            params = {
                "identifiers": gene,
                "species": self.species,
                "limit": 20,
            }

            res = requests.get(url, params=params)
            if res.status_code != 200:
                return {"error": f"STRING API error (status {res.status_code})"}

            data = res.json()
            if not data:
                return {"error": f"No interactions found for '{gene}'"}

            interactions = []
            for item in data:
                interactions.append({
                    "partner": item.get("preferredName_B", ""),
                    "score": item.get("score", 0.0),
                    "string_id": item.get("stringId_B", ""),
                })

            return {
                "query": gene,
                "interactions": interactions
            }

        except Exception as e:
            return {"error": f"STRING error: {e}"}

    def network_image(self, gene: str) -> str:
        """
        Generate URL for STRING network visualization image.
        
        Args:
            gene: Gene symbol or protein name
            
        Returns:
            Direct URL to PNG image of the protein interaction network
        """
        return (
            "https://string-db.org/api/image/network?"
            f"identifiers={gene}&species={self.species}"
        )

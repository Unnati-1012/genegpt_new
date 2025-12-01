import requests

class STRINGTools:
    def __init__(self):
        self.base = "https://string-db.org/api"
        self.format = "json"
        self.species = 9606  # Human

    def fetch_interactions(self, gene):
        """
        Fetch top protein-protein interactions using STRING DB.
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


    def network_image(self, gene):
        """
        Return a direct URL for the STRING network PNG.
        """
        return (
            "https://string-db.org/api/image/network?"
            f"identifiers={gene}&species={self.species}"
        )

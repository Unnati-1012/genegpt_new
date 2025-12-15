import requests

class PubChemTools:
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    TIMEOUT = 20  # seconds

    def _safe_request(self, url: str) -> requests.Response | None:
        """Make a request with timeout and error handling."""
        try:
            return requests.get(url, timeout=self.TIMEOUT)
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.RequestException:
            return None

    # 1. Search for a chemical by name
    def pubchem_search(self, query: str):
        url = f"{self.BASE}/compound/name/{query}/JSON"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout while searching for '{query}'"}
        if r.status_code != 200:
            return {"error": f"No compound found for '{query}'"}

        try:
            data = r.json()
            cid = data["PC_Compounds"][0]["id"]["id"]["cid"]
            return {"query": query, "cid": cid}
        except (KeyError, IndexError):
            return {"error": f"Could not parse response for '{query}'"}

    # 1b. Get compound info by CID directly
    def pubchem_get_by_cid(self, cid: str | int):
        """Get compound info when CID is already known."""
        url = f"{self.BASE}/compound/cid/{cid}/description/JSON"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout for CID {cid}"}
        if r.status_code != 200:
            return {"error": f"No compound found for CID {cid}"}
        
        try:
            data = r.json()
            info_list = data.get("InformationList", {}).get("Information", [])
            
            # Extract the compound title/name
            name = "Unknown"
            for info in info_list:
                if "Title" in info:
                    name = info["Title"]
                    break
            
            return {"cid": int(cid), "name": name}
        except Exception:
            return {"cid": int(cid), "name": f"Compound {cid}"}

    # 2. Get compound properties by CID
    def pubchem_properties(self, cid: str | int):
        url = f"{self.BASE}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey/JSON"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout for CID {cid}"}
        if r.status_code != 200:
            return {"error": f"No properties found for CID {cid}"}
        
        try:
            props = r.json().get("PropertyTable", {}).get("Properties", [])
            return props[0] if props else {"error": "Properties missing"}
        except Exception:
            return {"error": "Could not parse properties"}

    # 3. Get 3D structure (SDF format)
    def pubchem_3d_structure(self, cid: str | int):
        url = f"{self.BASE}/compound/cid/{cid}/record/SDF"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout for CID {cid}"}
        if r.status_code != 200:
            return {"error": f"No 3D structure found for CID {cid}"}
        
        return {"cid": cid, "sdf": r.text}

    # 4. Generate a viewer iframe
    def pubchem_iframe(self, cid: str | int):
        return f"""
        <iframe
            src="https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
            style="width:100%; height:520px; border:none;">
        </iframe>
        """

# backend/app/pubchem_tools.py
"""
PubChem API tools for GeneGPT.

Provides access to chemical compound information from NCBI PubChem.
API Documentation: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
"""

import requests
from typing import Dict, Any, Optional


class PubChemTools:
    """
    Client for PubChem PUG REST API.
    
    Provides methods for:
    - Searching compounds by name
    - Retrieving compound properties (formula, weight, SMILES)
    - Getting 3D structure data
    - Generating embedded viewer iframes
    
    Attributes:
        BASE: Base URL for PubChem PUG REST API
        TIMEOUT: Request timeout in seconds
    """
    
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

    def pubchem_search(self, query: str) -> Dict[str, Any]:
        """
        Search for a chemical compound by name.
        
        Args:
            query: Compound name (e.g., "aspirin", "caffeine", "glucose")
            
        Returns:
            Dict containing:
            - query: The search term
            - cid: PubChem Compound ID (CID)
            
            Or {"error": str} if not found
        """
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

    def pubchem_get_by_cid(self, cid: str | int) -> Dict[str, Any]:
        """
        Get compound information by CID directly.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            Dict containing:
            - cid: The compound ID
            - name: Compound name/title
            
            Or {"error": str} if not found
        """
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

    def pubchem_properties(self, cid: str | int) -> Dict[str, Any]:
        """
        Get chemical properties for a compound.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            Dict containing:
            - MolecularFormula: Chemical formula (e.g., "C9H8O4")
            - MolecularWeight: Molecular weight
            - CanonicalSMILES: SMILES notation
            - InChIKey: International Chemical Identifier key
            
            Or {"error": str} if not found
        """
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

    def pubchem_3d_structure(self, cid: str | int) -> Dict[str, Any]:
        """
        Get 3D structure in SDF format for a compound.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            Dict containing:
            - cid: The compound ID
            - sdf: 3D structure in SDF format
            
            Or {"error": str} if not available
        """
        url = f"{self.BASE}/compound/cid/{cid}/record/SDF"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout for CID {cid}"}
        if r.status_code != 200:
            return {"error": f"No 3D structure found for CID {cid}"}
        
        return {"cid": cid, "sdf": r.text}

    def pubchem_iframe(self, cid: str | int) -> str:
        """
        Generate an embedded iframe for PubChem compound viewer.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            HTML iframe string for embedding PubChem compound page
        """
        return f"""
        <iframe
            src="https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
            style="width:100%; height:520px; border:none;">
        </iframe>
        """

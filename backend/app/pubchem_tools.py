import requests

class PubChemTools:
    BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    # 1. Search for a chemical by name
    def pubchem_search(self, query: str):
        url = f"{self.BASE}/compound/name/{query}/JSON"
        r = requests.get(url)
        if r.status_code != 200:
            return {"error": f"No compound found for '{query}'"}

        data = r.json()
        cid = data["PC_Compounds"][0]["id"]["id"]["cid"]
        return {"query": query, "cid": cid}

    # 2. Get compound properties by CID
    def pubchem_properties(self, cid: str | int):
        url = f"{self.BASE}/compound/cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey/JSON"
        r = requests.get(url)
        if r.status_code != 200:
            return {"error": f"No properties found for CID {cid}"}
        
        props = r.json().get("PropertyTable", {}).get("Properties", [])
        return props[0] if props else {"error": "Properties missing"}

    # 3. Get 3D structure (SDF format)
    def pubchem_3d_structure(self, cid: str | int):
        url = f"{self.BASE}/compound/cid/{cid}/record/SDF"
        r = requests.get(url)
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

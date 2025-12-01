import requests

class PDBTools:
    BASE_SUMMARY = "https://data.rcsb.org/rest/v1/core/entry/"
    BASE_MMCIF = "https://files.rcsb.org/download/"
    BASE_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
    BASE_LIGAND = "https://data.rcsb.org/rest/v1/core/ligand/"

    # 1. Fetch metadata for a PDB entry
    def pdb_fetch_entry(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_SUMMARY}{pdb_id}"
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
        return {"error": f"PDB entry {pdb_id} not found"}

    # 2. Download mmCIF structure file
    def pdb_fetch_mmcif(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_MMCIF}{pdb_id}.cif"
        r = requests.get(url)
        if r.status_code == 200:
            return {"pdb_id": pdb_id, "mmcif": r.text}
        return {"error": f"mmCIF for {pdb_id} not found"}

    # 3. Search for PDB IDs linked to a UniProt accession
    def pdb_search_by_uniprot(self, uniprot_id: str):
        query = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                    "value": uniprot_id
                }
            },
            "return_type": "entry"
        }
        r = requests.post(self.BASE_SEARCH, json=query)

        if r.status_code == 200:
            results = r.json().get("result_set", [])
            pdb_ids = [entry["identifier"] for entry in results]
            return {"uniprot_id": uniprot_id, "pdb_ids": pdb_ids}

        return {"error": "Search failed"}

    # 4. Fetch ligands for a PDB entry
    def pdb_fetch_ligands(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_LIGAND}{pdb_id}"
        r = requests.get(url)
        if r.status_code == 200:
            return r.json()
        return {"error": f"No ligands found for {pdb_id}"}

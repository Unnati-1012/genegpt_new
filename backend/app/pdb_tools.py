import requests

class PDBTools:
    BASE_SUMMARY = "https://data.rcsb.org/rest/v1/core/entry/"
    BASE_MMCIF = "https://files.rcsb.org/download/"
    BASE_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
    BASE_LIGAND = "https://data.rcsb.org/rest/v1/core/ligand/"
    
    # Well-known PDB structures for common genes (fallback when API fails)
    KNOWN_PDB_MAP = {
        "EGFR": ["1M17", "5UG9", "3POZ", "4HJO", "2ITY"],
        "KRAS": ["4OBE", "6GOD", "4DSO", "5TAR", "6MNX"],
        "TP53": ["1TUP", "2OCJ", "3KMD", "4HJE", "5AOK"],
        "BRCA1": ["1JM7", "4IGK", "3K0H", "4Y2G"],
        "MYC": ["1NKP", "5I50"],
        "AKT1": ["3O96", "4EKL", "3CQW"],
        "MDM2": ["1YCR", "4ERF", "3JZK"],
        "BRAF": ["1UWH", "4MNE", "6P3D"],
        "HER2": ["3PP0", "1N8Z", "3WSQ"],
        "ALK": ["2XP2", "4MKC", "5AAA"],
        "BCL2": ["1G5M", "2O2F", "4LVT"],
        "PTEN": ["1D5R", "5BZZ"],
        "RAS": ["4OBE", "5P21", "6GOD"],
        "P53": ["1TUP", "2OCJ", "3KMD"],
        "INSULIN": ["4INS", "1ZNI", "1AI0"],
        "HEMOGLOBIN": ["1HHO", "2HHB", "1A3N"],
    }

    def _safe_request(self, method: str, url: str, **kwargs):
        """Make a request with timeout and error handling."""
        kwargs.setdefault('timeout', 15)
        kwargs.setdefault('headers', {'User-Agent': 'GeneGPT/1.0'})
        try:
            if method.lower() == 'get':
                return requests.get(url, **kwargs)
            else:
                return requests.post(url, **kwargs)
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.ConnectionError:
            return None
        except Exception:
            return None

    # 1. Fetch metadata for a PDB entry
    def pdb_fetch_entry(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_SUMMARY}{pdb_id}"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
            return r.json()
        return {"error": f"PDB entry {pdb_id} not found or connection failed"}

    # 2. Download mmCIF structure file
    def pdb_fetch_mmcif(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_MMCIF}{pdb_id}.cif"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
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
        r = self._safe_request('post', self.BASE_SEARCH, json=query)

        if r and r.status_code == 200:
            results = r.json().get("result_set", [])
            pdb_ids = [entry["identifier"] for entry in results]
            return {"uniprot_id": uniprot_id, "pdb_ids": pdb_ids}

        return {"error": "Search failed or connection timeout"}
    
    # Get known PDB IDs for a gene (fallback)
    def get_known_pdb_ids(self, gene_name: str):
        """Return known PDB IDs for common genes."""
        return self.KNOWN_PDB_MAP.get(gene_name.upper(), [])

    # 4. Fetch ligands for a PDB entry
    def pdb_fetch_ligands(self, pdb_id: str):
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_LIGAND}{pdb_id}"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
            return r.json()
        return {"error": f"No ligands found for {pdb_id}"}

    # 5. Search for PDB entries by gene name or protein name (text search)
    def pdb_search_by_text(self, query: str, max_results: int = 5):
        """Search PDB by gene name, protein name, or any text."""
        search_query = {
            "query": {
                "type": "group",
                "logical_operator": "or",
                "nodes": [
                    {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {
                            "attribute": "rcsb_entity_source_organism.rcsb_gene_name.value",
                            "operator": "exact_match",
                            "value": query.upper()
                        }
                    },
                    {
                        "type": "terminal",
                        "service": "full_text",
                        "parameters": {
                            "value": query
                        }
                    }
                ]
            },
            "return_type": "entry",
            "request_options": {
                "results_content_type": ["experimental"],
                "sort": [{"sort_by": "rcsb_accession_info.deposit_date", "direction": "desc"}],
                "paginate": {"start": 0, "rows": max_results}
            }
        }
        
        r = self._safe_request('post', self.BASE_SEARCH, json=search_query)
        if r and r.status_code == 200:
            data = r.json()
            results = data.get("result_set", [])
            pdb_ids = [entry["identifier"] for entry in results]
            return {"query": query, "pdb_ids": pdb_ids, "total": data.get("total_count", 0)}
        
        return {"error": "Search failed or connection timeout"}

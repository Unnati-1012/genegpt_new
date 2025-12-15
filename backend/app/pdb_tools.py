# backend/app/pdb_tools.py
"""
Protein Data Bank (PDB) API tools for GeneGPT.

Provides access to 3D protein structure data from RCSB PDB.
API Documentation: https://data.rcsb.org/
"""

import requests
from typing import Dict, Any, List, Optional


class PDBTools:
    """
    Client for RCSB Protein Data Bank API.
    
    Provides methods for:
    - Fetching PDB entry metadata
    - Downloading mmCIF structure files
    - Searching by UniProt ID, gene name, or text
    - Fetching ligand information
    
    Includes fallback mapping for well-known gene structures when API fails.
    
    Attributes:
        BASE_SUMMARY: URL for PDB entry metadata
        BASE_MMCIF: URL for structure file downloads
        BASE_SEARCH: URL for PDB search API
        BASE_LIGAND: URL for ligand information
        KNOWN_PDB_MAP: Fallback mapping of gene names to known PDB IDs
    """
    
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

    def pdb_fetch_entry(self, pdb_id: str) -> Dict[str, Any]:
        """
        Fetch metadata for a PDB entry.
        
        Args:
            pdb_id: 4-character PDB ID (e.g., "1TUP", "4OBE")
            
        Returns:
            Dict containing PDB entry metadata including:
            - struct.title: Structure title
            - rcsb_entry_info: Entry information
            - polymer_entities: Information about protein chains
            
            Or {"error": str} if not found
        """
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_SUMMARY}{pdb_id}"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
            return r.json()
        return {"error": f"PDB entry {pdb_id} not found or connection failed"}

    def pdb_fetch_mmcif(self, pdb_id: str) -> Dict[str, Any]:
        """
        Download mmCIF structure file for a PDB entry.
        
        Args:
            pdb_id: 4-character PDB ID (e.g., "1TUP")
            
        Returns:
            Dict containing:
            - pdb_id: The queried PDB ID
            - mmcif: The mmCIF file content as text
            
            Or {"error": str} if not found
        """
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_MMCIF}{pdb_id}.cif"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
            return {"pdb_id": pdb_id, "mmcif": r.text}
        return {"error": f"mmCIF for {pdb_id} not found"}

    def pdb_search_by_uniprot(self, uniprot_id: str) -> Dict[str, Any]:
        """
        Search for PDB entries linked to a UniProt accession.
        
        Args:
            uniprot_id: UniProt accession (e.g., "P04637" for TP53)
            
        Returns:
            Dict containing:
            - uniprot_id: The queried UniProt ID
            - pdb_ids: List of associated PDB IDs
            
            Or {"error": str} if search fails
        """
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

    def pdb_fetch_ligands(self, pdb_id: str) -> Dict[str, Any]:
        """
        Fetch ligand information for a PDB entry.
        
        Args:
            pdb_id: 4-character PDB ID
            
        Returns:
            Dict containing ligand information or {"error": str} if not found
        """
        pdb_id = pdb_id.lower()
        url = f"{self.BASE_LIGAND}{pdb_id}"
        r = self._safe_request('get', url)
        if r and r.status_code == 200:
            return r.json()
        return {"error": f"No ligands found for {pdb_id}"}

    def pdb_search_by_text(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Search PDB by gene name, protein name, or free text.
        
        Uses both exact gene name matching and full-text search,
        returning the most recently deposited structures.
        
        Args:
            query: Search term (gene symbol, protein name, or keywords)
            max_results: Maximum number of results to return (default: 5)
            
        Returns:
            Dict containing:
            - query: The search term
            - pdb_ids: List of matching PDB IDs
            - total: Total number of matches in PDB
            
            Or {"error": str} if search fails
        """
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

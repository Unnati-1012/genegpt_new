# backend/app/kegg_tools.py
"""
KEGG (Kyoto Encyclopedia of Genes and Genomes) API tools for GeneGPT.

Provides access to biological pathway data from KEGG.
API Documentation: https://www.kegg.jp/kegg/rest/keggapi.html
"""

import requests
from typing import Dict, Any, List, Optional


class KEGGTools:
    """
    Client for KEGG REST API.
    
    Provides methods for:
    - Finding pathways associated with genes
    - Retrieving pathway information and names
    - Generating pathway map visualizations
    
    Includes a built-in mapping of common gene symbols to KEGG IDs
    for faster lookups.
    
    Attributes:
        BASE: Base URL for KEGG REST API
        TIMEOUT: Request timeout in seconds
        GENE_TO_KEGG: Mapping of gene symbols to KEGG gene IDs
        pathway_cache: Cache of pathway ID to name mappings
    """
    
    BASE = "https://rest.kegg.jp"
    TIMEOUT = 15  # seconds

    # ----------------------------------------------------
    # INTERNAL CACHE: pathway_id → pathway_name
    # ----------------------------------------------------
    pathway_cache = {}
    
    # Common gene symbol to KEGG ID mapping for human genes
    GENE_TO_KEGG = {
        "TP53": "hsa:7157",
        "BRCA1": "hsa:672",
        "BRCA2": "hsa:675",
        "EGFR": "hsa:1956",
        "KRAS": "hsa:3845",
        "AKT1": "hsa:207",
        "PTEN": "hsa:5728",
        "PIK3CA": "hsa:5290",
        "MYC": "hsa:4609",
        "RB1": "hsa:5925",
        "BRAF": "hsa:673",
        "ERBB2": "hsa:2064",
        "HER2": "hsa:2064",
        "CDK4": "hsa:1019",
        "CDK6": "hsa:1021",
        "VEGFA": "hsa:7422",
        "MTOR": "hsa:2475",
        "JAK2": "hsa:3717",
        "BCL2": "hsa:596",
        "NRAS": "hsa:4893",
        "ALK": "hsa:238",
        "RET": "hsa:5979",
        "MET": "hsa:4233",
        "FGFR1": "hsa:2260",
        "FGFR2": "hsa:2263",
        "FGFR3": "hsa:2261",
        "ATM": "hsa:472",
        "CHEK2": "hsa:11200",
        "PALB2": "hsa:79728",
        "RAD51": "hsa:5888",
        "CDKN2A": "hsa:1029",
        "VHL": "hsa:7428",
        "NF1": "hsa:4763",
        "NF2": "hsa:4771",
        "WT1": "hsa:7490",
        "APC": "hsa:324",
        "SMAD4": "hsa:4089",
        "MLH1": "hsa:4292",
        "MSH2": "hsa:4436",
        "INS": "hsa:3630",
        "GCK": "hsa:2645",
        "HNF1A": "hsa:6927",
        "HNF4A": "hsa:3172",
        "CFTR": "hsa:1080",
        "DMD": "hsa:1756",
        "HTT": "hsa:3064",
        "FMR1": "hsa:2332",
        "SOD1": "hsa:6647",
        "APP": "hsa:351",
        "PSEN1": "hsa:5663",
        "PSEN2": "hsa:5664",
        "APOE": "hsa:348",
        "LRRK2": "hsa:120892",
        "SNCA": "hsa:6622",
        "PARK7": "hsa:11315",
        "PINK1": "hsa:65018",
    }

    def __init__(self):
        """Load all human pathway names once."""
        self.pathway_names = {}

    def _safe_request(self, url: str) -> requests.Response | None:
        """Make a request with timeout and error handling."""
        try:
            return requests.get(url, timeout=self.TIMEOUT)
        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.RequestException:
            return None

    def _find_kegg_gene_id(self, gene_symbol: str) -> Optional[str]:
        """
        Find KEGG gene ID from a gene symbol.
        
        First checks the built-in GENE_TO_KEGG mapping, then falls back
        to the KEGG find API if not found.
        
        Args:
            gene_symbol: Gene symbol (e.g., "TP53", "BRCA1")
            
        Returns:
            KEGG gene ID (e.g., "hsa:7157") or None if not found
        """
        gene_upper = gene_symbol.upper().strip()
        
        # Check our known mapping first
        if gene_upper in self.GENE_TO_KEGG:
            return self.GENE_TO_KEGG[gene_upper]
        
        # Try KEGG find API
        url = f"{self.BASE}/find/genes/{gene_symbol}"
        r = self._safe_request(url)
        
        if r and r.status_code == 200 and r.text.strip():
            # Parse results - look for human (hsa:) genes
            for line in r.text.strip().split("\n"):
                if line.startswith("hsa:"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        kegg_id = parts[0].strip()
                        description = parts[1].upper() if len(parts) > 1 else ""
                        # Check if this matches our gene symbol
                        if gene_upper in description or f";{gene_upper}" in description or f" {gene_upper}," in description:
                            return kegg_id
            
            # If no exact match, return the first human result
            first_line = r.text.strip().split("\n")[0]
            if first_line.startswith("hsa:"):
                return first_line.split("\t")[0].strip()
        
        return None

    def load_all_pathway_names(self) -> None:
        """
        Load all human pathway names from KEGG into the cache.
        
        Populates pathway_cache with pathway_id -> pathway_name mappings
        for all human (hsa) pathways. Called once at initialization.
        """
        try:
            r = requests.get(f"{self.BASE}/list/pathway/hsa", timeout=10)
            if r.status_code != 200:
                print("⚠️ Failed to load KEGG pathway list.")
                return

            for line in r.text.strip().split("\n"):
                try:
                    pid, name = line.split("\t")
                    pid = pid.replace("path:", "").strip()
                    self.pathway_cache[pid] = name.strip()
                except:
                    continue

            print(f"✅ Loaded {len(self.pathway_cache)} KEGG pathways.")
        except Exception:
            print("⚠️ Failed to load KEGG pathway list (timeout).")

    def gene_pathways(self, gene_id: str) -> Dict[str, Any]:
        """
        Get list of pathways associated with a gene.
        
        Args:
            gene_id: KEGG gene ID (e.g., "hsa:7157") or gene symbol
            
        Returns:
            Dict containing:
            - gene: The queried gene ID
            - pathways: List of KEGG pathway IDs
            
            Or {"error": str} if not found
        """
        url = f"{self.BASE}/link/pathway/{gene_id}"
        r = self._safe_request(url)

        if r is None:
            return {"error": f"Connection timeout while fetching pathways for {gene_id}"}
        if r.status_code != 200 or not r.text.strip():
            return {"error": f"No KEGG pathways found for {gene_id}"}

        pathways = sorted([
            line.split("\t")[1].replace("path:", "")
            for line in r.text.strip().split("\n")
            if "\t" in line
        ])

        return {"gene": gene_id, "pathways": pathways}

    def pathway_name(self, pid: str) -> str:
        """
        Get human-readable name for a pathway ID.
        
        Checks cache first, then queries KEGG API if not found.
        
        Args:
            pid: KEGG pathway ID (e.g., "hsa04110")
            
        Returns:
            Pathway name string (e.g., "Cell cycle - Homo sapiens (human)")
        """
        # Check cache first
        if pid in self.pathway_cache:
            return self.pathway_cache[pid]
        
        # Try to fetch from API if not in cache
        url = f"{self.BASE}/get/{pid}"
        r = self._safe_request(url)
        
        if r and r.status_code == 200:
            # Parse the first line which usually has the name
            lines = r.text.strip().split("\n")
            for line in lines:
                if line.startswith("NAME"):
                    name = line.replace("NAME", "").strip()
                    self.pathway_cache[pid] = name
                    return name
        
        return f"Pathway {pid}"

    def pathway_info(self, pathway_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a KEGG pathway.
        
        Args:
            pathway_id: KEGG pathway ID (e.g., "hsa04110")
            
        Returns:
            Dict containing:
            - pathway_id: The queried pathway ID
            - raw: Raw KEGG flat file text with full pathway details
            
            Or {"error": str} if not found
        """
        url = f"{self.BASE}/get/{pathway_id}"
        r = self._safe_request(url)

        if r is None:
            return {"error": f"Connection timeout for pathway {pathway_id}"}
        if r.status_code != 200:
            return {"error": f"No info found for pathway {pathway_id}"}

        return {"pathway_id": pathway_id, "raw": r.text}

    def pathway_map(self, pid: str) -> str:
        """
        Generate HTML iframe for KEGG pathway map visualization.
        
        Args:
            pid: KEGG pathway ID (can include "hsa" or "map" prefix)
            
        Returns:
            HTML iframe string for embedding pathway map image
        """
        pid = pid.replace("hsa", "").replace("map", "").strip()
        url = f"https://www.kegg.jp/kegg/pathway/map/map{pid}.png"

        return f"""
        <iframe src="{url}"
                style="width:100%; height:900px; border:none;">
        </iframe>
        """

    def search_pathway(self, query: str) -> Dict[str, Any]:
        """
        Search for KEGG pathways by name/keyword.
        
        Args:
            query: Search term (e.g., "PI3K-AKT", "cell cycle", "apoptosis")
            
        Returns:
            Dict containing:
            - pathways: List of matching pathways with id, name, image_url, and link
            
            Or {"error": str} if not found
        """
        # First, search KEGG for pathways matching the query
        url = f"{self.BASE}/find/pathway/{query}"
        r = self._safe_request(url)
        
        if r is None:
            return {"error": f"Connection timeout searching for pathway '{query}'"}
        
        if r.status_code != 200 or not r.text.strip():
            # Try alternate search - look for human pathways only
            url2 = f"{self.BASE}/list/pathway/hsa"
            r2 = self._safe_request(url2)
            
            if r2 and r2.status_code == 200:
                query_lower = query.lower()
                matching = []
                for line in r2.text.strip().split("\n"):
                    if query_lower in line.lower():
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            pid = parts[0].replace("path:", "").strip()
                            name = parts[1].strip()
                            matching.append((pid, name))
                
                if matching:
                    pathways = []
                    for pid, name in matching[:5]:  # Limit to 5 results
                        pathway_num = pid.replace("hsa", "")
                        pathways.append({
                            "pathway_id": pid,
                            "name": name,
                            "image_url": f"https://www.kegg.jp/kegg/pathway/hsa/{pid}.png",
                            "pathway_link": f"https://www.kegg.jp/pathway/{pid}",
                            "interactive_map": f"https://www.kegg.jp/kegg-bin/show_pathway?{pid}"
                        })
                    return {"pathways": pathways, "query": query}
            
            return {"error": f"No pathways found for '{query}'"}
        
        # Parse search results
        pathways = []
        for line in r.text.strip().split("\n")[:5]:  # Limit to 5 results
            parts = line.split("\t")
            if len(parts) >= 2:
                pid = parts[0].replace("path:", "").strip()
                name = parts[1].strip()
                
                # Convert to human pathway if it's a generic map
                if pid.startswith("map"):
                    hsa_pid = pid.replace("map", "hsa")
                else:
                    hsa_pid = pid
                
                pathway_num = hsa_pid.replace("hsa", "")
                
                pathways.append({
                    "pathway_id": hsa_pid,
                    "name": name,
                    "image_url": f"https://www.kegg.jp/kegg/pathway/hsa/{hsa_pid}.png",
                    "pathway_link": f"https://www.kegg.jp/pathway/{hsa_pid}",
                    "interactive_map": f"https://www.kegg.jp/kegg-bin/show_pathway?{hsa_pid}"
                })
        
        if not pathways:
            return {"error": f"No pathways found for '{query}'"}
        
        return {"pathways": pathways, "query": query}

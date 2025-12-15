# backend/app/db_handlers/ensembl_handler.py
"""
Ensembl database handler for GeneGPT.
Handles gene lookups, transcripts, and genomic regions.
"""

import re
import requests
from typing import Optional
from ..schemas import DatabaseResult
from ..ensembl_tools import EnsemblTools
from .base import success_result, error_result

# Initialize Ensembl tools
ensembl_tools = EnsemblTools()


def fetch_ensembl(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch genomic data from Ensembl.
    
    Args:
        search_term: Gene name, Ensembl ID, or region
        sub_command: "id", "transcripts", "region", or None for gene lookup
        
    Returns:
        DatabaseResult with Ensembl data
    """
    if sub_command == "id":
        return _fetch_by_id(search_term)
    elif sub_command == "transcripts":
        return _fetch_transcripts(search_term)
    elif sub_command == "region":
        return _fetch_region(search_term)
    else:
        return _fetch_gene(search_term)


def _fetch_by_id(stable_id: str) -> DatabaseResult:
    """Lookup by Ensembl stable ID."""
    data = ensembl_tools.lookup_id(stable_id)
    
    if not data:
        return error_result("ensembl", stable_id,
                           f"No Ensembl record found for ID '{stable_id}'")
    
    return success_result("ensembl", stable_id, {
        "source": "id_lookup",
        "record": data
    })


def _fetch_transcripts(gene_id: str) -> DatabaseResult:
    """Get transcripts for a gene."""
    transcripts = ensembl_tools.gene_transcripts(gene_id)
    
    if not transcripts:
        return error_result("ensembl", gene_id,
                           f"No transcripts found for '{gene_id}'")
    
    return success_result("ensembl", gene_id, {
        "source": "transcripts",
        "transcripts": transcripts
    })


def _fetch_region(region_str: str) -> DatabaseResult:
    """Get genes/features in a genomic region."""
    # Parse the region - support formats like "17:7565097-7590856" or "chr17:7565097-7590856"
    region_match = re.match(r'^(?:chr)?(\w+):(\d+)-(\d+)$', region_str.strip())
    
    if not region_match:
        return error_result("ensembl", region_str,
                           "Invalid region format. Use format: chromosome:start-end (e.g., 17:7565097-7590856)")
    
    chrom = region_match.group(1)
    start = int(region_match.group(2))
    end = int(region_match.group(3))
    
    # Use Ensembl overlap API to get features in region
    url = f"https://rest.ensembl.org/overlap/region/human/{chrom}:{start}-{end}"
    
    try:
        r = requests.get(url,
            headers={"Content-Type": "application/json"},
            params={"feature": "gene"},
            timeout=15
        )
        
        if r.status_code != 200:
            return error_result("ensembl", region_str,
                               f"No genes found in region {chrom}:{start}-{end}")
        
        genes = r.json()
        
        if not genes:
            return error_result("ensembl", region_str,
                               f"No genes found in region {chrom}:{start}-{end}")
        
        # Format the results
        gene_list = []
        for g in genes[:20]:  # Limit to 20 genes
            gene_list.append({
                "id": g.get("gene_id", g.get("id", "")),
                "name": g.get("external_name", "Unknown"),
                "biotype": g.get("biotype", ""),
                "start": g.get("start"),
                "end": g.get("end"),
                "strand": g.get("strand"),
                "description": g.get("description", "")
            })
        
        return success_result("ensembl", region_str, {
            "source": "region",
            "region": f"{chrom}:{start}-{end}",
            "chromosome": chrom,
            "start": start,
            "end": end,
            "genes": gene_list,
            "total_genes": len(genes),
            "ensembl_url": f"https://ensembl.org/Homo_sapiens/Location/View?r={chrom}:{start}-{end}"
        })
        
    except requests.exceptions.Timeout:
        return error_result("ensembl", region_str,
                           "Connection timeout while fetching region data")
    except Exception as e:
        return error_result("ensembl", region_str,
                           f"Error fetching region data: {str(e)}")


def _fetch_gene(symbol: str) -> DatabaseResult:
    """Lookup gene by symbol."""
    gene = ensembl_tools.lookup_gene(symbol, species="human")
    
    if not gene:
        return error_result("ensembl", symbol,
                           f"No Ensembl gene found for '{symbol}'")
    
    return success_result("ensembl", symbol, {
        "source": "gene_lookup",
        "gene": gene
    })

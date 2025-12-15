# backend/app/db_handlers/ncbi_handler.py
"""
NCBI database handler for GeneGPT.
Handles Gene and PubMed queries.
"""

from typing import Optional
from ..schemas import DatabaseResult
from ..ncbi_tools import NCBITools
from .base import success_result, error_result

# Initialize NCBI tools
ncbi_tools = NCBITools()


def fetch_ncbi(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch data from NCBI (Gene or PubMed).
    
    Args:
        search_term: Gene name or search query
        sub_command: "pubmed" for literature, "gene" for gene info
        
    Returns:
        DatabaseResult with NCBI data
    """
    if sub_command == "pubmed":
        return _fetch_pubmed(search_term)
    else:
        return _fetch_gene(search_term)


def _fetch_pubmed(search_term: str) -> DatabaseResult:
    """Fetch PubMed literature search results."""
    results = ncbi_tools.pubmed_search(search_term)
    
    if "error" in results:
        return error_result("ncbi", search_term, results["error"])
    
    return success_result("ncbi", search_term, {
        "source": "pubmed",
        "results": results.get("results", [])
    })


def _fetch_gene(search_term: str) -> DatabaseResult:
    """Fetch NCBI gene information."""
    gene_result = ncbi_tools.gene_search(search_term)
    
    if "error" in gene_result:
        return error_result("ncbi", search_term, gene_result["error"])
    
    gene_id = gene_result.get("gene_id")
    summary = ncbi_tools.gene_summary(gene_id)
    
    return success_result("ncbi", search_term, {
        "source": "gene",
        "gene_id": gene_id,
        "summary": summary
    })

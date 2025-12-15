# backend/app/db_handlers/clinvar_handler.py
"""
ClinVar database handler for GeneGPT.
Handles genetic variant queries.
"""

from typing import Optional
from ..schemas import DatabaseResult
from ..clinvar_tools import ClinVarTools
from .base import success_result, error_result

# Initialize ClinVar tools
clinvar_tools = ClinVarTools()


def fetch_clinvar(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch variant data from ClinVar.
    
    Args:
        search_term: Gene name
        sub_command: Not used for ClinVar
        
    Returns:
        DatabaseResult with variant data
    """
    data = clinvar_tools.variants_for_gene(search_term.upper())
    
    if "error" in data:
        return error_result("clinvar", search_term, data["error"])
    
    variants = data.get("results", [])
    
    # Summarize by clinical significance
    significance_counts = {}
    for v in variants:
        sig = v.get("clinical_significance", "Unknown")
        significance_counts[sig] = significance_counts.get(sig, 0) + 1
    
    return success_result("clinvar", search_term, {
        "gene": search_term.upper(),
        "total_variants": len(variants),
        "significance_summary": significance_counts,
        "sample_variants": variants[:10]  # First 10 variants
    })

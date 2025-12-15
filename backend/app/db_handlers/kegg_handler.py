# backend/app/db_handlers/kegg_handler.py
"""
KEGG database handler for GeneGPT.
Handles pathway and gene queries.
"""

import re
from typing import Optional
from ..schemas import DatabaseResult
from ..kegg_tools import KEGGTools
from .base import success_result, error_result

# Initialize KEGG tools
kegg_tools = KEGGTools()


def fetch_kegg(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch pathway data from KEGG.
    
    Args:
        search_term: Gene name, pathway ID, or pathway name
        sub_command: "pathway" for pathway info, "diagram" for pathway image, None for gene pathways
        
    Returns:
        DatabaseResult with KEGG data
    """
    # Check if this is a pathway diagram/image request
    search_lower = search_term.lower()
    is_diagram_request = any(word in search_lower for word in 
                              ['diagram', 'image', 'map', 'picture', 'pathway', 'signaling', 'signal'])
    
    if sub_command == "pathway" or sub_command == "diagram":
        return _fetch_pathway_diagram(search_term)
    elif is_diagram_request:
        # User is asking for a pathway diagram
        return _fetch_pathway_diagram(search_term)
    else:
        return _fetch_gene_pathways(search_term)


def _fetch_pathway_diagram(search_term: str) -> DatabaseResult:
    """Fetch KEGG pathway diagram/image by searching for the pathway."""
    # Clean up the search term - remove words like "diagram", "image", "pathway", etc.
    clean_term = search_term.lower()
    for word in ['diagram', 'image', 'map', 'picture', 'show me', 'show', 'pathway', 
                 'of', 'the', 'diagrams', 'images', 'maps']:
        clean_term = clean_term.replace(word, ' ')
    clean_term = ' '.join(clean_term.split()).strip()
    
    # Check if it's a pathway ID (like hsa04151 or 04151)
    pathway_id_match = re.match(r'^(hsa)?(\d{5})$', clean_term.replace(' ', ''))
    if pathway_id_match:
        pid = f"hsa{pathway_id_match.group(2)}"
        name = kegg_tools.pathway_name(pid)
        return success_result("kegg", search_term, {
            "source": "pathway_diagram",
            "pathways": [{
                "pathway_id": pid,
                "name": name,
                "image_url": f"https://www.kegg.jp/kegg/pathway/hsa/{pid}.png",
                "pathway_link": f"https://www.kegg.jp/pathway/{pid}",
                "interactive_map": f"https://www.kegg.jp/kegg-bin/show_pathway?{pid}"
            }]
        })
    
    # Search for pathway by name
    result = kegg_tools.search_pathway(clean_term)
    
    if "error" in result:
        return error_result("kegg", search_term, result["error"])
    
    return success_result("kegg", search_term, {
        "source": "pathway_diagram",
        "query": clean_term,
        "pathways": result.get("pathways", [])
    })


def _fetch_pathway_info(search_term: str) -> DatabaseResult:
    """Fetch KEGG pathway information."""
    # Ensure pathway ID has correct format (hsa prefixed)
    pathway_id = search_term
    if not pathway_id.startswith("hsa") and not pathway_id.startswith("map"):
        pathway_id = f"hsa{search_term}"
    
    info = kegg_tools.pathway_info(pathway_id)
    
    if "error" in info:
        return error_result("kegg", search_term, info["error"])
    
    return success_result("kegg", search_term, {
        "source": "pathway",
        "info": info
    })


def _fetch_gene_pathways(search_term: str) -> DatabaseResult:
    """Fetch pathways for a gene."""
    gene_symbol = search_term.upper().strip()
    
    # Look up KEGG gene ID from gene symbol
    kegg_gene_id = kegg_tools._find_kegg_gene_id(gene_symbol)
    
    if not kegg_gene_id:
        return error_result("kegg", search_term,
                           f"Could not find KEGG gene ID for '{gene_symbol}'. Try searching on KEGG directly.")
    
    pathways = kegg_tools.gene_pathways(kegg_gene_id)
    
    if "error" in pathways:
        return error_result("kegg", search_term, pathways["error"])
    
    # Get pathway names and generate map URLs
    pathway_list = []
    for pid in pathways.get("pathways", [])[:10]:
        name = kegg_tools.pathway_name(pid)
        # Generate pathway map URL with gene highlighted
        map_url = f"https://www.kegg.jp/kegg-bin/show_pathway?{pid}+{kegg_gene_id}"
        pathway_list.append({"id": pid, "name": name, "map_url": map_url})
    
    return success_result("kegg", search_term, {
        "source": "gene",
        "gene": gene_symbol,
        "kegg_id": kegg_gene_id,
        "pathways": pathway_list,
        "total_pathways": len(pathways.get("pathways", []))
    })

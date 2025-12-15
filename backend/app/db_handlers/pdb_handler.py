# backend/app/db_handlers/pdb_handler.py
"""
PDB database handler for GeneGPT.
Handles 3D structure queries with AlphaFold fallback.
"""

import re
import requests
from typing import Optional
from ..schemas import DatabaseResult
from ..pdb_tools import PDBTools
from ..gene_map import KNOWN_GENE_MAP
from .base import success_result, error_result

# Initialize PDB tools
pdb_tools = PDBTools()


def fetch_pdb(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch 3D structure data from PDB.
    
    Args:
        search_term: Gene name, UniProt accession, or PDB ID
        sub_command: "mmcif" for structure file, None for viewer
        
    Returns:
        DatabaseResult with structure data
    """
    gene_upper = search_term.upper()
    
    # Handle mmCIF request specifically
    if sub_command == "mmcif":
        return _fetch_mmcif(search_term)
    
    # Check if it's a direct PDB ID (4 characters, starts with digit)
    if len(search_term) == 4 and search_term[0].isdigit():
        return _fetch_by_pdb_id(search_term)
    
    # Try to find PDB via UniProt accession
    accession = KNOWN_GENE_MAP.get(gene_upper)
    if accession:
        result = _fetch_via_uniprot(search_term, gene_upper, accession)
        if result.success:
            return result
    
    # Fallback 1: text search by gene name
    result = _fetch_via_text_search(search_term, gene_upper)
    if result.success:
        return result
    
    # Fallback 2: Use known PDB IDs from hardcoded map
    known_pdb_ids = pdb_tools.get_known_pdb_ids(gene_upper)
    if known_pdb_ids:
        return _fetch_from_known_ids(search_term, gene_upper, known_pdb_ids)
    
    # Fallback 3: Use AlphaFold structure
    if accession:
        return _create_alphafold_result(search_term, gene_upper, accession)
    
    # Final fallback: Try UniProt search for AlphaFold
    return _fetch_alphafold_via_uniprot_search(search_term, gene_upper)


def _fetch_mmcif(search_term: str) -> DatabaseResult:
    """Fetch mmCIF structure file."""
    # Extract PDB ID - it should be 4 characters
    pdb_id = search_term.lower() if len(search_term) == 4 else None
    
    if not pdb_id:
        match = re.search(r'\b(\d[a-zA-Z0-9]{3})\b', search_term)
        if match:
            pdb_id = match.group(1).lower()
    
    if not pdb_id:
        return error_result("pdb", search_term, 
                           "Please provide a valid PDB ID (e.g., 1A1U, 4OBE)")
    
    mmcif_data = pdb_tools.pdb_fetch_mmcif(pdb_id)
    entry = pdb_tools.pdb_fetch_entry(pdb_id)
    
    if "error" in mmcif_data:
        return error_result("pdb", search_term,
                           f"Could not fetch mmCIF for {pdb_id}: {mmcif_data.get('error')}")
    
    # Truncate mmCIF content for display (first 500 lines)
    mmcif_content = mmcif_data.get("mmcif", "")
    mmcif_lines = mmcif_content.split('\n')
    mmcif_preview = '\n'.join(mmcif_lines[:500])
    total_lines = len(mmcif_lines)
    
    return success_result("pdb", search_term, {
        "pdb_id": pdb_id,
        "request_type": "mmcif",
        "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
        "mmcif_preview": mmcif_preview,
        "mmcif_total_lines": total_lines,
        "download_url": f"https://files.rcsb.org/download/{pdb_id}.cif",
        "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
    })


def _fetch_by_pdb_id(pdb_id: str) -> DatabaseResult:
    """Fetch structure by direct PDB ID."""
    pdb_id = pdb_id.lower()
    entry = pdb_tools.pdb_fetch_entry(pdb_id)
    
    if "error" not in entry:
        # Get source organism from main entry
        source_organism = "Unknown"
        
        # Get protein names and details from polymer entity API
        protein_name = ""
        protein_description = ""
        gene_name = ""
        
        entity_info_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/1"
        try:
            entity_resp = requests.get(entity_info_url, timeout=10)
            if entity_resp.status_code == 200:
                entity_data = entity_resp.json()
                
                # Get protein description (e.g., "Cellular tumor antigen p53")
                protein_description = entity_data.get("rcsb_polymer_entity", {}).get("pdbx_description", "")
                
                # Get source organism
                src_orgs = entity_data.get("rcsb_entity_source_organism", [])
                if src_orgs:
                    source_organism = src_orgs[0].get("scientific_name", "Unknown")
                    # Get gene name
                    gene_names = src_orgs[0].get("rcsb_gene_name", [])
                    if gene_names:
                        gene_name = gene_names[0].get("value", "")
        except Exception:
            pass
        
        # Use protein_description as the primary name, fallback to title
        if protein_description:
            protein_name = protein_description
        else:
            protein_name = entry.get("struct", {}).get("title", "Unknown")
        
        # Build comprehensive result with clear protein name
        result_data = {
            "pdb_id": pdb_id.upper(),
            "protein_name": protein_name,
            "gene_name": gene_name if gene_name else "N/A",
            "structure_title": entry.get("struct", {}).get("title", "Unknown"),
            "organism": source_organism,
            "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") else "Unknown",
            "resolution": entry.get("rcsb_entry_info", {}).get("resolution_combined", ["N/A"])[0] if entry.get("rcsb_entry_info") else "N/A",
            "release_date": entry.get("rcsb_accession_info", {}).get("initial_release_date", "Unknown"),
            "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
        }
        
        return success_result("pdb", pdb_id, result_data)
    
    return error_result("pdb", pdb_id, f"PDB entry {pdb_id} not found")


def _fetch_via_uniprot(search_term: str, gene_upper: str, accession: str) -> DatabaseResult:
    """Fetch PDB via UniProt accession."""
    pdb_results = pdb_tools.pdb_search_by_uniprot(accession)
    
    if "error" not in pdb_results and pdb_results.get("pdb_ids"):
        pdb_id = pdb_results["pdb_ids"][0]
        entry = pdb_tools.pdb_fetch_entry(pdb_id)
        
        return success_result("pdb", search_term, {
            "pdb_id": pdb_id,
            "gene_name": gene_upper,
            "uniprot_accession": accession,
            "all_pdb_ids": pdb_results["pdb_ids"][:10],
            "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
            "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") and "error" not in entry else "Unknown",
            "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
        })
    
    return error_result("pdb", search_term, "No PDB via UniProt")


def _fetch_via_text_search(search_term: str, gene_upper: str) -> DatabaseResult:
    """Fetch PDB via text search."""
    text_results = pdb_tools.pdb_search_by_text(search_term)
    
    if "error" not in text_results and text_results.get("pdb_ids"):
        pdb_id = text_results["pdb_ids"][0]
        entry = pdb_tools.pdb_fetch_entry(pdb_id)
        
        return success_result("pdb", search_term, {
            "pdb_id": pdb_id,
            "gene_name": gene_upper,
            "all_pdb_ids": text_results["pdb_ids"][:10],
            "total_structures": text_results.get("total", 0),
            "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
            "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") and "error" not in entry else "Unknown",
            "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
        })
    
    return error_result("pdb", search_term, "No PDB via text search")


def _fetch_from_known_ids(search_term: str, gene_upper: str, known_pdb_ids: list) -> DatabaseResult:
    """Fetch from known PDB IDs cache."""
    pdb_id = known_pdb_ids[0].lower()
    entry = pdb_tools.pdb_fetch_entry(pdb_id)
    
    return success_result("pdb", search_term, {
        "pdb_id": pdb_id,
        "gene_name": gene_upper,
        "all_pdb_ids": known_pdb_ids,
        "title": entry.get("struct", {}).get("title", f"{gene_upper} structure") if "error" not in entry else f"{gene_upper} structure",
        "method": entry.get("exptl", [{}])[0].get("method", "X-ray/Cryo-EM") if entry.get("exptl") and "error" not in entry else "X-ray/Cryo-EM",
        "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}",
        "note": "Using cached PDB ID due to connection issues"
    })


def _create_alphafold_result(search_term: str, gene_upper: str, accession: str) -> DatabaseResult:
    """Create AlphaFold result."""
    return success_result("pdb", search_term, {
        "pdb_id": f"AF-{accession}",
        "gene_name": gene_upper,
        "uniprot_accession": accession,
        "title": f"{gene_upper} - AlphaFold Predicted Structure",
        "method": "AlphaFold AI Prediction",
        "viewer_url": f"https://alphafold.ebi.ac.uk/entry/{accession}",
        "is_alphafold": True
    })


def _fetch_alphafold_via_uniprot_search(search_term: str, gene_upper: str) -> DatabaseResult:
    """Final fallback: search UniProt for AlphaFold structure."""
    try:
        uniprot_search = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene_upper}+AND+organism_id:9606&format=json&size=1"
        r = requests.get(uniprot_search, timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                acc = results[0].get("primaryAccession")
                if acc:
                    return _create_alphafold_result(search_term, gene_upper, acc)
    except Exception:
        pass
    
    return error_result("pdb", search_term,
                       f"No PDB structure found for '{search_term}'. Try searching with a specific PDB ID (e.g., 4OBE for KRAS, 1M17 for EGFR).")

# backend/app/db_handlers/pubchem_handler.py
"""
PubChem database handler for GeneGPT.
"""

import re
from typing import Optional
from ..schemas import DatabaseResult
from ..pubchem_tools import PubChemTools
from .base import success_result, error_result

# Initialize PubChem tools
pubchem_tools = PubChemTools()


def fetch_pubchem(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch compound data from PubChem.
    
    Args:
        search_term: Compound name or CID
        sub_command: "3d" for 3D viewer, None for 2D
        
    Returns:
        DatabaseResult with compound data
    """
    cid = None
    compound_name = search_term.capitalize()
    
    # Check if search_term is a CID (numeric) or contains "CID"
    cid_match = re.match(r'^(?:cid\s*)?(\d+)$', search_term.strip(), re.IGNORECASE)
    
    if cid_match:
        # Direct CID lookup
        cid = int(cid_match.group(1))
        cid_info = pubchem_tools.pubchem_get_by_cid(cid)
        if "error" not in cid_info:
            compound_name = cid_info.get("name", f"Compound {cid}")
        else:
            compound_name = f"Compound {cid}"
    else:
        # Search by name
        search_result = pubchem_tools.pubchem_search(search_term)
        
        if "error" in search_result:
            return error_result("pubchem", search_term, search_result["error"])
        
        cid = search_result.get("cid")
        compound_name = search_term.capitalize()
    
    # Get properties (optional - don't fail if this times out)
    props = pubchem_tools.pubchem_properties(cid)
    props_dict = props if isinstance(props, dict) and "error" not in props else {}
    
    # Determine if 3D view is requested
    show_3d = sub_command == "3d"
    
    compound_data = {
        "query": search_term,
        "cid": cid,
        "name": compound_name,
        "molecular_formula": props_dict.get("MolecularFormula", "Unknown"),
        "molecular_weight": props_dict.get("MolecularWeight", "Unknown"),
        "canonical_smiles": props_dict.get("CanonicalSMILES", ""),
        "inchi_key": props_dict.get("InChIKey", ""),
        "properties": props if "error" not in props else None,
        "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
        "structure_image_url": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=300x300",
        "structure_3d_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=3D-Conformer",
        "show_3d": show_3d
    }
    
    return success_result("pubchem", search_term, compound_data)

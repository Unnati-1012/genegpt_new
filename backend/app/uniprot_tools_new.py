# backend/app/uniprot_tools.py
"""
UniProt API tools for GeneGPT.
Handles protein information retrieval from UniProt.
"""

import re
from typing import List, Optional, Dict, Any

from .utils import safe_get, clean_message, multimodal_response
from .bio_classifier import is_bio_query
from .gene_map import KNOWN_GENE_MAP, get_accession_for_gene, find_gene_in_text
from .iframe_generators import generate_pdb_iframe, generate_alphafold_iframe
from .pdb_tools import PDBTools
from .pubchem_tools import PubChemTools

# Initialize external tools
pdb_tools = PDBTools()
pubchem = PubChemTools()

# Track last used accession for context
LAST_ACCESSION: Optional[str] = None

# Re-export for backward compatibility
__all__ = [
    "route_query",
    "multimodal_response", 
    "KNOWN_GENE_MAP",
    "search_uniprot",
    "get_uniprot_entry",
    "extract_key_info",
    "get_pdb_ids_from_uniprot",
    "resolve_to_accession",
    "is_bio_query",
]


# -------------------------------------------------
# UNIPROT API FUNCTIONS
# -------------------------------------------------
def search_uniprot(query: str, size: int = 5) -> dict:
    """
    Search UniProt for proteins matching a query.
    
    Args:
        query: Search query (gene name, protein name, etc.)
        size: Maximum number of results
        
    Returns:
        Dictionary with 'results' list containing matches
    """
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {"query": query, "size": size, "format": "json"}

    resp = safe_get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("results", []):
        accession = item.get("primaryAccession")
        pname = (
            item.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", "")
        )
        organism = item.get("organism", {}).get("scientificName", "")
        results.append({
            "accession": accession,
            "protein": pname,
            "organism": organism,
        })

    return {"results": results}


def get_uniprot_entry(accession: str) -> dict:
    """
    Fetch a complete UniProt entry by accession.
    
    Args:
        accession: UniProt accession (e.g., 'P04637')
        
    Returns:
        Full UniProt entry as dictionary
    """
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
    resp = safe_get(url)
    resp.raise_for_status()
    return resp.json()


def extract_key_info(entry_json: dict) -> dict:
    """
    Extract key information from a UniProt entry.
    
    Args:
        entry_json: Full UniProt entry
        
    Returns:
        Dictionary with key fields extracted
    """
    protein = (
        entry_json.get("proteinDescription", {})
        .get("recommendedName", {})
        .get("fullName", {})
        .get("value", "N/A")
    )

    genes = entry_json.get("genes", [])
    gene = genes[0].get("geneName", {}).get("value", "N/A") if genes else "N/A"

    organism = entry_json.get("organism", {}).get("scientificName", "N/A")

    seq = entry_json.get("sequence", {}).get("value", "")
    length = entry_json.get("sequence", {}).get("length", len(seq))

    return {
        "accession": entry_json.get("primaryAccession"),
        "protein_name": protein,
        "gene": gene,
        "organism": organism,
        "sequence": seq,
        "sequence_length": length,
    }


def get_pdb_ids_from_uniprot(accession: str) -> List[str]:
    """
    Get PDB IDs associated with a UniProt accession.
    
    Args:
        accession: UniProt accession
        
    Returns:
        List of PDB IDs
    """
    try:
        entry = get_uniprot_entry(accession)
    except Exception:
        return []

    pdbs = [
        ref.get("id").upper()
        for ref in entry.get("dbReferences", [])
        if ref.get("type") == "PDB"
    ]

    # Remove duplicates while preserving order
    seen = set()
    out = []
    for p in pdbs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def resolve_to_accession(text: str) -> Optional[str]:
    """
    Resolve text (gene name, accession, or search term) to UniProt accession.
    
    Args:
        text: Input text to resolve
        
    Returns:
        UniProt accession or None
    """
    raw = clean_message(text)
    
    # Check for direct UniProt accession pattern
    acc_match = re.search(r"\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b", raw)
    if acc_match:
        return acc_match.group(1).upper()
    
    # Check known gene map
    accession = find_gene_in_text(raw)
    if accession:
        return accession
    
    # Try UniProt search
    try:
        result = search_uniprot(raw, size=1)
        if result.get("results"):
            return result["results"][0]["accession"].upper()
    except Exception:
        pass
    
    return None


# -------------------------------------------------
# LEGACY ROUTER (for backward compatibility)
# -------------------------------------------------
def route_query(message: str) -> Optional[dict]:
    """
    Legacy router for handling biological queries.
    Routes to appropriate tool based on message content.
    
    Note: This is kept for backward compatibility.
    New code should use the LLM-based DatabaseRouter instead.
    
    Args:
        message: User message
        
    Returns:
        Response dict with 'reply' and 'html', or None
    """
    global LAST_ACCESSION

    raw = clean_message(message)
    msg = raw.lower()

    if not raw or not is_bio_query(msg):
        return None

    # -------------------------------------------------
    # 1) PubChem CID query
    # -------------------------------------------------
    cid_match = re.search(r"\b(cid|compound)\s*[:=]?\s*([0-9]+)\b", msg)
    if cid_match:
        cid = cid_match.group(2)
        iframe = pubchem.pubchem_iframe(cid)
        return multimodal_response(f"Showing PubChem compound CID {cid}", iframe)

    # -------------------------------------------------
    # 2) PubChem NAME / 3D search
    # -------------------------------------------------
    if ("pubchem" in msg or "chemical" in msg or
        msg.endswith(" 3d") or msg.endswith("3d")):

        chem_name = raw
        for token in ["pubchem", "PubChem", "chemical", "Chemical", "3d", "3D"]:
            chem_name = chem_name.replace(token, "")
        chem_name = chem_name.strip()

        if not chem_name:
            return multimodal_response(
                "Please specify a compound name for PubChem search.",
                None
            )

        result = pubchem.pubchem_search(chem_name)
        if result and "cid" in result:
            iframe = pubchem.pubchem_iframe(result["cid"])
            return multimodal_response(
                f"Showing PubChem 3D structure for {chem_name}",
                iframe,
            )
        else:
            return multimodal_response(
                f"No PubChem record found for '{chem_name}'.",
                None
            )

    # -------------------------------------------------
    # 3) PDB direct information
    # -------------------------------------------------
    if msg.startswith("pdb info ") or msg.startswith("pdb fetch "):
        try:
            pdb_id = raw.split()[-1].upper()
            data = pdb_tools.pdb_fetch_entry(pdb_id)
            return multimodal_response(str(data), None)
        except Exception:
            pass

    # -------------------------------------------------
    # 4) PDB mmCIF
    # -------------------------------------------------
    if msg.startswith("pdb mmcif "):
        try:
            pdb_id = raw.split()[-1].upper()
            mm = pdb_tools.pdb_fetch_mmcif(pdb_id)

            if "error" in mm:
                return multimodal_response(mm["error"], None)

            cif_text = mm.get("mmcif", "")
            html = f"""
            <h3>mmCIF Structure File: {pdb_id}</h3>
            <pre style="max-height:400px; overflow:auto; background:#111; padding:12px;
                        border-radius:8px; white-space:pre-wrap; color:#ddd;">
{cif_text}
            </pre>
            """
            return multimodal_response(f"Loaded mmCIF structure for {pdb_id}", html)

        except Exception as e:
            return multimodal_response(f"Failed to load mmCIF: {str(e)}", None)

    # -------------------------------------------------
    # 5) PDB ID auto-detection
    # -------------------------------------------------
    pdb_match = re.search(r"\b([0-9][A-Za-z0-9]{3})\b", raw)
    if pdb_match:
        pdb_id = pdb_match.group(1).upper()
        if not pdb_id.isdigit():
            iframe = generate_pdb_iframe(pdb_id)
            return multimodal_response(f"Showing PDB structure {pdb_id}", iframe)

    # -------------------------------------------------
    # 6) UniProt detection
    # -------------------------------------------------
    extracted_acc = resolve_to_accession(raw)

    if not extracted_acc:
        return None

    LAST_ACCESSION = extracted_acc

    # -------------------------------------------------
    # 7) Structure lookup
    # -------------------------------------------------
    if any(k in msg for k in ["structure", "pdb", "model", "3d", "visualize", "show"]):
        pdbs = get_pdb_ids_from_uniprot(extracted_acc)
        if pdbs:
            iframe = generate_pdb_iframe(pdbs[0])
            return multimodal_response(f"Showing PDB structure {pdbs[0]}", iframe)

        iframe = generate_alphafold_iframe(extracted_acc)
        return multimodal_response(
            f"Showing AlphaFold model for {extracted_acc}",
            iframe,
        )

    # -------------------------------------------------
    # 8) UniProt summary
    # -------------------------------------------------
    try:
        entry = get_uniprot_entry(extracted_acc)
        info = extract_key_info(entry)
        txt = (
            f"Protein: {info['protein_name']}\n"
            f"Gene: {info['gene']}\n"
            f"Organism: {info['organism']}\n"
            f"Length: {info['sequence_length']}"
        )
        return multimodal_response(txt)
    except Exception:
        return None

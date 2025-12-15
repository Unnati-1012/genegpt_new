# backend/app/db_handlers/uniprot_handler.py
"""
UniProt database handler for GeneGPT.
Handles protein data fetching including isoform sequences.
"""

import re
import requests
from typing import Optional, Tuple
from ..schemas import DatabaseResult
from ..gene_map import KNOWN_GENE_MAP
from ..logger import get_logger
from .base import success_result, error_result

logger = get_logger()


def _parse_isoform_query(search_term: str) -> Tuple[str, Optional[int], bool]:
    """
    Parse search term to extract gene name, isoform number, and whether all isoforms are requested.
    
    Examples:
        "AKT1 isoform 2" -> ("AKT1", 2, False)
        "isoform 2 of AKT1" -> ("AKT1", 2, False)
        "TP53" -> ("TP53", None, False)
        "BRCA1 isoform 1" -> ("BRCA1", 1, False)
        "what are the isoforms of BRCA1" -> ("BRCA1", None, True)
        "BRCA1 all isoforms" -> ("BRCA1", None, True)
        "list all isoforms of AKT1" -> ("AKT1", None, True)
        "are there other isoforms of BRCA1" -> ("BRCA1", None, True)
    
    Returns:
        Tuple of (gene_name, isoform_number, all_isoforms_requested)
    """
    # Common words to exclude (not gene names)
    exclude_words = {'all', 'the', 'of', 'for', 'and', 'or', 'are', 'is', 'what', 'which', 
                     'show', 'list', 'get', 'display', 'other', 'more', 'different', 
                     'multiple', 'any', 'there', 'does', 'do', 'have', 'has', 'how', 'many',
                     'isoform', 'isoforms', 'protein', 'gene', 'sequence'}
    
    # First, find all potential gene names in the query (uppercase words 2-10 chars)
    gene_candidates = re.findall(r'\b([A-Za-z][A-Za-z0-9]{1,9})\b', search_term)
    gene_candidates = [g.upper() for g in gene_candidates if g.lower() not in exclude_words and len(g) >= 2]
    
    # Check if this query contains "isoform" word
    has_isoform_word = 'isoform' in search_term.lower()
    
    # Check for specific isoform number (like "isoform 2" or "isoform2")
    isoform_num_match = re.search(r'isoform\s*(\d+)', search_term, re.IGNORECASE)
    specific_isoform_num = int(isoform_num_match.group(1)) if isoform_num_match else None
    
    # Determine gene name
    gene_name = gene_candidates[0] if gene_candidates else search_term.upper()
    
    # If we have "isoform" word but NO specific number, user wants ALL isoforms
    if has_isoform_word and specific_isoform_num is None:
        logger.debug(f"Parsed isoform query: gene={gene_name}, all_isoforms=True")
        return gene_name, None, True
    
    # If we have a specific isoform number
    if specific_isoform_num is not None:
        logger.debug(f"Parsed isoform query: gene={gene_name}, isoform={specific_isoform_num}")
        return gene_name, specific_isoform_num, False
    
    # No isoform-related query, just return the gene name
    logger.debug(f"Parsed query (no isoform): gene={gene_name}")
    return gene_name, None, False


def fetch_isoform_fasta(accession: str, isoform_id: str) -> Optional[str]:
    """
    Fetch FASTA sequence for a specific isoform from UniProt.
    
    Args:
        accession: Base UniProt accession (e.g., "P31749")
        isoform_id: Full isoform ID (e.g., "P31749-2")
        
    Returns:
        FASTA sequence string or None if not found
    """
    url = f"https://rest.uniprot.org/uniprotkb/{isoform_id}.fasta"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        logger.debug(f"Failed to fetch isoform FASTA: {e}")
    return None


def fetch_uniprot(search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
    """
    Fetch protein data from UniProt, including features like motifs and domains.
    Supports isoform-specific queries like "AKT1 isoform 2".
    Also handles general isoform queries like "what are the isoforms of BRCA1".
    
    Args:
        search_term: Gene symbol or UniProt accession (can include "isoform X")
        sub_command: Optional sub-command (not used for UniProt)
        
    Returns:
        DatabaseResult with protein data
    """
    # Parse for isoform-specific query
    gene_name, requested_isoform, all_isoforms_requested = _parse_isoform_query(search_term)
    
    # Check if it's a known gene symbol
    accession = KNOWN_GENE_MAP.get(gene_name.upper())
    
    if not accession:
        # Try to search UniProt
        search_url = f"https://rest.uniprot.org/uniprotkb/search?query={gene_name}+AND+organism_id:9606&format=json&size=1"
        try:
            r = requests.get(search_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    accession = results[0].get("primaryAccession")
        except Exception as e:
            logger.debug(f"UniProt search fallback: {e}")
    
    if not accession:
        return error_result("uniprot", search_term, 
                           f"Could not find UniProt entry for '{gene_name}'")
    
    # Fetch full entry
    entry_url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
    try:
        r = requests.get(entry_url, timeout=10)
        if r.status_code == 200:
            entry_data = r.json()
            protein_data = _extract_protein_data(entry_data, gene_name, accession)
            
            # If user requested a specific isoform, fetch its sequence
            if requested_isoform is not None:
                protein_data = _add_specific_isoform_data(
                    protein_data, accession, requested_isoform
                )
            
            # If user asked about ALL isoforms, fetch all sequences
            if all_isoforms_requested:
                protein_data = _add_all_isoforms_data(protein_data, accession)
            
            return success_result("uniprot", search_term, protein_data)
        else:
            return error_result("uniprot", search_term,
                               f"Failed to fetch UniProt entry for {accession}")
    except Exception as e:
        return error_result("uniprot", search_term, str(e))


def _parse_fasta(fasta_text: str) -> Tuple[str, str, int]:
    """
    Parse FASTA format to extract header and sequence.
    
    Returns:
        Tuple of (header, sequence, length)
    """
    if not fasta_text:
        return "", "", 0
    
    lines = fasta_text.strip().split('\n')
    header = lines[0] if lines else ""
    sequence = ''.join(lines[1:]) if len(lines) > 1 else ""
    return header, sequence, len(sequence)


def _add_specific_isoform_data(protein_data: dict, accession: str, isoform_num: int) -> dict:
    """
    Add specific isoform sequence data when user requests a particular isoform.
    Fetches the actual FASTA sequence from UniProt.
    """
    isoforms = protein_data.get("isoforms", [])
    gene_name = protein_data.get("gene_name", "Unknown")
    
    # Find the requested isoform (1-indexed for user, 0-indexed in array)
    if isoform_num <= 0:
        protein_data["requested_isoform_error"] = f"Invalid isoform number: {isoform_num}"
        return protein_data
    
    if isoform_num > len(isoforms):
        protein_data["requested_isoform_error"] = (
            f"Isoform {isoform_num} not found. {gene_name} has {len(isoforms)} isoforms."
        )
        return protein_data
    
    # Get the specific isoform (user asks for isoform 2, we get index 1)
    target_isoform = isoforms[isoform_num - 1]
    isoform_ids = target_isoform.get("ids", [])
    
    if isoform_ids:
        isoform_id = isoform_ids[0]  # e.g., "P31749-2"
        
        # Fetch the actual FASTA sequence
        fasta_raw = fetch_isoform_fasta(accession, isoform_id)
        header, sequence, seq_length = _parse_fasta(fasta_raw)
        
        protein_data["requested_isoform"] = {
            "number": isoform_num,
            "name": target_isoform.get("name", f"Isoform {isoform_num}"),
            "uniprot_id": isoform_id,
            "synonyms": target_isoform.get("synonyms", []),
            "sequence_status": target_isoform.get("sequence_status", "Displayed"),
            "note": target_isoform.get("note", ""),
            "sequence": sequence,
            "sequence_length": seq_length,
            "fasta_header": header,
            "fasta_url": f"https://rest.uniprot.org/uniprotkb/{isoform_id}.fasta",
            "uniprot_url": f"https://www.uniprot.org/uniprotkb/{isoform_id}",
            "alphafold_url": f"https://alphafold.ebi.ac.uk/entry/{isoform_id}"
        }
    else:
        protein_data["requested_isoform"] = {
            "number": isoform_num,
            "name": target_isoform.get("name", f"Isoform {isoform_num}"),
            "error": "No UniProt ID available for this isoform"
        }
    
    return protein_data


def _add_all_isoforms_data(protein_data: dict, accession: str) -> dict:
    """
    Fetch ALL isoform sequences when user asks about all isoforms.
    This populates 'all_isoforms_data' with complete sequence information for each.
    """
    isoforms = protein_data.get("isoforms", [])
    gene_name = protein_data.get("gene_name", "Unknown")
    
    logger.info(f"_add_all_isoforms_data called for {gene_name} ({accession}), found {len(isoforms)} isoforms in data")
    
    # If no isoforms in extracted data, try to fetch them directly
    if not isoforms:
        logger.info(f"No isoforms in extracted data, trying to fetch directly for {accession}")
        isoforms = _fetch_isoforms_from_uniprot(accession)
        protein_data["isoforms"] = isoforms
        protein_data["isoform_count"] = len(isoforms)
    
    if not isoforms:
        protein_data["all_isoforms_data"] = []
        protein_data["all_isoforms_error"] = f"No isoforms found for {gene_name}"
        return protein_data
    
    all_isoforms_data = []
    
    for idx, iso in enumerate(isoforms, 1):
        iso_ids = iso.get("ids", [])
        iso_id = iso_ids[0] if iso_ids else None
        iso_name = iso.get("name", f"Isoform {idx}")
        
        logger.debug(f"Processing isoform {idx}: {iso_name} ({iso_id})")
        
        isoform_entry = {
            "number": idx,
            "name": iso_name,
            "uniprot_id": iso_id or "N/A",
            "synonyms": iso.get("synonyms", []),
            "sequence_status": iso.get("sequence_status", "Unknown"),
            "note": iso.get("note", ""),
            "sequence": "",
            "sequence_length": 0,
        }
        
        # Fetch the actual FASTA sequence for each isoform
        if iso_id:
            fasta_raw = fetch_isoform_fasta(accession, iso_id)
            header, sequence, seq_length = _parse_fasta(fasta_raw)
            isoform_entry["sequence"] = sequence
            isoform_entry["sequence_length"] = seq_length
            isoform_entry["fasta_header"] = header
            logger.debug(f"Fetched sequence for {iso_id}: {seq_length} aa")
        
        all_isoforms_data.append(isoform_entry)
    
    protein_data["all_isoforms_data"] = all_isoforms_data
    logger.info(f"Added {len(all_isoforms_data)} isoforms to response")
    return protein_data


def _fetch_isoforms_from_uniprot(accession: str) -> list:
    """
    Directly fetch isoform information from UniProt API.
    This is a fallback when isoforms aren't found in the main entry.
    """
    try:
        url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        
        entry_data = r.json()
        isoforms = []
        
        for comment in entry_data.get("comments", []):
            if comment.get("commentType") == "ALTERNATIVE PRODUCTS":
                logger.info(f"Found ALTERNATIVE PRODUCTS section for {accession}")
                
                for isoform in comment.get("isoforms", []):
                    # Get isoform name
                    isoform_name = isoform.get("name", {})
                    if isinstance(isoform_name, dict):
                        name = isoform_name.get("value", "Unknown")
                    elif isinstance(isoform_name, list) and isoform_name:
                        name = isoform_name[0].get("value", "Unknown") if isinstance(isoform_name[0], dict) else str(isoform_name[0])
                    else:
                        name = str(isoform_name) if isoform_name else "Unknown"
                    
                    # Get synonyms
                    synonyms = []
                    for syn in isoform.get("synonyms", []):
                        if isinstance(syn, dict):
                            synonyms.append(syn.get("value", ""))
                        else:
                            synonyms.append(str(syn))
                    
                    isoform_info = {
                        "name": name,
                        "synonyms": synonyms,
                        "ids": isoform.get("isoformIds", []),
                        "sequence_status": isoform.get("isoformSequenceStatus", "Displayed"),
                        "note": "",
                    }
                    
                    # Get note
                    notes = isoform.get("note", {})
                    if isinstance(notes, dict):
                        texts = notes.get("texts", [])
                        if texts:
                            isoform_info["note"] = texts[0].get("value", "") if isinstance(texts[0], dict) else str(texts[0])
                    
                    isoforms.append(isoform_info)
                    logger.info(f"Found isoform: {name} ({isoform.get('isoformIds', [])})")
        
        return isoforms
    except Exception as e:
        logger.error(f"Error fetching isoforms for {accession}: {e}")
        return []


def _extract_protein_data(entry_data: dict, search_term: str, accession: str) -> dict:
    """Extract key information from UniProt entry."""
    protein_data = {
        "accession": accession,
        "gene_name": search_term.upper(),
        "protein_name": entry_data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "Unknown"),
        "organism": entry_data.get("organism", {}).get("scientificName", "Unknown"),
        "function": None,
        "sequence": entry_data.get("sequence", {}).get("value", ""),
        "sequence_length": entry_data.get("sequence", {}).get("length", 0),
        "molecular_weight": entry_data.get("sequence", {}).get("molWeight", 0),
        "alphafold_url": f"https://alphafold.ebi.ac.uk/entry/{accession}",
        "motifs": [],
        "domains": [],
        "regions": [],
        "binding_sites": [],
        "active_sites": [],
        "modifications": [],
    }
    
    # Extract function from comments
    for comment in entry_data.get("comments", []):
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts", [])
            if texts:
                protein_data["function"] = texts[0].get("value", "")
                break
    
    # Log all feature types for debugging
    all_feature_types = set()
    for feature in entry_data.get("features", []):
        all_feature_types.add(feature.get("type", ""))
    logger.debug(f"Feature types in {accession}: {all_feature_types}")
    
    # Extract features (motifs, domains, etc.)
    for feature in entry_data.get("features", []):
        feature_type = feature.get("type", "")
        description = feature.get("description", "")
        location = feature.get("location", {})
        start = location.get("start", {}).get("value", "?")
        end = location.get("end", {}).get("value", "?")
        
        feature_info = {
            "description": description or feature_type,
            "start": start,
            "end": end,
        }
        
        # Handle motifs
        if feature_type in ["Motif", "Short sequence motif"]:
            protein_data["motifs"].append(feature_info)
        # Handle domains - check multiple possible names
        elif feature_type in ["Domain", "Topological domain", "Transmembrane", "Zinc finger", 
                              "DNA binding", "DNA-binding region", "Repeat", "Compositional bias"]:
            protein_data["domains"].append(feature_info)
        # Handle regions
        elif feature_type in ["Region", "Region of interest", "Coiled coil", "Disordered"]:
            protein_data["regions"].append(feature_info)
        elif feature_type == "Binding site":
            protein_data["binding_sites"].append(feature_info)
        elif feature_type == "Active site":
            protein_data["active_sites"].append(feature_info)
        elif feature_type in ["Modified residue", "Glycosylation", "Lipidation", "Cross-link", 
                              "Disulfide bond", "Phosphorylation"]:
            protein_data["modifications"].append({
                "type": feature_type,
                "description": description,
                "position": start
            })
    
    # Extract isoform information
    isoforms = []
    for comment in entry_data.get("comments", []):
        if comment.get("commentType") == "ALTERNATIVE PRODUCTS":
            logger.info(f"Found ALTERNATIVE PRODUCTS in _extract_protein_data for {accession}")
            # Get events (e.g., "Alternative splicing")
            events = [e.get("value", "") for e in comment.get("events", [])]
            
            for isoform in comment.get("isoforms", []):
                # Get isoform name - can be in different formats
                isoform_name = isoform.get("name", {})
                if isinstance(isoform_name, dict):
                    name = isoform_name.get("value", "Unknown")
                elif isinstance(isoform_name, list) and isoform_name:
                    name = isoform_name[0].get("value", "Unknown") if isinstance(isoform_name[0], dict) else str(isoform_name[0])
                else:
                    name = str(isoform_name) if isoform_name else "Unknown"
                
                # Get synonyms if any
                synonyms = []
                syn_list = isoform.get("synonyms", [])
                for syn in syn_list:
                    if isinstance(syn, dict):
                        synonyms.append(syn.get("value", ""))
                    else:
                        synonyms.append(str(syn))
                
                isoform_info = {
                    "name": name,
                    "synonyms": synonyms,
                    "ids": isoform.get("isoformIds", []),
                    "sequence_status": isoform.get("isoformSequenceStatus", "Displayed"),
                    "note": "",
                }
                
                # Get note/description if available
                notes = isoform.get("note", {})
                if isinstance(notes, dict):
                    texts = notes.get("texts", [])
                    if texts:
                        isoform_info["note"] = texts[0].get("value", "") if isinstance(texts[0], dict) else str(texts[0])
                
                isoforms.append(isoform_info)
                logger.info(f"Extracted isoform: {name} with IDs: {isoform.get('isoformIds', [])}")
            
            protein_data["alternative_products_events"] = events
    
    protein_data["isoforms"] = isoforms
    protein_data["isoform_count"] = len(isoforms)
    logger.info(f"Total isoforms extracted for {accession}: {len(isoforms)}")
    
    # If user asked about a specific isoform, add a note
    if isoforms:
        protein_data["isoform_summary"] = f"{protein_data['gene_name']} has {len(isoforms)} known isoforms: " + \
            ", ".join([f"{iso['name']} ({iso['ids'][0] if iso['ids'] else 'no ID'})" for iso in isoforms])
    
    return protein_data

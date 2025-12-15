# backend/app/bio_classifier.py
"""
Biological query intent classifier for GeneGPT.
Determines if a user message is a biology-related query.
"""

import re


# Keywords that indicate a biological/medical query
BIO_KEYWORDS = [
    "protein",
    "gene",
    "sequence",
    "uniprot",
    "pdb",
    "structure",
    "3d",
    "model",
    "visualize",
    "enzyme",
    "domain",
    "residue",
    "alpha fold",
    "alphafold",
    "pubchem",
    "chemical",
    "compound",
    "clinvar",
    "variant",
    "mutation",
    "pathway",
    "kegg",
    "ensembl",
    "ncbi",
    "pubmed",
    "drug",
    "molecule",
    "amino acid",
    "nucleotide",
    "dna",
    "rna",
    "mrna",
    "transcription",
    "expression",
]


def is_bio_query(msg: str) -> bool:
    """
    Determine if a message is a biology-related query.
    
    Args:
        msg: User message to classify
        
    Returns:
        True if the message appears to be a biology query
    """
    if not msg or len(msg.strip()) < 4:
        return False

    lowered = msg.lower()
    
    # Check for biology keywords
    if any(k in lowered for k in BIO_KEYWORDS):
        return True

    # Check for PDB ID pattern (e.g., 1ABC)
    if re.search(r"\b[0-9][A-Za-z0-9]{3}\b", msg):
        return True

    # Check for UniProt accession pattern (e.g., P12345)
    if re.search(r"\b[A-Z][0-9][A-Z0-9]{3}[0-9]\b", msg):
        return True

    return False


def detect_query_intent(msg: str) -> dict:
    """
    Detect the intent of a biology query.
    
    Args:
        msg: User message
        
    Returns:
        Dictionary with detected intents
    """
    lowered = msg.lower()
    
    return {
        "wants_structure": any(k in lowered for k in ["structure", "3d", "pdb", "model", "visualize", "show"]),
        "wants_sequence": any(k in lowered for k in ["sequence", "fasta", "amino acid"]),
        "wants_function": any(k in lowered for k in ["function", "role", "what does"]),
        "wants_interactions": any(k in lowered for k in ["interact", "partner", "binding", "network"]),
        "wants_variants": any(k in lowered for k in ["variant", "mutation", "snp"]),
        "wants_pathways": any(k in lowered for k in ["pathway", "kegg", "metabolic"]),
        "wants_chemical": any(k in lowered for k in ["pubchem", "chemical", "compound", "drug", "molecule"]),
    }

"""
uniprot_tools.py

Hybrid Intelligent Router for GeneGPT
- Smart: conversations handled by LLM
- Router activates only for REAL biology queries
- Supports UniProt + PDB + AlphaFold + PubChem
"""

import requests
import re
from typing import List, Optional

# NEW: PDB tools
from .pdb_tools import PDBTools
pdb_tools = PDBTools()

# NEW: PubChem tools
from .pubchem_tools import PubChemTools
pubchem = PubChemTools()

LAST_ACCESSION: Optional[str] = None


# -------------------------------------------------
# GENE SYMBOL → UNIPROT ACCESSION MAP
# -------------------------------------------------
KNOWN_GENE_MAP = {
    "TP53": "P04637",
    "BRCA1": "P38398",
    "EGFR": "P00533",
    "KRAS": "P01116",
    "MYC": "P01106",
    "MDM2": "Q00987",
    "AKT1": "P31749",
}


# -------------------------------------------------
# UTILITIES
# -------------------------------------------------
def _safe_get(
    url: str,
    method: str = "get",
    timeout: int = 8,
    allow_redirects: bool = True,
    params: dict = None,
):
    headers = {"User-Agent": "Mozilla/5.0 (GeneGPT Bot)"}
    if method.lower() == "head":
        return requests.head(
            url, headers=headers, timeout=timeout, allow_redirects=allow_redirects
        )
    return requests.get(
        url,
        headers=headers,
        timeout=timeout,
        allow_redirects=allow_redirects,
        params=params,
    )


def clean_message(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\"\'\%\{\}\|\^\~\[\]\<\>]", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


# -------------------------------------------------
# BIO INTENT CLASSIFIER
# -------------------------------------------------
def is_bio_query(msg: str) -> bool:
    if not msg or len(msg.strip()) < 4:
        return False

    bio_keywords = [
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

    ]

    lowered = msg.lower()
    if any(k in lowered for k in bio_keywords):
        return True

    if re.search(r"\b[0-9][A-Za-z0-9]{3}\b", msg):
        return True

    if re.search(r"\b[A-Z][0-9][A-Z0-9]{3}[0-9]\b", msg):
        return True

    return False


# -------------------------------------------------
# UNIPROT HELPERS
# -------------------------------------------------
def search_uniprot(query: str, size: int = 5) -> dict:
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {"query": query, "size": size, "format": "json"}

    resp = _safe_get(url, params=params)
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
        results.append(
            {
                "accession": accession,
                "protein": pname,
                "organism": organism,
            }
        )

    return {"results": results}


def get_uniprot_entry(accession: str) -> dict:
    url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
    resp = _safe_get(url)
    resp.raise_for_status()
    return resp.json()


def extract_key_info(entry_json: dict) -> dict:
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
    try:
        entry = get_uniprot_entry(accession)
    except Exception:
        return []

    pdbs = [
        ref.get("id").upper()
        for ref in entry.get("dbReferences", [])
        if ref.get("type") == "PDB"
    ]

    seen = set()
    out = []
    for p in pdbs:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# -------------------------------------------------
# IFRAME GENERATORS
# -------------------------------------------------
def generate_pdb_iframe(pdb_id: str) -> str:
    return f"""
    <iframe
        style="width:100%; height:520px; border:none; background:black;"
        src="https://www.rcsb.org/3d-view/{pdb_id.upper()}">
    </iframe>
    """


def generate_alphafold_iframe(accession: str) -> str:
    return f"""
    <iframe
        style="width:100%; height:520px; border:none; background:black;"
        src="https://alphafold.ebi.ac.uk/entry/{accession.upper()}">
    </iframe>
    """


# -------------------------------------------------
# RESPONSE WRAPPER
# -------------------------------------------------
def multimodal_response(text=None, html=None):
    return {"reply": text, "html": html}


# -------------------------------------------------
# MAIN ROUTER
# -------------------------------------------------
def route_query(message: str):

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
    # -------------------------------------------------
    # 2) PubChem NAME / 3D search
    #    Handles:
    #      - "pubchem caffeine"
    #      - "PubChem caffeine 3D"
    #      - "caffeine 3d"
    #      - "chemical aspirin 3d"
    # -------------------------------------------------
    if ("pubchem" in msg or "chemical" in msg or
        msg.endswith(" 3d") or msg.endswith("3d")):

        # Start from the original cleaned text
        chem_name = raw

        # Strip helper words (both cases) and "3d"/"3D"
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
    # ✅ FIXED: PDB mmCIF SECTION
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
    # 4) PDB ID auto-detection
    # -------------------------------------------------
    pdb_match = re.search(r"\b([0-9][A-Za-z0-9]{3})\b", raw)
    if pdb_match:
        pdb_id = pdb_match.group(1).upper()

        if not pdb_id.isdigit():
            iframe = generate_pdb_iframe(pdb_id)
            return multimodal_response(f"Showing PDB structure {pdb_id}", iframe)

    # -------------------------------------------------
    # 5) UniProt detection
    # -------------------------------------------------
    acc_match = re.search(r"\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b", raw)
    extracted_acc = acc_match.group(1).upper() if acc_match else None

    token = raw.upper().strip()
    if not extracted_acc and token in KNOWN_GENE_MAP:
        extracted_acc = KNOWN_GENE_MAP[token]

    if not extracted_acc:
        for word in raw.upper().split():
            if word in KNOWN_GENE_MAP:
                extracted_acc = KNOWN_GENE_MAP[word]
                break

    if not extracted_acc:
        try:
            result = search_uniprot(raw, size=1)
            if result.get("results"):
                extracted_acc = result["results"][0]["accession"].upper()
        except Exception:
            extracted_acc = None

    if not extracted_acc:
        return None

    LAST_ACCESSION = extracted_acc

    # -------------------------------------------------
    # 6) Structure lookup
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
    # 7) UniProt summary
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

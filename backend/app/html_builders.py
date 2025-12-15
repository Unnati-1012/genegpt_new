# backend/app/html_builders.py
"""
HTML building functions for different database results.
Each function generates formatted HTML for display in the frontend.
"""

from typing import Any


def build_html_for_result(db_type: str, data: dict, query: str = "") -> str | None:
    """
    Build optional HTML display for database results.
    Only shows HTML when it adds value beyond the text response.
    
    Args:
        db_type: The database that was queried
        data: The data returned from the database
        query: The original user query (to determine relevance)
        
    Returns:
        HTML string or None if no HTML needed
    """
    query_lower = query.lower() if query else ""
    
    # Determine what the user is asking about
    wants_sequence = any(w in query_lower for w in ["sequence", "amino acid", "fasta"])
    wants_structure = any(w in query_lower for w in ["structure", "3d", "fold", "pdb", "visualize"])
    wants_interactions = any(w in query_lower for w in ["interact", "partner", "binding", "network"])
    wants_variants = any(w in query_lower for w in ["variant", "mutation", "snp", "clinvar"])
    wants_pathways = any(w in query_lower for w in ["pathway", "kegg", "metabolic"])
    wants_domains = any(w in query_lower for w in ["domain", "region"])
    wants_motifs = any(w in query_lower for w in ["motif"])
    wants_images = any(w in query_lower for w in ["image", "picture", "show me", "photo"])
    wants_papers = any(w in query_lower for w in ["paper", "pubmed", "publication", "research", "study"])
    
    # For general info queries, text response is usually sufficient
    is_general_info = any(w in query_lower for w in ["isoform", "tell me about", "what are", "describe", "explain", "overview"])
    
    # Route to appropriate builder
    if db_type == "string":
        return _build_string_html(data, query, wants_interactions)
    elif db_type == "clinvar":
        return _build_clinvar_html(data, query, wants_variants)
    elif db_type == "image_search":
        return _build_image_search_html(data, query)
    elif db_type == "pdb":
        return _build_pdb_html(data, query, wants_structure)
    elif db_type == "uniprot":
        return _build_uniprot_html(data, query, wants_sequence, wants_structure, 
                                   wants_domains, wants_motifs, is_general_info)
    elif db_type == "ncbi":
        return _build_ncbi_html(data, query, wants_papers)
    elif db_type == "kegg":
        return _build_kegg_html(data, query, wants_pathways)
    elif db_type == "ensembl":
        return _build_ensembl_html(data, query)
    elif db_type == "pubchem":
        return _build_pubchem_html(data, query)
    
    return None


# -------------------------------------------------
# STRING Database HTML Builder
# -------------------------------------------------
def _build_string_html(data: Any, query: str, wants_interactions: bool) -> str | None:
    """Build HTML for STRING database results."""
    if not data or not data.get("interactions"):
        return None
    
    # Only show STRING HTML if user asked about interactions
    if not wants_interactions:
        return None
    
    interactions = data["interactions"]
    rows = ""
    for item in interactions[:10]:
        partner = item.get("partner", "")
        score = item.get("score", 0)
        rows += f"<tr><td style='padding:6px;border:1px solid #555;'>{partner}</td><td style='padding:6px;border:1px solid #555;'>{score}</td></tr>"
    
    network_img = data.get("network_image_url", "")
    html = f"""
    <h3>STRING Interactions for <b>{data.get('query', '')}</b></h3>
    <table style='width:100%; border-collapse:collapse; margin-top:10px;'>
        <tr style='background:#444;'>
            <th style='padding:8px; border:1px solid #666;'>Partner</th>
            <th style='padding:8px; border:1px solid #666;'>Score</th>
        </tr>
        {rows}
    </table>
    <br><h3>Network Image</h3>
    <img src="{network_img}" alt="STRING network" style="width:100%; border-radius:10px; border:1px solid #555;">
    """
    return html


# -------------------------------------------------
# ClinVar HTML Builder
# -------------------------------------------------
def _build_clinvar_html(data: Any, query: str, wants_variants: bool) -> str | None:
    """Build HTML for ClinVar results."""
    if not data or not data.get("sample_variants"):
        return None
    
    # Only show ClinVar HTML if user asked about variants
    if not wants_variants:
        return None
    
    variants = data["sample_variants"]
    rows = ""
    for v in variants:
        vid = v.get("id", "")
        sig = v.get("clinical_significance", "Unknown")
        conds = ", ".join(v.get("conditions", [])) or "—"
        rows += f"<tr><td style='padding:6px;border:1px solid #555;'>{vid}</td><td style='padding:6px;border:1px solid #555;'>{sig}</td><td style='padding:6px;border:1px solid #555;'>{conds}</td></tr>"
    
    html = f"""
    <h3>ClinVar Variants for <b>{data.get('gene', '')}</b></h3>
    <p>Total: {data.get('total_variants', 0)} variants</p>
    <table style='width:100%; border-collapse:collapse; margin-top:8px;'>
        <tr style='background:#333;color:#fff;'>
            <th style='padding:6px;border:1px solid #555;'>ID</th>
            <th style='padding:6px;border:1px solid #555;'>Significance</th>
            <th style='padding:6px;border:1px solid #555;'>Conditions</th>
        </tr>
        {rows}
    </table>
    """
    return html


# -------------------------------------------------
# Image Search HTML Builder
# -------------------------------------------------
def _build_image_search_html(data: Any, query: str) -> str | None:
    """Build HTML for Google Image Search results."""
    if not data or not data.get("results"):
        return None
    
    results = data["results"]
    items = ""
    for i, r in enumerate(results, 1):
        items += f"<li style='margin-bottom:8px;'><a href='{r.get('link', '')}' target='_blank'>{i}. {r.get('title', 'Image')}</a></li>"
    
    html = f"<p>Image results:</p><ol style='padding-left:20px;'>{items}</ol>"
    return html


# -------------------------------------------------
# PDB HTML Builder (with AlphaFold fallback)
# -------------------------------------------------
def _build_pdb_html(data: Any, query: str, wants_structure: bool) -> str | None:
    """Build HTML for PDB results, including 3D structure viewer."""
    if not data or not data.get("pdb_id"):
        return None
    
    pdb_id = data["pdb_id"]
    title = data.get("title", "Unknown structure")
    request_type = data.get("request_type", "view")
    is_alphafold = data.get("is_alphafold", False)
    
    # Handle mmCIF content display
    if request_type == "mmcif" and data.get("mmcif_preview"):
        mmcif_preview = data.get("mmcif_preview", "")
        total_lines = data.get("mmcif_total_lines", 0)
        download_url = data.get("download_url", "")
        viewer_url = data.get("viewer_url", "")
        
        # Escape HTML entities in mmCIF content
        mmcif_escaped = mmcif_preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        html = f"""
        <h3>📄 mmCIF Structure File: {pdb_id.upper()}</h3>
        <p><b>{title}</b></p>
        <p style='color:#888; font-size:0.9em;'>Showing first 500 of {total_lines} lines</p>
        
        <details style='margin-top:10px; background:#1a1a2e; padding:12px; border-radius:8px;'>
            <summary style='cursor:pointer; color:#4ecdc4; font-weight:bold;'>📂 Click to expand mmCIF content</summary>
            <pre style='margin-top:10px; font-family:monospace; font-size:11px; line-height:1.4; max-height:500px; overflow-y:auto; white-space:pre-wrap; word-break:break-all; color:#ddd;'>{mmcif_escaped}</pre>
        </details>
        
        <p style='margin-top:12px;'>
            <a href="{download_url}" target="_blank" style='color:#4ecdc4; margin-right:15px;'>⬇️ Download full mmCIF file</a>
            <a href="{viewer_url}" target="_blank" style='color:#4ecdc4;'>🔬 View 3D structure</a>
        </p>
        """
        return html
    
    # Handle AlphaFold structures
    if is_alphafold:
        accession = data.get("uniprot_accession", "")
        gene_name = data.get("gene_name", "")
        viewer_url = data.get("viewer_url", f"https://alphafold.ebi.ac.uk/entry/{accession}")
        
        html = f"""
        <h3>🔬 {gene_name} - AlphaFold Predicted Structure</h3>
        <p><b>{title}</b></p>
        <p style='color:#888; font-size:0.9em;'>UniProt: {accession} | Method: AlphaFold AI Prediction</p>
        
        <div style='margin-top:15px; background:#000; border-radius:10px; overflow:hidden;'>
            <iframe src="{viewer_url}" 
                    style="width:100%; height:500px; border:none;">
            </iframe>
        </div>
        <p style='color:#888; font-size:0.85em; text-align:center; margin-top:5px;'>
            AlphaFold predicted structure • <a href="{viewer_url}" target="_blank" style='color:#4ecdc4;'>Open in new tab</a>
        </p>
        
        <p style='margin-top:10px;'>
            <a href="https://www.uniprot.org/uniprotkb/{accession}" target="_blank" style='color:#4ecdc4;'>🔗 View on UniProt</a>
        </p>
        """
        return html
    
    # Show PDB structure viewer
    method = data.get("method", "")
    gene_name = data.get("gene_name", data.get("search_query", ""))
    all_pdb_ids = data.get("all_pdb_ids", [])
    total = data.get("total_structures", len(all_pdb_ids))
    
    # Build list of other available structures if there are multiple
    other_structures = ""
    if len(all_pdb_ids) > 1:
        other_items = "".join([
            f"<a href='https://www.rcsb.org/structure/{pid}' target='_blank' style='margin-right:8px; color:#4ecdc4;'>{pid.upper()}</a>"
            for pid in all_pdb_ids[1:6]
        ])
        other_structures = f"""
        <details style='margin-top:10px;'>
            <summary style='cursor:pointer; color:#4ecdc4;'>📚 Other available structures ({total} total)</summary>
            <p style='margin-top:8px;'>{other_items}</p>
        </details>
        """
    
    html = f"""
    <h3>🔬 PDB Structure: {pdb_id.upper()}</h3>
    <p><b>{title}</b></p>
    <p style='color:#888; font-size:0.9em;'>{f"Gene: {gene_name} | " if gene_name else ""}Method: {method}</p>
    
    <iframe src="https://www.rcsb.org/3d-view/{pdb_id}" 
            style="width:100%; height:500px; border:none; border-radius:10px; margin-top:10px;">
    </iframe>
    
    {other_structures}
    
    <p style='margin-top:10px;'>
        <a href="https://www.rcsb.org/structure/{pdb_id}" target="_blank" style='color:#4ecdc4;'>🔗 View on RCSB PDB</a>
    </p>
    """
    return html


# -------------------------------------------------
# UniProt HTML Builder
# -------------------------------------------------
def _build_uniprot_html(data: Any, query: str, wants_sequence: bool, 
                        wants_structure: bool, wants_domains: bool, 
                        wants_motifs: bool, is_general_info: bool) -> str | None:
    """Build HTML for UniProt results."""
    if not data or not data.get("accession"):
        return None
    
    # For general info queries, the text answer is sufficient - no HTML card needed
    if is_general_info and not (wants_sequence or wants_structure or wants_domains or wants_motifs):
        return None
    
    accession = data.get("accession", "")
    gene_name = data.get("gene_name", "Unknown")
    protein_name = data.get("protein_name", "Unknown")
    sequence = data.get("sequence", "")
    seq_length = data.get("sequence_length", 0)
    alphafold_url = data.get("alphafold_url", "")
    
    # If user wants sequence, show just the sequence
    if wants_sequence and sequence:
        formatted_seq = "<br>".join([sequence[i:i+60] for i in range(0, len(sequence), 60)])
        html = f"""
        <h3>🧬 {gene_name} Sequence ({seq_length} amino acids)</h3>
        <p><b>UniProt:</b> {accession} | <b>Protein:</b> {protein_name}</p>
        <div style='margin-top:10px; padding:12px; background:#1a1a2e; border-radius:8px; font-family:monospace; font-size:12px; word-break:break-all; line-height:1.6; max-height:400px; overflow-y:auto;'>
            {formatted_seq}
        </div>
        <button onclick="navigator.clipboard.writeText(`{sequence}`)" 
                style='margin-top:8px; padding:6px 12px; background:#4ecdc4; color:#000; border:none; border-radius:4px; cursor:pointer;'>
            📋 Copy Sequence
        </button>
        <p style='margin-top:10px;'>
            <a href="https://www.uniprot.org/uniprotkb/{accession}" target="_blank" style='color:#4ecdc4;'>🔗 View on UniProt</a>
        </p>
        """
        return html
    
    # If user wants motifs, show just motifs
    if wants_motifs and data.get("motifs"):
        motif_items = "".join([
            f"<tr><td style='padding:6px;border:1px solid #555;'>{m.get('description', 'Unknown')}</td>"
            f"<td style='padding:6px;border:1px solid #555;'>{m.get('start', '?')}-{m.get('end', '?')}</td></tr>"
            for m in data["motifs"]
        ])
        html = f"""
        <h3>📋 Motifs in {gene_name}</h3>
        <p><b>UniProt:</b> {accession}</p>
        <table style='width:100%; border-collapse:collapse; margin-top:10px;'>
            <tr style='background:#444;'>
                <th style='padding:8px; border:1px solid #666;'>Motif</th>
                <th style='padding:8px; border:1px solid #666;'>Position</th>
            </tr>
            {motif_items}
        </table>
        """
        return html
    
    # If user wants domains, show just domains
    if wants_domains and data.get("domains"):
        domain_items = "".join([
            f"<tr><td style='padding:6px;border:1px solid #555;'>{d.get('description', 'Unknown')}</td>"
            f"<td style='padding:6px;border:1px solid #555;'>{d.get('start', '?')}-{d.get('end', '?')}</td></tr>"
            for d in data["domains"]
        ])
        html = f"""
        <h3>🔷 Domains in {gene_name}</h3>
        <p><b>UniProt:</b> {accession}</p>
        <table style='width:100%; border-collapse:collapse; margin-top:10px;'>
            <tr style='background:#444;'>
                <th style='padding:8px; border:1px solid #666;'>Domain</th>
                <th style='padding:8px; border:1px solid #666;'>Position</th>
            </tr>
            {domain_items}
        </table>
        """
        return html
    
    # If user wants structure, show AlphaFold 3D viewer embedded
    if wants_structure:
        html = f"""
        <h3>🔬 {gene_name} - 3D Structure</h3>
        <p><b>UniProt:</b> {accession} | <b>Protein:</b> {protein_name}</p>
        
        <div style='margin-top:15px; background:#000; border-radius:10px; overflow:hidden;'>
            <iframe src="https://alphafold.ebi.ac.uk/entry/{accession}" 
                    style="width:100%; height:500px; border:none;">
            </iframe>
        </div>
        <p style='color:#888; font-size:0.85em; text-align:center; margin-top:5px;'>
            AlphaFold predicted structure • <a href="{alphafold_url}" target="_blank" style='color:#4ecdc4;'>Open in new tab</a>
        </p>
        
        <p style='margin-top:12px;'>
            <a href="https://www.uniprot.org/uniprotkb/{accession}" target="_blank" style='color:#4ecdc4;'>🔗 View on UniProt</a>
        </p>
        """
        return html
    
    # For other specific queries, no HTML needed - text response is sufficient
    return None


# -------------------------------------------------
# NCBI HTML Builder
# -------------------------------------------------
def _build_ncbi_html(data: Any, query: str, wants_papers: bool) -> str | None:
    """Build HTML for NCBI results (Gene, PubMed, etc.)."""
    if not data or not data.get("results"):
        return None
    
    # Only show paper list if user asked for papers/publications
    if not wants_papers:
        return None
    
    results = data["results"]
    items = ""
    for i, r in enumerate(results[:10], 1):
        title = r.get("title", "No title")
        pmid = r.get("pmid", "")
        link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
        items += f"<li style='margin-bottom:8px;'><a href='{link}' target='_blank'>{i}. {title}</a></li>"
    
    html = f"<p>NCBI/PubMed results:</p><ol style='padding-left:20px;'>{items}</ol>"
    return html


# -------------------------------------------------
# KEGG HTML Builder
# -------------------------------------------------
def _build_kegg_html(data: Any, query: str, wants_pathways: bool) -> str | None:
    """Build HTML for KEGG results."""
    if not data or not data.get("pathways"):
        return None
    
    # Only show pathway list if user asked for pathways
    if not wants_pathways:
        return None
    
    pathways = data["pathways"]
    items = ""
    for pid in pathways[:10]:
        url = f"https://www.kegg.jp/dbget-bin/www_bget?{pid}"
        items += f"<li style='margin-bottom:8px;'><a href='{url}' target='_blank'>{pid}</a></li>"
    
    html = f"<p>KEGG Pathways:</p><ol style='padding-left:20px;'>{items}</ol>"
    return html


# -------------------------------------------------
# Ensembl HTML Builder
# -------------------------------------------------
def _build_ensembl_html(data: Any, query: str) -> str | None:
    """Build HTML for Ensembl results."""
    # Ensembl data is usually specific enough to not need HTML unless genomic coords requested
    if not data or not data.get("id"):
        return None
    return None


# -------------------------------------------------
# PubChem HTML Builder
# -------------------------------------------------
def _build_pubchem_html(data: Any, query: str) -> str | None:
    """Build HTML for PubChem results with 2D/3D structure viewers."""
    if not data or not data.get("cid"):
        return None
    
    cid = data.get("cid")
    name = data.get("name", data.get("query", "Compound"))
    structure_img = data.get("structure_image_url", f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=300x300")
    pubchem_url = data.get("pubchem_url", f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}")
    molecular_formula = data.get("molecular_formula", "Unknown")
    molecular_weight = data.get("molecular_weight", "Unknown")
    smiles = data.get("canonical_smiles", "")
    inchi_key = data.get("inchi_key", "")
    show_3d = data.get("show_3d", False)
    
    # 2D structure section
    structure_2d = f"""
    <div style='text-align:center; margin:15px 0; padding:15px; background:#1a1a2e; border-radius:10px;'>
        <img src="{structure_img}" alt="{name} structure" style="max-width:300px; border-radius:8px; background:#fff;">
    </div>
    """
    
    # 3D viewer using MolView
    viewer_3d = ""
    if show_3d:
        viewer_3d = f"""
        <h4 style='margin-top:15px;'>🔬 3D Conformer</h4>
        <div style='text-align:center; margin:10px 0; background:#000; border-radius:10px; overflow:hidden;'>
            <iframe src="https://embed.molview.org/v1/?mode=balls&cid={cid}&bg=gray" 
                    style="width:100%; height:400px; border:none;">
            </iframe>
        </div>
        <p style='color:#888; font-size:0.85em; text-align:center;'>Drag to rotate • Scroll to zoom • Right-click to pan</p>
        """
    
    html = f"""
    <h3>🧪 {name} - Chemical Structure</h3>
    
    {structure_2d}
    
    {viewer_3d}
    
    <div style='margin-top:12px;'>
        <p><b>CID:</b> {cid}</p>
        <p><b>Molecular Formula:</b> {molecular_formula}</p>
        <p><b>Molecular Weight:</b> {molecular_weight} g/mol</p>
        {f"<p><b>SMILES:</b> <code style='background:#333; padding:2px 6px; border-radius:4px;'>{smiles}</code></p>" if smiles else ""}
        {f"<p><b>InChIKey:</b> <code style='background:#333; padding:2px 6px; border-radius:4px;'>{inchi_key}</code></p>" if inchi_key else ""}
    </div>
    
    <p style='margin-top:12px;'>
        <a href="{pubchem_url}" target="_blank" style='color:#4ecdc4;'>🔗 View on PubChem</a>
        {f" | <a href='{pubchem_url}#section=3D-Conformer' target='_blank' style='color:#4ecdc4; margin-left:10px;'>🔬 Full 3D Viewer</a>" if show_3d else f" | <a href='{pubchem_url}#section=3D-Conformer' target='_blank' style='color:#4ecdc4; margin-left:10px;'>🔬 View 3D Structure</a>"}
    </p>
    """
    return html

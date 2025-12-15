# backend/app/db_router.py
"""
Database Router for GeneGPT.
Routes queries to appropriate biomedical databases based on LLM classification.
"""

import requests
from typing import Dict, Any, Optional
from .schemas import QueryClassification, DatabaseResult
from .logger import get_logger

# Initialize logger
logger = get_logger()

# Import all database tools
from .uniprot_tools import route_query, KNOWN_GENE_MAP
from .ncbi_tools import NCBITools
from .pubchem_tools import PubChemTools
from .pdb_tools import PDBTools
from .string_tools import STRINGTools
from .kegg_tools import KEGGTools
from .ensembl_tools import EnsemblTools
from .clinvar_tools import ClinVarTools
from .google_image_tools import GoogleImageSearch


class DatabaseRouter:
    """
    Routes queries to the appropriate database and returns structured results.
    """
    
    def __init__(self):
        """Initialize all database tool instances."""
        self.ncbi = NCBITools()
        self.pubchem = PubChemTools()
        self.pdb = PDBTools()
        self.string = STRINGTools()
        self.kegg = KEGGTools()
        self.ensembl = EnsemblTools()
        self.clinvar = ClinVarTools()
        self.image_search = GoogleImageSearch()
    
    def route_and_fetch(self, classification: QueryClassification) -> DatabaseResult:
        """
        Route to the appropriate database and fetch data.
        
        Args:
            classification: The query classification from LLM
            
        Returns:
            DatabaseResult with data or error
        """
        db_type = classification.db_type
        search_term = classification.search_term or ""
        sub_command = classification.sub_command
        
        # Log the database hit
        logger.database_hit(db_type or "unknown", search_term, sub_command)
        
        try:
            if db_type == "uniprot":
                return self._fetch_uniprot(search_term)
            
            elif db_type == "string":
                return self._fetch_string(search_term)
            
            elif db_type == "pubchem":
                return self._fetch_pubchem(search_term, sub_command)
            
            elif db_type == "pdb":
                return self._fetch_pdb(search_term, sub_command)
            
            elif db_type == "ncbi":
                return self._fetch_ncbi(search_term, sub_command)
            
            elif db_type == "kegg":
                return self._fetch_kegg(search_term, sub_command)
            
            elif db_type == "ensembl":
                return self._fetch_ensembl(search_term, sub_command)
            
            elif db_type == "clinvar":
                return self._fetch_clinvar(search_term)
            
            elif db_type == "image_search":
                return self._fetch_images(search_term)
            
            else:
                logger.warning(f"Unknown database type: {db_type}")
                return DatabaseResult(
                    db_type=db_type or "unknown",
                    search_term=search_term,
                    success=False,
                    error=f"Unknown database type: {db_type}"
                )
                
        except Exception as e:
            logger.error(f"Database routing error: {e}")
            return DatabaseResult(
                db_type=db_type or "unknown",
                search_term=search_term,
                success=False,
                error=str(e)
            )
    
    # ===========================================
    # INDIVIDUAL DATABASE HANDLERS
    # ===========================================
    
    def _fetch_uniprot(self, search_term: str) -> DatabaseResult:
        """Fetch protein data from UniProt, including features like motifs and domains."""
        import requests
        
        # Check if it's a known gene symbol
        accession = KNOWN_GENE_MAP.get(search_term.upper())
        
        if not accession:
            # Try to search UniProt
            search_url = f"https://rest.uniprot.org/uniprotkb/search?query={search_term}+AND+organism_id:9606&format=json&size=1"
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
            return DatabaseResult(
                db_type="uniprot",
                search_term=search_term,
                success=False,
                error=f"Could not find UniProt entry for '{search_term}'"
            )
        
        # Fetch full entry
        entry_url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
        try:
            r = requests.get(entry_url, timeout=10)
            if r.status_code == 200:
                entry_data = r.json()
                
                # Extract key information
                protein_data = {
                    "accession": accession,
                    "gene_name": search_term.upper(),
                    "protein_name": entry_data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "Unknown"),
                    "organism": entry_data.get("organism", {}).get("scientificName", "Unknown"),
                    "function": None,
                    "sequence": entry_data.get("sequence", {}).get("value", ""),  # The actual amino acid sequence
                    "sequence_length": entry_data.get("sequence", {}).get("length", 0),
                    "molecular_weight": entry_data.get("sequence", {}).get("molWeight", 0),
                    "alphafold_url": f"https://alphafold.ebi.ac.uk/entry/{accession}",
                    # Feature extraction
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
                
                # Extract isoform information from comments
                isoforms = []
                for comment in entry_data.get("comments", []):
                    if comment.get("commentType") == "ALTERNATIVE PRODUCTS":
                        for isoform in comment.get("isoforms", []):
                            isoform_info = {
                                "name": isoform.get("name", {}).get("value", "Unknown"),
                                "ids": isoform.get("isoformIds", []),
                                "sequence_status": isoform.get("isoformSequenceStatus", "")
                            }
                            isoforms.append(isoform_info)
                
                protein_data["isoforms"] = isoforms
                protein_data["isoform_count"] = len(isoforms)
                
                return DatabaseResult(
                    db_type="uniprot",
                    search_term=search_term,
                    success=True,
                    data=protein_data
                )
            else:
                return DatabaseResult(
                    db_type="uniprot",
                    search_term=search_term,
                    success=False,
                    error=f"Failed to fetch UniProt entry for {accession}"
                )
        except Exception as e:
            return DatabaseResult(
                db_type="uniprot",
                search_term=search_term,
                success=False,
                error=str(e)
            )
    
    def _fetch_string(self, search_term: str) -> DatabaseResult:
        """Fetch protein-protein interactions from STRING."""
        data = self.string.fetch_interactions(search_term)
        
        if "error" in data:
            return DatabaseResult(
                db_type="string",
                search_term=search_term,
                success=False,
                error=data["error"]
            )
        
        # Add network image URL
        data["network_image_url"] = self.string.network_image(search_term)
        
        return DatabaseResult(
            db_type="string",
            search_term=search_term,
            success=True,
            data=data
        )
    
    def _fetch_pubchem(self, search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
        """Fetch compound data from PubChem."""
        import re
        
        cid = None
        compound_name = search_term.capitalize()
        
        # Check if search_term is a CID (numeric) or contains "CID"
        cid_match = re.match(r'^(?:cid\s*)?(\d+)$', search_term.strip(), re.IGNORECASE)
        
        if cid_match:
            # Direct CID lookup - we have the CID, so we can proceed even if name lookup times out
            cid = int(cid_match.group(1))
            # Try to get compound name from CID, but don't fail if it times out
            cid_info = self.pubchem.pubchem_get_by_cid(cid)
            if "error" not in cid_info:
                compound_name = cid_info.get("name", f"Compound {cid}")
            else:
                compound_name = f"Compound {cid}"
        else:
            # Search by name - this is required
            search_result = self.pubchem.pubchem_search(search_term)
            
            if "error" in search_result:
                return DatabaseResult(
                    db_type="pubchem",
                    search_term=search_term,
                    success=False,
                    error=search_result["error"]
                )
            
            cid = search_result.get("cid")
            compound_name = search_term.capitalize()
        
        # Get properties (optional - don't fail if this times out)
        props = self.pubchem.pubchem_properties(cid)
        
        # Extract properties for easier access
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
        
        return DatabaseResult(
            db_type="pubchem",
            search_term=search_term,
            success=True,
            data=compound_data
        )
    
    def _fetch_pdb(self, search_term: str, sub_command: Optional[str] = None) -> DatabaseResult:
        """Fetch 3D structure data from PDB."""
        gene_upper = search_term.upper()
        
        # Handle mmCIF request specifically
        if sub_command == "mmcif":
            # Extract PDB ID - it should be 4 characters
            pdb_id = search_term.lower() if len(search_term) == 4 else None
            
            if not pdb_id:
                # Try to extract PDB ID from search term
                import re
                match = re.search(r'\b(\d[a-zA-Z0-9]{3})\b', search_term)
                if match:
                    pdb_id = match.group(1).lower()
            
            if pdb_id:
                mmcif_data = self.pdb.pdb_fetch_mmcif(pdb_id)
                entry = self.pdb.pdb_fetch_entry(pdb_id)
                
                if "error" not in mmcif_data:
                    # Truncate mmCIF content for display (first 500 lines)
                    mmcif_content = mmcif_data.get("mmcif", "")
                    mmcif_lines = mmcif_content.split('\n')
                    mmcif_preview = '\n'.join(mmcif_lines[:500])
                    total_lines = len(mmcif_lines)
                    
                    return DatabaseResult(
                        db_type="pdb",
                        search_term=search_term,
                        success=True,
                        data={
                            "pdb_id": pdb_id,
                            "request_type": "mmcif",
                            "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
                            "mmcif_preview": mmcif_preview,
                            "mmcif_total_lines": total_lines,
                            "download_url": f"https://files.rcsb.org/download/{pdb_id}.cif",
                            "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
                        }
                    )
                else:
                    return DatabaseResult(
                        db_type="pdb",
                        search_term=search_term,
                        success=False,
                        error=f"Could not fetch mmCIF for {pdb_id}: {mmcif_data.get('error')}"
                    )
            else:
                return DatabaseResult(
                    db_type="pdb",
                    search_term=search_term,
                    success=False,
                    error="Please provide a valid PDB ID (e.g., 1A1U, 4OBE)"
                )
        
        # First check if it's a direct PDB ID (4 characters, starts with digit)
        if len(search_term) == 4 and search_term[0].isdigit():
            pdb_id = search_term.lower()
            entry = self.pdb.pdb_fetch_entry(pdb_id)
            
            if "error" not in entry:
                return DatabaseResult(
                    db_type="pdb",
                    search_term=search_term,
                    success=True,
                    data={
                        "pdb_id": pdb_id,
                        "title": entry.get("struct", {}).get("title", "Unknown"),
                        "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") else "Unknown",
                        "resolution": entry.get("rcsb_entry_info", {}).get("resolution_combined", ["N/A"])[0] if entry.get("rcsb_entry_info") else "N/A",
                        "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
                    }
                )
        
        # Check if we have known PDB IDs for this gene (fastest, works offline)
        known_pdb_ids = self.pdb.get_known_pdb_ids(gene_upper)
        
        # Try to find PDB via UniProt accession
        accession = KNOWN_GENE_MAP.get(gene_upper)
        if accession:
            pdb_results = self.pdb.pdb_search_by_uniprot(accession)
            if "error" not in pdb_results and pdb_results.get("pdb_ids"):
                pdb_id = pdb_results["pdb_ids"][0]
                entry = self.pdb.pdb_fetch_entry(pdb_id)
                
                return DatabaseResult(
                    db_type="pdb",
                    search_term=search_term,
                    success=True,
                    data={
                        "pdb_id": pdb_id,
                        "gene_name": gene_upper,
                        "uniprot_accession": accession,
                        "all_pdb_ids": pdb_results["pdb_ids"][:10],
                        "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
                        "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") and "error" not in entry else "Unknown",
                        "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
                    }
                )
        
        # Fallback 1: text search by gene name
        text_results = self.pdb.pdb_search_by_text(search_term)
        if "error" not in text_results and text_results.get("pdb_ids"):
            pdb_id = text_results["pdb_ids"][0]
            entry = self.pdb.pdb_fetch_entry(pdb_id)
            
            return DatabaseResult(
                db_type="pdb",
                search_term=search_term,
                success=True,
                data={
                    "pdb_id": pdb_id,
                    "gene_name": gene_upper,
                    "all_pdb_ids": text_results["pdb_ids"][:10],
                    "total_structures": text_results.get("total", 0),
                    "title": entry.get("struct", {}).get("title", "Unknown") if "error" not in entry else "Unknown",
                    "method": entry.get("exptl", [{}])[0].get("method", "Unknown") if entry.get("exptl") and "error" not in entry else "Unknown",
                    "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}"
                }
            )
        
        # Fallback 2: Use known PDB IDs from our hardcoded map (when API fails)
        if known_pdb_ids:
            pdb_id = known_pdb_ids[0].lower()
            # Try to fetch entry details, but don't fail if connection issues
            entry = self.pdb.pdb_fetch_entry(pdb_id)
            
            return DatabaseResult(
                db_type="pdb",
                search_term=search_term,
                success=True,
                data={
                    "pdb_id": pdb_id,
                    "gene_name": gene_upper,
                    "all_pdb_ids": known_pdb_ids,
                    "title": entry.get("struct", {}).get("title", f"{gene_upper} structure") if "error" not in entry else f"{gene_upper} structure",
                    "method": entry.get("exptl", [{}])[0].get("method", "X-ray/Cryo-EM") if entry.get("exptl") and "error" not in entry else "X-ray/Cryo-EM",
                    "viewer_url": f"https://www.rcsb.org/3d-view/{pdb_id}",
                    "note": "Using cached PDB ID due to connection issues"
                }
            )
        
        # Fallback 3: Use AlphaFold structure via UniProt accession
        if accession:
            return DatabaseResult(
                db_type="pdb",
                search_term=search_term,
                success=True,
                data={
                    "pdb_id": f"AF-{accession}",
                    "gene_name": gene_upper,
                    "uniprot_accession": accession,
                    "title": f"{gene_upper} - AlphaFold Predicted Structure",
                    "method": "AlphaFold AI Prediction",
                    "viewer_url": f"https://alphafold.ebi.ac.uk/entry/{accession}",
                    "is_alphafold": True
                }
            )
        
        # Final fallback: Try to get UniProt accession for AlphaFold
        try:
            uniprot_search = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene_upper}+AND+organism_id:9606&format=json&size=1"
            r = requests.get(uniprot_search, timeout=10)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    acc = results[0].get("primaryAccession")
                    if acc:
                        return DatabaseResult(
                            db_type="pdb",
                            search_term=search_term,
                            success=True,
                            data={
                                "pdb_id": f"AF-{acc}",
                                "gene_name": gene_upper,
                                "uniprot_accession": acc,
                                "title": f"{gene_upper} - AlphaFold Predicted Structure",
                                "method": "AlphaFold AI Prediction",
                                "viewer_url": f"https://alphafold.ebi.ac.uk/entry/{acc}",
                                "is_alphafold": True
                            }
                        )
        except Exception:
            pass
        
        return DatabaseResult(
            db_type="pdb",
            search_term=search_term,
            success=False,
            error=f"No PDB structure found for '{search_term}'. Try searching with a specific PDB ID (e.g., 4OBE for KRAS, 1M17 for EGFR)."
        )
    
    def _fetch_ncbi(self, search_term: str, sub_command: Optional[str]) -> DatabaseResult:
        """Fetch data from NCBI (Gene or PubMed)."""
        
        if sub_command == "pubmed":
            # PubMed literature search
            results = self.ncbi.pubmed_search(search_term)
            
            if "error" in results:
                return DatabaseResult(
                    db_type="ncbi",
                    search_term=search_term,
                    success=False,
                    error=results["error"]
                )
            
            return DatabaseResult(
                db_type="ncbi",
                search_term=search_term,
                success=True,
                data={"source": "pubmed", "results": results.get("results", [])}
            )
        
        else:
            # Default: Gene search
            gene_result = self.ncbi.gene_search(search_term)
            
            if "error" in gene_result:
                return DatabaseResult(
                    db_type="ncbi",
                    search_term=search_term,
                    success=False,
                    error=gene_result["error"]
                )
            
            gene_id = gene_result.get("gene_id")
            summary = self.ncbi.gene_summary(gene_id)
            
            return DatabaseResult(
                db_type="ncbi",
                search_term=search_term,
                success=True,
                data={"source": "gene", "gene_id": gene_id, "summary": summary}
            )
    
    def _fetch_kegg(self, search_term: str, sub_command: Optional[str]) -> DatabaseResult:
        """Fetch pathway data from KEGG."""
        
        if sub_command == "pathway":
            # Get pathway info
            # Ensure pathway ID has correct format (hsa prefixed)
            pathway_id = search_term
            if not pathway_id.startswith("hsa") and not pathway_id.startswith("map"):
                pathway_id = f"hsa{search_term}"
            
            info = self.kegg.pathway_info(pathway_id)
            
            if "error" in info:
                return DatabaseResult(
                    db_type="kegg",
                    search_term=search_term,
                    success=False,
                    error=info["error"]
                )
            
            return DatabaseResult(
                db_type="kegg",
                search_term=search_term,
                success=True,
                data={"source": "pathway", "info": info}
            )
        
        else:
            # Default: Gene pathways
            gene_symbol = search_term.upper().strip()
            
            # Look up KEGG gene ID from gene symbol
            kegg_gene_id = self.kegg._find_kegg_gene_id(gene_symbol)
            
            if not kegg_gene_id:
                return DatabaseResult(
                    db_type="kegg",
                    search_term=search_term,
                    success=False,
                    error=f"Could not find KEGG gene ID for '{gene_symbol}'. Try searching on KEGG directly."
                )
            
            pathways = self.kegg.gene_pathways(kegg_gene_id)
            
            if "error" in pathways:
                return DatabaseResult(
                    db_type="kegg",
                    search_term=search_term,
                    success=False,
                    error=pathways["error"]
                )
            
            # Get pathway names and generate map URLs
            pathway_list = []
            for pid in pathways.get("pathways", [])[:10]:
                name = self.kegg.pathway_name(pid)
                # Generate pathway map URL with gene highlighted
                map_url = f"https://www.kegg.jp/kegg-bin/show_pathway?{pid}+{kegg_gene_id}"
                pathway_list.append({"id": pid, "name": name, "map_url": map_url})
            
            return DatabaseResult(
                db_type="kegg",
                search_term=search_term,
                success=True,
                data={
                    "source": "gene", 
                    "gene": gene_symbol,
                    "kegg_id": kegg_gene_id,
                    "pathways": pathway_list,
                    "total_pathways": len(pathways.get("pathways", []))
                }
            )
    
    def _fetch_ensembl(self, search_term: str, sub_command: Optional[str]) -> DatabaseResult:
        """Fetch genomic data from Ensembl."""
        
        if sub_command == "id":
            # Lookup by Ensembl ID
            data = self.ensembl.lookup_id(search_term)
            
            if not data:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error=f"No Ensembl record found for ID '{search_term}'"
                )
            
            return DatabaseResult(
                db_type="ensembl",
                search_term=search_term,
                success=True,
                data={"source": "id_lookup", "record": data}
            )
        
        elif sub_command == "transcripts":
            # Get transcripts for gene
            transcripts = self.ensembl.gene_transcripts(search_term)
            
            if not transcripts:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error=f"No transcripts found for '{search_term}'"
                )
            
            return DatabaseResult(
                db_type="ensembl",
                search_term=search_term,
                success=True,
                data={"source": "transcripts", "transcripts": transcripts}
            )
        
        elif sub_command == "region":
            # Get genes/features in a genomic region
            # Format: chromosome:start-end (e.g., 17:7565097-7590856)
            import re
            
            # Parse the region - support formats like "17:7565097-7590856" or "chr17:7565097-7590856"
            region_match = re.match(r'^(?:chr)?(\w+):(\d+)-(\d+)$', search_term.strip())
            
            if not region_match:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error=f"Invalid region format. Use format: chromosome:start-end (e.g., 17:7565097-7590856)"
                )
            
            chrom = region_match.group(1)
            start = int(region_match.group(2))
            end = int(region_match.group(3))
            
            # Use Ensembl overlap API to get features in region
            import requests
            url = f"https://rest.ensembl.org/overlap/region/human/{chrom}:{start}-{end}"
            
            try:
                r = requests.get(url, 
                    headers={"Content-Type": "application/json"},
                    params={"feature": "gene"},
                    timeout=15
                )
                
                if r.status_code != 200:
                    return DatabaseResult(
                        db_type="ensembl",
                        search_term=search_term,
                        success=False,
                        error=f"No genes found in region {chrom}:{start}-{end}"
                    )
                
                genes = r.json()
                
                if not genes:
                    return DatabaseResult(
                        db_type="ensembl",
                        search_term=search_term,
                        success=False,
                        error=f"No genes found in region {chrom}:{start}-{end}"
                    )
                
                # Format the results
                gene_list = []
                for g in genes[:20]:  # Limit to 20 genes
                    gene_list.append({
                        "id": g.get("gene_id", g.get("id", "")),
                        "name": g.get("external_name", "Unknown"),
                        "biotype": g.get("biotype", ""),
                        "start": g.get("start"),
                        "end": g.get("end"),
                        "strand": g.get("strand"),
                        "description": g.get("description", "")
                    })
                
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=True,
                    data={
                        "source": "region",
                        "region": f"{chrom}:{start}-{end}",
                        "chromosome": chrom,
                        "start": start,
                        "end": end,
                        "genes": gene_list,
                        "total_genes": len(genes),
                        "ensembl_url": f"https://ensembl.org/Homo_sapiens/Location/View?r={chrom}:{start}-{end}"
                    }
                )
                
            except requests.exceptions.Timeout:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error="Connection timeout while fetching region data"
                )
            except Exception as e:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error=f"Error fetching region data: {str(e)}"
                )
        
        else:
            # Default: Gene lookup
            gene = self.ensembl.lookup_gene(search_term, species="human")
            
            if not gene:
                return DatabaseResult(
                    db_type="ensembl",
                    search_term=search_term,
                    success=False,
                    error=f"No Ensembl gene found for '{search_term}'"
                )
            
            return DatabaseResult(
                db_type="ensembl",
                search_term=search_term,
                success=True,
                data={"source": "gene_lookup", "gene": gene}
            )
    
    def _fetch_clinvar(self, search_term: str) -> DatabaseResult:
        """Fetch variant data from ClinVar."""
        data = self.clinvar.variants_for_gene(search_term.upper())
        
        if "error" in data:
            return DatabaseResult(
                db_type="clinvar",
                search_term=search_term,
                success=False,
                error=data["error"]
            )
        
        variants = data.get("results", [])
        
        # Summarize by clinical significance
        significance_counts = {}
        for v in variants:
            sig = v.get("clinical_significance", "Unknown")
            significance_counts[sig] = significance_counts.get(sig, 0) + 1
        
        return DatabaseResult(
            db_type="clinvar",
            search_term=search_term,
            success=True,
            data={
                "gene": search_term.upper(),
                "total_variants": len(variants),
                "significance_summary": significance_counts,
                "sample_variants": variants[:10]  # First 10 variants
            }
        )
    
    def _fetch_images(self, search_term: str) -> DatabaseResult:
        """Fetch images via Google Image Search."""
        data = self.image_search.search_images(search_term, num=5)
        
        if "error" in data:
            return DatabaseResult(
                db_type="image_search",
                search_term=search_term,
                success=False,
                error=data["error"]
            )
        
        return DatabaseResult(
            db_type="image_search",
            search_term=search_term,
            success=True,
            data={"results": data.get("results", [])}
        )

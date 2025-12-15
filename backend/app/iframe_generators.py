# backend/app/iframe_generators.py
"""
HTML iframe generators for embedding 3D viewers.
"""


def generate_pdb_iframe(pdb_id: str) -> str:
    """
    Generate an iframe for RCSB PDB 3D viewer.
    
    Args:
        pdb_id: PDB ID (e.g., '1ABC')
        
    Returns:
        HTML iframe string
    """
    return f"""
    <iframe
        style="width:100%; height:520px; border:none; background:black;"
        src="https://www.rcsb.org/3d-view/{pdb_id.upper()}">
    </iframe>
    """


def generate_alphafold_iframe(accession: str) -> str:
    """
    Generate an iframe for AlphaFold structure viewer.
    
    Args:
        accession: UniProt accession (e.g., 'P04637')
        
    Returns:
        HTML iframe string
    """
    return f"""
    <iframe
        style="width:100%; height:520px; border:none; background:black;"
        src="https://alphafold.ebi.ac.uk/entry/{accession.upper()}">
    </iframe>
    """


def generate_molview_iframe(cid: str) -> str:
    """
    Generate an iframe for MolView 3D chemical structure viewer.
    
    Args:
        cid: PubChem CID
        
    Returns:
        HTML iframe string
    """
    return f"""
    <iframe
        style="width:100%; height:400px; border:none; background:#000; border-radius:10px;"
        src="https://embed.molview.org/v1/?mode=balls&cid={cid}&bg=gray">
    </iframe>
    """


def generate_pubchem_2d_image(cid: str, size: int = 300) -> str:
    """
    Generate an img tag for PubChem 2D structure.
    
    Args:
        cid: PubChem CID
        size: Image size in pixels
        
    Returns:
        HTML img tag string
    """
    return f"""
    <img src="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size={size}x{size}"
         alt="2D structure" 
         style="max-width:{size}px; border-radius:8px; background:#fff;">
    """

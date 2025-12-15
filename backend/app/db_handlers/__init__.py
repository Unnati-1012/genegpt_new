# backend/app/db_handlers/__init__.py
"""
Database handlers package for GeneGPT.
Each handler is responsible for fetching data from a specific database.
"""

from .uniprot_handler import fetch_uniprot
from .string_handler import fetch_string
from .pubchem_handler import fetch_pubchem
from .pdb_handler import fetch_pdb
from .ncbi_handler import fetch_ncbi
from .kegg_handler import fetch_kegg
from .ensembl_handler import fetch_ensembl
from .clinvar_handler import fetch_clinvar
from .image_handler import fetch_images

__all__ = [
    "fetch_uniprot",
    "fetch_string",
    "fetch_pubchem",
    "fetch_pdb",
    "fetch_ncbi",
    "fetch_kegg",
    "fetch_ensembl",
    "fetch_clinvar",
    "fetch_images",
]

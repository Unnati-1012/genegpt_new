# backend/app/db_router_new.py
"""
Database Router for GeneGPT.
Routes queries to appropriate biomedical databases based on LLM classification.

This is the modularized version that delegates to handler modules.
"""

from typing import Dict, Any
from .schemas import QueryClassification, DatabaseResult
from .logger import get_logger

# Import all database tools
from .ncbi_tools import NCBITools
from .pubchem_tools import PubChemTools
from .pdb_tools import PDBTools
from .string_tools import STRINGTools
from .kegg_tools import KEGGTools
from .ensembl_tools import EnsemblTools
from .google_image_tools import GoogleImageSearch

# Import handlers
from .db_handlers import (
    fetch_uniprot,
    fetch_string,
    fetch_pubchem,
    fetch_pdb,
    fetch_ncbi,
    fetch_kegg,
    fetch_ensembl,
    fetch_clinvar,
    fetch_images,
)

# Initialize logger
logger = get_logger()


class DatabaseRouter:
    """
    Routes queries to the appropriate database and returns structured results.
    Delegates actual fetching to handler modules.
    """
    
    def __init__(self):
        """Initialize all database tool instances."""
        self.ncbi = NCBITools()
        self.pubchem = PubChemTools()
        self.pdb = PDBTools()
        self.string = STRINGTools()
        self.kegg = KEGGTools()
        self.ensembl = EnsemblTools()
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
            result = self._dispatch(db_type, search_term, sub_command)
            return result
            
        except Exception as e:
            logger.error(f"Database routing error: {e}")
            return DatabaseResult(
                db_type=db_type or "unknown",
                search_term=search_term,
                success=False,
                error=f"Error fetching data: {str(e)}"
            )
    
    def _dispatch(self, db_type: str, search_term: str, sub_command: str = None) -> DatabaseResult:
        """
        Dispatch to the appropriate handler based on database type.
        
        Args:
            db_type: Database type identifier
            search_term: The term to search for
            sub_command: Optional sub-command for specific actions
            
        Returns:
            DatabaseResult from the handler
        """
        handlers = {
            "uniprot": lambda: fetch_uniprot(search_term),
            "string": lambda: fetch_string(self.string, search_term),
            "pubchem": lambda: fetch_pubchem(self.pubchem, search_term, sub_command),
            "pdb": lambda: fetch_pdb(self.pdb, search_term, sub_command),
            "ncbi": lambda: fetch_ncbi(self.ncbi, search_term, sub_command),
            "kegg": lambda: fetch_kegg(self.kegg, search_term, sub_command),
            "ensembl": lambda: fetch_ensembl(self.ensembl, search_term, sub_command),
            "clinvar": lambda: fetch_clinvar(search_term),
            "image_search": lambda: fetch_images(self.image_search, search_term),
        }
        
        handler = handlers.get(db_type)
        
        if handler:
            return handler()
        else:
            logger.warning(f"Unknown database type: {db_type}")
            return DatabaseResult(
                db_type=db_type or "unknown",
                search_term=search_term,
                success=False,
                error=f"Unknown database type: {db_type}"
            )

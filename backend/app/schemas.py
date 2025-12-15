"""
Pydantic schemas for structured LLM outputs in GeneGPT routing.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, List


# -------------------------------------------------
# EXISTING SCHEMAS (for backward compatibility)
# -------------------------------------------------
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: Optional[str] = None      # normal text response
    html: Optional[str] = None       # 3D structure / viewer HTML
    pdb_id: Optional[str] = None     # return selected PDB ID
    mmcif: Optional[str] = None      # return raw mmCIF data


# -------------------------------------------------
# QUERY CLASSIFICATION SCHEMA
# -------------------------------------------------
class QueryClassification(BaseModel):
    """
    Structured output for classifying user queries.
    The LLM uses this to determine query type and routing.
    """
    query_type: Literal["general", "medical"] = Field(
        description="Whether the query is general (non-medical) or medical/biology related"
    )
    
    # For general queries - provide a direct reply
    reply: Optional[str] = Field(
        default=None,
        description="Direct reply for general queries (non-medical questions)"
    )
    
    # For medical queries - either follow-up or route to database
    needs_clarification: bool = Field(
        default=False,
        description="True if the medical query is unclear and needs follow-up questions"
    )
    
    follow_up_question: Optional[str] = Field(
        default=None,
        description="Follow-up question to ask if the query needs clarification"
    )
    
    db_type: Optional[Literal[
        "uniprot",
        "string", 
        "pubchem",
        "pdb",
        "ncbi",
        "kegg",
        "ensembl",
        "clinvar",
        "image_search"
    ]] = Field(
        default=None,
        description="Database to query for medical/biology questions"
    )
    
    # Extracted entities for database queries
    search_term: Optional[str] = Field(
        default=None,
        description="The main search term extracted from the query (gene name, protein name, compound name, etc.)"
    )
    
    sub_command: Optional[str] = Field(
        default=None,
        description="Sub-command for databases that support multiple operations (e.g., 'gene', 'pathway', 'search', 'pubmed')"
    )


# -------------------------------------------------
# DATABASE QUERY RESULT
# -------------------------------------------------
class DatabaseResult(BaseModel):
    """
    Wrapper for database query results to pass to LLM for final answer generation.
    """
    db_type: str
    search_term: str
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# -------------------------------------------------
# FINAL ANSWER SCHEMA
# -------------------------------------------------
class FinalAnswer(BaseModel):
    """
    Structured final answer after database retrieval.
    """
    answer: str = Field(
        description="The complete, informative answer to the user's question"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of database sources used"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Confidence level in the answer"
    )

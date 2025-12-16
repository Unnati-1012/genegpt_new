import os
from dotenv import load_dotenv
import pathlib
import re
from typing import Optional, List

# Path: backend/app/main.py
# Move UP one directory to reach backend/
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

print("Loading .env from:", ENV_PATH)
load_dotenv(ENV_PATH)
print("Loaded GOOGLE_API_KEY:", os.environ.get("GOOGLE_API_KEY"))

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Database tools
from .pubchem_tools import PubChemTools
from .string_tools import STRINGTools
from .google_image_tools import GoogleImageSearch
from .ensembl_tools import EnsemblTools
from .kegg_tools import KEGGTools
from .ncbi_tools import NCBITools
from .pdb_tools import PDBTools
from .clinvar_tools import ClinVarTools

# NEW: Import the uniprot handler for isoform queries
from .db_handlers.uniprot_handler import fetch_uniprot as fetch_uniprot_handler

# NEW: Document processor for image/PDF handling
from .document_processor import process_uploaded_file, clean_ocr_text

# Initialize tools
pubchem = PubChemTools()
string_db = STRINGTools()
image_search = GoogleImageSearch()
ensembl = EnsemblTools()
kegg = KEGGTools()
ncbi = NCBITools()
pdb = PDBTools()
clinvar = ClinVarTools()

# Router + LLM (legacy)
from .uniprot_tools import route_query, multimodal_response, KNOWN_GENE_MAP
from .llm_client import LLMClient

# NEW: Database Router for intelligent routing
from .db_router import DatabaseRouter
from .schemas import DatabaseResult

# Logger
from .logger import get_logger
logger = get_logger()

# -------------------------------------------------
# PATH FIX
# -------------------------------------------------
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "static"
logger.info(f"Serving static from: {FRONTEND_DIR}")

# -------------------------------------------------
# APP
# -------------------------------------------------
app = FastAPI()
llm = LLMClient()
db_router = DatabaseRouter()  # NEW: Intelligent database router


# -------------------------------------------------
# STATIC
# -------------------------------------------------
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# -------------------------------------------------
# MODELS (Updated for conversation history)
# -------------------------------------------------
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


# -------------------------------------------------
# CORS
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# HELPER: DETECT ISOFORM QUERY
# -------------------------------------------------
def _detect_isoform_query(query: str) -> tuple[bool, str | None]:
    """
    Detect if the user query is asking about isoforms.
    Returns (is_isoform_query, gene_name).
    """
    query_lower = query.lower()
    
    # Check if query mentions isoforms
    if "isoform" not in query_lower:
        return False, None
    
    # Common words to exclude (not gene names)
    exclude_words = {'all', 'the', 'of', 'for', 'and', 'or', 'are', 'is', 'what', 'which', 
                     'show', 'list', 'get', 'display', 'other', 'more', 'different', 
                     'multiple', 'any', 'there', 'does', 'do', 'have', 'has', 'how', 'many',
                     'isoform', 'isoforms'}
    
    # Pattern 1: "GENE isoforms" or "GENE all isoforms" - gene at the START
    match = re.match(r'^([a-zA-Z][a-zA-Z0-9]+)\s+(?:all\s+)?isoforms?', query, re.IGNORECASE)
    if match:
        gene_name = match.group(1).strip().upper()
        if gene_name.lower() not in exclude_words and len(gene_name) >= 2:
            print(f"[DEBUG] Isoform query detected: gene={gene_name}")
            return True, gene_name
    
    # Pattern 2: "isoforms of GENE"
    match = re.search(r'isoforms?\s+(?:of|for)\s+([a-zA-Z][a-zA-Z0-9]+)', query, re.IGNORECASE)
    if match:
        gene_name = match.group(1).strip().upper()
        if gene_name.lower() not in exclude_words and len(gene_name) >= 2:
            print(f"[DEBUG] Isoform query detected: gene={gene_name}")
            return True, gene_name
    
    # Pattern 3: "GENE isoform 2" - specific isoform
    match = re.search(r'([a-zA-Z][a-zA-Z0-9]+)\s+isoform\s*(\d+)?', query, re.IGNORECASE)
    if match:
        gene_name = match.group(1).strip().upper()
        if gene_name.lower() not in exclude_words and len(gene_name) >= 2:
            print(f"[DEBUG] Isoform query detected: gene={gene_name}")
            return True, gene_name
    
    # Pattern 4: "isoform 2 of GENE"
    match = re.search(r'isoform\s*(\d+)?\s+(?:of|for)\s+([a-zA-Z][a-zA-Z0-9]+)', query, re.IGNORECASE)
    if match:
        gene_name = match.group(2).strip().upper()
        if gene_name.lower() not in exclude_words and len(gene_name) >= 2:
            print(f"[DEBUG] Isoform query detected: gene={gene_name}")
            return True, gene_name
    
    # Fallback: Find any word that looks like a gene name
    words = query.split()
    for word in words:
        word_clean = re.sub(r'[^a-zA-Z0-9]', '', word).upper()
        if word_clean and len(word_clean) >= 2 and word_clean.lower() not in exclude_words:
            # Check if it looks like a gene name (has letters and possibly numbers)
            if re.match(r'^[A-Z][A-Z0-9]*$', word_clean):
                print(f"[DEBUG] Isoform query detected (fallback): gene={word_clean}")
                return True, word_clean
    
    return False, None


# -------------------------------------------------
# HELPER: DETECT UNIPROT ACCESSION ID
# -------------------------------------------------
def _detect_uniprot_accession(query: str) -> str | None:
    """
    Detect if the query contains a UniProt accession ID.
    UniProt accession patterns: P31749, Q9Y6K9, O00141, A0A024R1R8
    Returns the accession ID if found, None otherwise.
    """
    # UniProt accession pattern: 
    # [OPQ][0-9][A-Z0-9]{3}[0-9] or [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}
    # Simplified: 6-10 alphanumeric starting with letter, containing numbers
    patterns = [
        r'\b([OPQ][0-9][A-Z0-9]{3}[0-9])\b',  # Primary accession like P31749
        r'\b([A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9])\b',  # Like A0A024
        r'\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b',  # General 6-char pattern
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query.upper())
        if match:
            accession = match.group(1)
            # Validate it's not a common word
            if len(accession) >= 6 and accession[1].isdigit():
                return accession
    
    return None


# -------------------------------------------------
# HELPER: EXTRACT GENE/PROTEIN FROM CONVERSATION CONTEXT
# -------------------------------------------------
def _extract_gene_from_context(messages: list[dict]) -> str | None:
    """
    Extract the most recently discussed gene/protein/PDB ID from conversation history.
    Used when user asks vague follow-up questions like "everything", "more", "functions",
    or pronoun-based questions like "what is the name of this protein?"
    """
    # Common gene name patterns
    gene_pattern = r'\b([A-Z][A-Z0-9]{1,9})\b'
    # PDB ID pattern (4 alphanumeric characters, typically starts with digit)
    pdb_pattern = r'\b([0-9][A-Z0-9]{3})\b'
    # UniProt accession pattern
    uniprot_pattern = r'\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b'
    
    exclude_words = {'THE', 'AND', 'FOR', 'ARE', 'YOU', 'CAN', 'WHAT', 'HOW', 'SHOW', 
                     'TELL', 'GIVE', 'GET', 'ALL', 'MORE', 'INFO', 'DATA', 'ABOUT',
                     'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'HAS', 'DOES', 'WILL',
                     'WOULD', 'COULD', 'SHOULD', 'PLEASE', 'THANKS', 'HELLO', 'GENE',
                     'PROTEIN', 'FUNCTION', 'STRUCTURE', 'SEQUENCE', 'ISOFORM', 'PDB',
                     'SOURCE', 'HTTP', 'HTTPS', 'WWW', 'ORG', 'COM', 'UNIPROT'}
    
    # Look through messages in reverse order (most recent first)
    for msg in reversed(messages[:-1]):  # Exclude current message
        content = msg.get("content", "")
        content_upper = content.upper()
        
        # First check for PDB IDs (like 1A1U)
        pdb_matches = re.findall(pdb_pattern, content_upper)
        for match in pdb_matches:
            if match not in exclude_words:
                return match
        
        # Check for UniProt accessions (like P31749)
        uniprot_matches = re.findall(uniprot_pattern, content_upper)
        for match in uniprot_matches:
            if match not in exclude_words:
                return match
        
        # Find potential gene names
        matches = re.findall(gene_pattern, content_upper)
        for match in matches:
            if match not in exclude_words and len(match) >= 2:
                # Validate it looks like a gene name (not just any word)
                # Common gene patterns: TP53, BRCA1, EGFR, AKT1, etc.
                if re.match(r'^[A-Z]+[0-9]*$', match) or re.match(r'^[A-Z][A-Z0-9]+$', match):
                    return match
    
    return None


# -------------------------------------------------
# HELPER: PROCESS A SINGLE QUERY (using intelligent routing)
# -------------------------------------------------
async def process_single_query(msg: str, messages: list[dict]):
    """
    Process a single query using LLM-based intelligent routing.
    """
    # Step 0a: Check for UniProt accession ID query - direct routing
    accession = _detect_uniprot_accession(msg)
    if accession:
        logger.info(f"UniProt accession detected: {accession}")
        print(f"[DEBUG] UniProt accession detected: {accession}")
        db_result = fetch_uniprot_handler(accession)
        if db_result.success and db_result.data:
            # Check if user is asking about isoforms of this accession
            if "isoform" in msg.lower():
                from .db_handlers.uniprot_handler import _add_all_isoforms_data
                db_result.data = _add_all_isoforms_data(db_result.data, accession)
                if "all_isoforms_data" in db_result.data and db_result.data["all_isoforms_data"]:
                    final_answer = _format_all_isoforms_response(db_result.data)
                    return {"reply": final_answer, "html": None}
            # Otherwise, generate answer with the data
            logger.llm_call("answer_generation", llm.generation_model)
            final_answer = await llm.generate_answer_with_data(msg, db_result, messages)
            return {"reply": final_answer, "html": None}
    
    # Step 0b: Handle vague/pronoun-based queries by extracting context
    msg_lower = msg.lower().strip()
    vague_words = {'everything', 'all', 'more', 'details', 'info', 'functions', 'function', 
                   'diseases', 'disease', 'tell me more', 'show me', 'what about'}
    
    # Pronoun patterns that indicate referring to something from context
    pronoun_patterns = [
        r'\bthis protein\b', r'\bthat protein\b', r'\bthe protein\b',
        r'\bthis gene\b', r'\bthat gene\b', r'\bthe gene\b',
        r'\bits?\b.*\b(function|structure|sequence|domain|isoform)',  # "its function", "it's structure"
        r'\bwhat is (this|that|it)\b',
        r'\bname of (this|that|the)\b',
        r'\babout (this|that|it)\b',
        r'\b(this|that|it) (is|does|has)\b',
    ]
    
    is_pronoun_query = any(re.search(p, msg_lower) for p in pronoun_patterns)
    is_vague_query = msg_lower in vague_words or any(msg_lower == w for w in vague_words)
    
    if is_pronoun_query or is_vague_query:
        context_gene = _extract_gene_from_context(messages)
        if context_gene:
            logger.info(f"Context-based query '{msg}' - using context gene: {context_gene}")
            print(f"[DEBUG] Context query, using context gene: {context_gene}")
            # Fetch data for the context gene
            db_result = fetch_uniprot_handler(context_gene)
            if db_result.success and db_result.data:
                logger.llm_call("answer_generation", llm.generation_model)
                # Enhance the query with context
                enhanced_msg = f"{msg} (referring to {context_gene})"
                final_answer = await llm.generate_answer_with_data(enhanced_msg, db_result, messages)
                return {"reply": final_answer, "html": None}
    
    # Step 0c: Check for isoform query - bypass LLM entirely for these
    is_isoform_query, gene_name = _detect_isoform_query(msg)
    print(f"[DEBUG] process_single_query: is_isoform_query={is_isoform_query}, gene_name={gene_name}")
    
    if is_isoform_query and gene_name:
        logger.info(f"Isoform query detected for gene: {gene_name}")
        print(f"[DEBUG] Calling fetch_uniprot_handler with msg='{msg}'")
        # Use the handler to fetch isoform data with full query
        db_result = fetch_uniprot_handler(msg)  # Pass full query to detect all vs specific isoform
        print(f"[DEBUG] db_result.success={db_result.success}")
        
        if db_result.success and db_result.data:
            print(f"[DEBUG] DB result keys: {list(db_result.data.keys())}")
            print(f"[DEBUG] isoforms in data: {'isoforms' in db_result.data}")
            print(f"[DEBUG] all_isoforms_data in data: {'all_isoforms_data' in db_result.data}")
            logger.info(f"DB result keys: {list(db_result.data.keys())}")
            
            # Check for ALL isoforms request
            if "all_isoforms_data" in db_result.data and db_result.data["all_isoforms_data"]:
                final_answer = _format_all_isoforms_response(db_result.data)
                logger.info("All isoforms query - using direct formatting (bypassing LLM)")
                return {"reply": final_answer, "html": None}
            # Check for specific isoform request
            if "requested_isoform" in db_result.data:
                final_answer = _format_isoform_response(db_result.data)
                logger.info("Specific isoform query - using direct formatting (bypassing LLM)")
                return {"reply": final_answer, "html": None}
            
            # FALLBACK: If we detected an isoform query but data wasn't populated, 
            # force-fetch and add isoform data
            logger.info(f"Isoform query but no isoform data found, forcing fetch...")
            from .db_handlers.uniprot_handler import _add_all_isoforms_data
            accession = db_result.data.get("accession", "")
            if accession:
                db_result.data = _add_all_isoforms_data(db_result.data, accession)
                if "all_isoforms_data" in db_result.data and db_result.data["all_isoforms_data"]:
                    final_answer = _format_all_isoforms_response(db_result.data)
                    logger.info("Isoform query - showing all isoforms after force-fetch (bypassing LLM)")
                    return {"reply": final_answer, "html": None}
                else:
                    # Even if no isoforms found, show what we have
                    final_answer = f"No alternative isoforms found for {gene_name} in UniProt. The canonical sequence is shown above."
                    return {"reply": final_answer, "html": None}
    
    # Step 1: Classify the query using LLM with structured output
    logger.llm_call("query_classification", llm.routing_model)
    classification = await llm.classify_query(msg, messages)
    
    # Step 2: Handle based on classification
    
    # 2a: General queries - return LLM's direct reply
    if classification.query_type == "general":
        reply = classification.reply or await llm.get_response_from_messages(messages)
        return {"reply": reply, "html": None}
    
    # 2b: Medical query needs clarification
    if classification.needs_clarification:
        return {
            "reply": classification.follow_up_question or "Could you please provide more details about your query?",
            "html": None
        }
    
    # 2c: Medical query - route to database
    if not classification.db_type:
        # Fallback if no database was selected
        reply = await llm.get_response_from_messages(messages)
        return {"reply": reply, "html": None}
    
    # Step 3: Fetch data from the appropriate database
    db_result = db_router.route_and_fetch(classification)
    
    # Log database result
    if db_result.success:
        record_count = len(db_result.data) if isinstance(db_result.data, list) else None
        logger.database_result(classification.db_type, True, record_count)
    else:
        logger.database_result(classification.db_type, False, error=db_result.error)

    # Step 4: Check if this is an isoform query - bypass LLM entirely with direct formatting
    if db_result.success and db_result.data:
        # Check for ALL isoforms request
        if "all_isoforms_data" in db_result.data:
            final_answer = _format_all_isoforms_response(db_result.data)
            logger.info("All isoforms query - using direct formatting (bypassing LLM)")
            return {"reply": final_answer, "html": None}
        # Check for specific isoform request
        if "requested_isoform" in db_result.data:
            final_answer = _format_isoform_response(db_result.data)
            logger.info("Isoform query - using direct formatting (bypassing LLM)")
            return {"reply": final_answer, "html": None}

    # Step 5: Generate final answer using LLM with retrieved data
    logger.llm_call("answer_generation", llm.generation_model)
    final_answer = await llm.generate_answer_with_data(msg, db_result, messages)
    logger.llm_response("answer_generation", len(final_answer))
    
    # Step 6: Build HTML for structured display (only if relevant to query)
    html = None
    if db_result.success and db_result.data:
        html = _build_html_for_result(classification.db_type, db_result.data, msg)
    
    return {"reply": final_answer, "html": html}


def _format_isoform_response(data: dict) -> str:
    """
    Format isoform data directly without LLM to avoid hallucination.
    Shows the requested isoform details AND lists all available isoforms.
    """
    import requests
    
    isoform = data.get("requested_isoform", {})
    gene_name = data.get("gene_name", "Unknown")
    protein_name = data.get("protein_name", "Unknown protein")
    accession = data.get("accession", "")
    all_isoforms = data.get("isoforms", [])
    
    # Check for errors
    if "error" in isoform:
        return f"**Error**: {isoform['error']}"
    
    if data.get("requested_isoform_error"):
        return f"**Error**: {data['requested_isoform_error']}"
    
    # Build clean response for the requested isoform
    uniprot_id = isoform.get("uniprot_id", "N/A")
    name = isoform.get("name", "N/A")
    seq_length = isoform.get("sequence_length", 0)
    sequence = isoform.get("sequence", "")
    isoform_num = isoform.get("number", "")
    synonyms = isoform.get("synonyms", [])
    note = isoform.get("note", "")
    
    response = f"""## {gene_name} Isoform {isoform_num} ({uniprot_id})

**Protein:** {protein_name}

| Property | Value |
|----------|-------|
| **UniProt ID** | {uniprot_id} |
| **Isoform Name** | {name} |
| **Sequence Length** | {seq_length} amino acids |"""
    
    if synonyms:
        response += f"\n| **Synonyms** | {', '.join(synonyms)} |"
    
    if note:
        response += f"\n\n**Note:** {note}"
    
    response += f"""

### Sequence
```
{sequence}
```

---

## All Available Isoforms for {gene_name}

{gene_name} has **{len(all_isoforms)} isoform(s)**:

| # | Isoform ID | Name | Length | Status |
|---|------------|------|--------|--------|"""
    
    # Fetch all isoform sequences to get their lengths
    for idx, iso in enumerate(all_isoforms, 1):
        iso_ids = iso.get("ids", [])
        iso_id = iso_ids[0] if iso_ids else "N/A"
        iso_name = iso.get("name", f"Isoform {idx}")
        iso_status = iso.get("sequence_status", "Unknown")
        
        # Try to fetch sequence length for each isoform
        iso_length = "N/A"
        if iso_id != "N/A":
            try:
                fasta_url = f"https://rest.uniprot.org/uniprotkb/{iso_id}.fasta"
                r = requests.get(fasta_url, timeout=5)
                if r.status_code == 200:
                    lines = r.text.strip().split('\n')
                    seq = ''.join(lines[1:]) if len(lines) > 1 else ""
                    iso_length = f"{len(seq)} aa"
            except:
                iso_length = "N/A"
        
        # Mark the currently requested isoform
        marker = "→" if idx == isoform_num else ""
        response += f"\n| {marker}{idx} | {iso_id} | {iso_name} | {iso_length} | {iso_status} |"
    
    response += f"""

---
**Source:** [UniProt](https://www.uniprot.org/uniprotkb/{accession})"""
    
    return response


def _format_all_isoforms_response(data: dict) -> str:
    """
    Format ALL isoforms data when user asks about all isoforms of a gene.
    Shows complete sequence information for every available isoform.
    """
    gene_name = data.get("gene_name", "Unknown")
    protein_name = data.get("protein_name", "Unknown protein")
    accession = data.get("accession", "")
    all_isoforms = data.get("all_isoforms_data", [])
    
    if not all_isoforms:
        error = data.get("all_isoforms_error", "No isoforms found")
        return f"**Error:** {error}"
    
    response = f"""## All Isoforms of {gene_name}

**Protein:** {protein_name}  
**UniProt Accession:** {accession}  
**Total Isoforms:** {len(all_isoforms)}

---
"""
    
    for iso in all_isoforms:
        iso_num = iso.get("number", "?")
        iso_id = iso.get("uniprot_id", "N/A")
        iso_name = iso.get("name", f"Isoform {iso_num}")
        seq_length = iso.get("sequence_length", 0)
        sequence = iso.get("sequence", "")
        synonyms = iso.get("synonyms", [])
        note = iso.get("note", "")
        status = iso.get("sequence_status", "Unknown")
        
        response += f"""### Isoform {iso_num}: {iso_name} ({iso_id})

| Property | Value |
|----------|-------|
| **UniProt ID** | {iso_id} |
| **Sequence Length** | {seq_length} amino acids |
| **Status** | {status} |"""
        
        if synonyms:
            response += f"\n| **Synonyms** | {', '.join(synonyms)} |"
        
        if note:
            response += f"\n\n**Note:** {note}"
        
        if sequence:
            response += f"""

**Sequence:**
```
{sequence}
```
"""
        else:
            response += "\n\n**Sequence:** Not available\n"
        
        response += "\n---\n"
    
    response += f"""
**Source:** [UniProt](https://www.uniprot.org/uniprotkb/{accession})"""
    
    return response


# -------------------------------------------------
# CHAT ENDPOINT (now uses intelligent routing)
# -------------------------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint using LLM-based intelligent routing.
    """
    messages = [m.model_dump() for m in req.messages]
    msg = req.messages[-1].content.strip()

    logger.separator("CHAT")
    logger.incoming_request("/chat", msg)

    # Process the query using intelligent routing
    result = await process_single_query(msg, messages)
    logger.response_sent(has_html=bool(result.get("html")), reply_length=len(result.get("reply", "")))
    return result


# -------------------------------------------------
# FILE UPLOAD ENDPOINT (for images/documents)
# -------------------------------------------------
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    query: str = Form(default=""),
    history: str = Form(default="[]")
):
    """
    Handle file upload with optional text query.
    Extracts text from images (OCR) and documents (PDF).
    """
    import json
    
    try:
        logger.separator("FILE UPLOAD")
        logger.info(f"Received file: {file.filename}, content_type: {file.content_type}")
        
        # Read file content
        file_bytes = await file.read()
        logger.info(f"Read {len(file_bytes)} bytes from file")
        
        # Process the file
        file_result = process_uploaded_file(file_bytes, file.filename, file.content_type)
        file_type = file_result.get("file_type", "file")
        
        if not file_result["success"] and not file_result["text"]:
            return {
                "reply": f"❌ Could not process the file: {file_result['error']}",
                "html": None
            }
        
        # Build the query with extracted text
        extracted_text = clean_ocr_text(file_result["text"]) if file_result["text"] else ""
        
        if extracted_text:
            logger.info(f"Extracted {len(extracted_text)} chars from {file_type}")
            
            # Use more of the extracted text (up to 20000 chars)
            text_to_analyze = extracted_text[:20000]
            
            # Combine user query with extracted text
            if query:
                combined_query = f"""The user uploaded a {file_type} file named "{file.filename}" and asked: "{query}"

Here is the COMPLETE text extracted from the file:
---
{text_to_analyze}
---

Please analyze this content thoroughly and answer the user's question. If it's a presentation, explain each slide/section in detail."""
            else:
                combined_query = f"""The user uploaded a {file_type} file named "{file.filename}". Here is the COMPLETE text extracted from it:
---
{text_to_analyze}
---

Please provide a comprehensive analysis of this document:
1. If it's a presentation, explain each slide in detail
2. Summarize the main topics and key points
3. If it contains biomedical information, provide relevant insights
4. If it appears to be questions or a quiz, answer them thoroughly"""
            
            # Parse conversation history
            try:
                conv_messages = json.loads(history)
            except:
                conv_messages = []
            
            # For document uploads, bypass the classifier and send directly to LLM
            # This ensures document analysis always works regardless of content type
            logger.info("Processing document upload - bypassing classifier for direct LLM analysis")
            
            # Build messages for LLM
            llm_messages = [
                {"role": "system", "content": f"You are a helpful assistant analyzing an uploaded document. The user uploaded a {file_type} file named '{file.filename}'. Provide detailed, comprehensive analysis of the document content. If it's a presentation, explain each slide. If it contains code, explain what it does. If it has questions, answer them."},
                *conv_messages[-10:],  # Include recent conversation
                {"role": "user", "content": combined_query}
            ]
            
            # Direct LLM call for document analysis
            try:
                from .llm_client import LLMClient
                llm = LLMClient()
                
                # Use the generation model for document analysis
                response = llm.client.chat.completions.create(
                    model=llm.generation_model,
                    messages=llm_messages,
                    temperature=0.3,
                    max_tokens=4000
                )
                reply = response.choices[0].message.content
                logger.info(f"Document analysis completed successfully, {len(reply)} chars response")
            except Exception as e:
                logger.error(f"LLM error during document analysis: {e}")
                import traceback
                traceback.print_exc()
                
                # Provide a fallback summary based on the extracted text
                reply = f"""## Document Summary

**File:** {file.filename}
**Type:** {file_type.upper()}
**Content Length:** {len(extracted_text)} characters

### Extracted Content:

{text_to_analyze[:3000]}

---
*Note: Automatic analysis failed. Above is the raw extracted content.*"""
            
            # Add a note about the file
            file_note = f"📎 *Processed {file_type.upper()}: {file.filename}* ({len(extracted_text)} characters extracted)\n\n"
            
            return {
                "reply": file_note + reply,
                "html": None,
                "document_context": text_to_analyze[:10000]
            }
        
        else:
            # No text extracted - inform user
            return {
                "reply": f"📎 Received file: **{file.filename}**\n\n⚠️ {file_result.get('error', 'Could not extract text from this file.')}",
                "html": None
            }
    
    except Exception as e:
        logger.error(f"Upload endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "reply": f"❌ Error processing upload: {str(e)}",
            "html": None
        }


# -------------------------------------------------
# HTML BUILDER FOR DATABASE RESULTS
# -------------------------------------------------
def _build_html_for_result(db_type: str, data: dict, query: str = "") -> str | None:
    """
    Build optional HTML display for database results.
    Only shows HTML when it adds value beyond the text response.
    
    Args:
        db_type: The database that was queried
        data: The data returned from the database
        query: The original user query (to determine relevance)
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
    wants_function = any(w in query_lower for w in ["function", "role", "what does", "what is"])
    wants_images = any(w in query_lower for w in ["image", "picture", "show me", "photo"])
    wants_papers = any(w in query_lower for w in ["paper", "pubmed", "publication", "research", "study"])
    
    # For general info queries (like "tell me about X", "what is X", "isoforms of X"), 
    # the text response is usually sufficient - no HTML needed
    is_general_info = any(w in query_lower for w in ["isoform", "tell me about", "what are", "describe", "explain", "overview"])
    
    if db_type == "string" and data.get("interactions"):
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
    
    elif db_type == "clinvar" and data.get("sample_variants"):
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
    
    elif db_type == "image_search" and data.get("results"):
        results = data["results"]
        items = ""
        for i, r in enumerate(results, 1):
            items += f"<li style='margin-bottom:8px;'><a href='{r.get('link', '')}' target='_blank'>{i}. {r.get('title', 'Image')}</a></li>"
        
        html = f"<p>Image results:</p><ol style='padding-left:20px;'>{items}</ol>"
        return html
    
    elif db_type == "pdb" and data.get("pdb_id"):
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
        
        # Show PDB structure viewer when user asks about structure
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
    
    elif db_type == "uniprot" and data.get("accession"):
        # For general info queries (isoforms, function descriptions, etc.), 
        # the text answer is sufficient - no HTML card needed
        if is_general_info and not (wants_sequence or wants_structure or wants_domains or wants_motifs):
            return None
        
        accession = data.get("accession", "")
        gene_name = data.get("gene_name", "Unknown")
        protein_name = data.get("protein_name", "Unknown")
        sequence = data.get("sequence", "")
        seq_length = data.get("sequence_length", 0)
        alphafold_url = data.get("alphafold_url", "")
        
        # Only build HTML for what the user actually asked about
        
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
    
    elif db_type == "ncbi" and data.get("results"):
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
    
    elif db_type == "kegg" and data.get("pathways"):
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
    
    elif db_type == "ensembl" and data.get("id"):
        # Ensembl data is usually specific enough to not need HTML unless genomic coords requested
        return None
    
    elif db_type == "pubchem" and data.get("cid"):
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
        
        # 3D viewer using PubChem's 3D Viewer widget (always show both 2D and 3D when 3D requested)
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
    
    return None

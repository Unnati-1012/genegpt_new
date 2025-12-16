# backend/app/llm_client.py
"""
Enhanced LLM Client with intelligent query routing using structured outputs.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from groq import Groq

from .schemas import QueryClassification, DatabaseResult
from .logger import get_logger

# Initialize logger
logger = get_logger()


class LLMClient:
    """
    LLM Client with intelligent routing:
    1. Classify query (general vs medical)
    2. Route to appropriate database
    3. Generate final answer with retrieved data
    """
    
    def __init__(self):
        """
        Initializes the Groq API client using the environment variable GROQ_API_KEY.
        """
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GROQ_API_KEY not found in environment variables. Please set it before running.")
        self.client = Groq(api_key=self.api_key)
        
        # Model for structured outputs (JSON mode)
        self.routing_model = "meta-llama/llama-4-maverick-17b-128e-instruct"
        # Model for final generation
        self.generation_model = "meta-llama/llama-4-maverick-17b-128e-instruct"

    # ===========================================
    # STEP 1: QUERY CLASSIFICATION
    # ===========================================
    
    async def classify_query(self, query: str, conversation_history: list = None) -> QueryClassification:
        """
        Classify a user query into general/medical and determine routing.
        Returns structured QueryClassification object.
        """
        return await asyncio.to_thread(self._classify_sync, query, conversation_history)
    
    def _classify_sync(self, query: str, conversation_history: list = None) -> QueryClassification:
        """Synchronous classification using structured JSON output."""
        
        system_prompt = """You are a query classifier for a biomedical AI assistant called Noviq.AI.
Your job is to analyze user queries and classify them.

CLASSIFICATION RULES:

1. **query_type**: 
   - "general": Non-medical queries like greetings, math, weather, general knowledge
   - "medical": Anything related to biology, medicine, genetics, proteins, drugs, diseases

2. For **general** queries:
   - Set reply to a helpful response
   - Leave other fields null

3. For **medical** queries:
   - ONLY ask for clarification if ABSOLUTELY necessary (e.g., query is just "hello" or completely meaningless)
   - If CLEAR or can be inferred from context: set db_type, search_term, and optionally sub_command

4. **CRITICAL - USE CONVERSATION HISTORY FOR FOLLOW-UP QUESTIONS**:
   - Look at the conversation history to find the gene/protein being discussed
   - If user asks "this protein", "its function", "what is it", "name of this" → Find the entity from previous messages
   - Example: User discussed TP53, then asks "what is the name of this protein?" → search_term=TP53, db_type=uniprot
   - Example: User asked about BRCA1, then says "its isoforms" → search_term=BRCA1, db_type=uniprot
   - Example: User discussed EGFR, then asks "show me its structure" → search_term=EGFR, db_type=pdb
   - Example: User queried 1A1U (PDB), then asks "what is the name?" → This is asking about the protein in that PDB structure
   - **NEVER ask for clarification if the entity is mentioned in conversation history**
   - ONLY set needs_clarification=true if there's NO context at all AND the query is meaningless

5. **PRONOUNS AND VAGUE REFERENCES** - Always resolve these from context:
   - "this", "it", "its", "the protein", "this gene", "that" → Look at previous messages for the entity
   - "what is the name?" after discussing something → User wants info about that entity
   - "everything", "all", "functions", "more", "details" → Apply to the entity from context

6. **VALIDATION**: Extract ONLY the base gene/protein name for search_term
   - "EGFR isoform 99" → search_term="EGFR"
   - "TP53 variant X123Y" → search_term="TP53"
   - "BRCA1 mutation" → search_term="BRCA1"

7. **db_type** selection guide:
   - "uniprot": Protein info, sequences, functions, domains, motifs, isoforms, diseases, protein names (NOT for 3D structure)
   - "string": Protein-protein interactions, interaction networks
   - "pubchem": Chemical compounds, drugs, molecules, SMILES, CID
   - "pdb": 3D protein structures, crystallography, structure visualization, PDB IDs - USE THIS FOR ANY "structure" REQUEST
   - "ncbi": Gene info, PubMed papers, literature search
   - "kegg": Metabolic pathways, biological pathways, pathway maps
   - "ensembl": Genomic data, transcripts, gene coordinates, Ensembl IDs
   - "clinvar": Genetic variants, mutations, clinical significance, disease associations
   - "image_search": When user asks for images, pictures, diagrams

8. **STRUCTURE QUERIES**: When user asks for "structure" of a protein/gene, ALWAYS use db_type="pdb"
   - "EGFR structure" → db_type=pdb, search_term=EGFR
   - "Show me AKT1 structure" → db_type=pdb, search_term=AKT1
   - "3D structure of TP53" → db_type=pdb, search_term=TP53
   - "Structure and function of BRCA1" → db_type=pdb, search_term=BRCA1 (we'll get function from the response)

9. **search_term**: Extract the main entity (gene name like TP53, drug name like aspirin, protein ID, etc.)
   - **UniProt Accession IDs**: Patterns like P31749, Q9Y6K9, P38398 are UniProt accessions - use db_type=uniprot
   - **PDB IDs**: 4-character codes like 1A1U, 4OBE, 6LU7 are PDB IDs - use db_type=pdb
   - **Ensembl IDs**: Patterns like ENSG00000141510 are Ensembl IDs - use db_type=ensembl
   - **Gene names**: TP53, BRCA1, EGFR, AKT1, etc.

10. **IMPORTANT - Accession ID Queries**:
   - "P31749" alone → medical, db_type=uniprot, search_term=P31749 (this is AKT1)
   - "what is P38398" → medical, db_type=uniprot, search_term=P38398 (this is BRCA1)
   - "P31749 isoforms" → medical, db_type=uniprot, search_term=P31749
   - "1A1U" → medical, db_type=pdb, search_term=1A1U
   - "ENSG00000141510" → medical, db_type=ensembl, search_term=ENSG00000141510

11. **sub_command**: For databases with multiple operations:
   - NCBI: "gene" for gene info, "pubmed" for literature search
   - KEGG: "gene" for gene pathways, "pathway" for pathway details
   - Ensembl: "gene", "id", "transcripts", "region"
   - PDB: "structure" for 3D viewer, "mmcif" for mmCIF structure file
   - PubChem: "2d" or null for 2D structure, "3d" for 3D conformer view

EXAMPLES:
- "What is TP53?" → medical, db_type=uniprot, search_term=TP53
- "P31749" → medical, db_type=uniprot, search_term=P31749 (UniProt accession)
- "what is P31749" → medical, db_type=uniprot, search_term=P31749
- "P38398 isoforms" → medical, db_type=uniprot, search_term=P38398
- "Show me protein interactions for BRCA1" → medical, db_type=string, search_term=BRCA1  
- "Tell me about aspirin" → medical, db_type=pubchem, search_term=aspirin
- "What mutations exist in EGFR?" → medical, db_type=clinvar, search_term=EGFR
- "Find papers on cancer immunotherapy" → medical, db_type=ncbi, sub_command=pubmed, search_term=cancer immunotherapy
- "Hello, how are you?" → general, reply="Hello! I'm Noviq.AI, ready to help with biomedical questions."
- [After discussing TP53] "what is the name of this protein?" → medical, db_type=uniprot, search_term=TP53
- [After asking about 1A1U] "what protein is this?" → medical, db_type=pdb, search_term=1A1U
- "What pathways is AKT1 involved in?" → medical, db_type=kegg, sub_command=gene, search_term=AKT1
- "Show me the 3D structure of hemoglobin" → medical, db_type=pdb, search_term=hemoglobin
- "EGFR structure" → medical, db_type=pdb, search_term=EGFR
- "AKT1 structure and function" → medical, db_type=pdb, search_term=AKT1
- "Structure of BRCA1" → medical, db_type=pdb, search_term=BRCA1
- "Get genomic info for ENSG00000141510" → medical, db_type=ensembl, sub_command=id, search_term=ENSG00000141510
- "pdb mmcif 1A1U" → medical, db_type=pdb, sub_command=mmcif, search_term=1A1U
- "Show mmCIF file for 4OBE" → medical, db_type=pdb, sub_command=mmcif, search_term=4OBE
- "3D structure of aspirin" → medical, db_type=pubchem, sub_command=3d, search_term=aspirin
- "Show 3D conformer for caffeine" → medical, db_type=pubchem, sub_command=3d, search_term=caffeine
- "Function of TP53" → medical, db_type=uniprot, search_term=TP53
- "Sequence of EGFR" → medical, db_type=uniprot, search_term=EGFR

Respond ONLY with valid JSON matching the schema."""

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history for context if provided
        if conversation_history:
            for msg in conversation_history[-4:]:  # Last 4 messages for context
                messages.append(msg)
        
        messages.append({"role": "user", "content": f"Classify this query: {query}"})
        
        try:
            completion = self.client.chat.completions.create(
                model=self.routing_model,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "query_classification",
                        "schema": QueryClassification.model_json_schema()
                    }
                },
                temperature=0.1,  # Low temperature for consistent classification
            )
            
            result = json.loads(completion.choices[0].message.content)
            classification = QueryClassification.model_validate(result)
            
            # Log the classification
            logger.query_classification(
                query_type=classification.query_type,
                db_type=classification.db_type,
                search_term=classification.search_term,
                needs_clarification=classification.needs_clarification
            )
            logger.llm_response("query_classification", len(completion.choices[0].message.content))
            
            return classification
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            # Fallback: treat as general query
            return QueryClassification(
                query_type="general",
                reply="I'm having trouble understanding your query. Could you please rephrase it?"
            )

    # ===========================================
    # STEP 2: GENERATE FINAL ANSWER WITH DATA
    # ===========================================
    
    async def generate_answer_with_data(
        self, 
        original_query: str, 
        db_result: DatabaseResult,
        conversation_history: list = None
    ) -> str:
        """
        Generate a comprehensive answer using retrieved database data.
        """
        return await asyncio.to_thread(
            self._generate_answer_sync, 
            original_query, 
            db_result, 
            conversation_history
        )
    
    def _generate_answer_sync(
        self, 
        original_query: str, 
        db_result: DatabaseResult,
        conversation_history: list = None
    ) -> str:
        """Synchronous answer generation with database context."""
        
        system_prompt = """You are Noviq.AI, an expert biomedical AI assistant.
You have access to data retrieved from specialized databases.

YOUR OUTPUT RULES - FOLLOW STRICTLY:

1. **ALWAYS START with full protein/gene name**: Begin your answer with the official protein name and gene symbol.
   - Example: "**Tumor Protein P53 (TP53)** is a tumor suppressor..."
   - Example: "**Epidermal Growth Factor Receptor (EGFR)** is..."
   - Note: p53, P53, TP53 all refer to the same protein - use the official name from the data

2. **NEVER expose internal details** - Don't mention "JSON", "data not in JSON", "separate query needed", "provided data", or any backend/technical terms.

3. **NEVER say data is unavailable if it exists** - Check ALL fields in the data before saying something doesn't exist.

4. **Present data cleanly** - Format as a direct answer to the user's question.

5. **For PDB structure queries**: Present the structure information in this format:
   - **Protein Name**: Use the protein_name field (e.g., "Cellular tumor antigen p53")
   - **Gene**: Use the gene_name field (e.g., "TP53")
   - **Organism**: Use the organism field (e.g., "Homo sapiens")
   - **Method**: The experimental method (X-ray, NMR, Cryo-EM)
   - **Structure Description**: What the structure shows (from structure_title)
   
   Example output format:
   "**Cellular tumor antigen p53** (Gene: TP53)
   
   **Organism:** Homo sapiens
   **PDB ID:** 1A1U
   **Method:** Solution NMR
   
   This structure shows the mutant dimerization domain of p53..."

6. **For PubMed/Literature queries**: Format each paper with full details:
   - Include the paper title in bold
   - Authors (first 5 + "et al." if more)
   - Journal name and year
   - A brief description/abstract
   - **ALWAYS include the direct PubMed link** using the "link" field
   
   Example format for each paper:
   "1. **[Paper Title]**
      Authors: [Author names]
      Journal: [Journal Name], [Year]
      Description: [Brief abstract]
      🔗 [https://pubmed.ncbi.nlm.nih.gov/PMID/](https://pubmed.ncbi.nlm.nih.gov/PMID/)"

7. **For isoforms**: If isoform data exists, present it cleanly:
   - Show the isoform name, UniProt ID, sequence length
   - Show the full amino acid sequence in a code block
   - If multiple isoforms exist, list them all with their details

8. **For KEGG pathway queries**: Provide direct links to pathway diagrams:
   - Include the pathway name
   - Provide the direct image URL (image_url field)
   - Provide the interactive map link (interactive_map field)
   - Format like: "**PI3K-Akt Signaling Pathway** (hsa04151)
     - 📊 View Pathway: [Link](https://www.kegg.jp/pathway/hsa04151)
     - 🖼️ Pathway Image: [Direct Image](https://www.kegg.jp/kegg/pathway/hsa/hsa04151.png)"

9. **For domains/features**: List all domains found with their positions.

10. **For functions**: Describe the protein's function clearly, using the data provided.

11. **Keep it professional** - Write as if you're a knowledgeable scientist explaining to a colleague.

12. **Source citation** - End with "Source: [Database name]" only.

BAD EXAMPLES (never do this):
- "The JSON doesn't contain..."
- "A separate query is needed..."
- "Based on the provided data..."
- "The isoform details aren't directly available..."
- "You can search on PubMed using..." (NEVER say this - always provide the actual links!)
- "You can try searching for hsa04151..." (NEVER say this - always provide the actual links!)

GOOD EXAMPLES:
- "**Tumor Protein P53 (TP53)** is a multifunctional transcription factor..."
- "**Epidermal Growth Factor Receptor (EGFR)** has 4 known isoforms..."
- "**TP53 Dimerization Domain** (PDB: 1A1U) - This NMR structure from Homo sapiens shows..."
- "1. **Value of germline BRCA testing...** Authors: Smith J, et al. Journal: Nature, 2025. 🔗 https://pubmed.ncbi.nlm.nih.gov/12345678/"
- "**PI3K-Akt Signaling Pathway** (hsa04151) - View: https://www.kegg.jp/pathway/hsa04151"
"""

        # Build context from database result
        if db_result.success and db_result.data:
            # For isoform queries, include the full sequence data
            data_json = json.dumps(db_result.data, indent=2, default=str)
            # Allow more data for detailed queries
            max_len = 10000
            data_context = f"""
DATABASE: {db_result.db_type.upper()}
SEARCH: {db_result.search_term}

DATA:
```json
{data_json[:max_len]}
```

IMPORTANT: Use the data above to answer the user's question. Present it cleanly without mentioning JSON or technical details.
"""
        else:
            data_context = f"""
DATABASE: {db_result.db_type.upper()}
SEARCH: {db_result.search_term}
STATUS: Query failed - {db_result.error or "Unknown error"}

Politely inform the user that the information could not be found and suggest trying a different search term.
"""

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-4:]:
                messages.append(msg)
        
        # Add the data context and original query
        messages.append({
            "role": "user", 
            "content": f"""{data_context}

Question: {original_query}

Provide a direct, concise answer. No step-by-step reasoning. If the specific entity asked about doesn't exist in the data, say so briefly."""
        })
        
        try:
            completion = self.client.chat.completions.create(
                model=self.generation_model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more accurate responses
            )
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Answer generation error: {e}")
            return f"I retrieved data from {db_result.db_type} but encountered an error generating the response. Please try again."

    # ===========================================
    # LEGACY METHODS (for backward compatibility)
    # ===========================================

    async def get_response(self, prompt: str) -> str:
        """
        Backward-compatible method:
        Generates a response from a single prompt.
        """
        return await asyncio.to_thread(self._generate_sync_from_prompt, prompt)

    def _generate_sync_from_prompt(self, prompt: str) -> str:
        """Synchronous helper for single prompt use-case."""
        try:
            completion = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You must NEVER remove, rewrite, paraphrase, or block Markdown provided by the user. "
                            "Especially image Markdown like ![](url). Always return it EXACTLY as provided. "
                            "Do NOT say 'I cannot display images'. Do NOT replace images with descriptions."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I couldn't generate a response due to an internal error."

    async def get_response_from_messages(self, messages: list) -> str:
        return await asyncio.to_thread(self._generate_sync_from_messages, messages)

    def _generate_sync_from_messages(self, messages: list) -> str:
        """Synchronous helper that calls Groq with full conversation history."""
        try:
            system_prompt = {
                "role": "system",
                "content": (
                    "IMPORTANT RULES:\n"
                    "- NEVER remove, alter, rewrite, paraphrase, or block Markdown written by the user.\n"
                    "- NEVER replace image markdown with text like 'I cannot display images'.\n"
                    "- When you see image markdown (e.g., ![](https://example.com/img.png)), "
                    "you MUST output it EXACTLY, unchanged.\n"
                    "- Do NOT sanitize, filter, describe, or modify the link.\n"
                    "- If asked to show an image, you MUST reply with the markdown image tag."
                )
            }

            completion = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[system_prompt] + messages,
                temperature=0.7,
            )

            return completion.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I couldn't generate a response due to an internal error."

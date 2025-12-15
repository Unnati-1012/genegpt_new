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
        
        system_prompt = """You are a query classifier for a biomedical AI assistant called GeneGPT.
Your job is to analyze user queries and classify them.

CLASSIFICATION RULES:

1. **query_type**: 
   - "general": Non-medical queries like greetings, math, weather, general knowledge, or very vague queries that need clarification
   - "medical": Anything related to biology, medicine, genetics, proteins, drugs, diseases

2. For **general** queries:
   - Set reply to a helpful response
   - Leave other fields null

3. For **medical** queries:
   - If the query is UNCLEAR, TOO VAGUE, or needs more info: set needs_clarification=true and provide follow_up_question
   - Examples of unclear queries: "all", "show me everything", "info", "data", single words without context
   - If CLEAR: set db_type, search_term, and optionally sub_command

4. **IMPORTANT**: For unclear/vague queries, set needs_clarification=true
   - Query "all" alone → needs_clarification=true, follow_up_question="What would you like to know about? Please specify a gene, protein, drug, or topic."
   - Query "show me" → needs_clarification=true, follow_up_question="What would you like me to show you? Please specify."
   - Query "isoforms" → needs_clarification=true, follow_up_question="Which gene or protein's isoforms would you like to know about?"

5. **VALIDATION**: Extract ONLY the base gene/protein name for search_term
   - "EGFR isoform 99" → search_term="EGFR", but note the specific isoform request
   - "TP53 variant X123Y" → search_term="TP53", but note the variant request
   - "BRCA1 mutation" → search_term="BRCA1"
   - The database will return what exists; the answer generator will validate if the specific variant/isoform exists

6. **db_type** selection guide:
   - "uniprot": Protein info, sequences, functions, domains, motifs, isoforms (NOT for 3D structure)
   - "string": Protein-protein interactions, interaction networks
   - "pubchem": Chemical compounds, drugs, molecules, SMILES, CID
   - "pdb": 3D protein structures, crystallography, structure visualization, PDB IDs - USE THIS FOR ANY "structure" REQUEST
   - "ncbi": Gene info, PubMed papers, literature search
   - "kegg": Metabolic pathways, biological pathways, pathway maps
   - "ensembl": Genomic data, transcripts, gene coordinates, Ensembl IDs
   - "clinvar": Genetic variants, mutations, clinical significance, disease associations
   - "image_search": When user asks for images, pictures, diagrams

7. **STRUCTURE QUERIES**: When user asks for "structure" of a protein/gene, ALWAYS use db_type="pdb"
   - "EGFR structure" → db_type=pdb, search_term=EGFR
   - "Show me AKT1 structure" → db_type=pdb, search_term=AKT1
   - "3D structure of TP53" → db_type=pdb, search_term=TP53
   - "Structure and function of BRCA1" → db_type=pdb, search_term=BRCA1 (we'll get function from the response)

8. **search_term**: Extract the main entity (gene name like TP53, drug name like aspirin, protein ID, etc.)

9. **sub_command**: For databases with multiple operations:
   - NCBI: "gene" for gene info, "pubmed" for literature search
   - KEGG: "gene" for gene pathways, "pathway" for pathway details
   - Ensembl: "gene", "id", "transcripts", "region"
   - PDB: "structure" for 3D viewer, "mmcif" for mmCIF structure file
   - PubChem: "2d" or null for 2D structure, "3d" for 3D conformer view

EXAMPLES:
- "What is TP53?" → medical, db_type=uniprot, search_term=TP53
- "Show me protein interactions for BRCA1" → medical, db_type=string, search_term=BRCA1  
- "Tell me about aspirin" → medical, db_type=pubchem, search_term=aspirin
- "What mutations exist in EGFR?" → medical, db_type=clinvar, search_term=EGFR
- "Find papers on cancer immunotherapy" → medical, db_type=ncbi, sub_command=pubmed, search_term=cancer immunotherapy
- "Hello, how are you?" → general, reply="Hello! I'm GeneGPT, ready to help with biomedical questions."
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
        
        system_prompt = """You are GeneGPT, an expert biomedical AI assistant.
You have access to data retrieved from specialized databases.

CRITICAL INSTRUCTIONS:
1. **GIVE DIRECT ANSWERS** - No step-by-step reasoning. Just answer directly.
2. **FORMAT NICELY** - Use markdown for readability:
   - Use **bold** for key terms
   - Use bullet points for lists
   - Remove raw database references like (PubMed:12345678) - just cite "Source: UniProt" at the end
3. **CLEAN UP RAW DATA** - The function descriptions from databases often have references like (PubMed:12345). Remove these inline citations and write clean, readable text.
4. **BE CONCISE** - Summarize long descriptions into key points (under 200 words)
5. **VALIDATE DATA** - If something doesn't exist (like "isoform 99"), say so
6. Always cite the source database at the end

FORMATTING EXAMPLE:
Raw data: "TP53 acts as a tumor suppressor (PubMed:12345678, PubMed:87654321). It regulates cell cycle (PubMed:11111111)."
Formatted output: 
"**TP53** acts as a tumor suppressor and regulates the cell cycle.

**Key functions:**
- Tumor suppression
- Cell cycle regulation

Source: UniProt"

NEVER:
- Show raw PubMed references in the response
- Use step-by-step reasoning
- Hallucinate information not in the data"""

        # Build context from database result
        if db_result.success and db_result.data:
            data_context = f"""
DATABASE QUERY RESULTS:
- Source: {db_result.db_type.upper()}
- Search Term: {db_result.search_term}
- Status: SUCCESS
- Data Retrieved (USE ONLY THIS DATA):
```json
{json.dumps(db_result.data, indent=2, default=str)[:4000]}
```
"""
        else:
            data_context = f"""
DATABASE QUERY RESULTS:
- Source: {db_result.db_type.upper()}
- Search Term: {db_result.search_term}
- Status: FAILED
- Error: {db_result.error or "Unknown error"}

Since the query failed, inform the user that the data could not be retrieved and suggest they try again or use a different query.
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

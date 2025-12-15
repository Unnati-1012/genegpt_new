# backend/app/llm_client_new.py
"""
Enhanced LLM Client with intelligent query routing using structured outputs.

This is the modularized version that imports prompts from prompts.py.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from groq import Groq

from .schemas import QueryClassification, DatabaseResult
from .logger import get_logger
from .prompts import (
    CLASSIFICATION_SYSTEM_PROMPT,
    ANSWER_GENERATION_SYSTEM_PROMPT,
    LEGACY_SINGLE_PROMPT,
    LEGACY_MESSAGES_PROMPT,
)

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
        
        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT}
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
            {"role": "system", "content": ANSWER_GENERATION_SYSTEM_PROMPT}
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
                    {"role": "system", "content": LEGACY_SINGLE_PROMPT},
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
            system_prompt = {"role": "system", "content": LEGACY_MESSAGES_PROMPT}

            completion = self.client.chat.completions.create(
                model=self.generation_model,
                messages=[system_prompt] + messages,
                temperature=0.7,
            )

            return completion.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Sorry, I couldn't generate a response due to an internal error."

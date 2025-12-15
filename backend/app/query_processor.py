# backend/app/query_processor.py
"""
Query processing logic for GeneGPT.
"""

from typing import Optional

from .llm_client import LLMClient
from .db_router import DatabaseRouter
from .html_builders import build_html_for_result
from .logger import get_logger

logger = get_logger()


async def process_single_query(
    msg: str,
    messages: list,
    llm_client: LLMClient,
    db_router: DatabaseRouter
) -> dict:
    """
    Process a single query using LLM-based intelligent routing.
    
    Args:
        msg: The user's current message
        messages: Conversation history as list of dicts with role/content
        llm_client: LLM client instance
        db_router: Database router instance
        
    Returns:
        Dictionary with 'reply' and 'html' keys
    """
    # Step 1: Classify the query using LLM with structured output
    logger.llm_call("query_classification", llm_client.routing_model)
    classification = await llm_client.classify_query(msg, messages)
    
    # Step 2: Handle based on classification
    
    # 2a: General queries - return LLM's direct reply
    if classification.query_type == "general":
        reply = classification.reply or await llm_client.get_response_from_messages(messages)
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
        reply = await llm_client.get_response_from_messages(messages)
        return {"reply": reply, "html": None}
    
    # Step 3: Fetch data from the appropriate database
    db_result = db_router.route_and_fetch(classification)
    
    # Log database result
    if db_result.success:
        record_count = len(db_result.data) if isinstance(db_result.data, list) else None
        logger.database_result(classification.db_type, True, record_count)
    else:
        logger.database_result(classification.db_type, False, error=db_result.error)

    # Step 4: Generate final answer using LLM with retrieved data
    logger.llm_call("answer_generation", llm_client.generation_model)
    final_answer = await llm_client.generate_answer_with_data(msg, db_result, messages)
    logger.llm_response("answer_generation", len(final_answer))
    
    # Step 5: Build HTML for structured display (only if relevant to query)
    html = None
    if db_result.success and db_result.data:
        html = build_html_for_result(classification.db_type, db_result.data, msg)
    
    return {"reply": final_answer, "html": html}

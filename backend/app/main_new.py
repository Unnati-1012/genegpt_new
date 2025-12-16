# backend/app/main.py
"""
GeneGPT - Main FastAPI Application

A biomedical chatbot that routes queries to appropriate databases
and generates natural language responses.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Local imports
from .config import settings
from .logger import get_logger
from .llm_client import LLMClient
from .db_router import DatabaseRouter
from .query_processor import process_single_query

logger = get_logger()


# -------------------------------------------------
# REQUEST/RESPONSE MODELS
# -------------------------------------------------
class Message(BaseModel):
    """Single message in conversation."""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    messages: list[Message]


# -------------------------------------------------
# CREATE APPLICATION
# -------------------------------------------------
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Noviq.AI",
        description="Biomedical chatbot with database routing",
        version="1.0.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )
    
    # Mount static files
    if settings.FRONTEND_DIR.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(settings.FRONTEND_DIR)),
            name="static"
        )
        logger.info(f"Mounted static files from: {settings.FRONTEND_DIR}")
    else:
        logger.warning(f"Frontend directory not found: {settings.FRONTEND_DIR}")
    
    return app


# -------------------------------------------------
# APPLICATION INSTANCE
# -------------------------------------------------
app = create_app()

# Initialize components
llm_client = LLMClient()
db_router = DatabaseRouter()


# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.get("/")
def root():
    """Serve the frontend application."""
    return FileResponse(str(settings.FRONTEND_DIR / "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint using LLM-based intelligent routing.
    
    The message is classified, routed to the appropriate database,
    and a natural language response is generated.
    """
    messages = [m.model_dump() for m in req.messages]
    msg = req.messages[-1].content.strip()

    logger.separator("CHAT")
    logger.incoming_request("/chat", msg)

    # Process the query using intelligent routing
    result = await process_single_query(msg, messages, llm_client, db_router)
    
    logger.response_sent(
        has_html=bool(result.get("html")), 
        reply_length=len(result.get("reply", ""))
    )
    
    return result


# -------------------------------------------------
# MAIN ENTRY POINT
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

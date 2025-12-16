# backend/app/config.py
"""
Configuration and environment setup for Noviq.AI.
"""

import os
import pathlib
from dotenv import load_dotenv

# -------------------------------------------------
# PATHS
# -------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "static"

# -------------------------------------------------
# TESSERACT OCR PATH (Windows)
# -------------------------------------------------
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    os.environ["TESSERACT_CMD"] = TESSERACT_PATH

# -------------------------------------------------
# LOAD ENVIRONMENT
# -------------------------------------------------
def load_environment():
    """Load environment variables from .env file."""
    print(f"Loading .env from: {ENV_PATH}")
    load_dotenv(ENV_PATH)
    print(f"Loaded GOOGLE_API_KEY: {os.environ.get('GOOGLE_API_KEY')}")


# Load on import
load_environment()


# -------------------------------------------------
# CONFIGURATION SETTINGS
# -------------------------------------------------
class Settings:
    """Application settings."""
    
    # API Keys
    GOOGLE_API_KEY: str = os.environ.get("GOOGLE_API_KEY", "")
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    
    # Paths
    BASE_DIR: pathlib.Path = BASE_DIR
    FRONTEND_DIR: pathlib.Path = FRONTEND_DIR
    
    # CORS Settings
    CORS_ORIGINS: list = ["*"]
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]


settings = Settings()

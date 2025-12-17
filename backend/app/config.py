# backend/app/config.py
"""
Configuration and environment setup for Noviq.AI.
"""

import os
import pathlib
import secrets
from dotenv import load_dotenv

# -------------------------------------------------
# PATHS
# -------------------------------------------------
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
FRONTEND_DIR = BASE_DIR.parent / "frontend" / "static"
DATABASE_DIR = BASE_DIR / "data"

# Ensure data directory exists
DATABASE_DIR.mkdir(exist_ok=True)

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
    
    # -------------------------------------------------
    # DATABASE SETTINGS
    # -------------------------------------------------
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", 
        f"sqlite+aiosqlite:///{DATABASE_DIR}/noviqai.db"
    )
    DATABASE_ECHO: bool = os.environ.get("DATABASE_ECHO", "false").lower() == "true"
    
    # -------------------------------------------------
    # JWT AUTHENTICATION SETTINGS
    # -------------------------------------------------
    # Secret key for JWT encoding/decoding
    # Generate a secure key: python -c "import secrets; print(secrets.token_hex(32))"
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY",
        secrets.token_hex(32)  # Auto-generate if not set (not recommended for production)
    )
    JWT_ALGORITHM: str = "HS256"
    
    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60")  # 1 hour
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7")  # 7 days
    )


settings = Settings()


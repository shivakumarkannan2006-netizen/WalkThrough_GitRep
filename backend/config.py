import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

def _cors_origins() -> list:
    # Allow override via env var (comma-separated list)
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

class Settings:
    """Core application settings"""

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # LLM
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Browserbase
    BROWSERBASE_API_KEY: str = os.getenv("BROWSERBASE_API_KEY", "")
    BROWSERBASE_PROJECT_ID: str = os.getenv("BROWSERBASE_PROJECT_ID", "")

    # Server — Railway injects PORT; fall back to 8000 for local dev
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Audit Thresholds
    MAX_PAGES_PER_AUDIT: int = int(os.getenv("MAX_PAGES_PER_AUDIT", "500"))
    BFS_TIMEOUT_SECONDS: int = int(os.getenv("BFS_TIMEOUT_SECONDS", "1800"))
    PAGE_LOAD_TIMEOUT_MS: int = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "30000"))
    INTERACTION_TIMEOUT_MS: int = int(os.getenv("INTERACTION_TIMEOUT_MS", "300"))
    LOADING_STATE_THRESHOLD_MS: int = int(os.getenv("LOADING_STATE_THRESHOLD_MS", "300"))
    PERFORMANCE_BASELINE_THRESHOLD_MS: int = int(os.getenv("PERFORMANCE_BASELINE_THRESHOLD_MS", "2000"))

    # Playwright
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_ARGS: list = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-web-resources",
    ]

    # CORS — computed at import time so env vars are read fresh
    CORS_ORIGINS: list = _cors_origins()

    # Feature Flags
    ENABLE_RAG_VAULT_COUNSEL: bool = True
    ENABLE_LLM_ANALYSIS: bool = True
    ENABLE_SCREENSHOTS: bool = True
    ENABLE_PERSONAS: bool = True

    class Config:
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

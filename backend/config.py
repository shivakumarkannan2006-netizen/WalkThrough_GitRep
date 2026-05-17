import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

def _cors_origins() -> list:
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://bolt.new",
    ]


def _env_bool(name: str, default: bool = True) -> bool:
    val = os.getenv(name, str(default)).lower()
    return val in ("1", "true", "yes", "on")


class Settings:
    """Core application settings"""

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # LLM — Gemini 1.5 Flash for all vision + text analysis
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_VISION_MAX_TOKENS: int = int(os.getenv("GEMINI_VISION_MAX_TOKENS", "4096"))
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    MAX_GEMINI_CALLS_PER_AUDIT: int = int(os.getenv("MAX_GEMINI_CALLS_PER_AUDIT", "0"))

    # Browserbase
    BROWSERBASE_API_KEY: str = os.getenv("BROWSERBASE_API_KEY", "")
    BROWSERBASE_PROJECT_ID: str = os.getenv("BROWSERBASE_PROJECT_ID", "")

    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8080")))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Audit profile: quick | standard | deep
    AUDIT_PROFILE: str = os.getenv("AUDIT_PROFILE", "standard").lower()

    # Audit Thresholds
    MAX_PAGES_PER_AUDIT: int = int(os.getenv("MAX_PAGES_PER_AUDIT", "500"))
    BFS_TIMEOUT_SECONDS: int = int(os.getenv("BFS_TIMEOUT_SECONDS", "1800"))
    PAGE_LOAD_TIMEOUT_MS: int = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "30000"))
    POST_LOAD_IDLE_MS: int = int(os.getenv("POST_LOAD_IDLE_MS", "3000"))
    INTERACTION_TIMEOUT_MS: int = int(os.getenv("INTERACTION_TIMEOUT_MS", "300"))
    LOADING_STATE_THRESHOLD_MS: int = int(os.getenv("LOADING_STATE_THRESHOLD_MS", "300"))
    PERFORMANCE_BASELINE_THRESHOLD_MS: int = int(os.getenv("PERFORMANCE_BASELINE_THRESHOLD_MS", "2000"))

    # Pipeline — analyze pages while BFS continues
    PIPELINE_ANALYSIS_CONCURRENCY: int = int(os.getenv("PIPELINE_ANALYSIS_CONCURRENCY", "2"))

    # Sitemap / crawl
    SITEMAP_MAX_URLS: int = int(os.getenv("SITEMAP_MAX_URLS", "50"))
    ENABLE_HEAD_PREFLIGHT: bool = _env_bool("ENABLE_HEAD_PREFLIGHT", True)

    # Screenshot compression
    SCREENSHOT_MAX_WIDTH: int = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1024"))
    SCREENSHOT_JPEG_QUALITY: int = int(os.getenv("SCREENSHOT_JPEG_QUALITY", "75"))

    EXIF_MAX_IMAGES_PER_PAGE: int = int(os.getenv("EXIF_MAX_IMAGES_PER_PAGE", "20"))
    EXTERNAL_LINK_TIMEOUT_S: int = int(os.getenv("EXTERNAL_LINK_TIMEOUT_S", "10"))

    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_ARGS: list = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-blink-features=AutomationControlled",
        "--single-process",
        "--no-zygote",
    ]

    CORS_ORIGINS: list = _cors_origins()

    ENABLE_RAG_VAULT_COUNSEL: bool = _env_bool("ENABLE_RAG_VAULT_COUNSEL", True)
    ENABLE_LLM_ANALYSIS: bool = _env_bool("ENABLE_LLM_ANALYSIS", True)
    ENABLE_SCREENSHOTS: bool = _env_bool("ENABLE_SCREENSHOTS", True)
    ENABLE_PERSONAS: bool = _env_bool("ENABLE_PERSONAS", True)

    class Config:
        case_sensitive = True

    def is_quick_profile(self) -> bool:
        return self.AUDIT_PROFILE == "quick"

    def is_deep_profile(self) -> bool:
        return self.AUDIT_PROFILE == "deep"

    def run_interaction_phases(self) -> bool:
        if self.is_quick_profile():
            return False
        return self.ENABLE_PERSONAS or self.AUDIT_PROFILE in ("standard", "deep")

    def max_cta_clicks(self) -> int:
        return {"quick": 0, "standard": 3, "deep": 5}.get(self.AUDIT_PROFILE, 3)

    def max_forms(self) -> int:
        return {"quick": 0, "standard": 1, "deep": 3}.get(self.AUDIT_PROFILE, 1)

    def max_form_input_types(self) -> int:
        return {"quick": 0, "standard": 2, "deep": 3}.get(self.AUDIT_PROFILE, 2)

    def max_hovers(self) -> int:
        return {"quick": 0, "standard": 8, "deep": 15}.get(self.AUDIT_PROFILE, 8)

    def max_anchor_tests(self) -> int:
        return {"quick": 0, "standard": 10, "deep": 10}.get(self.AUDIT_PROFILE, 10)

    def use_sitemap_seed(self) -> bool:
        return self.AUDIT_PROFILE == "deep"

    def gemini_max_output_tokens(self) -> int:
        return self.GEMINI_VISION_MAX_TOKENS


@lru_cache()
def get_settings() -> Settings:
    return Settings()

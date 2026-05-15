"""
Supabase database initialization and utilities
"""

from supabase import create_client
from config import get_settings
import logging

logger = logging.getLogger(__name__)

_supabase_client = None

def init_supabase():
    """Initialize Supabase client with proper error handling"""
    global _supabase_client

    if _supabase_client:
        return _supabase_client

    settings = get_settings()

    if not settings.SUPABASE_URL:
        msg = "SUPABASE_URL environment variable must be set"
        logger.error(msg)
        raise ValueError(msg)

    # Prefer service role key so all backend writes bypass RLS.
    # Falls back to SUPABASE_KEY if service role key is not configured.
    key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_KEY
    if not key:
        msg = "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) environment variable must be set"
        logger.error(msg)
        raise ValueError(msg)

    try:
        _supabase_client = create_client(settings.SUPABASE_URL, key)
        key_type = "service role" if settings.SUPABASE_SERVICE_ROLE_KEY else "anon"
        logger.info(f"Supabase client initialized successfully using {key_type} key")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        raise

def get_supabase():
    """Get existing Supabase client"""
    global _supabase_client

    if not _supabase_client:
        return init_supabase()

    return _supabase_client

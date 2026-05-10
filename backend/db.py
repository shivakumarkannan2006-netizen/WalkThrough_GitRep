"""
Supabase database initialization and utilities
"""

from supabase import create_client
from config import get_settings
import logging

logger = logging.getLogger(__name__)

_supabase_client = None

def init_supabase():
    """Initialize Supabase client"""
    global _supabase_client

    if _supabase_client:
        return _supabase_client

    settings = get_settings()

    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    logger.info("Supabase client initialized")

    return _supabase_client

def get_supabase():
    """Get existing Supabase client"""
    global _supabase_client

    if not _supabase_client:
        return init_supabase()

    return _supabase_client

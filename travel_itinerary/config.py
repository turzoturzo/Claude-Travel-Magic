"""Configuration: .env loading, paths, constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root = parent of travel_itinerary/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL_PRIMARY = os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini")
LLM_MODEL_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "gpt-4o")

# --- Paths ---
MBOX_PATH = os.getenv("MBOX_PATH", str(PROJECT_ROOT / "2025-1-16_TRAVEL_MATTHEW TURZO.mbox"))
EXTRACTION_CACHE_PATH = PROJECT_ROOT / "extraction_cache_v2.json"
OUTPUT_DIR = PROJECT_ROOT / "output"

# --- Assembly ---
HOME_BASE_EUROPE = "Barcelona"
GAP_THRESHOLD_DAYS = 14  # flag gaps longer than this
DEDUP_DATE_WINDOW_DAYS = 2  # group events within this window for dedup

# --- Extraction ---
MAX_BODY_CHARS = 6000  # truncate email body sent to LLM
BATCH_SIZE = 20  # emails per batch for progress reporting

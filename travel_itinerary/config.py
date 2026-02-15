"""Configuration: .env loading, paths, constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root = parent of travel_itinerary/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# --- LLM API ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Default to Gemini via OpenAI-compatible endpoint; fall back to OpenAI if no Google key
LLM_BACKEND = os.getenv("LLM_BACKEND", "gemini" if GOOGLE_API_KEY else "openai")
LLM_MODEL_PRIMARY = os.getenv("LLM_MODEL_PRIMARY", "gemini-2.5-flash-preview-05-20" if LLM_BACKEND == "gemini" else "gpt-4o-mini")
LLM_MODEL_FALLBACK = os.getenv("LLM_MODEL_FALLBACK", "gemini-2.0-flash" if LLM_BACKEND == "gemini" else "gpt-4o")

# --- Traveler ---
DEFAULT_TRAVELER_NAME = os.getenv("TRAVELER_NAME", "Matthew Turzo")

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

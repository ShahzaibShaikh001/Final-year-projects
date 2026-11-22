"""App configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "").strip()
IEEE_API_KEY: str = os.getenv("IEEE_API_KEY", "").strip()

DEFAULT_PAPER_COUNT = 1
MIN_PAPER_COUNT = 1
MAX_PAPER_COUNT = 20
DEFAULT_YEAR_FROM = 2020
CONTACT_EMAIL: str = os.getenv("CONTACT_EMAIL", "researcher@local.dev").strip()

def require_groq_key() -> str:
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
        )
    return GROQ_API_KEY

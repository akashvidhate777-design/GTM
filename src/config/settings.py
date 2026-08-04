"""Central configuration for the Alepo Outbound Email Agent."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root = two levels above this file (src/config -> repo root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load OPENAI_API_KEY (and optional overrides) from the root .env
load_dotenv(PROJECT_ROOT / ".env")

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# Google OAuth client secrets (download from Google Cloud Console)
CREDENTIALS_PATH: Path = PROJECT_ROOT / "src" / "config" / "credentials.json"

# Local token storage for OAuth refresh tokens after browser auth
TOKEN_PATH: Path = PROJECT_ROOT / "src" / "config" / "token.json"

# Default Alepo lead sheet from the campaign brief
DEFAULT_SHEET_ID: str = os.getenv(
    "GOOGLE_SHEET_ID",
    "1pDcQrVToC-bsnCjR_X5FpaiP3bKO0Ka-zy9B2V3fOFU",
)

# Optional worksheet/tab name; None => first sheet in the workbook
DEFAULT_SHEET_NAME: str | None = os.getenv("GOOGLE_SHEET_NAME") or None

GOOGLE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.send",
]

# Delay range (seconds) between outbound actions to respect Gmail volume guidelines
MIN_DELAY_SECONDS: int = 30
MAX_DELAY_SECONDS: int = 90

DEFAULT_EMAIL_SUBJECT: str = "Alepo Digital BSS — Omnichannel Engagement Demo"


def require_openai_api_key() -> str:
    """Return the OpenAI API key or raise a clear error if missing."""
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("your_actual_"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to the root .env file "
            "(see .env.example)."
        )
    return OPENAI_API_KEY


def validate_google_credentials_file() -> Path:
    """Ensure credentials.json exists before starting OAuth."""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials not found at {CREDENTIALS_PATH}. "
            "Download the Desktop App client JSON from Google Cloud Console, "
            "rename it to credentials.json, and place it in src/config/."
        )
    logger.info("Using Google credentials at %s", CREDENTIALS_PATH)
    return CREDENTIALS_PATH

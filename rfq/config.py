"""Central settings. The API key is read from the environment only and never logged."""

from __future__ import annotations

import os
from pathlib import Path

try:  # .env is optional; a missing python-dotenv must not break the run
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"

MODEL = os.environ.get("RFQ_MODEL", "gpt-4.1-mini")
PROMPT_VERSION = "v0"
TEMPERATURE = 0.0
REQUEST_TIMEOUT_S = 90
MAX_RETRIES = 3

# Input caps (protect cost and latency on pathological attachments)
MAX_PDF_PAGES = 20
MAX_IMAGES_PER_EMAIL = 12
MIN_IMAGE_SIDE_PX = 64  # smaller inline images are treated as logos / signatures

VALID_UOMS = ("EA", "FT", "M", "IN", "BX", "PK", "PR", "DZ", "RL", "LB", "SET", "GAL", "BAG", "CS")
CLASSIFICATIONS = (
    "rfq",
    "rfq_revision",
    "purchase_order",
    "vendor_quote",
    "status_inquiry",
    "auto_reply",
    "other",
)
REQUEST_KINDS = ("rfq", "rfq_revision", "purchase_order")
OUR_DOMAIN = "ridgeline-supply.example"


def api_key_present() -> bool:
    """True if a key is configured. Never returns or prints the key itself."""
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())

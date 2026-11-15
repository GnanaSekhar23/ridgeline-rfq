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
MAX_PDF_PAGES = 20  # text pages read per PDF
MAX_SCAN_PAGES = 6  # scanned pages rendered to images per PDF
MAX_IMAGES_PER_EMAIL = 12
MAX_IMAGE_SIDE_PX = 1600  # images are downscaled to this before sending
SCAN_DPI = 150
MAX_ROWS_PER_SHEET = 2000
MAX_TEXT_LINES = 3000  # per source
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
NESTED_EML_DEPTH = 2
# An inline image this short, or this wide-and-short, is a logo / signature banner
LOGO_MAX_SIDE_PX = 100
LOGO_MIN_ASPECT = 4.0
LOGO_MAX_HEIGHT_PX = 120

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

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
CACHE_DIR = Path(os.environ.get("RFQ_CACHE_DIR") or ROOT / "cache")
RUNS_DIR = Path(os.environ.get("RFQ_RUNS_DIR") or ROOT / "runs")
REPORTS_DIR = Path(os.environ.get("RFQ_REPORTS_DIR") or ROOT / "reports")

MODEL = os.environ.get("RFQ_MODEL", "gpt-4.1")
PROMPT_VERSION = "p4"  # bump on any prompt/schema change -> new cache keys
TEMPERATURE = 0.0
REQUEST_TIMEOUT_S = 120
MAX_RETRIES = 3  # transient errors only (429, 5xx, timeout, connection)
# Runaway protection. Largest dev email has ~50 items; at ~90 output tokens per item (JSON keys +
# a self-contained description) that is ~4.5k tokens + ~300 for reasoning. Cap the list at 100
# items (2x the largest dev list) and the output at 100 * 90 + 1000 = 10k tokens. A runaway
# now costs at most ~$0.08 instead of ~$0.13; a list at the cap is flagged for review.
MAX_LINE_ITEMS = 100
MAX_OUTPUT_TOKENS = 10_000
IMAGE_DETAIL = "high"  # scans and photos of lists need full resolution
MAX_PROMPT_CHARS = 200_000  # rendered text budget per email (~50k tokens); beyond -> truncated + review

# USD per 1M tokens: (input, cached input, output). Check https://openai.com/api/pricing before
# trusting dollar figures; these are the list prices this code was written against.
PRICES = {
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4o": (2.50, 1.25, 10.00),
    "gpt-4o-mini": (0.15, 0.075, 0.60),
}

# Input caps (protect cost and latency on pathological attachments)
MAX_PDF_PAGES = 20  # text pages read per PDF
MAX_SCAN_PAGES = 6  # scanned pages rendered to images per PDF
MAX_IMAGES_PER_EMAIL = 30  # scans use 1 overview + ~3 strips per page
MAX_IMAGE_SIDE_PX = 2048  # the API's own high-detail limit; we never send less than it would use
SCAN_DPI = 200
# Scanned pages (no text layer) go as a low-detail overview + overlapping high-detail strips.
# The API shrinks a high-detail image so its SHORT side is <= 768px; a full page therefore loses
# resolution, a wide strip <= 768px tall keeps it. Overlap so no row is cut in every strip.
SCAN_STRIP_HEIGHT_PX = 720
SCAN_STRIP_OVERLAP_PX = 140
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

"""Test isolation, applied before any `rfq` import:
- never call the real API (offline, and an empty key so .env cannot supply one),
- never write to the real cache/, runs/ or reports/.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="rfq-tests-"))
os.environ["RFQ_OFFLINE"] = "1"
os.environ["OPENAI_API_KEY"] = ""  # load_dotenv(override=False) will not replace this
os.environ["RFQ_CACHE_DIR"] = str(_TMP / "cache")
os.environ["RFQ_RUNS_DIR"] = str(_TMP / "runs")
os.environ["RFQ_REPORTS_DIR"] = str(_TMP / "reports")

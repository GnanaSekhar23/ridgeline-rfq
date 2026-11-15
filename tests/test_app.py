"""Review app: the page loads, an email's detail renders, and an override is saved."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from rfq.catalog import parts

SYN = Path(__file__).resolve().parent / "synthetic" / "emails"


def test_page_loads_and_override_saves(tmp_path: Path) -> None:
    emails = tmp_path / "emails"
    emails.mkdir()
    shutil.copy(SYN / "S04.eml", emails / "S04.eml")  # has an xlsx attachment
    sku = parts()[0].sku
    parsed = tmp_path / "parsed.json"
    parsed.write_text(json.dumps({"S04": {
        "classification": "rfq", "revises": None, "duplicate_of": None, "needs_review": False,
        "review_reason": None, "line_items": [
            {"raw": "1 | 8 | EA", "description": "ball valve", "qty": 8, "uom": "EA",
             "source": "CP-2209_valves.xlsx", "sku": None, "match": "ambiguous",
             "match_reason": "2 parts fit", "candidates": [sku]}]}}), encoding="utf-8")
    overrides = tmp_path / "overrides.json"
    client = TestClient(create_app(emails, parsed, overrides))

    page = client.get("/")
    assert page.status_code == 200 and '<select id="picker">' in page.text
    assert "http://" not in page.text and "https://" not in page.text  # nothing loaded from outside

    assert client.get("/api/emails").json()[0]["id"] == "S04"
    d = client.get("/api/emails/S04").json()
    assert d["headers"]["subject"].startswith("RFQ CP-2209")
    assert d["attachments"][0]["name"] == "CP-2209_valves.xlsx"
    assert d["lines"][0]["candidate_parts"][0]["sku"] == sku
    assert client.get("/api/emails/..%2Fsecret").status_code == 404

    r = client.post("/api/overrides", json={"email": "S04", "line": 0, "action": "override", "sku": sku})
    assert r.status_code == 200 and r.json()["part"]["sku"] == sku
    saved = json.loads(overrides.read_text(encoding="utf-8"))["S04#0"]
    assert saved["match"] == "matched" and saved["sku"] == sku and saved["system"]["match"] == "ambiguous"

    client.post("/api/overrides", json={"email": "S04", "line": 0, "action": "override", "not_in_catalog": True})
    assert json.loads(overrides.read_text(encoding="utf-8"))["S04#0"]["match"] == "not_in_catalog"
    assert client.get("/api/emails/S04").json()["lines"][0]["override"]["match"] == "not_in_catalog"

    bad = client.post("/api/overrides", json={"email": "S04", "line": 0, "action": "override", "sku": "RL-NOPE"})
    assert bad.status_code == 400

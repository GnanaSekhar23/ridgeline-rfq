"""Review app: walk one email through the system and accept / override each catalog match.

Reads parsed.json, the .eml files and data/catalog.csv. Writes only app/overrides.json.
No model calls, no outbound requests (the page loads nothing from the internet).

    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from rfq.catalog import parts
from rfq.config import ROOT
from rfq.extractors import extract_all
from rfq.mime import parse_message

HERE = Path(__file__).resolve().parent


class OverrideIn(BaseModel):
    email: str
    line: int  # index into the email's line_items
    action: str  # "accept" | "override"
    sku: str | None = None  # override to this part
    not_in_catalog: bool = False  # override to "we don't stock it"


def create_app(emails_dir: Path, parsed_path: Path, overrides_path: Path) -> FastAPI:
    app = FastAPI(title="RFQ review", docs_url=None, redoc_url=None)
    lock = threading.Lock()
    catalog = {p.sku: p for p in parts()}

    def parsed() -> dict:
        return json.loads(parsed_path.read_text(encoding="utf-8")) if parsed_path.exists() else {}

    def overrides() -> dict:
        return json.loads(overrides_path.read_text(encoding="utf-8")) if overrides_path.exists() else {}

    def eml_path(eid: str) -> Path:
        known = {p.stem: p for p in emails_dir.glob("*.eml")}  # whitelist: no path tricks
        if eid not in known:
            raise HTTPException(404, f"unknown email {eid!r}")
        return known[eid]

    def load(eid: str):
        email = parse_message(eml_path(eid).read_bytes(), eid)
        return email, extract_all(email)

    def part(sku: str | None) -> dict | None:
        p = catalog.get(sku or "")
        return {"sku": p.sku, "description": p.description} if p else None

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (HERE / "index.html").read_text(encoding="utf-8")

    @app.get("/api/emails")
    def list_emails() -> list[dict]:
        res = parsed()
        out = []
        for p in sorted(emails_dir.glob("*.eml")):
            r = res.get(p.stem, {})
            out.append({"id": p.stem, "classification": r.get("classification"),
                        "needs_review": r.get("needs_review"), "lines": len(r.get("line_items", []))})
        return out

    @app.get("/api/emails/{eid}")
    def email_detail(eid: str) -> dict:
        email, docs = load(eid)
        result = parsed().get(eid)
        ov = overrides()
        images = []
        for d in docs:
            for i, im in enumerate(d.images):
                if " strip " in im.label:  # scan strips repeat the page; show the overview / page
                    continue
                images.append({"label": im.label, "url": f"/api/emails/{eid}/images/{len(images)}"})
        lines = []
        for i, li in enumerate((result or {}).get("line_items", [])):
            lines.append({**li, "index": i, "part": part(li.get("sku")),
                          "candidate_parts": [part(c) for c in li.get("candidates") or []],
                          "override": ov.get(f"{eid}#{i}")})
        return {
            "id": eid,
            "headers": email.headers,
            "body": email.body, "forwarded": email.forwarded, "quoted": email.quoted,
            "attachments": [{"name": a.filename, "mime": a.mime, "size": len(a.data), "inline": a.inline}
                            for a in email.attachments],
            "read_notes": [f"{d.source}: {n}" for d in docs for n in d.notes]
                          + [f"{d.source}: ERROR {d.error}" for d in docs if d.error],
            "images": images,
            "result": None if result is None else {k: v for k, v in result.items() if k != "line_items"},
            "lines": lines,
        }

    @app.get("/api/emails/{eid}/images/{n}")
    def email_image(eid: str, n: int) -> Response:
        _, docs = load(eid)
        imgs = [im for d in docs for im in d.images if " strip " not in im.label]
        if not 0 <= n < len(imgs):
            raise HTTPException(404, "no such image")
        return Response(imgs[n].png, media_type="image/png")  # always re-encoded PNG, never raw bytes

    @app.post("/api/overrides")
    def save_override(o: OverrideIn) -> dict:
        res = parsed().get(o.email)
        if res is None:
            raise HTTPException(404, f"unknown email {o.email!r}")
        items = res.get("line_items", [])
        if not 0 <= o.line < len(items):
            raise HTTPException(400, "no such line")
        li = items[o.line]
        if o.action == "accept":
            decision = {"match": li.get("match"), "sku": li.get("sku")}
        elif o.action == "override" and o.not_in_catalog:
            decision = {"match": "not_in_catalog", "sku": None}
        elif o.action == "override" and o.sku:
            sku = o.sku.strip().upper()
            if sku not in catalog:
                raise HTTPException(400, f"{sku} is not in the catalog")
            decision = {"match": "matched", "sku": sku}
        else:
            raise HTTPException(400, "action must be 'accept', or 'override' with a sku or not_in_catalog")
        record = {
            "action": o.action, **decision,
            "system": {"match": li.get("match"), "sku": li.get("sku")},
            "raw": li.get("raw"),
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with lock:
            data = overrides()
            data[f"{o.email}#{o.line}"] = record
            overrides_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = overrides_path.with_name(overrides_path.name + ".tmp")
            tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(overrides_path)
        return {**record, "part": part(decision["sku"])}

    return app


app = create_app(
    emails_dir=Path(os.environ.get("APP_EMAILS") or ROOT / "data" / "dev" / "emails"),
    parsed_path=Path(os.environ.get("APP_PARSED") or ROOT / "parsed.json"),
    overrides_path=Path(os.environ.get("APP_OVERRIDES") or HERE / "overrides.json"),
)

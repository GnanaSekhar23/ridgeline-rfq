# CLAUDE.md — Ridgeline RFQ Inbox parser

## What we are building
A CLI: `parse --emails <dir> --out parsed.json` that reads every .eml, classifies it
(rfq, rfq_revision, purchase_order, vendor_quote, status_inquiry, auto_reply, other),
extracts line items, and flags needs_review. The contract is `data/README.md`; the brief is
`ASSESSMENT.md`. Read both before changing behaviour. Output must pass
`python data/check_format.py parsed.json --emails data/dev/emails`.

## Architecture (keep to it)
1. `rfq/mime.py` — headers, body, quoted-history split, attachments, inline cid images, nested .eml.
2. `rfq/extractors/` — xlsx (openpyxl: skip hidden sheets, sheet names, merged notes, strikethrough),
   csv, docx (iterate body in order so headings stay with tables), pdf (encrypted → error,
   text → pdfplumber, scanned → pypdfium2 page images, page cap), image (Pillow → PNG, tiny inline
   logos flagged). Every extractor returns a `Doc` and never raises. Every text line gets a stable
   row ID like `[body!B12]`, `[Sheet!R5]`, `[file.pdf!P1L8]`.
3. `rfq/dedupe.py`, `rfq/threads.py` — duplicates and `revises` links in code, no model.
4. `rfq/prompt.py`, `rfq/llm.py`, `rfq/schema.py`, `rfq/cache.py` — ONE OpenAI structured-output
   call per email (vision for images/scans), Pydantic discriminated union
   (RFQ | Revision | PurchaseOrder | NoItems). Cache key = sha256(model + prompt_version + input).
   Only valid results are cached. Retries on 429/5xx/timeout only; one repair retry on schema error.
5. `rfq/validate.py` — code fills raw/qty/uom from real cells via row_id, drops unknown row IDs and
   struck rows, grounding check for free text, qty ≠ size/schedule/class/price, uom normalisation,
   coverage check, silent-loss guard (request with 0 lines and no flag → needs_review).
6. `rfq/matcher.py` (optional) — code decides SKU from attributes; the model never picks a SKU.
7. `rfq/costlog.py` → `runs/<id>/calls.jsonl`, `reports/cost.md`.
   Failure store → `runs/<id>/failures.jsonl` with a `retryable` flag; `parse --retry-failed <run>`.
8. `eval/eval.py` — scores against `data/dev/answer_key.json`, with component modes → `reports/eval.md`.
9. `app/` (optional) — FastAPI + one HTML page, reads files only, no model calls.

## Hard rules
- NEVER read, print, cat, or echo `.env` or the value of OPENAI_API_KEY. Read the key only via
  `os.environ` in code. Never write it to logs, runs/, cache/, or request.json.
- NEVER special-case dev data: no email IDs, customer names, subjects, or exact strings from
  `data/dev` in code or prompts. A held-out inbox of ~40 different emails is the real test.
  Fix the general cause, not the example.
- `parse` must NEVER read `answer_key.json`. Only `eval/` may.
- One bad email must never crash the run: per-email try/except → flagged entry, keep going.
- No API key + cache miss → flagged entry, never a crash.
- No outbound calls except the OpenAI API. Nothing sends email.
- Must run on Windows (native Python 3.11+). Use pathlib, no shell-specific code.
- Default model comes from `rfq/config.py`; temperature 0.

## How to work
- Small steps. After each step: run tests (`pytest -q`), run parse on dev, run eval if it exists,
  then stop and tell me what changed and what the numbers are. I commit.
- Prefer clear, boring code over clever code. Type hints. Short functions.
- When an eval number drops, show me which emails/lines changed before "fixing" anything.

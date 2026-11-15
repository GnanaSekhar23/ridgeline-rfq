# Running it

Python 3.11+ (tested on Windows with 3.11.9 and 3.14).

## Setup

```
python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate
pip install -e .
```

If PowerShell blocks `activate`, run `Set-ExecutionPolicy -Scope Process Bypass` first.

The OpenAI key is read from `OPENAI_API_KEY` (or a `.env` file). **No key is needed for the dev
inbox**: every model answer is cached in `cache/`.

## Run

```
rfq parse --emails data/dev/emails --out parsed.json
python data/check_format.py parsed.json --emails data/dev/emails
```

- A second run makes **0 model calls** (answers come from the cache).
- No key and no cached answer: that email is flagged `needs_review`; the run never crashes.
- After a provider outage: `rfq parse --emails <dir> --out parsed.json --retry-failed latest`
  re-calls only the emails that failed.

## Model and cost

- **Model:** `gpt-4.1`, one call per email, temperature 0. Photos and scanned pages go in as images.
- **Dev cost:** 23 calls, **$0.37 total, about $0.016 per email**. Details in `reports/cost.md`.
- **Catalog matcher:** on by default, in the same call. See `MATCHER.md`.

## Check it

```
python eval/eval.py parsed.json    # score vs the dev answer key -> reports/eval.md
pytest -q                          # 143 pass, 1 known failure (xfail)
```

## Review app (optional)

```
uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000: each email, its extracted lines with their source and catalog match,
and buttons for a rep to accept or override a match. It makes no model calls.

## Recording

Link: _to be added_
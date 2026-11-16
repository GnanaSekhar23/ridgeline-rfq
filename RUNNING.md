# Running it

Python 3.11+ (tested on Windows with 3.11.9 and 3.14).

## Setup

Windows PowerShell:

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Windows cmd: same, but activate with `.venv\Scripts\activate.bat`.

macOS / Linux:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

If PowerShell blocks `activate`, run `Set-ExecutionPolicy -Scope Process Bypass` first. Activate
the venv again in every new terminal.

The OpenAI key is read from `OPENAI_API_KEY` (or a `.env` file in this folder). **No key is needed
for the dev inbox**: every model answer is cached in `cache/`.

## Run

Dev inbox:

```
rfq parse --emails data/dev/emails --out parsed.json
python data/check_format.py parsed.json --emails data/dev/emails
```

Another inbox, e.g. the held-out set in a folder called `heldout/emails`:

```
rfq parse --emails heldout/emails --out heldout_parsed.json
python data/check_format.py heldout_parsed.json --emails heldout/emails
```

- The output contains exactly the `.eml` files in the folder you pass.
- The first run calls the model once per email (with your key) and saves each answer in `cache/`.
  Running the same command again, even without a key, gives the same result with 0 model calls.
- No key and no cached answer: that email is flagged `needs_review`. The run never crashes.
- After a provider outage, re-call only the emails that failed:
  `rfq parse --emails heldout/emails --out heldout_parsed.json --retry-failed latest`
- If `rfq` is not found, activate the venv, or use `python -m rfq parse ...` instead.

## Model and cost

- **Model:** `gpt-4.1`, one call per email, temperature 0. Photos and scanned pages go in as
  images. Change it with `--model` or the `RFQ_MODEL` variable.
- **Dev cost:** 23 calls, **$0.37 total, about $0.016 per email** (details in `reports/cost.md`).
- **Catalog matcher:** on by default, in the same call. See `MATCHER.md`.

## Check it

```
python eval/eval.py parsed.json    # dev only: score vs the dev answer key -> reports/eval.md
pytest -q                          # 143 pass, 1 known failure (xfail)
```

## Review app (optional)

```
uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000 to see each email, its extracted lines with their source and catalog
match, and buttons for a rep to accept or override a match. It makes no model calls. It shows the
dev inbox by default; for another inbox, set `APP_EMAILS` (the email folder) and `APP_PARSED`
(its output file) before starting it.

## Recording

Link: https://docs.google.com/videos/d/1__Pg4BfPvQcYOFtuNKyW1ZYzm__wmL89fQJg43NI7hM/play?usp=sharing
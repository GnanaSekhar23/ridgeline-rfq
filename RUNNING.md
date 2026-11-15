# Running it

Python 3.11+ on Windows (native), macOS or Linux. Tested on Windows with 3.11.9 and 3.14.

## Setup

Create the venv, activate it, and install. This installs the pinned `requirements.txt` and the
`rfq` command.

**Windows PowerShell** (5.1 has no `&&`, so one command per line):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

If PowerShell refuses to run `Activate.ps1` (script execution disabled), allow it for this window
only with `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.

**Windows cmd:**

```
python -m venv .venv && .venv\Scripts\activate.bat && pip install -e .
```

**bash** (macOS / Linux; on Windows Git Bash use `.venv/Scripts/activate`):

```
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

**Activate the venv before running `rfq`** in each new terminal (the second line above). Without
activating, call it by path instead: `.venv\Scripts\rfq` on Windows, `.venv/bin/rfq` on
macOS / Linux. The same goes for `python` and `pytest` below.

The OpenAI key is read from the `OPENAI_API_KEY` environment variable, or from a `.env` file in
the repo root.

## Parse an inbox

```
rfq parse --emails data/dev/emails --out parsed.json
python data/check_format.py parsed.json --emails data/dev/emails
```

- **No key needed for dev.** Every model answer is cached in `cache/` (committed), so the dev
  inbox replays with 0 model calls. `--offline` guarantees no calls.
- **A new inbox** calls the model once per email (duplicates are skipped). A second run makes no
  calls.
- **No key and nothing cached:** that email comes back flagged with `needs_review`. The run never
  crashes.
- **`rfq parse ... --retry-failed latest`** re-calls the model only for the retryable failures
  of the last run, e.g. after a provider outage. Everything else comes from the cache.
- **Logs:** each run writes `runs/<id>/calls.jsonl` and `failures.jsonl`. Rejected model output
  goes to `runs/<id>/emails/<id>/response.json`, and the cost report to `reports/cost.md`.

## Model and cost

- **Model:** `gpt-4.1` (OpenAI), one structured-output call per email, temperature 0. Scanned
  pages, photos and pasted images go in as images. Change the model with `--model` or
  `RFQ_MODEL`.
- **Catalog matcher:** on by default. The model normalizes each line's attributes in the same
  call, and code picks the part (see `MATCHER.md`). `RFQ_MATCHER=0` turns it off; that setting
  has no cache, so it calls the model.
- **Dev cost:** 23 model calls (1 duplicate skipped), 120k input and 26k output tokens,
  **$0.37 in total, about $0.016 per email** (`reports/cost.md`). Prices are in `rfq/config.py`.
- **`rfq estimate --emails <dir>`** prices a run before making it.

## Evaluate and test

```
python eval/eval.py parsed.json            # vs data/dev/answer_key.json -> reports/eval.md
python eval/eval.py parsed.json --baseline reports/eval.json   # what changed since last time
pytest -q                                  # 143 tests; synthetic inbox replays from tests/synthetic/cache
```

## Review app

```
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Pick an email to see:
- its headers;
- the current, forwarded and quoted text;
- its attachments (images and scanned pages shown);
- the extracted lines, each with its catalog match, SKU, catalog description and reason.

**Accept**, **Use SKU** or **Not in catalog** saves the rep's decision to `app/overrides.json`.
The app reads `parsed.json`, the emails and the catalog only. It makes no model calls and loads
nothing from the internet. Set `APP_EMAILS`, `APP_PARSED` and `APP_OVERRIDES` to point it
elsewhere.

## Recording

Link: _to be added_.

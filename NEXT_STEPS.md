# Next steps

## Where we are

Steps 1–4 of the plan are done. **40 tests pass** (`pytest -q`). `parse` runs on the dev inbox and
`check_format.py` passes, but every email still comes back as `other` with no lines, because
there is no model call yet. Eval baseline: 19 silent losses, 20 lost requests, 0/210 lines.

| Step | What it gave us |
|---|---|
| 1. Skeleton | `rfq parse --emails <dir> --out parsed.json`. Each email is processed separately, so one bad email can't stop the run. The output file is written safely in one go. Settings live in `rfq/config.py`, and the API key is read from `.env`. |
| 2. Eval | `eval/eval.py` scores against the answer key using the README's grading rules. Phrase checks match whole words only. `--baseline` shows which emails and lines changed since the last run. Scoring the answer key against itself gives 100%. |
| 3. MIME | `rfq/mime.py` splits each email into its current text, forwarded text and quoted history. It also collects attachments, inline images with their alt text, and attached emails. `rfq inspect <dir>` prints how emails were split. |
| 4. Extractors | `rfq/extractors/` reads xlsx, csv, docx, pdf (text pages, scans, text with a big picture, encrypted), images (logos skipped), html/txt and attached emails. Every line gets a stable ID like `[body!B12]`, `[Sheet!R5]` or `[f.pdf!P1L8]`. Extractors never raise an error. Hitting a limit is always noted, and `read_problems()` lists those notes plus any errors. |

Decisions already made that later steps rely on:
- Quoted history is **kept and marked** (`body!Q…`). It is allowed as a line source only for
  `rfq_revision`, and for a `purchase_order` that refers to quoted items ("go ahead with items 1, 2 and 4").
- Forwarded content (`body!F…`) counts as the request when one of our reps forwards it.
- An email that fails completely comes back as `rfq` with `needs_review: true`. A wrong review
  flag costs minutes; a lost request costs a customer.
- Things the dev inbox has already shown: E017 "BOM attached" with only a logo (attachment missing),
  E022 encrypted PDF, E005 old revision on a hidden sheet, E010 pasted screenshot plus a logo,
  E013 bounce with our own supplier request inside.

## What's left

### 5. Duplicates and thread links (code only, no model)
- `rfq/dedupe.py`: find the same request sent twice by comparing normalised bodies plus the
  content of attachments, ignoring "resend" wording, signatures and dates. The email with the later
  `Date:` gets `duplicate_of` set to the original's ID and `line_items: []`, and keeps the
  original's classification.
- `rfq/threads.py`: work out `revises` from `In-Reply-To` / `References`, with a fallback on the
  normalised subject plus sender's domain. Link only to an email that is in this inbox.
- Tests use made-up email pairs. Check the result against the two links in the eval.

### 6. The model call
- `rfq/schema.py`: Pydantic schemas, one per type of answer: RFQ, Revision, PurchaseOrder,
  and NoItems (vendor quote, status inquiry, auto reply, other). Each line refers to a `row_id`.
- `rfq/prompt.py`: shows the email, with every line's ID, plus images (scans, photos, screenshots).
  It covers the rules from the README: classify what the current message does, carry the
  headings, notes, sheet names and subject that apply to each line, and never invent a spec.
  **Workbooks with several visible sheets:** the model decides whether the sheets are sections of
  one order (use all of them) or versions of the same list (use the newest, judged by sheet name,
  file name, dates or what the email says). If that's unclear, it sets `needs_review`.
- `rfq/llm.py`: **one** OpenAI call per email using structured output, temperature 0, with
  images when there are any. It retries only on rate limits, server errors and timeouts
  (tenacity), and makes one repair attempt if the answer doesn't fit the schema.
- `rfq/cache.py`: responses are saved under `cache/<sha256>.json`. The key is a hash of model +
  prompt version + rendered input + image hashes. Only valid answers are saved. The cache is committed.
- `rfq/costlog.py`: `runs/<id>/calls.jsonl` records tokens, dollars, time taken and whether the
  answer came from the cache.
- No key and nothing cached → that email is flagged, not crashed. Run once on dev with the key,
  commit the cache, then re-run without the key: the output must be identical, with 0 live calls.

### 7. Validation (code checks what the model said)
- `rfq/validate.py`:
  - **Lines:** drop lines whose row ID doesn't exist or whose row is struck. Refill `raw`,
    `qty` and `uom` from the real cells where we can.
  - **Description:** check that the free text is grounded in the source (rapidfuzz).
  - **Quantity and unit:** a quantity can't be a size, schedule, class or price. Units are
    normalised to the allowed list.
  - **Coverage:** detect rows that look like items but have no line.
  - **Silent-loss guard:** a request with 0 lines and no flag becomes `needs_review`.
  - **Read problems:** add `read_problems()` to the review reason.
  - **Review flag scope:** only `rfq`, `rfq_revision` and `purchase_order` can be flagged.
- Tune the prompt against the eval. When a number drops, look at the changed emails and lines
  before fixing anything. Fix the general cause, never a dev string.

### 8. Robustness and cost
- `runs/<id>/failures.jsonl` with a `retryable` flag, and `rfq parse --retry-failed <run>`.
- Time limit per email, and checks on oversize inputs from start to finish.
- `reports/cost.md`: model calls, tokens and dollars per email on dev.

### 9. Write-ups
- `RUNNING.md`: one setup step, model(s) used, cost of a run, link to the recording.
- `DECISIONS.md` (≤ 2 pages), with the four required sections plus time spent:
  surprise in the data, disagreement with the brief, predicted held-out numbers and the two kinds
  of email we expect to get wrong, and how it runs for real (webhook volume, provider outage,
  300-page PDF, duplicate delivery).
- `AI_USAGE.md` (≤ 1 page), plus `ai-sessions/` exported and searched for `sk-` before sending.

### Optional, if time allows (10)
- `rfq/matcher.py` + `MATCHER.md`: code picks the SKU from attributes, and the model never picks a SKU.
- `app/`: a read-only FastAPI app with one page, to walk one email through the system.

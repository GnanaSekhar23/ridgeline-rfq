# DECISIONS

**Dev result** (`reports/eval.md`): 24/24 classification, 210/210 lines (0 hallucinated, 0 silent
losses), qty/uom/source/context 100%, links 2/2, review 2/2. Matcher: 210/210, 0 confident wrong,
16/16 not-in-catalog. Cost: 23 calls, $0.37 for the dev inbox (~$0.016/email, gpt-4.1).
Time spent: **~11 hours** (Sat evening + Sun), plus ~1 hour reading the package beforehand.

## Something in the data that surprised me
The hardest email was not the messiest one. The threads, forwards and hidden spreadsheet sheet
(E005 hides its old "Rev A (old)" revision behind the current one) were handled once the text
was laid out well. The hard one was a clean scanned table (E009): the model read every item
correctly but took quantities from the neighbouring row, 20/32 right. Rendering at 200 DPI changed
nothing, and the token count showed why: the API downscales high-detail images to 768 px on the
short side, so extra DPI is thrown away before the model sees it. Cutting scanned pages into
overlapping horizontal strips gives each row more pixels: 32/32, for ~$0.013 more per scanned page.
It only applies to pages with no text layer, so normal emails cost the same.

## Something in the brief / README I disagree with, and what I did
`needs_review` is only allowed on requests, but "an email we could not read" is not known to be a
non-request. If parsing or the model fails, we don't know what the email was, so I return it as
`rfq` + `needs_review` with the reason, never as `other`. A wrongly flagged non-request costs a rep a
minute; a silently dropped request costs a customer. This can add a phantom request on a bad day,
and I accept that trade.
Second, a single run per prompt version is a noisy eval: one dev line flipped between right and
wrong on unrelated prompt edits. I gate prompt changes on "no dev metric gets worse", and with more
time I would run each version 3× and compare averages.

## Predicted held-out numbers, and the two kinds of email I expect to get wrong
Dev is 100% after several rounds of fixes chosen by reading dev errors, so I don't expect that on
held-out. My 9 synthetic emails (situations dev doesn't show) give 9/9 on the core checks, 8/9 on
the stricter ones. Prediction: **classification ~92–96%, line recall ~88–93%, qty ~90%, silent
losses 0–1, matcher confident-wrong 0–2.** The two kinds I expect to get wrong:
1. **Scans, photos and handwriting.** There is no row to point at, so the model transcribes, and
   code can't check raw/qty against a source. Misread quantities and long or short `raw` text
   are where my numbers will drop.
2. **Specs carried onto loosely related items.** "Six tees … same, and a couple of caps" puts the
   tees' SCH 40 / butt weld onto the caps (synthetic S09, a strict xfail test). A prompt rule fixed
   it but cost dev accuracy elsewhere, so it is tracked rather than shipped.

## How this runs for real
- **3,000 emails/day by webhook.** Webhook → queue (SQS) → stateless workers running the same
  `process_email`; cache and results move to shared storage (S3/Redis + Postgres). ~2 emails a
  minute, ~$50/day at today's per-email cost. *Designed, not built.*
- **Provider down for two hours.** Retries with backoff only on 429/5xx/timeouts; then the email is
  flagged `needs_review`, logged as `retryable` in `failures.jsonl`, and nothing bad is cached. Reps
  see it flagged meanwhile; `rfq parse --retry-failed latest` re-calls only those emails.
  *Built and tested* (outage, partial outage, recovery). Not built: a second provider.
- **A 300-page PDF.** Read the first 20 text pages / 6 scanned pages, mark it truncated, and flag
  the email with the reason, so nothing is cut silently. *Built.* Real fix: page-chunked calls
  merged in code.
- **The same email delivered twice.** Same Message-ID or same content means it is detected as a
  duplicate, and a replay hits the cache: no second call, identical output. *Built.*

## Where the model decides and where code decides
- **The model:** classification; which lines are items; the self-contained description; reading
  images; the catalog attributes of each line.
- **Code:**
  - MIME and every file format (hidden sheets, merged notes, strikethrough, encrypted PDFs).
  - Duplicates and thread links.
  - **raw/qty/uom for every text or table line.** The model returns a row ID and code copies the
    real cells ("the model points, code copies"), so a quantity can't be invented.
  - Dropping unknown, struck or out-of-place rows.
  - Every `needs_review` safety net.
  - **The SKU decision.** The model never picks a part.

## How I measured it
- `eval/eval.py` mirrors the README's grading, with whole-token phrase matching (so "sch40" can't
  match inside "sch400"). Every change was compared with `--baseline` against the last run.
- 143 unit tests on invented files, plus a fake model client.
- 9 synthetic emails replayed from cache.
- An audit of `rfq/` for dev-specific strings.
- Offline replay is byte-identical, and a fresh clone with no key makes 0 calls.

## What I rejected
- **A 4-shape Pydantic union sent to the model.** Strict output writes fields in schema order, so
  the model chose a type before reading. The first real run scored 7/24 with 15 silent losses. I
  replaced it with one flat schema (reasoning, then type, then lines); code enforces the type rules.
- **Prompt versions p5/p6.** They fixed synthetic cases but regressed dev, so I reverted them.
- **Prompt examples copied from dev emails.** I replaced them with invented ones; scores didn't move.
- **React for the review page.** Polish counts for nothing here, and it would need a build step.

## What I know is broken / what's next
- **Broken:** S09 (spec carry-over above). One answer is capped at 100 lines, so a longer BOM gets
  flagged and is incomplete. Post-processing rules (image `raw` trimming, overridden-default
  removal, matcher normalisations) were motivated by dev errors, so their held-out value is unproven.
- **Next:** chunk long lists and PDFs; repeat-run evals; use `app/overrides.json` (rep decisions) as
  a live accuracy measure; a second provider behind the same schema.

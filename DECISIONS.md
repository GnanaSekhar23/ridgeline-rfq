# DECISIONS

On the 24 dev emails the parser gets every email type right (24/24) and finds all 210 line items
with the right quantity, unit, source and specs. The optional catalog matcher picks the right
part for 210/210 lines and never picks a wrong one. A full run of the dev inbox costs about $0.37
with gpt-4.1, around 1.6 cents per email. I spent about 11 hours on this.

## Something in the data that surprised me

I expected the messy emails to be the hard part: long threads, forwards, an Excel file that
hides an old revision on a hidden sheet. Once each file was turned into clean, numbered lines,
those were fine. The hardest one was a clean scanned table (E009). The model read every item
correctly but kept taking the quantity from the row above or below, so only 20 of 32 quantities
were right. Making the scan sharper (200 DPI) did nothing. When I checked the token counts I saw
why: OpenAI shrinks large images to 768 pixels before the model sees them, so the extra detail
was thrown away. Cutting each scanned page into overlapping horizontal strips gave every row more
pixels, and all 32 quantities came out right. It costs about one extra cent per scanned page, and
only pages that are pure images get cut up, so normal emails cost the same.

## Something in the brief I disagree with, and what I did

The README treats `needs_review` as a simple yes/no. At 3,000 emails a day that isn't enough. If
a rep only sees "needs review", they have to open every flagged email to find out why, and they
can't read everything. A flag is only useful if it tells the rep what to do.

So every flag in my output carries a specific reason the rep can act on without digging, for
example "AldenMarine_RFQ.pdf: PDF is password-protected", "BOM mentioned but no attachment",
"refers to quote Q-26-05120; its items are not in this email", or "only the first 20 pages were
read". Problems on our side are kept apart from problems in the email. If the model call times
out or the provider is down, the email is flagged and also logged as retryable, so
`--retry-failed` can process it again without a rep touching it; it only needs a person if it
keeps failing. And a flag is never used as a catch-all:
a vague quantity like "a couple" gets `qty: null`, not a review flag, because the rep can quote
the rest and confirm that one number.

In production I'd go one step further and give each flag a type (missing attachment, unreadable
file, reference to an old order, partly read, system error) so reps can sort and route them, for
example sending all system errors to one queue and "refers to an old order" to the rep who owns
that customer.

## My predicted held-out numbers, and two kinds of email I expect to get wrong

Dev is at 100%, but I fixed things by looking at dev mistakes, so I don't expect that on emails
I haven't seen. I also wrote 9 made-up emails for situations dev doesn't cover (out-of-office,
"same as our last order", a struck-through row, a Word file with a photo of a list, and so on),
and 8 of 9 pass every check. My guess for the held-out inbox: email type right 92-96% of the
time, 88-93% of lines found, quantities right on about 90%, 0-1 silent losses, and 0-2 wrong
catalog parts.

The two kinds I expect to get wrong:

1. **Scans, phone photos and handwriting.** For text and spreadsheets, the model only points at
   a row and my code copies the real text and quantity, so it can't make numbers up. For a
   picture there's nothing to copy from, so I rely on the model's reading. That's where
   quantities will be wrong.
2. **Specs applied to the wrong item.** If a customer writes "six tees, SCH 40 butt weld, same
   again, and a couple of caps", the model also gives the caps SCH 40 butt weld. A prompt rule
   fixed this but broke other dev emails, so I left it out. It's a known failing test (S09).

## How this runs for real

- **3,000 emails a day by webhook.** I'd put each email on a queue and have a few workers run the
  same per-email code, with the cache and results in shared storage instead of local files.
  That's only about 2 emails a minute and roughly $50 a day. *I designed this but didn't build it.*
- **The model provider is down for two hours.** Each call retries a few times, but only for
  errors worth retrying (rate limits, server errors, timeouts). After that the email is flagged
  for review and logged as "retryable", and nothing broken is saved to the cache. When the
  provider is back, `rfq parse ... --retry-failed latest` re-runs only those emails. *Built and
  tested.*
- **A customer sends a 300-page PDF.** I read the first 20 text pages (or 6 scanned pages), mark
  the file as cut short, and flag the email with that reason, so nothing is dropped silently.
  *Built.* The proper fix is to read it in chunks and merge the results.
- **The same email is delivered twice.** It's detected as a duplicate and answered from the
  cache: no second model call, same output. *Built.*

## Where the model decides and where my code decides

The model decides what kind of email it is, which lines are items, how to describe each item
fully (carrying specs from headings, notes and sheet names), and what it reads in pictures.

My code does everything that can be checked. It opens every file type (skipping hidden sheets,
noticing struck-through rows, catching password-protected PDFs). It finds duplicates and reply
threads. Most importantly, for text and table lines the model only gives a row ID, and the code
copies the real text, quantity and unit from that row. Code also picks the catalog part from the
model's description of the item; the model never chooses a SKU.

## How I measured it

- **An eval script** that scores my output the way the README describes grading. I compared every
  change against the previous run to see what got better and what got worse.
- **143 unit tests** on small made-up files, with a fake model so they run free.
- **The 9 made-up emails**, replayed from saved answers.
- **A check for dev-specific code**, and **a fresh clone with no API key**, which makes zero model
  calls and gives identical output.

## What I tried and dropped

- **Four different answer shapes for the model** (one per kind of email). The model had to pick
  a shape before reading the email, and my first real run got only 7 of 24 types right. I
  switched to one simple shape where the model writes its reasoning first, then the type, then
  the lines.
- **Two prompt versions (p5, p6)** that fixed my made-up cases but made dev worse. I rolled them
  back.
- **Prompt examples copied from dev emails.** I found them in an audit and swapped in invented
  ones; the scores didn't change.
- **React for the review page.** The brief values clarity, not polish, and React adds a build step.

## What I know is broken, and what's next

The spec carry-over problem above (S09). One model answer holds at most 100 lines, so a longer
list gets flagged and is incomplete. Some small clean-up rules (shortening the text read from a
label photo, removing a default spec a line overrides, a few matcher rules) came from dev
mistakes, so I don't know yet how much they help on new emails.

Next I'd split long lists and PDFs into chunks, run each prompt version several times, use the
rep decisions saved by the review app as a live accuracy measure, and add a second model provider
as a fallback.
# AI_USAGE

## Setup

- **Coding agent:** Claude Code in VS Code (Opus 5.5). All the code was written in one session,
  `3263c3bb-f65e-4b08-869b-829429b58078`, and its log is in `ai-sessions/`.
- **Instruction files:** `CLAUDE.md` holds the architecture and a few hard rules: never read
  `.env`, no logic written for specific dev emails, `parse` must never read the answer key, and
  stop after each step so I can review. `.claude/settings.json` blocks the agent from reading `.env`.
- No subagents, skills or MCP servers.
- A separate Claude chat was used for planning (reading the brief, designing the architecture,
  drafting `CLAUDE.md`) and for reviewing the agent's output.

## How I worked

I had Claude Code propose a plan first, corrected it, and then built one step at a time:
skeleton, eval script, email parsing, file readers, duplicates and threads, the model call,
reliability, made-up test emails, matcher, review app. I built the eval script before any model
code so I could measure every change from the start. After each step I read the summary and the
code changes, ran the tests or the eval, asked about anything I didn't understand, and
committed. Before the first paid run I made it estimate the cost. For prompt changes I used one
rule: if any dev number gets worse, roll it back.

## Three moments

**1. The agent was wrong and I caught it (commit `43c0469`).** Its first design gave the model
four different answer shapes. The first real run got only 7 of 24 email types right and lost 15
customer requests. The eval showed the problem straight away, and the model's own notes gave
away the cause: it wrote "this is an rfq" but labelled the email `vendor_quote`, because it had
to pick the shape before reading. I had it switch to one simple shape with the reasoning first.
The next run got 24 of 24 at a third of the cost.

**2. I overruled it (commits `8475a67`, `42420b0`).** Its eval matched phrases loosely, so
"sch40" also counted inside "sch400", and it said that was acceptable. I said no, because it would
make my own score look better than it was, and had it match whole words with a test for both
cases. Later I asked it to check its own code for anything fitted to the dev emails. It found
that one prompt example it wrote was almost the exact answer to a graded dev line, and that a
test it called made-up used dev text. I had both replaced with invented examples and decided to
keep whatever score came out. It didn't change.

**3. It saved me real time (commit `61385cb`).** I asked whether the file readers handle things
the dev emails don't show: a photo pasted inside a Word file, a PDF page with text and a picture,
and limits that cut content off. Within minutes it found that pictures inside Word files and
pictures on mixed PDF pages were being ignored. On the hidden inbox those would have been
requests lost without any warning. It fixed both, added tests with made-up files, and made every
size limit flag the email for review.
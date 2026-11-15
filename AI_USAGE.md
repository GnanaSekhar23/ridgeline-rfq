# AI_USAGE

## Setup
- **Claude Code** (VS Code extension, model Opus 5.5) wrote the code. It ran in one session,
  `3263c3bb-f65e-4b08-869b-829429b58078`, whose log is in `ai-sessions/`.
- **Instructions:** `CLAUDE.md` (architecture plus hard rules: never read `.env`; no dev-specific
  logic; `parse` never reads the answer key; stop after every step) and `.claude/settings.json`
  (denies reading `.env`). No subagents, skills or MCP servers.
- A separate Claude chat was used for planning (reading the brief, designing the architecture,
  drafting `CLAUDE.md`) and for reviewing the agent's output.

## How I worked
I gave Claude Code one step at a time from a plan it proposed and I corrected. The order was:
skeleton, then the eval harness (before any model code), MIME, extractors, duplicate and thread
links, the model call, reliability, synthetic emails, matcher, app. After each step I:
- read its summary and the diff (Manual or "Edit automatically" mode);
- ran `pytest`, `rfq inspect` or the eval;
- committed;
- asked it to explain anything I didn't follow.

I made it estimate cost before the first paid run. Every prompt change was compared against the
last run with `--baseline`, under a rule I set: revert on any dev regression. I also asked it to
test cases the dev set doesn't contain, and to audit its own work for dev-fitting.

## Three moments
1. **The agent was wrong, and I caught it.** Its first model-call design used a 4-shape union
   schema. The first real run scored 7/24 classification with 15 silent losses. The eval caught it,
   and the model's own rationales ("this is an rfq…" next to `vendor_quote`) showed why: strict
   output made it commit to a type before reading. I had it switch to one flat schema with
   reasoning first and code-side rules. Result: 24/24 and 0 silent losses, at a third of the cost.
   *Commit `43c0469`; session `3263c3bb…`.*
2. **I overruled it.** Its eval scorer matched phrases as substrings, and it judged "sch40 also
   matches inside sch400" *acceptable*. I said no, because that would inflate my own score. I had
   it match on whole tokens and test both cases. Later, I had it audit `rfq/` for dev-fitting. It
   found that a prompt example it had written was essentially the answer to one graded dev line,
   and that a test it had called "made-up" copied dev text. I had both replaced with invented
   examples and decided to keep the honest score whatever it was (it didn't move).
   *Commits `8475a67`, `42420b0`; session `3263c3bb…`.*
3. **It saved me real time.** I asked whether the readers handle cases dev doesn't show: a Word
   file with a pasted photo, a PDF page with text plus a picture, limits that cut content. In
   minutes it found that Word pictures and the picture half of mixed PDF pages were silently
   dropped, which would have been silent losses on the held-out inbox. It fixed both with
   invented-file tests, and made every limit flag the email.
   *Commit `61385cb`; session `3263c3bb…`.*

# Catalog matcher

**The model normalizes, code decides.** In the existing extraction call (no extra call), each
line also carries `attrs`: the item in the catalog's own vocabulary. Those values are `product`,
`size`, `spec`, `material`, `ends` and `extra`, and the allowed values are generated from
`data/catalog.csv` into the schema. `null` means "not stated" and `other` means "stated, but not
a value we stock". `rfq/matcher.py` picks the part. The model never sees or picks a SKU.

The matcher is **on by default** (prompt `p7`). `RFQ_MATCHER=0` turns it off; its answers are
not cached, so that setting would call the model.

## How a line is decided

1. **Candidates.** The catalog parts with the same `product` and the same numeric size
   (`1 1/2"` = `1-1/2` = `1.5`, `6" x 4"` = `6 x 4`). A bolt's thread pitch and a length in feet
   (`3/4"-10 x 6 ft` rod) are not part of the size.
2. **Hard filters.** Every stated `spec` / `material` / `ends` / `extra` must agree, because a
   part one attribute off is a wrong quote. Agreement is exact, with two exceptions:
   - A **less specific material** agrees with a more specific one (`GALV` ⊆ `MI GALV`), but never
     the reverse, and never a different grade (`316 SS` ≠ `304 SS`).
   - **Threaded** is satisfied by `THD` or `TBE` (threaded both ends), but not `TOE`.
3. **Evidence check.** Each attribute the model filled in must be supported by the line's own
   description or raw text (`316L` supports `A403 WP316L`, `galv` supports `MI GALV`, `npt`
   supports `THD`). An unsupported one is **ignored**. That can only widen the candidate set; it
   can never force a part.
4. **Narrowing by text.** If several parts remain and the model left an attribute null, code may
   narrow by a catalog value that the customer's text supports. Example: E021's sheet name
   "PIPE - SCH 80 SMLS" leaves only `A106B SMLS` among the SCH 80 pipes. It narrows only when at
   least one part survives, and the reason says so: `(material A106B SMLS from text)`.
5. **Verdict.**
   - 0 parts: `not_in_catalog`, with the nearest stocked part and what differs.
   - 1 part: `matched`.
   - More than 1: `ambiguous`, with up to 10 `candidates` and the attributes that tell them apart.
   - `other`, an unstocked size, or an unknown product: `not_in_catalog`.
   - No size or no product: `ambiguous`.
   - Every verdict comes with a one-line `match_reason` a rep can check.

**Never left to the model alone:** choosing between candidates, deciding not-in-catalog, and
filling in an attribute the customer didn't state.

**Where the model helps:** mapping customer wording ("Class 150", "malleable black", a sheet
name) onto catalog terms.

## Measured on dev (`eval/eval.py` → `reports/eval.md`)

| | first version | after code fixes (0 new calls) |
|---|---|---|
| confident wrong matches | 0 | **0** |
| not-in-catalog recall | 16/16 | **16/16** |
| match accuracy | 184/209 (88%) | **208/209 (99.5%)** |
| predictions | 168 matched · 26 NIC · 15 ambiguous | 192 matched · 16 NIC · 1 ambiguous |

**What the code fixes changed:**
- **Narrowing by text:** 14 E021 pipes (sheet name → SMLS).
- **Material subset:** 7 E007 galv fittings.
- **THD ≈ TBE:** E002's close nipple.
- **Length in feet:** E010's threaded rod.

**The one miss left: E018 "PTFE thread tape", left ambiguous on purpose.** No size was given, and
the catalog has a size-less tape and a `1/2 x 520` one. Picking the size-less one because "no
size was stated" would be a guess, so it's left to a rep.

**Cost:** the attributes add output tokens. Dev costs **$0.3709** with the matcher vs $0.2753
without (+$0.10, about $0.004 per email).

## Caveats

- **Tuned on dev.** These fixes were chosen by reading the dev errors. Each one is a general rule,
  but held-out data will show cases dev doesn't, such as other material families or unusual
  sizes. Expect accuracy below 99.5% there, with errors still landing on *ambiguous* or
  *not in catalog* rather than a wrong part. The evidence check and exact hard filters are what
  hold that line.
- **Material subset in the other direction.** A customer's `GALV` agrees with `A53 GALV` *and*
  `MI GALV`. Product and size usually separate those, but where both exist the result is
  ambiguous, which is correct.
- **Narrowing trusts the line's text.** It narrows on what's written in the line's description,
  which the model composed from the email. If the model carries a spec onto a line that doesn't
  apply (synthetic S09), narrowing inherits that mistake.
- **E005-6 context.** With `p7`, context carried is 208/209. That line also flipped under an
  unrelated prompt change (`p6`), so it's treated as noise, not as a cost of the matcher.

**Next:** add matcher expectations to the synthetic set, a list of material families (CS / SS /
galv / MI) to catch more lines, and a reviewer UI to accept or overturn each verdict.

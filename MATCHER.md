# Catalog matcher

**The model normalizes, code decides.** In the existing extraction call (no extra call), each
line also carries `attrs`: the item in the catalog's own vocabulary. Those values are `product`,
`size`, `spec`, `material`, `ends` and `extra`, and the allowed values are generated from
`data/catalog.csv` into the schema. `null` means "not stated" and `other` means "stated, but not
a value we stock". `rfq/matcher.py` picks the part. The model never sees or picks a SKU.

The matcher is **on by default** (prompt `p8`). `RFQ_MATCHER=0` turns it off. That uses a
different prompt (`p8-nomatch`) with no cached answers, so it would call the model.

## How a line is decided

1. **Candidates.** The catalog parts with the same `product` and the same numeric size
   (`1 1/2"` = `1-1/2` = `1.5`, `6" x 4"` = `6 x 4`). A bolt's thread pitch and a length in feet
   (`5/8"-11 x 10 ft` rod) are not part of the size.
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
   narrow by a catalog value that the customer's text supports. For example, a sheet name or
   heading that states the pipe material leaves only that material among same-schedule pipes. It
   narrows only when at least one part survives, and the reason says so: `(material ... from text)`.
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

| | first version (p7) | p7 + matcher code fixes | **now (p8)** |
|---|---|---|---|
| confident wrong matches | 0 | 0 | **0** |
| not-in-catalog recall | 16/16 | 16/16 | **16/16** |
| match accuracy | 184/209 (88%) | 208/209 (99.5%) | **209/210 (99.5%)** |
| predictions | 168 matched · 26 NIC · 15 ambiguous | 192 · 16 · 1 | **193 · 16 · 1** |

p8 scores 210 lines instead of 209 because a validation fix (trimming an image line's raw to its
model / part-number line) made one nameplate line pair with the answer key; it matched correctly.
p8 replaced the prompt's examples with neutral invented ones; the matcher results did not change.

**What the matcher code fixes changed** (from the first version):
- **Narrowing by text:** 14 pipe lines whose sheet name stated the material.
- **Material subset:** 7 galvanized fittings written as plain "galv".
- **THD ≈ TBE:** one threaded nipple.
- **Length in feet:** one threaded-rod line whose size included its length.

**The one miss left: a thread-tape line with no size, left ambiguous on purpose.** The catalog has
a size-less tape and a sized one. Picking the size-less one because "no size was stated" would be
a guess, so it's left to a rep.

**Cost:** the attributes add output tokens. Dev costs **$0.3683** with the matcher (p8), against
$0.2753 without it when that was last measured (p4): about +$0.004 per email.

## Caveats

- **Tuned on dev.** The code fixes were chosen by reading dev errors. Each one is a general rule,
  but held-out data will show cases dev doesn't, such as other material families or unusual
  sizes. Expect accuracy below 99.5% there, with errors still landing on *ambiguous* or
  *not in catalog* rather than a wrong part. The evidence check and exact hard filters are what
  hold that line.
- **Material subset in the other direction.** A customer's `GALV` agrees with `A53 GALV` *and*
  `MI GALV`. Product and size usually separate those, but where both exist the result is
  ambiguous, which is correct.
- **Narrowing trusts the line's text.** It narrows on what's written in the line's description,
  which the model composed from the email. If the model carries a spec onto a line it doesn't
  apply to (synthetic S09), narrowing inherits that mistake.

**Next:** add matcher expectations to the synthetic set, and a list of material families
(CS / SS / galv / MI) to catch more lines. Reps can already accept or overturn each verdict in
the review app (`app/`, see `RUNNING.md`); their overrides in `app/overrides.json` are the data
for measuring the matcher on real traffic.

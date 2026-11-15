# Eval vs dev answer key

| metric | value |
|---|---|
| silent_losses | 0 |
| hallucinated_lines | 1 |
| lost_requests | 0 |
| phantom_requests | 0 |
| classification | 100.0% (24/24) |
| line_recall | 99.5% (209/210) |
| line_precision | 99.5% (209/210) |
| qty | 94.3% (197/209) |
| uom | 100.0% (209/209) |
| source | 100.0% (209/209) |
| context_carried | 100.0% (209/209) |
| links | 100.0% (2/2) |
| review_precision | 100.0% (2/2) |
| review_recall | 100.0% (2/2) |

## Missed key lines (1)

```
E023-1: 'MODEL: HV-800-FGS'
```

## Hallucinated / unpaired predicted lines (1)

```
E023: 'HALVORSEN VALVE CO. FORGED STEEL GATE VALVE MODEL: HV-800-FGS SIZE: 2 IN CLASS: 800 LB ENDS: NPT BODY: A105 TRIM: 13CR' [IMG_4417.jpg]
```

## Paired-line field errors (12)

```
E009-2: qty 6 != 4
    desc: 'FLANGES: 6 EA 1-1/2" WN 150# RF'
E009-25: qty 24 != 16
    desc: 'STUD BOLTS: 24 EA 5/8" x 3-1/2" B7 with 2 heavy hex nuts'
E009-3: qty 2 != 10
    desc: 'FLANGES: 2 EA 10" WN 150# RF'
E009-7: qty 2 != 4
    desc: 'FLANGES: 2 EA 8" WN 150# RF'
E009-6: qty 4 != 6
    desc: 'FLANGES: 4 EA 6" WN 150# RF'
E009-4: qty 6 != 8
    desc: 'FLANGES: 6 EA 3" WN 150# RF'
E009-19: qty 12 != 16
    desc: 'GASKETS: 12 EA 4" Spiral wound, 304/graphite, 150#'
E009-18: qty 16 != 12
    desc: 'GASKETS: 16 EA 3" Spiral wound, 304/graphite, 150#'
E009-10: qty 2 != 6
    desc: 'FLANGES: 2 EA 6" SO 150# RF'
E009-26: qty 24 != 48
    desc: 'STUD BOLTS: 24 EA 3/4" x 4-1/4" B7 with 2 heavy hex nuts'
E009-5: qty 6 != 12
    desc: 'FLANGES: 6 EA 4" WN 150# RF'
E009-12: qty 6 != 2
    desc: 'FLANGES: 6 EA 2" WN 150# RF'
```

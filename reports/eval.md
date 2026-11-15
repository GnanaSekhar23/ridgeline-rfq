# Eval vs dev answer key

| metric | value |
|---|---|
| silent_losses | 0 |
| hallucinated_lines | 1 |
| lost_requests | 0 |
| phantom_requests | 0 |
| classification | 100.0% (24/24) |
| line_recall | 98.6% (207/210) |
| line_precision | 99.5% (207/208) |
| qty | 94.7% (196/207) |
| uom | 100.0% (207/207) |
| source | 100.0% (207/207) |
| context_carried | 99.5% (206/207) |
| links | 100.0% (2/2) |
| review_precision | 66.7% (2/3) |
| review_recall | 100.0% (2/2) |

## Missed key lines (3)

```
E009-20: '20 | 8 | EA | 6" | Spiral wound, 304/graphite, 150#'
E009-26: '26 | 48 | EA | 3/4" x 4" | B7 w/ 2 heavy hex nuts'
E023-1: 'MODEL: HV-800-FGS'
```

## Hallucinated / unpaired predicted lines (1)

```
E023: 'HALVORSEN VALVE CO. FORGED STEEL GATE VALVE MODEL: HV-800-FGS SIZE: 2 IN CLASS: 800 LB ENDS: NPT BODY: A105 TRIM: 13CR' [IMG_4417.jpg]
```

## Paired-line field errors (12)

```
E005-6: must-not ['sch 40']
    desc: 'Gulf Terminals - Tank 14 Piping Modifications - Bid 26-0412; ALL FITTINGS BW SCH 40 A234 WPB UNLESS NOTED; TEES & REDUCERS; 6" x 4" Reducer, concentric, SCH 80'
E009-2: qty 6 != 4
    desc: 'FLANGES: 6 EA 1-1/2" WN 150# RF'
E009-25: qty 24 != 16
    desc: 'STUD BOLTS: 24 EA 5/8" x 3-1/2" B7 w/ 2 heavy hex nuts'
E009-3: qty 2 != 10
    desc: 'FLANGES: 2 EA 10" WN 150# RF'
E009-7: qty 2 != 4
    desc: 'FLANGES: 2 EA 8" WN 150# RF'
E009-4: qty 6 != 8
    desc: 'FLANGES: 6 EA 3" WN 150# RF'
E009-22: qty 8 != 2
    desc: 'GASKETS: 8 EA 10" Spiral wound, 304/graphite, 150#'
E009-10: qty 2 != 6
    desc: 'FLANGES: 2 EA 8" SO 150# RF'
E009-18: qty 16 != 12
    desc: 'GASKETS: 16 EA 4" Spiral wound, 304/graphite, 150#'
E009-5: qty 6 != 12
    desc: 'FLANGES: 6 EA 4" WN 150# RF'
E009-11: qty 2 != 4
    desc: 'FLANGES: 2 EA 10" SO 150# RF'
E009-8: qty 6 != 4
    desc: 'FLANGES: 6 EA 2" WN 150# RF'
```

## needs_review errors (1)

```
E002: key=False pred=True reason="The quantity for 'caps' is vague ('a couple'), and the material (316 SS) and thread type are implied but not explicitly stated for each item."
```

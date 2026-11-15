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
| qty | 100.0% (209/209) |
| uom | 100.0% (209/209) |
| source | 100.0% (209/209) |
| context_carried | 99.5% (208/209) |
| links | 100.0% (2/2) |
| review_precision | 100.0% (2/2) |
| review_recall | 100.0% (2/2) |
| matcher_confident_wrong | 0 |
| matcher_not_in_catalog_recall | 100.0% (16/16) |
| matcher_accuracy | 99.5% (208/209) |
| matcher_predictions | ambiguous=1, matched=192, not_in_catalog=16 |

## Missed key lines (1)

```
E023-1: 'MODEL: HV-800-FGS'
```

## Hallucinated / unpaired predicted lines (1)

```
E023: 'HALVORSEN VALVE CO. FORGED STEEL GATE VALVE MODEL: HV-800-FGS SIZE: 2 IN CLASS: 800 LB ENDS: NPT BODY: A105 TRIM: 13CR' [IMG_4417.jpg]
```

## Paired-line field errors (1)

```
E005-6: must-not ['sch 40']
    desc: 'ALL FITTINGS BW SCH 40 A234 WPB UNLESS NOTED. 6 | 2 | EA | 6" x 4" | Reducer, concentric, SCH 80'
```

## Matcher errors (1)

```
E018-6: miss key=matched RL-17191 pred=ambiguous 
    reason: ptfe thread tape: size not stated (2 stocked sizes)
```

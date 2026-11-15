# Eval vs dev answer key

| metric | value |
|---|---|
| silent_losses | 0 |
| hallucinated_lines | 0 |
| lost_requests | 0 |
| phantom_requests | 0 |
| classification | 100.0% (24/24) |
| line_recall | 100.0% (210/210) |
| line_precision | 100.0% (210/210) |
| qty | 100.0% (210/210) |
| uom | 100.0% (210/210) |
| source | 100.0% (210/210) |
| context_carried | 100.0% (210/210) |
| links | 100.0% (2/2) |
| review_precision | 100.0% (2/2) |
| review_recall | 100.0% (2/2) |
| matcher_confident_wrong | 0 |
| matcher_not_in_catalog_recall | 100.0% (16/16) |
| matcher_accuracy | 99.5% (209/210) |
| matcher_predictions | ambiguous=1, matched=193, not_in_catalog=16 |

## Matcher errors (1)

```
E018-6: miss key=matched RL-17191 pred=ambiguous 
    reason: ptfe thread tape: size not stated (2 stocked sizes)
```

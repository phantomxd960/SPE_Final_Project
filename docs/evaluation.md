# Change-detection evaluation

Generated 2026-11-22 by `tests/evaluation/evaluate.py` from `tests/evaluation/labels.json`.
Embedding model: `BAAI/bge-small-en-v1.5`. Thresholds: renumbered ≥ 0.95, semantically equivalent ≥ 0.92 embedding similarity with word overlap ≤ 0.7.

Data: 2 regulation version pairs, 31 hand-labelled clause pairs (17 changed, 14 unchanged).

## Results

| Metric | Result | Target (SRS §10) |
| --- | --- | --- |
| Change detection precision (flagged clauses that really changed) | 1.00 (17/17) | ≥ 0.85 |
| Change detection recall (real changes that were flagged) | 1.00 (17/17) | ≥ 0.85 |
| Change detection F1 | 1.00 | |
| Change type accuracy (exact type) | 0.94 (29/31) | |
| Substantial changes caught (amount, rate, date, obligation) | 1.00 (6/6) | |
| Clause alignment accuracy | 1.00 (31/31) | |

## Confusion by change type

Rows are the labelled type, columns the predicted type.

| labelled \ predicted | added | deleted | modified | renumbered | semantically_equivalent | substantially_changed | unchanged |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **added** | 4 | · | · | · | · | · | · |
| **deleted** | · | 1 | · | · | · | · | · |
| **modified** | · | · | 1 | · | 1 | · | · |
| **renumbered** | · | · | · | 3 | · | · | · |
| **semantically_equivalent** | · | · | 1 | · | · | · | · |
| **substantially_changed** | · | · | · | · | · | 6 | · |
| **unchanged** | · | · | · | · | · | · | 14 |

## Disagreements

| Pair | Clause | Labelled | Predicted | Aligned to the right clause |
| --- | --- | --- | --- | --- |
| REG002 consumer credit | 1.2 | semantically_equivalent | modified | yes |
| REG002 consumer credit | 3.1 | modified | semantically_equivalent | yes |

## Notes

- The first run (before the fix below) scored precision 1.00, recall 1.00, type accuracy 0.94 and alignment 0.97: REG002 clause 1.2, a complete rewrite with the same meaning, shared too few words to be aligned and was reported as deleted + added.
- Fix: two clauses with the same number now also match when their embedding similarity is at least 0.85, so a reworded clause keeps its identity while an unrelated clause under a shifted number still does not (ai-engine/regdiff_ai/analysis/align.py).
- REG002 clause 3.1 is labelled 'modified', but 'withdraw ... without giving a reason' and 'cancel ... do not need to give any reason' arguably mean the same, so the system's 'semantically equivalent' is defensible. The label was kept as originally written rather than changed after seeing the result.

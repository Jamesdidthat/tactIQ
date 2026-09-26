# Pre-Match Review evidence compatibility validation

**Date:** 2026-09-11  
**Scope:** all 190 La Liga 2015/16 team-season pairings  
**Profiles:** 20 teams, 38 matches each  
**Ranking weights changed:** no  
**Evidence threshold changed:** no (`0.58`)  
**Family cap changed:** no (`2`)  
**Shortlist maximum changed:** no (`5`)

## Compatibility contract

| Category | May provide primary review evidence? | Meaning |
| --- | --- | --- |
| `same_metric` | Yes | Both team-season distributions use the same metric, unit, definition, and provider context. |
| `direct_attack_vs_defence_counterpart` | Yes | The defensive exposure is the exact opposition mirror of attacking production. |
| `validated_relationship` | Yes, with reference | Different metrics have a separately validated relationship and an explicit validation reference. |
| `unsupported_cross_metric` | No | The metrics describe different football concepts without a validated relationship. |

The high-regain-production versus turnover-to-shot-exposure pairing is now
`unsupported_cross_metric`. Its source medians, quartiles, counts, coverage,
definitions, and direction remain visible in the interaction API and UI. Its
signed mismatch, standardized mismatch, distribution-overlap verdict, and
interaction-strength score are unavailable. It cannot create a directional
finding or enter, merge into, support, or upgrade a review priority.

## Full 190-pair rescreen

Before the refactor, every pairing had at least two “qualified” directional
interactions because the unsupported cross-metric comparison qualified in both
directions. After applying compatibility before qualification:

| Qualified directional findings | Pair count after refactor |
| ---: | ---: |
| 0 | 146 |
| 1 | 16 |
| 2 | 12 |
| 3 | 8 |
| 4 | 6 |
| 6 | 1 |
| 7 | 1 |

This changes qualification semantics, not the frozen ranking configuration.

## Regression cases from the original QA

| Pairing | Previous qualified interactions | Current qualified interactions | Previous priorities | Current priorities | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Levante UD vs Málaga | 2 | 0 | 1 | 0 | Misleading sole cross-metric priority removed. |
| Málaga vs Real Sociedad | 2 | 0 | 1 | 0 | Misleading sole cross-metric priority removed. |
| Valencia vs Celta Vigo | 2 | 0 | 1 | 0 | Misleading sole cross-metric priority removed. |
| Valencia vs Real Sociedad | 2 | 0 | 1 | 0 | Misleading sole cross-metric priority removed. |

The new empty shortlists are appropriately cautious: no eligible same-metric,
direct-counterpart, or validated-relationship evidence clears the existing
priority threshold. The product does not invent a replacement theme.

Atlético Madrid vs Las Palmas also changed from three priorities to two. Its
same-metric defensive-activity and high-regain season contrasts remain; the
unsupported high-regain/turnover item was removed.

## Direction and auditability

- Directional provenance remains unchanged for every retained interaction.
- Configured `target_baseline` and `opponent_baseline` identities remain stable
  even when the opponent is the attacking side.
- Each of the ten rescreened QA pairings contains two audit rows with status
  `unsupported_cross_metric`, one for each direction.
- Every selected priority in the rescreen uses either `same_metric` or
  `direct_attack_vs_defence_counterpart` primary evidence.
- There are currently no registered `validated_relationship` interaction
  definitions. The contract rejects that category unless a validation reference
  is supplied.

The exact rerun output is
`artifacts/pre_match_review_priority_qa_compatibility_v2.json`. The original
failure audit remains preserved in
`docs/pre_match_review_priority_multi_matchup_qa.md` and
`artifacts/pre_match_review_priority_qa_v1.json`.
